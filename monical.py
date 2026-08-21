#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monical -- keyboard-driven monitor calibration tool for vision science labs.

Renders standard visual stimuli with real-time adjustable parameters, an
on-screen readout, and JSON snapshot export. You measure with a photometer or
oscilloscope, read the values off screen, and enter them into your experiment
code by hand.

Monical does not run experiments, collect data, or apply corrections. It
characterizes and verifies. Output is REFERENCE ONLY -- nothing auto-loads
calibration_values.json.

    python monical.py

Single file, PsychoPy only (psychopy_visionscience optional, radial
checkerboard only). See docs/PRD.md for the design authority.

STATUS: scaffold. Window, intro screen, main-loop skeleton, JSON output.
Stimuli, parameter knobs, modes, and the HUD are not implemented yet.
"""

import os
import json
import argparse
import datetime

import numpy as np

from psychopy import visual, core, event, monitors
from psychopy import __version__ as PSYCHOPY_VERSION

# The plugin is imported defensively so the intro screen can REPORT a failure
# rather than dying at import. Only the radial checkerboard needs it; every
# other stimulus type works without.
try:
    from psychopy_visionscience.radial import RadialStim
    HAS_RADIAL = True
    RADIAL_ERR = ''
except Exception as _err:                                    # noqa: BLE001
    RadialStim = None
    HAS_RADIAL = False
    RADIAL_ERR = '{}: {}'.format(type(_err).__name__, _err)

# Held-key detection for the auto-repeat knobs. event.getKeys() is edge
# triggered and cannot report that a key is STILL down, so repeat needs the
# pyglet key state directly (the window is winType='pyglet'). Guarded: without
# it the tool loses auto-repeat only, and every knob still works per press.
try:
    from pyglet.window import key as pyglet_key
    HAS_KEYSTATE = True
except Exception:                                            # noqa: BLE001
    pyglet_key = None
    HAS_KEYSTATE = False


# =============================================================================
# CONSTANTS
# =============================================================================

MONICAL_VERSION = '0.1'

# PRD 5.2 fixes DISPLAY precision, which is coarser than some defaults are
# (size 0.225 -> "0.23"). Knob values are stored -- in state and in the JSON --
# at 4 dp, the seed tool's precedent, and rounded only for the HUD. Rounding
# the file to display precision would lose the value the scientist dialled in.
STORE_DP = 4

REQUESTED_RESOLUTION = (1920, 1080)
SCREEN_INDEX = 0
UNITS = 'height'
MONITOR_NAME = 'testMonitor'
DEFAULT_BG = 0.0

READOUT_FONT = 'Consolas'

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(OUT_DIR, 'calibration_values.json')

# Stimulus types, in intro-screen selector order [1-4].
STIM_RADIAL = 'radial_checkerboard'
STIM_GABOR = 'gabor'
STIM_GRATING = 'grating'
STIM_UNIFORM = 'uniform_patch'
STIM_CUSTOM_PNG = 'custom_png'

STIMULUS_TYPES = [STIM_RADIAL, STIM_GABOR, STIM_GRATING, STIM_UNIFORM,
                  STIM_CUSTOM_PNG]

STIMULUS_LABELS = {
    STIM_RADIAL: 'Radial checkerboard (SSVEP standard)',
    STIM_GABOR: 'Gabor patch (attention/perception)',
    STIM_GRATING: 'Sinusoidal grating (contrast/SF tuning)',
    STIM_UNIFORM: 'Uniform patch (color/luminance calibration)',
    STIM_CUSTOM_PNG: 'Custom PNG (your own texture)',
}

FIXATION_SIZE = (0.07, 0.07)      # experiment FIXATION_SIZE, from the seed

# PRD 4.5 fallback when --image is absent or unreadable.
TEST_PATTERN_RES = 256
TEST_PATTERN_CELLS = 8
GENERATED_LABEL = '<generated 8x8 checkerboard>'

# Modes. Named here so the scaffold's state dict and JSON records already use
# the final vocabulary; only static_on is reachable until modes land.
MODE_STATIC_ON = 'static_on'
MODE_STATIC_OFF = 'static_off'
MODE_FLICKER_15 = 'flicker_15hz'
MODE_FLICKER_20 = 'flicker_20hz'
MODE_FLICKER_CUSTOM = 'flicker_custom'
MODE_GAMMA = 'gamma_steps'
MODE_UNIFORMITY = 'spatial_uniformity'

# Runtime mode keys (PRD 6). [6] is unassigned in the PRD's own table.
# Dual stimulus [7] is NOT here: see DUAL note below.
MODE_KEYS = {
    '1': MODE_STATIC_ON,
    '2': MODE_STATIC_OFF,
    '3': MODE_FLICKER_15,
    '4': MODE_FLICKER_20,
    '5': MODE_FLICKER_CUSTOM,
    'g': MODE_GAMMA,
    '8': MODE_UNIFORMITY,
}

FLICKER_HZ = {MODE_FLICKER_15: 15, MODE_FLICKER_20: 20}

# [7] toggles dual rendering, which is a flag rather than a mode because
# PRD 6.3 says both copies "flicker at the same frequency IF IN A FLICKER
# MODE" -- that only has meaning while a flicker mode is still selected, so
# dual has to compose with the mode rather than replace it.
DUAL_KEY = '7'

# PRD 6.2 -- 11 levels in PsychoPy rgb units, index 5 is mid-gray.
GAMMA_LEVELS = [-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

# PRD 6.4 -- center first, then the eight surround positions. This is the
# order the PRD enumerates; LAYOUT is the same nine names placed on the 3x3
# so the arrow keys can walk rows and columns.
UNIFORMITY_GRID = [
    'center', 'top_left', 'top_center', 'top_right',
    'mid_left', 'mid_right', 'bottom_left', 'bottom_center', 'bottom_right',
]
UNIFORMITY_LAYOUT = [
    ['top_left', 'top_center', 'top_right'],
    ['mid_left', 'center', 'mid_right'],
    ['bottom_left', 'bottom_center', 'bottom_right'],
]

FLASH_FRAMES = 60                 # how long the snapshot confirmation shows


# -----------------------------------------------------------------------------
# Universal parameter knobs (PRD 5). One table drives both the key handler and
# the auto-repeat loop, so a step or a range is defined in exactly one place.
#
#   key -> (state field, delta, low, high, kind)
#
# kind is 'float' (clamped, stored at STORE_DP), 'int' (clamped, rounded to a
# whole number) or 'wrap' (modulo the high limit -- orientation only, where
# 355 + 5 must land on 0 rather than sticking at 360).
#
# Within a pair the FIRST key listed in the PRD increases: [C/V], [F/H], [;/'],
# [Z/X], [R/T], [E/W], [D/A]. LEFT/RIGHT and PAGEUP/PAGEDN follow the arrow.
#
# PsychoPy names keys with pyglet's symbol_string() lowercased, which is where
# 'pageup', 'pagedown', 'semicolon', 'apostrophe' and 'num_add' come from.
# -----------------------------------------------------------------------------

STEP_POS = 0.01
STEP_BG = 0.001                   # fine, for photometer luminance matching
STEP_SIZE = 0.01
STEP_CONTRAST = 0.001             # fine, for photometer luminance matching
STEP_FREQ = 1
STEP_DISTANCE = 1

KNOBS = {
    'right':        ('x_pos', +STEP_POS, -1.0, 1.0, 'float'),
    'left':         ('x_pos', -STEP_POS, -1.0, 1.0, 'float'),
    'pageup':       ('y_pos', +STEP_POS, -0.5, 0.5, 'float'),
    'pagedown':     ('y_pos', -STEP_POS, -0.5, 0.5, 'float'),
    'up':           ('bg_gray', +STEP_BG, -1.0, 1.0, 'float'),
    'down':         ('bg_gray', -STEP_BG, -1.0, 1.0, 'float'),
    'equal':        ('size', +STEP_SIZE, 0.01, 2.0, 'float'),
    'plus':         ('size', +STEP_SIZE, 0.01, 2.0, 'float'),
    'num_add':      ('size', +STEP_SIZE, 0.01, 2.0, 'float'),
    'minus':        ('size', -STEP_SIZE, 0.01, 2.0, 'float'),
    'num_subtract': ('size', -STEP_SIZE, 0.01, 2.0, 'float'),
    'c':            ('contrast', +STEP_CONTRAST, 0.0, 1.0, 'float'),
    'v':            ('contrast', -STEP_CONTRAST, 0.0, 1.0, 'float'),
    'f':            ('custom_freq_hz', +STEP_FREQ, 1, 120, 'int'),
    'h':            ('custom_freq_hz', -STEP_FREQ, 1, 120, 'int'),
    'semicolon':    ('viewing_distance_cm', +STEP_DISTANCE, 1, 500, 'int'),
    'apostrophe':   ('viewing_distance_cm', -STEP_DISTANCE, 1, 500, 'int'),
}

# Stimulus-specific knobs (PRD 4.2-4.5), overlaid on KNOBS once the type is
# chosen. The same four key pairs are reused with different meanings per type
# -- the open question in PRD 12.1 -- so the intro tutorial and HUD line 5 both
# spell out the active legend.
STEP_SF = 0.5
STEP_ORI = 5.0
STEP_PHASE = 0.05
STEP_SD = 0.01
STEP_RGB = 0.001
STEP_ALPHA = 0.01

_GRATING_KNOBS = {
    'z': ('sf', +STEP_SF, 0.5, 50.0, 'float'),
    'x': ('sf', -STEP_SF, 0.5, 50.0, 'float'),
    'r': ('ori', +STEP_ORI, 0.0, 360.0, 'wrap'),
    't': ('ori', -STEP_ORI, 0.0, 360.0, 'wrap'),
    'e': ('phase', +STEP_PHASE, 0.0, 1.0, 'float'),
    'w': ('phase', -STEP_PHASE, 0.0, 1.0, 'float'),
}

STIM_KNOBS = {
    STIM_RADIAL: {},                          # locked to the standard form
    STIM_GABOR: dict(_GRATING_KNOBS, **{
        'd': ('envelope_sd', +STEP_SD, 0.01, 1.0, 'float'),
        'a': ('envelope_sd', -STEP_SD, 0.01, 1.0, 'float'),
    }),
    STIM_GRATING: dict(_GRATING_KNOBS),       # same, minus the envelope
    STIM_UNIFORM: {
        'r': ('r', +STEP_RGB, -1.0, 1.0, 'float'),
        't': ('r', -STEP_RGB, -1.0, 1.0, 'float'),
        'e': ('g', +STEP_RGB, -1.0, 1.0, 'float'),
        'w': ('g', -STEP_RGB, -1.0, 1.0, 'float'),
        'd': ('b', +STEP_RGB, -1.0, 1.0, 'float'),
        'a': ('b', -STEP_RGB, -1.0, 1.0, 'float'),
        'z': ('alpha', +STEP_ALPHA, 0.0, 1.0, 'float'),
        'x': ('alpha', -STEP_ALPHA, 0.0, 1.0, 'float'),
    },
    STIM_CUSTOM_PNG: {
        'z': ('alpha', +STEP_ALPHA, 0.0, 1.0, 'float'),
        'x': ('alpha', -STEP_ALPHA, 0.0, 1.0, 'float'),
    },
}

# PRD 5.1 -- only these auto-repeat. At 0.001 per press they need ~1000 presses
# to cross their range; every other knob is coarse enough to stay single-press.
REPEAT_KEYS = ('up', 'down', 'c', 'v')
# ...plus the colour channels, which share the 0.001 step and so the same
# problem. Alpha is 0.01 and stays single-press.
REPEAT_KEYS_BY_STIM = {
    STIM_UNIFORM: ('r', 't', 'e', 'w', 'd', 'a'),
}

# Clock-driven rather than frame-driven, so the rate is the same whatever the
# panel refresh turns out to be (20/s is one increment every 3 frames at 60 Hz,
# every 12 at 240 Hz).
REPEAT_DELAY_S = 1.0              # hold this long before repeating starts
REPEAT_RATE_HZ = 20.0             # increments per second once it starts


# The 4x4 balanced checker texture (PRD 4.1). Every row carries two +1 and two
# -1, so each annulus of the radial warp is sign-balanced independently of
# unequal annulus areas. Defined here so the construction is locked to the
# standard form before any stimulus code is written against it.
CHECKER_PATTERN = np.ones((4, 4))
CHECKER_PATTERN[::2, ::2] = -1
CHECKER_PATTERN[1::2, 1::2] = -1


def stim_is_on(frame_idx, frames):
    """PRD 6.1. Stateless integer arithmetic. Do not change this.

    ON  for frames  0 .. frames//2 - 1  of each cycle,
    OFF for frames  frames//2 .. frames-1.
    """
    return (frame_idx % frames) < (frames // 2)


def clamp(value, low, high):
    return max(low, min(high, value))


def hz_to_frames(hz, refresh_hz):
    """Nearest integer frame count for a requested Hz at the measured rate."""
    return max(2, int(round(refresh_hz / float(hz))))


def frames_to_hz(frames, refresh_hz):
    """Realised Hz. Never a rounded literal -- always derived from frames."""
    return refresh_hz / float(frames)


def uniformity_rc(name):
    """(row, col) of a grid position name in the 3x3 layout."""
    for row, names in enumerate(UNIFORMITY_LAYOUT):
        if name in names:
            return row, names.index(name)
    return 1, 1


def uniformity_xy(name, aspect, size):
    """Centre of the uniformity patch at grid position `name`, in height units.

    Pushed as far into each corner as the patch fits without clipping, since
    the point of the mode is to characterise the panel edges.
    """
    row, col = uniformity_rc(name)
    x_extent = max(0.0, aspect / 2.0 - size / 2.0)
    y_extent = max(0.0, 0.5 - size / 2.0)
    return (round((col - 1) * x_extent, STORE_DP),
            round((1 - row) * y_extent, STORE_DP))


def move_uniformity(state, key):
    """Walk the 3x3 grid with the arrow keys (PRD 6.4). True if it moved."""
    row, col = uniformity_rc(UNIFORMITY_GRID[state['uniformity_grid_index']])
    if key == 'left':
        col -= 1
    elif key == 'right':
        col += 1
    elif key == 'up':
        row -= 1
    elif key == 'down':
        row += 1
    else:
        return False
    name = UNIFORMITY_LAYOUT[int(clamp(row, 0, 2))][int(clamp(col, 0, 2))]
    state['uniformity_grid_index'] = UNIFORMITY_GRID.index(name)
    return True


def mode_frames(state, refresh_hz):
    """Frames per flicker cycle for the active mode, or None if not flickering.

    PRD 6.1: the count is the nearest integer at the MEASURED refresh, and the
    readout reports the frequency that count actually realises.
    """
    mode = state['mode']
    if mode in FLICKER_HZ:
        return hz_to_frames(FLICKER_HZ[mode], refresh_hz)
    if mode == MODE_FLICKER_CUSTOM:
        return hz_to_frames(state['custom_freq_hz'], refresh_hz)
    return None


def knob_table(stimulus_type):
    """Universal knobs plus the chosen type's own. Built once per session."""
    table = dict(KNOBS)
    table.update(STIM_KNOBS.get(stimulus_type, {}))
    return table


def repeat_key_names(stimulus_type):
    return tuple(REPEAT_KEYS) + tuple(
        REPEAT_KEYS_BY_STIM.get(stimulus_type, ()))


def apply_knob(state, key, table):
    """Apply one increment of the knob bound to `key`. True if it moved.

    Every knob goes through here -- single press and auto-repeat alike -- so a
    held key and a tapped key can never drift apart. Floats are re-rounded each
    step because 0.001 has no exact binary form and 1000 accumulations would
    otherwise leave the readout showing 0.4999999999.
    """
    spec = table.get(key)
    if spec is None:
        return False
    field, delta, low, high, kind = spec
    value = state[field] + delta
    if kind == 'wrap':
        # Orientation is cyclic: 355 + 5 is 0, not a clamp at 360.
        state[field] = round(value % high, STORE_DP)
    elif kind == 'int':
        state[field] = int(round(clamp(value, low, high)))
    else:
        state[field] = round(clamp(value, low, high), STORE_DP)
    return True


# =============================================================================
# STATE
# =============================================================================

def default_state(stimulus_type):
    """Every adjustable parameter in one dict, at its PRD default."""
    return {
        # Universal (PRD 5)
        'x_pos': 0.66,
        'y_pos': 0.0,
        'bg_gray': 0.0,
        'size': 0.225,
        'contrast': 1.0,
        'custom_freq_hz': 15,
        'viewing_distance_cm': 40,

        # Selection
        'stimulus_type': stimulus_type,
        'mode': MODE_STATIC_ON,
        'dual': False,            # PRD 6.3, orthogonal to mode

        # Screen width / height, filled in once the window is open. Needed for
        # the full-screen gamma patch and the uniformity grid extents.
        'aspect': 16.0 / 9.0,

        # Grating / Gabor (PRD 4.2, 4.3)
        'sf': 4.0,
        'ori': 0.0,
        'phase': 0.5,
        'envelope_sd': 0.06,

        # Uniform patch (PRD 4.4)
        'r': 0.0,
        'g': 0.0,
        'b': 0.0,
        'alpha': 1.0,

        # Custom PNG (PRD 4.5). Resolved at startup; GENERATED_LABEL when the
        # fallback pattern is in use.
        'image_path': GENERATED_LABEL,

        # Mode-local indices
        'gamma_step_index': 5,
        'uniformity_grid_index': 0,

        # Loop bookkeeping
        'frame_idx': 0,
        'snapshots': [],
    }


# =============================================================================
# STIMULUS CONSTRUCTION  (PRD 4)
# =============================================================================

def make_test_pattern(res=TEST_PATTERN_RES, cells=TEST_PATTERN_CELLS):
    """PRD 4.5 fallback: res x res checkerboard, cells x cells squares, -1/+1.

    Same value convention as CHECKER_PATTERN -- PsychoPy textures run -1
    (black) to +1 (white), so this is a full-contrast pattern before the
    contrast knob scales it.
    """
    block = max(1, res // cells)
    index = np.arange(res) // block
    return np.where((index[:, None] + index[None, :]) % 2 == 0,
                    1.0, -1.0).astype(np.float32)


def resolve_image(path):
    """(image for ImageStim, label). Falls back to the generated pattern.

    PRD 4.5: a missing file prints an error and falls back rather than dying --
    a calibration session should not be lost to a typo in a path.
    """
    if not path:
        return make_test_pattern(), GENERATED_LABEL
    if not os.path.isfile(path):
        print("ERROR: --image file not found: {}".format(path))
        print("       Falling back to the generated test pattern.")
        return make_test_pattern(), GENERATED_LABEL
    return path, os.path.abspath(path)


def gauss_sd_param(size, envelope_sd):
    """PsychoPy 'sd' for a Gaussian envelope whose SD is `envelope_sd` units.

    PsychoPy's maskParams 'sd' is NOT a standard deviation in stimulus units.
    createLumPattern builds the mask as exp(-rad^2 / (2 * (1/sd)^2)) where rad
    runs 0 at centre to 1 at the stimulus edge, so 'sd' is the NUMBER OF SDs
    that fit between centre and edge (its default, 3, is the familiar
    "3 sd.s by the edge"). Passing the PRD's envelope_sd straight through would
    mean sd=0.06 -> edge alpha 0.998, i.e. a hard-edged grating with no visible
    envelope at all.

    Converting: the envelope SD in stimulus units is (size / 2) / sd, so
    sd = (size / 2) / envelope_sd. At the defaults (size 0.225, SD 0.06) that
    gives 1.875, and the realised 1-SD half-width measures 0.06 height units.
    """
    radius = max(size, 1e-6) / 2.0
    return radius / max(envelope_sd, 1e-6)


# =============================================================================
# GEOMETRY / VISUAL ANGLE  (PRD 7)
# =============================================================================

def monitor_height_cm(mon, resolution):
    """Physical screen height in cm, or None if the Monitor has no width set.

    PsychoPy stores width only, so height comes back through the pixel aspect
    ratio. Returning None rather than a guess keeps an undetectable monitor
    visibly undetectable in the readout instead of silently wrong.
    """
    try:
        width_cm = mon.getWidth()
    except Exception:                                        # noqa: BLE001
        return None
    if not width_cm or not resolution[1]:
        return None
    aspect = float(resolution[0]) / float(resolution[1])
    return float(width_cm) / aspect


def visual_angle_deg(height_units, screen_height_cm, distance_cm):
    """Degrees subtended by an EXTENT given in 'height' units (PRD 7).

    In height units 1.0 spans the full screen height, so size_cm is just
    height_units * screen_height_cm. The factor of 2 is right here because an
    extent centred on the line of sight straddles it: half falls either side.
    """
    if not screen_height_cm or not distance_cm:
        return None
    size_cm = abs(float(height_units)) * float(screen_height_cm)
    return 2.0 * np.degrees(np.arctan(size_cm / (2.0 * float(distance_cm))))


def eccentricity_deg(offset_units, screen_height_cm, distance_cm):
    """Degrees from fixation to an OFF-AXIS point, in 'height' units.

    Deliberately NOT visual_angle_deg. That formula halves the extent and
    doubles the resulting angle, which is only correct when the thing measured
    straddles the line of sight. A displacement does not: the whole offset
    falls on one side, so it subtends atan(x / d) with no factor of 2.

    The two disagree by more than rounding. At x = 0.66 on a 33 cm-tall panel
    at 40 cm, the extent form gives 30.46 deg against the correct 28.57, and
    the overstatement grows with eccentricity -- which matters here, because
    eccentricity is exactly what a peripheral-stimulus experiment reports.
    """
    if not screen_height_cm or not distance_cm:
        return None
    offset_cm = abs(float(offset_units)) * float(screen_height_cm)
    return np.degrees(np.arctan(offset_cm / float(distance_cm)))


# =============================================================================
# INTRO SCREEN  (PRD 9)
# =============================================================================

WORKFLOWS = {
    STIM_RADIAL: [
        "1. Gamma calibrate first [G]: step levels, measure each,",
        "   enter the curve in PsychoPy Monitor Center.",
        "2. Static ON [1] and static OFF [2] at each position.",
        "   Photometer readings should match.",
        "3. Residual mismatch: trim background gray or contrast.",
        "4. Snapshot [S] at each matched position.",
        "5. Flicker [3][4][5]: photodiode + scope, check waveform.",
        "",
        "KNOBS: [LEFT/RIGHT] X   [PAGEUP/PAGEDN] Y   [UP/DOWN] BG",
        "       [+/-] size   [C/V] contrast   [F/H] custom Hz",
    ],
    STIM_GABOR: [
        "1. Gamma calibrate first [G]. Grating luminance is only",
        "   meaningful on a linearized display.",
        "2. Static ON [1]: set SF, orientation, phase and envelope",
        "   SD to the values your experiment uses.",
        "3. Photometer the mean luminance; it should equal the",
        "   background at contrast 1.0 if gamma is correct.",
        "4. Sweep contrast [C/V] and record the curve. Snapshot [S].",
        "",
        "KNOBS: [Z/X] SF   [R/T] orientation   [E/W] phase   [D/A] SD",
        "       plus the universal knobs.",
    ],
    STIM_GRATING: [
        "1. Gamma calibrate first [G].",
        "2. Static ON [1]: set SF and orientation to match your",
        "   experiment. No Gaussian envelope in this mode.",
        "3. Photometer the mean luminance across the patch; drift",
        "   across SF indicates a display MTF limit, not gamma.",
        "4. Sweep contrast [C/V], snapshot [S] at each step.",
        "",
        "KNOBS: [Z/X] SF   [R/T] orientation   [E/W] phase",
        "       plus the universal knobs.",
    ],
    STIM_UNIFORM: [
        "1. Per-channel gamma: drive R, G, B one at a time from",
        "   -1.0 to 1.0, photometer each step, snapshot [S].",
        "2. Channel independence: measure R, G, B separately, then",
        "   together. The sum should equal the combined reading.",
        "3. Spatial uniformity [8]: step the patch through the 3x3",
        "   grid, snapshot at each cell.",
        "4. Gamma steps [G] for the 11-level luminance ramp.",
        "",
        "KNOBS: [R/T] red   [E/W] green   [D/A] blue   [Z/X] alpha",
        "       plus the universal knobs.",
    ],
    STIM_CUSTOM_PNG: [
        "Load your experiment texture, verify rendering at target",
        "size/position/contrast.",
        "",
        "1. Gamma calibrate first [G].",
        "2. Static ON [1]: set size and position to the values your",
        "   experiment uses, then photometer the patch.",
        "3. Compare against the same texture rendered by your",
        "   experiment. Any difference is a rendering-path problem,",
        "   not a display one.",
        "4. Snapshot [S] -- the full path is recorded with it.",
        "",
        "KNOBS: [Z/X] alpha   plus the universal knobs.",
        "Pass a file with:  python monical.py --image path.png",
    ],
}


def build_intro_text(resolution, refresh_hz, selected_index, image_label):
    plugin_line = ('psychopy_visionscience  [OK]' if HAS_RADIAL else
                   'psychopy_visionscience  [FAILED -- '
                   'pip install psychopy-visionscience]')

    lines = [
        "MONICAL -- Monitor Calibration Tool  v{}".format(MONICAL_VERSION),
        "-------------------------------------------------------------",
        "Monitor:    {} x {}  @  {:.2f} Hz".format(
            resolution[0], resolution[1], refresh_hz),
        "PsychoPy:   {}".format(PSYCHOPY_VERSION),
        "Plugin:     {}".format(plugin_line),
        "",
        "SELECT STIMULUS TYPE:",
    ]

    for i, stim_type in enumerate(STIMULUS_TYPES):
        marker = '>' if i == selected_index else ' '
        lines.append("  {} [{}] {}".format(
            marker, i + 1, STIMULUS_LABELS[stim_type]))

    selected = STIMULUS_TYPES[selected_index]

    if selected == STIM_RADIAL and not HAS_RADIAL:
        # Selectable but not drawable. Say so here rather than at first flip.
        lines += [
            "",
            "!! RadialStim unavailable -- the checkerboard cannot be drawn.",
            "!! {}".format(RADIAL_ERR[:60]),
            "!!     pip install psychopy-visionscience",
        ]

    if selected == STIM_CUSTOM_PNG:
        lines += ["", "Texture: {}".format(image_label[-58:])]

    lines += [""] + WORKFLOWS[selected]
    lines += [
        "",
        "MODES: [1] static ON  [2] static OFF  [3] 15 Hz  [4] 20 Hz",
        "       [5] custom Hz  [G] gamma steps  [8] spatial uniformity",
        "       [7] toggles DUAL (two copies at +/-X, same flicker)",
        "[S] snapshot   [Q] quit (saves final state)",
        "",
        "Press SPACE to begin.",
    ]
    return "\n".join(lines)


def show_intro(win, resolution, refresh_hz, image_label):
    """White on black. Returns the chosen stimulus type, or None if aborted."""
    previous_color = win.color
    win.color = [-1, -1, -1]
    # Window colour needs a flip to take; two clears the FBO's stale buffer.
    win.flip()
    win.flip()

    select_keys = [str(i + 1) for i in range(len(STIMULUS_TYPES))]
    selected_index = 0
    text = visual.TextStim(
        win, text=build_intro_text(resolution, refresh_hz, selected_index,
                                   image_label),
        font=READOUT_FONT, height=0.020, color='white',
        pos=(0, 0), wrapWidth=1.7, alignText='left', anchorHoriz='center',
        autoLog=False)

    event.clearEvents()
    while True:
        text.draw()
        win.flip()

        dirty = False
        for key in event.getKeys(keyList=select_keys +
                                 ['space', 'q', 'escape']):
            if key in select_keys:
                selected_index = int(key) - 1
                dirty = True
            elif key in ('space', 'q', 'escape'):
                win.color = previous_color
                win.flip()
                win.flip()
                if key == 'space':
                    return STIMULUS_TYPES[selected_index]
                return None

        if dirty:
            text.text = build_intro_text(
                resolution, refresh_hz, selected_index, image_label)


# =============================================================================
# HUD  (PRD 8, precision per PRD 5.2)
# =============================================================================

def _deg(value):
    return '--' if value is None else '{:.2f}'.format(value)


def mode_line(state):
    """HUD line 2. Mode, dual flag, and whatever the mode itself owns."""
    mode = state['mode']
    parts = ['Mode: {}'.format(mode)]
    if mode == MODE_GAMMA:
        index = state['gamma_step_index']
        level = GAMMA_LEVELS[index]
        parts.append('Level {}/{}: {:+.1f} rgb ({} 8-bit)'.format(
            index + 1, len(GAMMA_LEVELS), level,
            int(round(255 * (level + 1.0) / 2.0))))
    elif mode == MODE_UNIFORMITY:
        name = UNIFORMITY_GRID[state['uniformity_grid_index']]
        grid_x, grid_y = uniformity_xy(name, state['aspect'], state['size'])
        parts.append('Cell: {} ({:.2f}, {:.2f})'.format(name, grid_x, grid_y))
    else:
        parts.append('Stim: {}'.format(state['stimulus_type']))
    if state['dual']:
        parts.append('DUAL +/-X')
    return ' | '.join(parts)


def stim_line(state):
    """HUD line 5. Adapts to the stimulus type (PRD 8)."""
    if state['mode'] == MODE_GAMMA:
        return 'Gamma steps: LEFT/RIGHT to change level | fixation hidden'
    if state['mode'] == MODE_UNIFORMITY:
        return 'Spatial uniformity: ARROWS move the patch across the 3x3 grid'
    stim_type = state['stimulus_type']
    if stim_type in (STIM_GABOR, STIM_GRATING):
        line = 'SF: {:.2f} c/unit | Ori: {:.1f} deg | Phase: {:.2f}'.format(
            state['sf'], state['ori'], state['phase'])
        if stim_type == STIM_GABOR:
            line += ' | SD: {:.3f} (mask sd {:.2f})'.format(
                state['envelope_sd'],
                gauss_sd_param(state['size'], state['envelope_sd']))
        return line
    if stim_type == STIM_UNIFORM:
        return 'R: {:.3f} | G: {:.3f} | B: {:.3f} | Alpha: {:.3f}'.format(
            state['r'], state['g'], state['b'], state['alpha'])
    if stim_type == STIM_CUSTOM_PNG:
        # Filename only; the full path goes in the snapshot (PRD 8).
        return 'File: {} | Alpha: {:.3f}'.format(
            os.path.basename(state['image_path']), state['alpha'])
    return 'No stimulus-specific parameters (construction locked)'


def build_hud(state, resolution, refresh_hz, live_hz, screen_height_cm):
    """The five lines of PRD 8, rebuilt every frame."""
    size_deg = visual_angle_deg(state['size'], screen_height_cm,
                                state['viewing_distance_cm'])
    ecc_deg = eccentricity_deg(state['x_pos'], screen_height_cm,
                               state['viewing_distance_cm'])

    # While flickering, report what the active mode realises. Otherwise report
    # what the standing custom setting WOULD realise, marked idle so nobody
    # reads it as a live measurement.
    frames = mode_frames(state, refresh_hz)
    if frames is None:
        idle = hz_to_frames(state['custom_freq_hz'], refresh_hz)
        freq_text = 'Freq: {:.3f} Hz ({} frames, idle)'.format(
            frames_to_hz(idle, refresh_hz), idle)
    else:
        freq_text = 'Freq: {:.3f} Hz ({} frames, {} on / {} off)'.format(
            frames_to_hz(frames, refresh_hz), frames,
            frames // 2, frames - frames // 2)

    return '\n'.join([
        '{}x{} | {:.2f} Hz | PsychoPy {} | Dist: {} cm'.format(
            resolution[0], resolution[1], live_hz, PSYCHOPY_VERSION,
            state['viewing_distance_cm']),
        mode_line(state),
        'X: {:.2f} | Y: {:.2f} | Size: {:.2f} ({} deg) | Ecc: {} deg'.format(
            state['x_pos'], state['y_pos'], state['size'],
            _deg(size_deg), _deg(ecc_deg)),
        'BG: {:.3f} | Contrast: {:.3f} | {}'.format(
            state['bg_gray'], state['contrast'], freq_text),
        stim_line(state),
    ])


# =============================================================================
# OUTPUT  (PRD 3.2)
# =============================================================================

def stimulus_specific(state):
    """Per-type parameters. Radial has none beyond universal (PRD 4.1)."""
    stim_type = state['stimulus_type']
    if stim_type == STIM_GABOR:
        record = {
            'sf': round(state['sf'], STORE_DP),
            'ori': round(state['ori'], STORE_DP),
            'phase': round(state['phase'], STORE_DP),
            'envelope_sd': round(state['envelope_sd'], STORE_DP),
        }
    elif stim_type == STIM_GRATING:
        record = {
            'sf': round(state['sf'], STORE_DP),
            'ori': round(state['ori'], STORE_DP),
            'phase': round(state['phase'], STORE_DP),
        }
    elif stim_type == STIM_UNIFORM:
        record = {
            'r': round(state['r'], STORE_DP),
            'g': round(state['g'], STORE_DP),
            'b': round(state['b'], STORE_DP),
            'alpha': round(state['alpha'], STORE_DP),
        }
    elif stim_type == STIM_CUSTOM_PNG:
        record = {
            'filepath': state['image_path'],
            'alpha': round(state['alpha'], STORE_DP),
        }
    else:
        record = {}

    # Mode-local values, without which a reading cannot be matched back to the
    # screen it was taken from.
    if state['mode'] == MODE_GAMMA:
        record['gamma_level'] = GAMMA_LEVELS[state['gamma_step_index']]
        record['gamma_step_index'] = state['gamma_step_index']
    elif state['mode'] == MODE_UNIFORMITY:
        name = UNIFORMITY_GRID[state['uniformity_grid_index']]
        grid_x, grid_y = uniformity_xy(name, state['aspect'], state['size'])
        record['grid_position'] = name
        record['grid_x'] = grid_x
        record['grid_y'] = grid_y
        # PRD 6.4 draws the uniform patch whatever the session's stimulus
        # type is, so its colour has to be recorded even for, say, a Gabor
        # session -- otherwise the snapshot does not describe what the
        # photometer was actually pointed at.
        if stim_type != STIM_UNIFORM:
            record['patch_r'] = round(state['r'], STORE_DP)
            record['patch_g'] = round(state['g'], STORE_DP)
            record['patch_b'] = round(state['b'], STORE_DP)
            record['patch_alpha'] = round(state['alpha'], STORE_DP)

    return record


def state_record(state, screen_height_cm, refresh_hz=None):
    angle = visual_angle_deg(state['size'], screen_height_cm,
                             state['viewing_distance_cm'])
    ecc = eccentricity_deg(state['x_pos'], screen_height_cm,
                           state['viewing_distance_cm'])
    frames = None if refresh_hz is None else mode_frames(state, refresh_hz)
    record = {
        'timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
        'stimulus_type': state['stimulus_type'],
        'mode': state['mode'],
        'dual_stimulus': bool(state['dual']),
        'x_position': round(state['x_pos'], STORE_DP),
        'y_position': round(state['y_pos'], STORE_DP),
        'background_gray': round(state['bg_gray'], STORE_DP),
        'disc_size': round(state['size'], STORE_DP),
        'contrast': round(state['contrast'], STORE_DP),
        'custom_frequency_hz': state['custom_freq_hz'],
        'visual_angle_deg': None if angle is None else round(angle, 2),
        'eccentricity_deg': None if ecc is None else round(ecc, 2),
        'stimulus_specific': stimulus_specific(state),
    }
    # Only meaningful while a flicker mode is active; the realised rate is
    # what the frame count actually delivers, never the requested value.
    if frames is not None:
        record['flicker_frames_per_cycle'] = frames
        record['flicker_realized_hz'] = round(
            frames_to_hz(frames, refresh_hz), 3)
    return record


def write_json(state, resolution, refresh_hz, screen_height_cm, final=None):
    payload = {
        'note': ('REFERENCE ONLY. Not loaded by any experiment. '
                 'Values are read by humans and entered manually.'),
        'monical_version': MONICAL_VERSION,
        'monitor_resolution': list(resolution),
        'measured_refresh_hz': round(float(refresh_hz), 3),
        'psychopy_version': str(PSYCHOPY_VERSION),
        'viewing_distance_cm': float(state['viewing_distance_cm']),
        'monitor_height_cm': (None if screen_height_cm is None
                              else round(screen_height_cm, 2)),
        'snapshots': state['snapshots'],
    }
    if final is not None:
        payload['final'] = final
    with open(OUT_PATH, 'w') as handle:
        json.dump(payload, handle, indent=2)
    return OUT_PATH


# =============================================================================
# MAIN
# =============================================================================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog='monical.py',
        description='Monitor calibration tool for vision science labs.')
    parser.add_argument(
        '--image', metavar='PATH', default=None,
        help='PNG texture for stimulus type [5]. Without it, [5] uses a '
             'generated 256x256 checkerboard test pattern.')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    image, image_label = resolve_image(args.image)

    mon = monitors.Monitor(MONITOR_NAME)

    win = visual.Window(
        size=REQUESTED_RESOLUTION, fullscr=True, screen=SCREEN_INDEX,
        monitor=mon, winType='pyglet', units=UNITS,
        color=[DEFAULT_BG] * 3, colorSpace='rgb',
        useFBO=True, allowStencil=False)
    win.mouseVisible = False

    resolution = (int(win.size[0]), int(win.size[1]))
    screen_height_cm = monitor_height_cm(mon, resolution)

    # getMsPerFrame returns (mean, std, median) in ms. Median is the robust
    # one -- a single scheduler stall inflates the mean by most of a frame.
    measured_refresh = None
    try:
        _mean_ms, _std_ms, median_ms = win.getMsPerFrame(nFrames=120)
        if median_ms and median_ms > 0:
            measured_refresh = 1000.0 / float(median_ms)
    except Exception as err:                                 # noqa: BLE001
        print("Refresh measurement failed ({}).".format(err))

    if measured_refresh is None:
        measured_refresh = 60.0
        print("WARNING: could not measure refresh rate; assuming 60.00 Hz. "
              "Frame-count frequencies will NOT be the stated values.")

    stimulus_type = show_intro(win, resolution, measured_refresh, image_label)
    if stimulus_type is None:
        win.close()
        print("Aborted at intro screen. Nothing written.")
        core.quit()

    state = default_state(stimulus_type)
    state['image_path'] = image_label
    state['aspect'] = resolution[0] / float(resolution[1])
    table = knob_table(stimulus_type)

    # ---- Stimuli (PRD 4) -----------------------------------------------------
    stim = None
    if stimulus_type == STIM_RADIAL:
        if HAS_RADIAL:
            # EXACT PRD 4.1 kwargs. Do not add a mask or angularCycles.
            stim = RadialStim(
                win=win, tex=CHECKER_PATTERN, size=state['size'],
                radialCycles=1, texRes=256, opacity=1,
                contrast=state['contrast'],
                pos=(state['x_pos'], state['y_pos']),
                name='calib_disc', autoLog=False)
        else:
            print("RadialStim unavailable -- background and fixation only.")
    elif stimulus_type in (STIM_GABOR, STIM_GRATING):
        is_gabor = stimulus_type == STIM_GABOR
        stim = visual.GratingStim(
            win=win, tex='sin', mask='gauss' if is_gabor else None,
            size=state['size'], sf=state['sf'], ori=state['ori'],
            phase=state['phase'], contrast=state['contrast'],
            pos=(state['x_pos'], state['y_pos']),
            maskParams=({'sd': gauss_sd_param(state['size'],
                                              state['envelope_sd'])}
                        if is_gabor else None),
            autoLog=False)
    elif stimulus_type == STIM_UNIFORM:
        stim = visual.Rect(
            win=win, width=state['size'], height=state['size'],
            fillColor=[state['r'], state['g'], state['b']],
            lineWidth=0, lineColor=None, colorSpace='rgb',
            opacity=state['alpha'], contrast=state['contrast'],
            pos=(state['x_pos'], state['y_pos']), autoLog=False)
    elif stimulus_type == STIM_CUSTOM_PNG:
        stim = visual.ImageStim(
            win=win, image=image, size=state['size'],
            contrast=state['contrast'], opacity=state['alpha'],
            pos=(state['x_pos'], state['y_pos']), autoLog=False)

    fixation = visual.ShapeStim(
        win=win, name='fixation_cross', vertices='cross',
        size=FIXATION_SIZE, ori=0.0, pos=(0.0, 0.0), anchor='center',
        lineWidth=1.0, colorSpace='rgb', lineColor='white',
        fillColor='white', depth=0.0, interpolate=True, autoLog=False)

    # Full-screen patch for gamma stepping (PRD 6.2). Width is the aspect
    # ratio because in height units the screen is 1.0 tall and aspect wide.
    gamma_patch = visual.Rect(
        win=win, width=state['aspect'], height=1.0, pos=(0, 0),
        lineWidth=0, lineColor=None,
        fillColor=[GAMMA_LEVELS[state['gamma_step_index']]] * 3,
        colorSpace='rgb', autoLog=False)

    # PRD 6.4 renders the uniform patch regardless of the selected type, so
    # this one exists even when the session is running a Gabor.
    uniformity_patch = visual.Rect(
        win=win, width=state['size'], height=state['size'], pos=(0, 0),
        lineWidth=0, lineColor=None,
        fillColor=[state['r'], state['g'], state['b']],
        colorSpace='rgb', opacity=state['alpha'],
        contrast=state['contrast'], autoLog=False)

    hud = visual.TextStim(
        win, text='', font=READOUT_FONT, height=0.018, color='white',
        pos=(0, -0.42), wrapWidth=1.8, alignText='center',
        anchorHoriz='center', autoLog=False)

    flash = visual.TextStim(
        win, text='', font=READOUT_FONT, height=0.030, color='yellow',
        pos=(0, 0.42), alignText='center', anchorHoriz='center',
        autoLog=False)
    flash_frames = 0
    flash_text = ''

    # Rebuilding the Gaussian mask uploads a 256x256 texture, so it happens
    # only when the SD or the size it is relative to actually changes.
    mask_cache = [None]

    # ---- Auto-repeat plumbing (PRD 5.1) --------------------------------------
    # KeyStateHandler only observes events, so it coexists with PsychoPy's own
    # handlers behind event.getKeys().
    key_state = None
    if HAS_KEYSTATE:
        try:
            key_state = pyglet_key.KeyStateHandler()
            win.winHandle.push_handlers(key_state)
        except Exception as err:                             # noqa: BLE001
            key_state = None
            print("Hold-to-repeat unavailable ({}). Single presses still work."
                  .format(err))

    repeat_symbols = {}
    if key_state is not None:
        for name in repeat_key_names(stimulus_type):
            symbol = getattr(pyglet_key, name.upper(), None)
            if symbol is not None:
                repeat_symbols[name] = symbol

    held_since = {}          # key name -> time it went down
    repeat_count = {}        # key name -> increments emitted so far this hold
    repeat_clock = core.Clock()

    def is_os_autorepeat(name):
        """True when this key is already tracked as held.

        Windows generates its own auto-repeat key events while a key is down,
        and PsychoPy delivers them through event.getKeys() exactly like real
        presses. Without this guard a held key would advance at the OS repeat
        rate AND at our clock-driven rate simultaneously. Only the first press
        of a hold gets through here; the rest are ours to time.
        """
        return name in held_since

    # ---- Main loop -----------------------------------------------------------
    running = True
    while running:
        # ---- Input -----------------------------------------------------------
        for key in event.getKeys():
            # --- Mode switching (PRD 6). Phase resets on every switch. -------
            if key in MODE_KEYS:
                if state['mode'] != MODE_KEYS[key]:
                    state['mode'] = MODE_KEYS[key]
                    state['frame_idx'] = 0
                continue
            if key == DUAL_KEY:
                state['dual'] = not state['dual']
                continue

            # --- Arrows are claimed by two modes (PRD 6.2, 6.4) -------------
            if state['mode'] == MODE_GAMMA and key in ('left', 'right'):
                step = 1 if key == 'right' else -1
                state['gamma_step_index'] = int(clamp(
                    state['gamma_step_index'] + step, 0,
                    len(GAMMA_LEVELS) - 1))
                continue
            if state['mode'] == MODE_UNIFORMITY and move_uniformity(state,
                                                                    key):
                continue

            if key in table:
                # Repeat-enabled knobs swallow the OS's own repeat events; the
                # clock below is the only thing allowed to advance them.
                if key in repeat_symbols and is_os_autorepeat(key):
                    continue
                apply_knob(state, key, table)
            elif key == 's':
                state['snapshots'].append(
                    state_record(state, screen_height_cm, measured_refresh))
                write_json(state, resolution, measured_refresh,
                           screen_height_cm)
                flash_text = 'Snapshot #{} saved'.format(
                    len(state['snapshots']))
                flash_frames = FLASH_FRAMES
                print("SNAPSHOT {} saved.".format(len(state['snapshots'])))
            elif key in ('q', 'escape'):
                running = False

        if not running:
            break

        # ---- Hold-to-repeat: background gray and contrast only ---------------
        # The count due is derived from how long the key has been down, NOT
        # from the time since the last increment. Those differ: an increment
        # can only be emitted on a frame boundary, so "wait 1/20 s since the
        # last one" rounds every interval UP to a whole frame -- 50 ms becomes
        # 3 frames sometimes and 4 others at 60 Hz, beating the realized rate
        # down to ~17/s. Measuring against the hold start instead lets a short
        # interval make up for a long one, so the average holds at exactly
        # REPEAT_RATE_HZ on any panel.
        if key_state is not None:
            now = repeat_clock.getTime()
            for name, symbol in repeat_symbols.items():
                if not key_state[symbol]:
                    held_since.pop(name, None)
                    repeat_count.pop(name, None)
                    continue
                if name not in held_since:
                    # First frame down. event.getKeys() already applied the
                    # initial increment above; just start the hold timer.
                    held_since[name] = now
                    repeat_count[name] = 0
                    continue
                holding = now - held_since[name] - REPEAT_DELAY_S
                if holding < 0:
                    continue
                due = int(holding * REPEAT_RATE_HZ)
                for _ in range(due - repeat_count.get(name, 0)):
                    apply_knob(state, name, table)
                repeat_count[name] = due

        # ---- Live parameter application --------------------------------------
        win.color = [state['bg_gray']] * 3

        if stim is not None:
            stim.pos = (state['x_pos'], state['y_pos'])
            stim.contrast = state['contrast']
            if stimulus_type == STIM_UNIFORM:
                stim.width = state['size']
                stim.height = state['size']
                stim.fillColor = [state['r'], state['g'], state['b']]
                stim.opacity = state['alpha']
            else:
                stim.size = state['size']
            if stimulus_type in (STIM_GABOR, STIM_GRATING):
                stim.sf = state['sf']
                stim.ori = state['ori']
                stim.phase = state['phase']
            if stimulus_type == STIM_GABOR:
                sd = round(gauss_sd_param(state['size'],
                                          state['envelope_sd']), 6)
                if sd != mask_cache[0]:
                    # Assigning maskParams re-runs the mask setter, which
                    # rebuilds the texture -- so only do it when sd moves.
                    stim.maskParams = {'sd': sd}
                    mask_cache[0] = sd
            if stimulus_type == STIM_CUSTOM_PNG:
                stim.opacity = state['alpha']

        # ---- Draw ------------------------------------------------------------
        mode = state['mode']
        frames = mode_frames(state, measured_refresh)

        if mode == MODE_GAMMA:
            gamma_patch.width = state['aspect']
            gamma_patch.fillColor = [
                GAMMA_LEVELS[state['gamma_step_index']]] * 3
            gamma_patch.draw()
        elif mode == MODE_UNIFORMITY:
            name = UNIFORMITY_GRID[state['uniformity_grid_index']]
            uniformity_patch.width = state['size']
            uniformity_patch.height = state['size']
            uniformity_patch.pos = uniformity_xy(name, state['aspect'],
                                                 state['size'])
            uniformity_patch.fillColor = [state['r'], state['g'], state['b']]
            uniformity_patch.opacity = state['alpha']
            uniformity_patch.contrast = state['contrast']
            uniformity_patch.draw()
        elif mode == MODE_STATIC_OFF:
            pass                      # background + fixation only (PRD 6)
        elif stim is not None:
            # static_on, or the ON half of a flicker cycle. stim_is_on is
            # stateless in frame_idx, which resets on every mode switch.
            if frames is None or stim_is_on(state['frame_idx'], frames):
                stim.draw()
                if state['dual']:
                    # PRD 6.3: the mirrored copy at -X, same flicker phase.
                    stim.pos = (-state['x_pos'], state['y_pos'])
                    stim.draw()
                    stim.pos = (state['x_pos'], state['y_pos'])

        # Fixation cross in every mode EXCEPT gamma steps (PRD 6.2): there the
        # photometer sits at screen centre and a cross under the aperture would
        # corrupt the gamma curve everything else depends on.
        if mode != MODE_GAMMA:
            fixation.draw()

        hud.text = build_hud(state, resolution, measured_refresh,
                             measured_refresh, screen_height_cm)
        hud.draw()

        if flash_frames > 0:
            flash.text = flash_text
            flash.draw()
            flash_frames -= 1

        win.flip()
        state['frame_idx'] += 1

    # ---- Quit ----------------------------------------------------------------
    final = state_record(state, screen_height_cm, measured_refresh)
    path = write_json(state, resolution, measured_refresh, screen_height_cm,
                      final=final)
    win.close()

    print("")
    print("Calibration values written to:")
    print("  {}".format(path))
    print("  {} snapshot(s), final state recorded.".format(
        len(state['snapshots'])))
    print("  REFERENCE ONLY -- no experiment reads this file.")
    core.quit()


if __name__ == '__main__':
    main()
