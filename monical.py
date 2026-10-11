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
the monical_*.json session files.

    python monical.py [--image PATH] [--text STRING] [--preset PATH] [--bench]

Single file, PsychoPy only (psychopy_visionscience optional, radial
checkerboard only). See docs/PRD.md for the design authority and
docs/MANUAL.md for operation.
"""

import os
import sys
import json
import math
import atexit
import argparse
import datetime
import collections
import faulthandler
import types

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
PRESET_DIR = os.path.join(OUT_DIR, 'presets')
SCREENSHOT_DIR = os.path.join(OUT_DIR, 'screenshots')

# One output file per session, named from session_start. Nothing is ever
# overwritten, so a second run cannot destroy the first run's measurements.
OUT_STAMP_FMT = '%Y-%m-%d_%H%M%S'
OUT_NAME_FMT = 'monical_{}.json'
PRESET_NAME_FMT = 'preset_{}.json'
SCREENSHOT_NAME_FMT = 'monical_screenshot_{}.png'
BENCH_NAME_FMT = 'bench_{}.json'   # same stamp as the session files
CRASH_NAME_FMT = 'monical_crash_{}.log'

# --bench (MANUAL "Verifying frame timing on your rig"): every type at each
# copy count with the readout off, then every type at the HUD counts with it
# on -- what reading the readout during a flicker check costs.
BENCH_COUNTS = (1, 2, 8, 16)
BENCH_HUD_COUNTS = (1, 16)
BENCH_FRAMES = 600
BENCH_WARMUP = 30                 # frames run, not recorded, per config
BENCH_BUDGET_WARN = 0.8           # flag p95 or max above 80% of a frame

# State keys that describe the rig or the run rather than the stimulus, and so
# are not carried in a preset. `aspect` comes from the window, `image_path`
# from --image, and the other two are live loop bookkeeping.
PRESET_EXCLUDE = ('frame_idx', 'snapshots', 'aspect', 'image_path',
                  'win_w', 'win_h', 'font_requested', 'font_rendered',
                  'text_extent')

SETTLE_S = 2.0                    # auto gamma dwell per level (PRD 6.5)

# Stimulus types, in intro-screen selector order [1-6].
STIM_RADIAL = 'radial_checkerboard'
STIM_GABOR = 'gabor'
STIM_GRATING = 'grating'
STIM_UNIFORM = 'uniform_patch'
STIM_CUSTOM_PNG = 'custom_png'
STIM_TEXT = 'text'

STIMULUS_TYPES = [STIM_RADIAL, STIM_GABOR, STIM_GRATING, STIM_UNIFORM,
                  STIM_CUSTOM_PNG, STIM_TEXT]

STIMULUS_LABELS = {
    STIM_RADIAL: 'Radial checkerboard (SSVEP standard)',
    STIM_GABOR: 'Gabor patch (attention/perception)',
    STIM_GRATING: 'Sinusoidal grating (contrast/SF tuning)',
    STIM_UNIFORM: 'Uniform patch (color/luminance calibration)',
    STIM_CUSTOM_PNG: 'Custom PNG (your own texture)',
    STIM_TEXT: 'Text / letter string (reading/crowding)',
}

# PRD 4.6. [B]/[N] cycle TEXT_PRESETS, or a list built from --text
# (text_cycle). Font family maps to the first installed name: Windows first,
# then macOS, then Linux.
TEXT_PRESETS = ['ABCDEF', 'abcdef', '123456', 'XXXXXX', 'oOoOoO']
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
TEXT_CYCLE_FWD = 'b'
TEXT_CYCLE_BACK = 'n'
FONT_CANDIDATES = {
    'monospace': ['Courier New', 'Menlo', 'DejaVu Sans Mono',
                  'Liberation Mono'],
    'sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'Liberation Sans'],
    'serif': ['Times New Roman', 'Times', 'DejaVu Serif', 'Liberation Serif'],
}
TEXT_HUD_CHARS = 24               # HUD shows longer strings truncated

# Physically implausible screen heights. Below or above these the Monitor
# object almost certainly holds a default rather than this rig's real size,
# and every visual angle derived from it is wrong (PRD 12).
MONITOR_H_MIN_CM = 15.0
MONITOR_H_MAX_CM = 80.0

# [H] toggles the readout. Custom-frequency-down moved from [H] to [J] to
# free it (PRD 8.1).
HUD_TOGGLE_KEY = 'h'

# [M] toggles the full keybinding reference card (PRD 8.3).
MENU_TOGGLE_KEY = 'm'

# The status bar sits below the HUD and never hides: smaller and dimmer than
# the readout so the two are visually distinct (PRD 8.2).
STATUS_HEIGHT = 0.013
STATUS_POS = (0, -0.487)
STATUS_COLOR = 'lightgray'
STATUS_NAME_CHARS = 34            # filename budget before truncation

# The readout. Line 5 wraps onto a line 6 rather than run off a narrow screen
# (the font never shrinks). Char width and line pitch were measured from
# rendered Consolas in PsychoPy; a wrapped HUD moves up half a pitch so its
# bottom edge stays clear of the status bar.
HUD_HEIGHT = 0.018
HUD_POS_Y = -0.42
HUD_WRAP_W = 1.8
HUD_CHAR_W = 0.514 * HUD_HEIGHT
HUD_LINE_PITCH = 0.0204

# The readout's timing figures (rolling refresh, sigma, drop count, all on
# line 1) change on every frame. Re-laying out text costs real time at 240 Hz,
# so those figures refresh at most this often, on the clock. Everything else
# in the readout still appears on the very next frame.
HUD_TIMING_INTERVAL_S = 0.1

# The intro screen. INTRO_HEIGHT is a ceiling: set_intro_text shrinks the
# block only when it would not fit above the monitor warning.
INTRO_HEIGHT = 0.020
INTRO_WRAP_W = 1.7
INTRO_WRAP_FRAC = 0.96            # of screen width, when that is narrower
INTRO_MARGIN = 0.01

MENU_HEIGHT = 0.021
MENU_BOX_W_FRAC = 0.72            # of screen width
MENU_BOX_H_FRAC = 0.62            # of screen height -- about 60% centred
MENU_BOX_OPACITY = 0.88
MENU_PAD = 0.03                   # gap between the panel edge and the text

FIXATION_SIZE = (0.07, 0.07)      # experiment FIXATION_SIZE, from the seed

# PRD 4.5 fallback when --image is absent or unreadable.
TEST_PATTERN_RES = 256
TEST_PATTERN_CELLS = 8
GENERATED_LABEL = '<generated 8x8 checkerboard>'
IMAGE_NAME_CHARS = 30             # --image basename budget on the intro screen

# Mode identifiers, as written to the JSON `mode` field (PRD 6).
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

# Modes where the photometer is pointed at the measured surface itself, so the
# fixation cross is hidden rather than drawn over the aperture (PRD 6.2 for
# gamma; spatial uniformity needs it too, since the centre cell of the 3x3 puts
# the patch exactly under the cross).
FIXATION_HIDDEN_MODES = (MODE_GAMMA, MODE_UNIFORMITY)

# [7] toggles multi-stimulus rendering (PRD 6.3), which is a flag rather than
# a mode: the copies flicker IN whatever flicker mode is selected, so multi
# has to compose with the mode rather than replace it. N copies sit on a ring
# through (X, Y) around (0, Y); N = 2 is the original dual layout.
DUAL_KEY = '7'
MULTI_MIN, MULTI_MAX = 2, 16
STEP_RING = 5.0
SELECT_PREV, SELECT_NEXT = '9', '0'
# [/] cycles the selected copy's state (PRD 6.3). 'steady' is drawn on every
# frame of a flicker mode; 'off' is never drawn.
COPY_STATE_KEY = 'slash'
COPY_STATES = ['flicker', 'steady', 'off']

# Selection marker (PRD 6.3): a short thin tick pointing at the selected copy,
# drawn with the readout. It sits outside every copy's footprint circle -- a
# tick that strayed onto a stimulus would corrupt a photometer reading.
MARKER_LEN = 0.03
MARKER_GAP = 0.012                # from the selected copy's footprint
MARKER_CLEAR = 0.006              # from every other copy's footprint
MARKER_COLOR = [1.0, 1.0, -1.0]   # yellow, rgb

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
# Within a pair the FIRST key listed in the PRD increases: [C/V], [F/J], [;/'],
# [Z/X], [R/T], [E/W], [D/A]. The arrows and PAGEUP/PAGEDN follow the arrow.
#
# PsychoPy names keys with pyglet's symbol_string() lowercased, which is where
# 'pageup', 'pagedown', 'semicolon', 'apostrophe' and 'num_add' come from.
# -----------------------------------------------------------------------------

STEP_POS = 0.005                  # fine placement; auto-repeats to cover range
STEP_BG = 0.001                   # fine, for photometer luminance matching
STEP_SIZE = 0.01
STEP_CONTRAST = 0.001             # fine, for photometer luminance matching
STEP_FRAMES = 1
DEFAULT_CUSTOM_HZ = 15            # mode 5 starts at the nearest frame count
STEP_DISTANCE = 1

KNOBS = {
    # Arrows move the stimulus; page keys adjust the background behind it.
    'right':        ('x_pos', +STEP_POS, -1.0, 1.0, 'float'),
    'left':         ('x_pos', -STEP_POS, -1.0, 1.0, 'float'),
    'up':           ('y_pos', +STEP_POS, -0.5, 0.5, 'float'),
    'down':         ('y_pos', -STEP_POS, -0.5, 0.5, 'float'),
    'pageup':       ('bg_gray', +STEP_BG, -1.0, 1.0, 'float'),
    'pagedown':     ('bg_gray', -STEP_BG, -1.0, 1.0, 'float'),
    'equal':        ('size', +STEP_SIZE, 0.01, 2.0, 'float'),
    'plus':         ('size', +STEP_SIZE, 0.01, 2.0, 'float'),
    'num_add':      ('size', +STEP_SIZE, 0.01, 2.0, 'float'),
    'minus':        ('size', -STEP_SIZE, 0.01, 2.0, 'float'),
    'num_subtract': ('size', -STEP_SIZE, 0.01, 2.0, 'float'),
    'c':            ('contrast', +STEP_CONTRAST, 0.0, 1.0, 'float'),
    'v':            ('contrast', -STEP_CONTRAST, 0.0, 1.0, 'float'),
    # [F/J], not the original [F/H]: [H] now toggles the readout, and F and J
    # are the two home-position index keys. Mode 5 steps whole frames, so
    # every press changes the realised rate. F still raises Hz, which means
    # FEWER frames. The upper limit (~1 Hz) depends on the refresh, so
    # knob_table fills it in.
    'f':            ('flicker_frames', -STEP_FRAMES, 2, None, 'int'),
    'j':            ('flicker_frames', +STEP_FRAMES, 2, None, 'int'),
    'semicolon':    ('viewing_distance_cm', +STEP_DISTANCE, 1, 500, 'int'),
    'apostrophe':   ('viewing_distance_cm', -STEP_DISTANCE, 1, 500, 'int'),
    # Multi-stimulus ring (PRD 6.3). ']' adds a stimulus; ',' turns the ring
    # +5 deg (counter-clockwise), '.' turns it back.
    'bracketright': ('multi_count', +1, MULTI_MIN, MULTI_MAX, 'int'),
    'bracketleft':  ('multi_count', -1, MULTI_MIN, MULTI_MAX, 'int'),
    'comma':        ('ring_offset_deg', +STEP_RING, 0.0, 360.0, 'wrap'),
    'period':       ('ring_offset_deg', -STEP_RING, 0.0, 360.0, 'wrap'),
}

# Stimulus-specific knobs (PRD 4.1-4.6), overlaid on KNOBS once the type is
# chosen. The same key pairs are reused with different meanings per type
# (settled in PRD 15.1), so the intro tutorial and the [M] card both spell out
# the active legend.
STEP_SF = 0.5
STEP_ORI = 5.0
STEP_PHASE = 0.05
STEP_SD = 0.01
STEP_RGB = 0.001
STEP_ALPHA = 0.01
STEP_ROT = 5.0
STEP_SPACING = 0.001

# Discrete parameters. Their knobs are kind 'choice': delta steps through the
# list, wrapping. Mask 'none' is stored as a string so it round-trips through
# JSON and presets, and becomes None only at the GratingStim.
CHOICES = {
    'waveform': ['sin', 'sqr', 'saw'],
    'mask': ['none', 'circle'],
    'shape': ['rect', 'circle'],
    'font_family': ['monospace', 'sans-serif', 'serif'],
}

_GRATING_KNOBS = {
    'z': ('sf', +STEP_SF, 0.5, 50.0, 'float'),
    'x': ('sf', -STEP_SF, 0.5, 50.0, 'float'),
    'r': ('ori', +STEP_ORI, 0.0, 360.0, 'wrap'),
    't': ('ori', -STEP_ORI, 0.0, 360.0, 'wrap'),
    'e': ('phase', +STEP_PHASE, 0.0, 1.0, 'float'),
    'w': ('phase', -STEP_PHASE, 0.0, 1.0, 'float'),
}

STIM_KNOBS = {
    # Wedges step by 2 from an even default, so they stay even.
    STIM_RADIAL: {
        'z': ('rings', +1, 1, 20, 'int'),
        'x': ('rings', -1, 1, 20, 'int'),
        'r': ('wedges', +2, 2, 32, 'int'),
        't': ('wedges', -2, 2, 32, 'int'),
    },
    STIM_GABOR: dict(_GRATING_KNOBS, **{
        'd': ('envelope_sd', +STEP_SD, 0.01, 1.0, 'float'),
        'a': ('envelope_sd', -STEP_SD, 0.01, 1.0, 'float'),
    }),
    # Gabor's D/A envelope pair becomes waveform here; B toggles the mask.
    STIM_GRATING: dict(_GRATING_KNOBS, **{
        'd': ('waveform', +1, None, None, 'choice'),
        'a': ('waveform', -1, None, None, 'choice'),
        'b': ('mask', +1, None, None, 'choice'),
    }),
    STIM_UNIFORM: {
        'r': ('r', +STEP_RGB, -1.0, 1.0, 'float'),
        't': ('r', -STEP_RGB, -1.0, 1.0, 'float'),
        'e': ('g', +STEP_RGB, -1.0, 1.0, 'float'),
        'w': ('g', -STEP_RGB, -1.0, 1.0, 'float'),
        'd': ('b', +STEP_RGB, -1.0, 1.0, 'float'),
        'a': ('b', -STEP_RGB, -1.0, 1.0, 'float'),
        'z': ('alpha', +STEP_ALPHA, 0.0, 1.0, 'float'),
        'x': ('alpha', -STEP_ALPHA, 0.0, 1.0, 'float'),
        'b': ('shape', +1, None, None, 'choice'),
    },
    STIM_CUSTOM_PNG: {
        'z': ('alpha', +STEP_ALPHA, 0.0, 1.0, 'float'),
        'x': ('alpha', -STEP_ALPHA, 0.0, 1.0, 'float'),
        'r': ('rotation_deg', +STEP_ROT, 0.0, 360.0, 'wrap'),
        't': ('rotation_deg', -STEP_ROT, 0.0, 360.0, 'wrap'),
    },
    # Text reuses the uniform patch's colour keys exactly; string cycling gets
    # its own [B]/[N] rather than overloading [R/T].
    STIM_TEXT: {
        'r': ('r', +STEP_RGB, -1.0, 1.0, 'float'),
        't': ('r', -STEP_RGB, -1.0, 1.0, 'float'),
        'e': ('g', +STEP_RGB, -1.0, 1.0, 'float'),
        'w': ('g', -STEP_RGB, -1.0, 1.0, 'float'),
        'd': ('b', +STEP_RGB, -1.0, 1.0, 'float'),
        'a': ('b', -STEP_RGB, -1.0, 1.0, 'float'),
        'z': ('alpha', +STEP_ALPHA, 0.0, 1.0, 'float'),
        'x': ('alpha', -STEP_ALPHA, 0.0, 1.0, 'float'),
        'u': ('letter_spacing', +STEP_SPACING, -0.05, 0.20, 'float'),
        'y': ('letter_spacing', -STEP_SPACING, -0.05, 0.20, 'float'),
        'i': ('font_family', +1, None, None, 'choice'),
        'o': ('font_family', -1, None, None, 'choice'),
        'k': ('rotation_deg', +STEP_ROT, 0.0, 360.0, 'wrap'),
        'l': ('rotation_deg', -STEP_ROT, 0.0, 360.0, 'wrap'),
    },
}

# Auto-repeating knobs. At 0.001 (bg, contrast, RGB) or 0.005 (position) per
# press these need hundreds of presses to cross their range; the coarser knobs
# -- size, frequency, distance -- stay single-press.
REPEAT_KEYS = ('left', 'right', 'up', 'down',      # x / y position
               'pageup', 'pagedown',               # background gray
               'c', 'v',                           # contrast
               'f', 'j')                           # custom flicker frames
# ...plus the colour channels and letter spacing, which share the 0.001 step
# and so the same problem. Alpha is 0.01 and stays single-press.
REPEAT_KEYS_BY_STIM = {
    STIM_UNIFORM: ('r', 't', 'e', 'w', 'd', 'a'),
    STIM_TEXT: ('r', 't', 'e', 'w', 'd', 'a', 'u', 'y'),
}

# Clock-driven rather than frame-driven, so the rate is the same whatever the
# panel refresh turns out to be (60/s is one increment per frame at 60 Hz, one
# every 4 frames at 240 Hz).
REPEAT_DELAY_S = 1.0              # hold this long before repeating starts
REPEAT_RATE_HZ = 60.0             # increments per second once it starts

# Live frame timing. The rolling window is long enough to average out jitter
# but short enough to react within about half a second on a fast panel.
ROLLING_FRAMES = 120
# A frame counts as dropped when its flip-to-flip interval runs past this
# multiple of the rolling MEDIAN interval -- 1.5x sits clear of ordinary jitter
# but below the 2.0x that a single missed vsync would produce. Median rather
# than the startup figure so the threshold self-calibrates to the panel that is
# actually running, and median rather than mean so the drops themselves do not
# inflate the threshold that detects them.
DROP_FACTOR = 1.5
# Below this many samples the median is too noisy to threshold against, so the
# startup measurement stands in.
MIN_DROP_SAMPLES = 15

# Startup getMsPerFrame and the rolling average should agree. When they do not,
# one of them is wrong -- most often getMsPerFrame having fallen back -- and
# every frame-count frequency in the session is suspect.
DIVERGENCE_WARN_HZ = 5.0


# The radial checker texture (PRD 4.1): one full cycle per axis, so
# radialCycles = rings / 2 and angularCycles = wedges / 2. Every row is
# sign-balanced, so each annulus is too, independently of annulus area.
CHECKER_PATTERN = np.array([[1, -1], [-1, 1]])

RADIAL_PHASE = 0.25               # see make_radial
DEFAULT_RINGS = 4
DEFAULT_WEDGES = 16


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


def max_flicker_frames(refresh_hz):
    """Longest custom cycle: about 1 Hz at this refresh."""
    return max(2, int(round(refresh_hz)))


def flicker_split(frames):
    """(on, off) frames per cycle -- the split stim_is_on draws."""
    return frames // 2, frames - frames // 2


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


def mode_claims_key(state, key):
    """True when the active mode has taken this arrow off the knob table.

    Gamma steps owns LEFT/RIGHT and spatial uniformity owns all four arrows
    (PRD 6.2, 6.4).
    """
    if state['mode'] == MODE_GAMMA:
        return key in ('left', 'right')
    if state['mode'] == MODE_UNIFORMITY:
        return key in ('left', 'right', 'up', 'down')
    return False


def key_claim(state, key, sweeping=False):
    """What the press dispatcher does with `key` BEFORE the knob table.

    Returns a tag, or None when the key falls through to the knobs. This is
    the one statement of dispatch precedence: the press loop acts on the tag,
    and the repeat loop refuses to step any key that has one. Without that a
    held key could drive a knob the press path would never reach -- a held
    [A] in gamma mode silently decremented blue at the repeat rate.
    """
    if key in MODE_KEYS:
        return 'mode'
    if key == DUAL_KEY:
        return 'dual'
    if key in (SELECT_PREV, SELECT_NEXT):
        return 'select'           # inert while multi is off
    if key == COPY_STATE_KEY:
        return 'copy_state'       # inert while multi is off
    # [A] is a knob on several types, so gamma mode claims it for the sweep.
    if key == 'a' and state['mode'] == MODE_GAMMA:
        return 'sweep_toggle'
    # ESC cancels a running sweep rather than quitting.
    if key == 'escape' and sweeping:
        return 'sweep_cancel'
    if mode_claims_key(state, key):
        return 'mode_arrow'
    if key == MENU_TOGGLE_KEY:
        return 'menu'
    if key == 'escape' and state['menu_visible']:
        return 'menu_close'
    if key == HUD_TOGGLE_KEY:
        return 'hud'
    if (state['stimulus_type'] == STIM_TEXT
            and key in (TEXT_CYCLE_FWD, TEXT_CYCLE_BACK)):
        return 'text_cycle'
    if key == 'p':
        return 'preset'
    if key == 'f12':
        return 'screenshot'
    return None


def rolling_stats(intervals):
    """(Hz, SD in ms, median interval in s), or (None, None, None).

    Mean of the intervals rather than of the per-frame rates: rate is the
    reciprocal of a duration, so averaging rates would bias the result. The
    median comes back too because the drop threshold keys off it.
    """
    if len(intervals) < 2:
        return None, None, None
    arr = np.asarray(intervals, dtype=float)
    mean_s = float(arr.mean())
    if mean_s <= 0:
        return None, None, None
    return (1.0 / mean_s, float(arr.std(ddof=1)) * 1000.0,
            float(np.median(arr)))


def vsync_state(win):
    """(is_on, detail). Which attribute said so is recorded, because they lie.

    PsychoPy has no `useRetrace`. `waitBlanking` is the flag that actually
    governs whether flip() blocks on the retrace, so that is the answer; the
    pyglet-level values go in beside it because on Windows the driver query
    routinely disagrees with the setting that is in force.
    """
    detail = {}
    wait = getattr(win, 'waitBlanking', None)
    detail['wait_blanking'] = None if wait is None else bool(wait)
    handle = getattr(win, 'winHandle', None)
    detail['pyglet_vsync'] = bool(getattr(handle, 'vsync', False)) \
        if handle is not None else None
    try:
        detail['context_get_vsync'] = bool(handle.context.get_vsync())
    except Exception:                                        # noqa: BLE001
        detail['context_get_vsync'] = None
    return bool(wait), detail


def mode_frames(state, refresh_hz):
    """Frames per flicker cycle for the active mode, or None if not flickering.

    PRD 6.1: the count is the nearest integer at the MEASURED refresh, and the
    readout reports the frequency that count actually realises.
    """
    mode = state['mode']
    if mode in FLICKER_HZ:
        return hz_to_frames(FLICKER_HZ[mode], refresh_hz)
    if mode == MODE_FLICKER_CUSTOM:
        return state['stim_frames'][selected(state)]
    return None


def selected(state):
    """Index of the selected copy: always 0 while multi is off."""
    if not state['multi']:
        return 0
    return min(state['selected_index'], state['multi_count'] - 1)


def sync_stim_frames(state):
    """Give every copy a frame count, and keep the selection on a copy.

    A copy beyond anything remembered takes the frames of the current last
    copy; one that existed earlier in the session gets its own value back.
    """
    for key in ('stim_frames', 'stim_states'):
        values = state[key]
        while len(values) < state['multi_count']:
            values.append(values[-1])
    state['selected_index'] = min(state['selected_index'],
                                  state['multi_count'] - 1)


def copy_states(state):
    """flicker / steady / off for each drawn copy. One 'flicker' copy when
    multi is off: the single stimulus behaves exactly as before."""
    if not state['multi']:
        return ['flicker']
    return list(state['stim_states'][:state['multi_count']])


def copy_frames(state, refresh_hz):
    """Frames per cycle for each drawn copy, or None if not flickering.

    Modes 3 and 4 drive every copy at the shared target; mode 5 gives each
    copy its own count.
    """
    count = len(ring_positions(state))
    mode = state['mode']
    if mode in FLICKER_HZ:
        return [hz_to_frames(FLICKER_HZ[mode], refresh_hz)] * count
    if mode == MODE_FLICKER_CUSTOM:
        if not state['multi']:
            return [state['stim_frames'][0]]
        return list(state['stim_frames'][:count])
    return None


def drawn_positions(state, refresh_hz):
    """Positions drawn THIS frame (PRD 6.1, 6.3).

    A 'flicker' copy is on iff (frame_idx % frames_i) < frames_i // 2 --
    stim_is_on, stateless in the one shared frame_idx, which resets on a mode
    switch. A 'steady' copy is on in every frame; an 'off' copy never is.
    """
    if state['mode'] == MODE_STATIC_OFF:
        return []
    positions = ring_positions(state)
    frames = copy_frames(state, refresh_hz) or [None] * len(positions)
    drawn = []
    for pos, n, copy_state in zip(positions, frames, copy_states(state)):
        if copy_state == 'off':
            continue
        if n is None or copy_state == 'steady' or stim_is_on(
                state['frame_idx'], n):
            drawn.append(pos)
    return drawn


def copy_half_extent(state):
    """(half width, half height) of one copy's axis-aligned bounding box.

    Text uses its string extent; every other type a size x size square. The
    box turns with the copy where the type turns: text and PNG rotation,
    grating and Gabor orientation.
    """
    width, height = state['text_extent'] or (state['size'], state['size'])
    stim_type = state['stimulus_type']
    if stim_type in (STIM_TEXT, STIM_CUSTOM_PNG):
        angle = math.radians(state['rotation_deg'])
    elif stim_type in (STIM_GRATING, STIM_GABOR):
        angle = math.radians(state['ori'])
    else:
        angle = 0.0
    c, s_ = abs(math.cos(angle)), abs(math.sin(angle))
    return (width * c + height * s_) / 2.0, (width * s_ + height * c) / 2.0


def offscreen_copies(state):
    """One bool per copy: True if any part of it falls outside the window."""
    hx, hy = copy_half_extent(state)
    half_w = state['aspect'] / 2.0
    return [x - hx < -half_w or x + hx > half_w or y - hy < -0.5 or
            y + hy > 0.5 for x, y in ring_positions(state)]


def footprint_radius(state, extent=None):
    """Radius of a circle that holds one copy, whatever its type and angle.

    `extent` is (width, height) for text, whose string can be far wider than
    the size knob; every other type fits in a size x size square.
    """
    width, height = (extent or state['text_extent'] or
                     (state['size'], state['size']))
    return 0.5 * math.hypot(width, height)


def marker_segment(state, radius):
    """(start, end) of the selection tick, or None if none can fit.

    Tried radially outward from the ring centre first, then swinging round in
    30 degree steps. A direction is used only if the tick stays MARKER_CLEAR
    outside every copy's footprint circle.
    """
    positions = ring_positions(state)
    cx, cy = positions[selected(state)]
    out = math.atan2(cy - state['y_pos'], cx) if (cx or
                                                   cy - state['y_pos']) else 0
    for step in (0, 6, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5):
        angle = out + math.radians(30 * step)
        dx, dy = math.cos(angle), math.sin(angle)
        start = (cx + dx * (radius + MARKER_GAP), cy + dy * (radius + MARKER_GAP))
        end = (cx + dx * (radius + MARKER_GAP + MARKER_LEN),
               cy + dy * (radius + MARKER_GAP + MARKER_LEN))
        if all(segment_distance(start, end, pos) > radius + MARKER_CLEAR
               for pos in positions):
            return start, end
    return None


def segment_distance(a, b, p):
    """Shortest distance from point p to the segment a-b."""
    ax, ay = a
    vx, vy = b[0] - ax, b[1] - ay
    t = ((p[0] - ax) * vx + (p[1] - ay) * vy) / float(vx * vx + vy * vy)
    t = clamp(t, 0.0, 1.0)
    return math.hypot(p[0] - (ax + t * vx), p[1] - (ay + t * vy))


def knob_table(stimulus_type, refresh_hz=60.0):
    """Universal knobs plus the chosen type's own. Built once per session.

    The custom flicker range is the one refresh-dependent limit.
    """
    table = dict(KNOBS)
    table.update(STIM_KNOBS.get(stimulus_type, {}))
    for key in ('f', 'j'):
        field, delta, low, _high, kind = table[key]
        table[key] = (field, delta, low, max_flicker_frames(refresh_hz), kind)
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
    if field == 'flicker_frames':
        # Mode 5 frames belong to the SELECTED copy (PRD 6.3).
        frames, index = state['stim_frames'], selected(state)
        frames[index] = int(clamp(frames[index] + delta, low, high))
        return True
    if kind == 'choice':
        options = CHOICES[field]
        state[field] = options[
            (options.index(state[field]) + delta) % len(options)]
        return True
    value = state[field] + delta
    if kind == 'wrap':
        # Orientation is cyclic: 355 + 5 is 0, not a clamp at 360.
        state[field] = round(value % high, STORE_DP)
    elif kind == 'int':
        state[field] = int(round(clamp(value, low, high)))
    else:
        state[field] = round(clamp(value, low, high), STORE_DP)
    if field == 'multi_count':
        sync_stim_frames(state)
    return True


def pyglet_key_name(symbol):
    """The name event.getKeys() reports for a pyglet symbol.

    Mirrors psychopy.event._onPygletKey, so held-key tracking and the press
    events it filters agree on what a key is called.
    """
    name = pyglet_key.symbol_string(symbol).lower().lstrip('_')
    return 'return' if name == 'enter' else name


def new_presses(keys, held_since):
    """The press events in `keys` that are real presses.

    A press for a key already held is never a new press, whatever the key.
    pyglet 1.4 already drops OS autorepeat on Windows; this keeps it true on
    any backend that does not. The only repeat is repeat_tick, for the
    repeat-enabled knobs.
    """
    return [key for key in keys if key not in held_since]


def repeat_tick(state, table, repeat_names, down, held_since, repeat_count,
                now, sweeping=False):
    """One frame of held-key tracking and hold-to-repeat.

    `down` is every key name currently held. held_since tracks ALL of them --
    the press loop drops any press event for a key already in it -- but only
    `repeat_names` ever step here.

    The count due is derived from how long the key has been down, NOT from the
    time since the last increment. Those differ: an increment can only be
    emitted on a frame boundary, so "wait 1/rate s since the last one" rounds
    every interval UP to a whole frame and beats the realised rate down.
    Measuring against the hold start lets a short interval make up for a long
    one, so the average holds at exactly REPEAT_RATE_HZ on any panel.
    """
    for name in list(held_since):
        if name not in down:
            held_since.pop(name)
            repeat_count.pop(name, None)
    for name in down:
        if name not in held_since:
            # First frame down. The press path already acted on it; just
            # start the hold timer.
            held_since[name] = now
            repeat_count[name] = 0
            continue
        if name not in repeat_names:
            continue
        if key_claim(state, name, sweeping) is not None:
            # Claimed ahead of the knob table, so not a knob right now. The
            # timer restarts, so it repeats only after a full delay unclaimed.
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


# =============================================================================
# STATE
# =============================================================================

def default_state(stimulus_type, refresh_hz=60.0):
    """Every adjustable parameter in one dict, at its PRD default.

    `refresh_hz` is the measured refresh, which mode 5's default frame count
    and its presets are relative to.
    """
    # Text starts white so the glyphs are visible at launch; rgb 0.0 is the
    # same mid-gray as the default background, which rendered them invisible.
    # The uniform patch keeps 0.0 -- there, mid-gray IS the calibration
    # starting point (PRD 4.4), and the patch is meant to be driven from it.
    channel_default = 1.0 if stimulus_type == STIM_TEXT else 0.0
    return {
        # Universal (PRD 5)
        'x_pos': 0.66,
        'y_pos': 0.0,
        'bg_gray': 0.0,
        'size': 0.225,
        'contrast': 1.0,
        # Mode 5 cycle length in whole frames, one per ring copy (PRD 6.1,
        # 6.3). Entries past multi_count are kept, so lowering then raising
        # the count brings dropped values back. Saved in presets with
        # refresh_hz, so a preset can tell when the panel changed.
        'stim_frames': [hz_to_frames(DEFAULT_CUSTOM_HZ, refresh_hz)] *
                       MULTI_MIN,
        'selected_index': 0,
        # Per-copy state, remembered past the count like stim_frames.
        'stim_states': ['flicker'] * MULTI_MIN,
        # Text only: (width, height) of the string, set by the main loop from
        # the GlyphString so footprints know how wide the copies are.
        'text_extent': None,
        'refresh_hz': refresh_hz,
        'viewing_distance_cm': 40,

        # Selection
        'stimulus_type': stimulus_type,
        'mode': MODE_STATIC_ON,
        # PRD 6.3, orthogonal to mode. The count is kept while multi is off.
        'multi': False,
        'multi_count': MULTI_MIN,
        'ring_offset_deg': 0.0,

        # Screen geometry, filled in once the window is open. Needed for the
        # full-screen gamma patch, the uniformity grid extents and the pixel
        # readout.
        'aspect': 16.0 / 9.0,
        'win_w': 1920,
        'win_h': 1080,

        # Radial checkerboard (PRD 4.1)
        'rings': DEFAULT_RINGS,
        'wedges': DEFAULT_WEDGES,

        # Grating / Gabor (PRD 4.2, 4.3)
        'sf': 4.0,
        'ori': 0.0,
        'phase': 0.5,
        'envelope_sd': 0.06,
        'waveform': 'sin',        # grating only (PRD 4.3)
        'mask': 'none',

        # Uniform patch (PRD 4.4)
        'r': channel_default,
        'g': channel_default,
        'b': channel_default,
        'alpha': 1.0,
        'shape': 'rect',          # also the spatial uniformity patch's

        # Custom PNG (PRD 4.5). Resolved at startup; GENERATED_LABEL when the
        # fallback pattern is in use.
        'image_path': GENERATED_LABEL,
        'rotation_deg': 0.0,

        # Text stimulus (PRD 4.6). rotation_deg above is shared with PNG.
        'text_string': TEXT_PRESETS[0],
        'text_index': 0,
        'letter_spacing': 0.0,
        'font_family': 'monospace',
        # Resolved at startup (resolve_font); not carried in presets.
        'font_requested': FONT_CANDIDATES['monospace'][0],
        'font_rendered': None,

        # HUD visibility (PRD 8.1). Only the readout hides; every stimulus
        # and the status bar keep rendering.
        'hud_visible': True,
        # Keybinding overlay (PRD 8.3).
        'menu_visible': False,

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
    """(image for ImageStim, label, failure). Falls back to the generated
    pattern.

    PRD 4.5: a missing file, or one PIL cannot decode, prints a warning and
    falls back rather than dying -- a calibration session should not be lost
    to a typo in a path. `failure` is the intro-screen note saying so, or ''.
    The label is the basename, so no absolute path reaches the JSON.
    """
    if not path:
        return make_test_pattern(), GENERATED_LABEL, ''
    name = os.path.basename(path)
    if len(name) > IMAGE_NAME_CHARS:
        name = '...' + name[-(IMAGE_NAME_CHARS - 3):]
    if not os.path.isfile(path):
        print("ERROR: --image file not found: {}".format(path))
        print("       Falling back to the generated test pattern.")
        return (make_test_pattern(), GENERATED_LABEL,
                'NOT FOUND {}, using test pattern'.format(name))
    try:
        # ImageStim decodes with PIL too, so this is the same test it would
        # fail -- but here, before the window and the session exist.
        from PIL import Image
        with Image.open(path) as img:
            img.load()
    except Exception as err:                                 # noqa: BLE001
        print("WARNING: --image could not be loaded: {} ({}: {})".format(
            path, type(err).__name__, err))
        print("         Falling back to the generated test pattern.")
        return (make_test_pattern(), GENERATED_LABEL,
                'FAILED to load {}, using test pattern'.format(name))
    return path, os.path.basename(path), ''


def output_path_label(path):
    """`path` as written to JSON: relative to OUT_DIR when it lies inside it,
    otherwise just the basename. No absolute path reaches an output file."""
    if not path:
        return path
    full = os.path.abspath(path)
    try:
        rel = os.path.relpath(full, OUT_DIR)
    except ValueError:            # another drive, on Windows
        return os.path.basename(full)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return os.path.basename(full)
    return rel.replace(os.sep, '/')


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


def grating_mask(state):
    """GratingStim mask for the grating type: 'none' is stored, None is used."""
    return None if state['mask'] == 'none' else state['mask']


def make_patch(win, state, shape):
    """PRD 4.4 uniform patch: a rect, or a circle whose DIAMETER is size.

    The circle is a ShapeStim like the rect -- same fill path, same colour
    space -- not a masked GratingStim, so the two render identical colour.
    """
    common = dict(fillColor=[state['r'], state['g'], state['b']],
                  lineWidth=0, lineColor=None, colorSpace='rgb',
                  opacity=state['alpha'], contrast=state['contrast'],
                  pos=(state['x_pos'], state['y_pos']), autoLog=False)
    if shape == 'circle':
        return visual.Circle(win=win, radius=state['size'] / 2.0, edges=256,
                             **common)
    return visual.Rect(win=win, width=state['size'], height=state['size'],
                       **common)


def size_patch(patch, size):
    if isinstance(patch, visual.Circle):
        patch.radius = size / 2.0
    else:
        patch.width = size
        patch.height = size


def text_cycle(text_arg):
    """(strings [B]/[N] cycle through, starting index) for --text (PRD 4.6).

    None: the five TEXT_PRESETS. One character: its alphabet, starting there
    (a-z for a lowercase letter; anything else is put in front of A-Z).
    Longer: the full string, each of its characters, then the whole alphabet
    as one string.
    """
    if not text_arg:
        return list(TEXT_PRESETS), 0
    if len(text_arg) == 1:
        letters = ALPHABET.lower() if text_arg in ALPHABET.lower() else ALPHABET
        if text_arg in letters:
            return list(letters), letters.index(text_arg)
        return [text_arg] + list(ALPHABET), 0
    return [text_arg] + list(text_arg) + [ALPHABET], 0


def resolve_font(family):
    """(requested, rendered) font names for a family on this machine.

    pyglet silently substitutes its default face for a name it cannot find,
    so have_font() is asked first: when no candidate is installed, `rendered`
    names the face pyglet will actually draw rather than the one requested.
    """
    import pyglet.font
    candidates = FONT_CANDIDATES[family]
    for name in candidates:
        if pyglet.font.have_font(name):
            return name, name
    fallback = getattr(getattr(pyglet.font, '_font_class', None),
                       '_default_name', None)
    return candidates[0], fallback or 'system default'


def font_label(state):
    """'serif (Times New Roman)', or an explicit fallback statement."""
    requested, rendered = state['font_requested'], state['font_rendered']
    if rendered is None or rendered == requested:
        return '{} ({})'.format(state['font_family'], requested)
    return '{} (FALLBACK {}: {} not installed)'.format(
        state['font_family'], rendered, requested)


def glyph_advances(text, font, height_px):
    """Pixel advance of each glyph, from the same pyglet face TextStim uses.

    TextStim hands pyglet.text.Label int(height_px * 0.75) pt at 96 dpi, and
    pyglet lays a line out by summing these advances (no kerning). Advances,
    not ink extents, so the layout matches a single TextStim.
    """
    import pyglet.font
    face = pyglet.font.load(font, int(height_px * 0.75))
    return [glyph.advance for glyph in face.get_glyphs(text)]


def glyph_offsets(advances_px, spacing, rotation_deg, win_h, wrap_px=None):
    """Offset of each glyph's pen origin from the string centre, height units.

    Pen i = sum of advances 0..i-1 + i * spacing, and the full advance extent
    is centred. Offsets are then turned with the string, clockwise like
    PsychoPy's ori, so the glyphs rotate as one rigid unit.

    Centring copies pyglet's integer arithmetic for a centred TextStim line,
    -(W // 2) + (W - width) // 2 with W its wrap width in px. A plain
    -width / 2 lands odd widths on a half pixel, 1 px off a single TextStim.
    """
    spacing_px = spacing * win_h
    total = sum(advances_px) + (len(advances_px) - 1) * spacing_px
    if wrap_px is None or total > wrap_px:
        pen = -total / 2.0
    else:
        pen = -(wrap_px // 2) + (wrap_px - total) // 2
    xs = []
    for advance in advances_px:
        xs.append(pen / float(win_h))
        pen += advance + spacing_px
    theta = math.radians(rotation_deg)
    return [(x * math.cos(theta), -x * math.sin(theta)) for x in xs]


class GlyphString(object):
    """PRD 4.6 text stimulus: one TextStim per glyph, laid out on advances.

    A single character is one ordinary centred TextStim, exactly the v1
    construction. So is an unspaced, unrotated string that fits the TextStim's
    wrap width -- the fast path: the per-glyph layout is pixel-identical to it
    there, and one draw is several times cheaper than one per glyph. Otherwise
    each glyph is its own TextStim, anchored at its pen origin, so letter
    spacing and rigid rotation are possible -- TextStim has neither. Exposes
    pos, contrast and draw() like a stimulus, so multi mode and flicker treat
    it as one.
    """

    def __init__(self, win, fast=True):
        self.win = win
        self.fast = fast
        self.pos = (0.0, 0.0)
        self.contrast = 1.0
        self.glyphs = []
        self.offsets = []
        self.advances = []
        self.height = 0.0
        self._advance_key = None
        self._wrap_probe = None
        self._build_key = None
        self._layout_key = None
        self._style = None

    def update(self, state):
        text, font = state['text_string'], state['font_requested']
        size, win_h = state['size'], self.win.size[1]
        if (text, font, size) != self._advance_key:
            self.advances = glyph_advances(text or ' ', font, size * win_h)
            self._advance_key = (text, font, size)
        whole = len(text) <= 1 or (
            self.fast and state['letter_spacing'] == 0 and
            state['rotation_deg'] == 0 and
            sum(self.advances) <= self._wrap_px(size))
        build_key = (text, font, size, whole)
        if build_key != self._build_key:
            pieces = [text or ' '] if whole else list(text)
            self.glyphs = [visual.TextStim(
                win=self.win, text=piece, font=font, height=size,
                colorSpace='rgb',
                anchorHoriz='center' if whole else 'left',
                alignText='center' if whole else 'left',
                autoLog=False) for piece in pieces]
            self.height = size
            self._build_key = build_key
            self._layout_key = self._style = None
        layout_key = (state['letter_spacing'], state['rotation_deg'])
        if layout_key != self._layout_key:
            if len(self.glyphs) == 1:   # one character, or the fast path
                self.offsets = [(0.0, 0.0)]     # spacing is inert
            else:
                # The wrap width a default single TextStim would centre in.
                wrap_px = getattr(self.glyphs[0], '_wrapWidthPix', None)
                self.offsets = glyph_offsets(self.advances, layout_key[0],
                                             layout_key[1], win_h, wrap_px)
            for glyph in self.glyphs:
                glyph.ori = layout_key[1]
            self._layout_key = layout_key
        style = (state['r'], state['g'], state['b'], state['alpha'],
                 self.contrast)
        if style != self._style:
            # Each setter rebuilds the glyph's pyglet label, so only on change.
            for glyph in self.glyphs:
                glyph.color = list(style[:3])
                glyph.opacity = style[3]
                glyph.contrast = style[4]
            self._style = style

    def _wrap_px(self, size):
        """The wrap width a default TextStim of this height would get."""
        if self._wrap_probe is None:
            self._wrap_probe = visual.TextStim(win=self.win, text=' ',
                                               height=size, autoLog=False)
        return self._wrap_probe._wrapWidthPix

    def extent(self):
        """(width, height) of the string's advance box, height units."""
        win_h = float(self.win.size[1])
        spacing = self._layout_key[0] if self._layout_key else 0.0
        width = (sum(self.advances) / win_h +
                 max(0, len(self.advances) - 1) * spacing)
        return width, self.height

    def draw(self):
        x, y = self.pos
        for glyph, (dx, dy) in zip(self.glyphs, self.offsets):
            glyph.pos = (x + dx, y + dy)
            glyph.draw()


def radial_cycles_for(state):
    """(radialCycles, angularCycles) for the 2x2 tex: one cycle = two checks."""
    return state['rings'] / 2.0, state['wedges'] / 2.0


def make_radial(win, state):
    """PRD 4.1 RadialStim. Do not add a mask or change texRes."""
    radial_cycles, angular_cycles = radial_cycles_for(state)
    # RadialStim's radial texcoord starts at 0.25 - radialPhase: one texel on
    # the old 4x4 tex, but half a texel on this 2x2. radialPhase=0.25 cancels
    # it, so rings=N draws N full-width rings from the centre, and the
    # defaults are pixel-identical to the v1 construction.
    return RadialStim(
        win=win, tex=CHECKER_PATTERN, size=state['size'],
        radialCycles=radial_cycles, angularCycles=angular_cycles,
        radialPhase=RADIAL_PHASE, texRes=256, opacity=1,
        contrast=state['contrast'],
        pos=(state['x_pos'], state['y_pos']),
        name='calib_disc', autoLog=False)


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


def to_pixels(state):
    """(x px, y px, size px) for the current position and size (PRD 8).

    Height units are relative to screen HEIGHT on both axes, so both
    coordinates scale by win_h; only the origin offset differs. Note y grows
    downward here -- PsychoPy's +y is up, so a positive y_pos reports a pixel
    row below centre.
    """
    win_w, win_h = state['win_w'], state['win_h']
    return (int(state['x_pos'] * win_h + win_w / 2.0),
            int(state['y_pos'] * win_h + win_h / 2.0),
            int(state['size'] * win_h))


def monitor_dimension_suspect(screen_height_cm):
    """True when the stored screen height cannot be this rig's real one.

    An absent height makes every angle unavailable; an implausible one makes
    them plausible AND wrong, which is worse. Both warrant the warning.
    """
    if not screen_height_cm:
        return True
    return not (MONITOR_H_MIN_CM <= screen_height_cm <= MONITOR_H_MAX_CM)


def monitor_warning_text(screen_height_cm):
    if not monitor_dimension_suspect(screen_height_cm):
        return ''
    if not screen_height_cm:
        measured = 'monitor height is unknown'
    else:
        measured = 'monitor height {:.1f} cm looks wrong'.format(
            screen_height_cm)
    return ('WARNING: {}. Set physical dimensions in PsychoPy Monitor '
            'Center. Visual angles will be incorrect.'.format(measured))


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
        "KNOBS: [Z/X] rings   [R/T] wedges   [ARROWS] move X/Y",
        "       [PAGEUP/PAGEDN] BG   [+/-] size   [C/V] contrast",
        "       [F/J] custom flicker, whole frames",
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
        "       [D/A] waveform sin/sqr/saw   [B] circular mask",
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
        "       [B] rect/circle   plus the universal knobs.",
    ],
    STIM_TEXT: [
        "1. Cycle strings with [B]/[N] (built in, or from --text).",
        "2. Adjust size for the target letter height in degrees;",
        "   readout line 3 shows degrees and pixels.",
        "3. Set text colour with [R/T], [E/W], [D/A]; step contrast",
        "   with [C/V].",
        "",
        "KNOBS: [B/N] string  [I/O] font  [U/Y] spacing  [K/L] rotate",
        "       [R/T] red  [E/W] green  [D/A] blue  [Z/X] alpha",
        "       plus the universal knobs. [M] for the full card.",
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
        "4. Snapshot [S] -- the file name is recorded with it.",
        "",
        "KNOBS: [Z/X] alpha   [R/T] rotation   plus the universal knobs.",
        "Pass a file with:  python monical.py --image path.png",
    ],
}


def build_intro_text(resolution, refresh_hz, selected_index, image_label,
                     out_name='', preset_name='', image_failure=''):
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
        # Where the session's measurements are going. Shown here because the
        # name is fixed at startup and never changes during the run.
        "Output:     {}".format(out_name),
    ]
    if preset_name:
        lines.append("Preset:     {}".format(preset_name[-49:]))
    if image_failure:
        # Whatever type is selected: the operator passed --image for a reason.
        lines.append("Image:      {}".format(image_failure))
    lines += [
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
        "       [7] MULTI ring on/off  [ / ] copies 2-16  [,/.] rotate",
        "       [9/0] select copy -- [F/J] then sets ITS mode 5 frames",
        "       [/] selected copy: flicker -> steady -> off",
        "[S] snapshot  [P] save preset  [F12] screenshot  [A] auto gamma",
        "[H] readout  [M] key card  [;/'] distance  [Q]/[ESC] save+quit",
        "",
        "Press SPACE to begin. Q or ESC here exits without saving.",
    ]
    return "\n".join(lines)


def intro_stims(win, resolution, warning=''):
    """(text, warn) stims for the intro screen, warn None without a warning.

    The wrap box is centred on screen and the text left-aligned inside it, so
    a box wider than the screen (1.7 units on a 1.33-wide 4:3 panel) would
    push the first column off the left edge. It is capped to the screen.
    """
    wrap = min(INTRO_WRAP_W, resolution[0] / float(resolution[1]) *
               INTRO_WRAP_FRAC)
    text = visual.TextStim(
        win, text='', font=READOUT_FONT, height=INTRO_HEIGHT, color='white',
        pos=(0, 0), wrapWidth=wrap, alignText='left', anchorHoriz='center',
        autoLog=False)
    # Yellow, and a separate stim because TextStim colours the whole block.
    # Anchored at its bottom edge, so a wrapped warning grows upward.
    warn = None
    if warning:
        warn = visual.TextStim(
            win, text=warning, font=READOUT_FONT, height=INTRO_HEIGHT,
            color='yellow', pos=(0, -0.5 + INTRO_MARGIN), wrapWidth=wrap,
            alignText='center', anchorHoriz='center', anchorVert='bottom',
            autoLog=False)
    return text, warn


def set_intro_text(win, text, warn, content):
    """Fill the intro block, centred in the space above the warning.

    The text keeps INTRO_HEIGHT unless the block would not fit there (a long
    workflow plus the preset and image lines), and only then shrinks. The
    block's height is predicted the way HudLines does it: pyglet rounds the
    font to whole points, and each line is ascent - descent of that face.
    """
    import pyglet.font
    win_h = float(win.size[1])
    top, bottom = 0.5 - INTRO_MARGIN, -0.5 + INTRO_MARGIN
    if warn is not None:
        bottom += warn.boundingBox[1] / win_h + INTRO_MARGIN
    lines = content.count('\n') + 1

    def fits(height):
        face = pyglet.font.load(READOUT_FONT, int(height * win_h * 0.75))
        return lines * (face.ascent - face.descent) <= (top - bottom) * win_h

    height = INTRO_HEIGHT
    if not fits(height):
        # Largest height that fits, to a few thousandths of a unit.
        low, high = INTRO_HEIGHT / 2.0, INTRO_HEIGHT
        for _ in range(7):
            mid = (low + high) / 2.0
            low, high = (mid, high) if fits(mid) else (low, mid)
        height = low
    if text.height != height:
        text.height = height
    text.pos = (0, (top + bottom) / 2.0)
    text.text = content


def show_intro(win, resolution, refresh_hz, image_label, out_name='',
               preset_name='', selected_index=0, warning='',
               image_failure=''):
    """White on black. Returns the chosen stimulus type, or None if aborted.

    `selected_index` preselects a type -- a loaded preset opens on the type it
    was saved from, though the operator can still change it before SPACE.
    """
    previous_color = win.color
    win.color = [-1, -1, -1]
    # Window colour needs a flip to take; two clears the FBO's stale buffer.
    win.flip()
    win.flip()

    select_keys = [str(i + 1) for i in range(len(STIMULUS_TYPES))]
    selected_index = int(clamp(selected_index, 0, len(STIMULUS_TYPES) - 1))
    text, warn = intro_stims(win, resolution, warning)
    set_intro_text(win, text, warn, build_intro_text(
        resolution, refresh_hz, selected_index, image_label, out_name,
        preset_name, image_failure))

    event.clearEvents()
    while True:
        text.draw()
        if warn is not None:
            warn.draw()
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
            set_intro_text(win, text, warn, build_intro_text(
                resolution, refresh_hz, selected_index, image_label,
                out_name, preset_name, image_failure))


# =============================================================================
# HUD  (PRD 8, precision per PRD 5.2)
# =============================================================================

def _deg(value):
    return '--' if value is None else '{:.2f}'.format(value)


def set_text(stim, text):
    """Assign TextStim text only if it changed: every assignment re-lays out
    the whole block in pyglet, which costs far more than comparing strings."""
    if stim.text != text:
        stim.text = text


class HudLines(object):
    """The readout as one TextStim per line (PRD 8).

    A line re-lays out only when its own string changes, so the 10 Hz timing
    tick on line 1 costs one short line, not the whole block.

    Each line sits exactly where pyglet put it in the old single multi-line
    TextStim. A centred multi-line label puts its top at y +
    content_height // 2 and line i's baseline (i+1) ascents and i descents
    below that; a one-line label puts its top at y + ascent // 2 -
    descent // 4 instead. The difference is a whole number of pixels per
    line, so every line keeps the block's sub-pixel position.
    """

    def __init__(self, win):
        self.win = win
        self.stims = []
        self.count = 0
        self._metrics = None

    def _line_metrics(self):
        """(ascent, descent) in px of the face TextStim's label uses."""
        if self._metrics is None:
            import pyglet.font
            height_px = HUD_HEIGHT * self.win.size[1]
            face = pyglet.font.load(READOUT_FONT, int(height_px * 0.75))
            self._metrics = (face.ascent, face.descent)
        return self._metrics

    def show(self, lines, block_y):
        """Lay out `lines` as one block centred at height-units y."""
        while len(self.stims) < len(lines):
            self.stims.append(visual.TextStim(
                self.win, text='', font=READOUT_FONT, height=HUD_HEIGHT,
                color='white', wrapWidth=HUD_WRAP_W, alignText='center',
                anchorHoriz='center', autoLog=False))
        ascent, descent = self._line_metrics()
        pitch = ascent - descent
        top = (len(lines) * pitch) // 2 - (ascent // 2 - descent // 4)
        win_h = float(self.win.size[1])
        for i, (stim, text) in enumerate(zip(self.stims, lines)):
            set_text(stim, text)
            pos = (0, block_y + (top - i * pitch) / win_h)
            if tuple(stim.pos) != pos:
                stim.pos = pos
        self.count = len(lines)

    @property
    def text(self):
        return '\n'.join(stim.text for stim in self.stims[:self.count])

    def draw(self):
        for stim in self.stims[:self.count]:
            stim.draw()


def ring_positions(state):
    """Centre of every drawn copy of the stimulus, height units (PRD 6.3).

    Multi off: just (X, Y). On: N copies on a ring of radius |X| about
    (0, Y), copy i at base + offset + i * 360 / N degrees, counter-clockwise,
    base pointing toward the sign of X. Rounded to 12 dp so that N = 2,
    offset 0 lands EXACTLY on (X, Y) and (-X, Y) -- sin(180 deg) is not
    quite 0 in floating point.
    """
    x, y = state['x_pos'], state['y_pos']
    if not state['multi']:
        return [(x, y)]
    n, radius = state['multi_count'], abs(x)
    base = 0.0 if x >= 0 else 180.0
    positions = []
    for i in range(n):
        angle = math.radians(base + state['ring_offset_deg'] + i * 360.0 / n)
        positions.append((round(radius * math.cos(angle), 12),
                          round(y + radius * math.sin(angle), 12)))
    return positions


def ring_overlap(state):
    """True when neighbouring copies are closer than the stimulus size.

    Compares the chord between neighbours, 2 r sin(pi / N), with the size.
    A warning only -- nothing is moved.
    """
    if not state['multi']:
        return False
    chord = 2.0 * abs(state['x_pos']) * math.sin(
        math.pi / state['multi_count'])
    return chord < state['size']


def mode_label(state, refresh_hz):
    """Mode for the readout: 3 and 4 show their target AND realised rate."""
    mode = state['mode']
    if mode in FLICKER_HZ:
        frames = hz_to_frames(FLICKER_HZ[mode], refresh_hz)
        on, off = flicker_split(frames)
        return 'Flicker {} ({:.2f} Hz{})'.format(
            FLICKER_HZ[mode], frames_to_hz(frames, refresh_hz),
            ' ASYM' if on != off else '')
    return mode


def mode_line(state):
    """HUD line 2. Mode, multi ring, and whatever the mode itself owns."""
    mode = state['mode']
    parts = ['Mode: {}'.format(mode_label(state, state['refresh_hz']))]
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
    if state['multi']:
        offscreen = sum(offscreen_copies(state))
        parts.append('MULTI {} r {:.2f} off {:g}{}{}'.format(
            state['multi_count'], abs(state['x_pos']),
            state['ring_offset_deg'],
            ' OVERLAP' if ring_overlap(state) else '',
            ' OFFSCREEN {}'.format(offscreen) if offscreen else ''))
    return ' | '.join(parts)


def stim_line(state, sweep=None):
    """HUD line 5. Adapts to the stimulus type (PRD 8)."""
    if state['mode'] == MODE_GAMMA:
        if sweep is not None:
            return ('Auto gamma: level {}/{} -- settling ({:.1f}s) | '
                    '[A] or [ESC] cancels'.format(
                        state['gamma_step_index'] + 1, len(GAMMA_LEVELS),
                        max(0.0, sweep['remaining'])))
        return ('Gamma steps: LEFT/RIGHT to change level | [A] auto sweep | '
                'fixation hidden')
    if state['mode'] == MODE_UNIFORMITY:
        return ('Spatial uniformity: ARROWS move the patch across the 3x3 '
                'grid | fixation hidden')
    stim_type = state['stimulus_type']
    if stim_type == STIM_RADIAL:
        return 'Rings: {} | Wedges: {}'.format(state['rings'], state['wedges'])
    if stim_type in (STIM_GABOR, STIM_GRATING):
        line = 'SF: {:.2f} c/unit | Ori: {:.1f} deg | Phase: {:.2f}'.format(
            state['sf'], state['ori'], state['phase'])
        if stim_type == STIM_GABOR:
            line += ' | SD: {:.3f} (mask sd {:.2f})'.format(
                state['envelope_sd'],
                gauss_sd_param(state['size'], state['envelope_sd']))
        else:
            line += ' | Wave: {} | Mask: {}'.format(state['waveform'],
                                                   state['mask'])
        return line
    if stim_type == STIM_UNIFORM:
        return ('R: {:.3f} | G: {:.3f} | B: {:.3f} | Alpha: {:.3f} | '
                'Shape: {}').format(state['r'], state['g'], state['b'],
                                    state['alpha'], state['shape'])
    if stim_type == STIM_TEXT:
        text = state['text_string']
        if len(text) > TEXT_HUD_CHARS:
            text = text[:TEXT_HUD_CHARS - 3] + '...'   # HUD only; JSON is full
        return ('Text: {} | Font: {} | Spacing: {:.3f} | Rot: {:g} | '
                'R {:.3f} G {:.3f} B {:.3f} A {:.3f}').format(
                    text, font_label(state), state['letter_spacing'],
                    state['rotation_deg'], state['r'], state['g'],
                    state['b'], state['alpha'])
    if stim_type == STIM_CUSTOM_PNG:
        # Filename only (PRD 8.3); the snapshot records the same basename.
        return 'File: {} | Alpha: {:.3f} | Rot: {:g} deg'.format(
            os.path.basename(state['image_path']), state['alpha'],
            state['rotation_deg'])
    return 'No stimulus-specific parameters'


def flicker_text(frames, refresh_hz):
    """'48.00 Hz (5 fr, 2 on/3 off) ASYM' -- realised rate and split.

    ASYM flags an odd count: it cannot split evenly, so ON is the shorter
    half (stim_is_on's frames // 2).
    """
    on, off = flicker_split(frames)
    return '{:.2f} Hz ({} fr, {} on/{} off){}'.format(
        frames_to_hz(frames, refresh_hz), frames, on, off,
        ' ASYM' if on != off else '')


def build_status_bar(state, out_name=''):
    """PRD 8.2. One dim line, always drawn, never hidden by [H].

    Carries the two toggle states and the custom-flicker setting with its
    keys -- mode 5 is otherwise undiscoverable, since nothing else on screen
    says how to change the rate it flickers at.
    """
    name = out_name or '-'
    if len(name) > STATUS_NAME_CHARS:
        name = '...' + name[-(STATUS_NAME_CHARS - 3):]
    # The selected copy can sit off screen at default settings; say so here
    # too, since this line never hides.
    lost = (state['multi'] and
            offscreen_copies(state)[selected(state)])
    return ('[{}] Text: {} | [{}] Menu: {} | [F/J] Custom: {} | '
            'Mode: {}{} | File: {}').format(
                HUD_TOGGLE_KEY.upper(),
                'ON' if state['hud_visible'] else 'OFF',
                MENU_TOGGLE_KEY.upper(),
                'ON' if state['menu_visible'] else 'OFF',
                flicker_text(state['stim_frames'][selected(state)],
                             state['refresh_hz']),
                mode_label(state, state['refresh_hz']),
                ' | SELECTED #{} OFF SCREEN'.format(selected(state) + 1)
                if lost else '', name)


MENU_STIM_KEYS = {
    STIM_RADIAL: 'Z/X = Rings | R/T = Wedges (+/-2)',
    STIM_GABOR: 'Z/X = SF | R/T = Orientation | E/W = Phase | D/A = Env SD',
    STIM_GRATING: ('Z/X = SF | R/T = Orientation | E/W = Phase | '
                   'D/A = Waveform | B = Mask'),
    STIM_UNIFORM: ('R/T = Red | E/W = Green | D/A = Blue | Z/X = Alpha | '
                   'B = Shape'),
    STIM_CUSTOM_PNG: 'Z/X = Alpha | R/T = Rotation',
    STIM_TEXT: ('B/N = Cycle string | I/O = Font | U/Y = Spacing | '
                'K/L = Rotation\n  R/T = Red | E/W = Green | D/A = Blue | '
                'Z/X = Alpha'),
}


def build_menu_text(state):
    """PRD 8.3. The full reference card, adapted to the active type."""
    lines = [
        'KEYBINDINGS -- {}'.format(
            STIMULUS_LABELS[state['stimulus_type']]),
        '',
        'MOVEMENT:  LEFT/RIGHT = X position | UP/DOWN = Y position',
        'DISPLAY:   PAGEUP/DN = Background | +/- = Size | C/V = Contrast',
        'FREQUENCY: F/J = Custom flicker faster/slower (one frame per step)',
        "DISTANCE:  ;/' = Viewing distance +/-1 cm",
        'MODES:     1=ON  2=OFF  3=15Hz  4=20Hz  5=Custom',
        '           G=Gamma  7=Multi on/off  8=Uniformity',
        'RING:      [ ] = Copies 2-16 | ,/. = Rotate +/-5 deg | '
        '9/0 = Select copy',
        "           / = Selected copy: flicker -> steady -> off",
        '           F/J step the selected copy only',
        'ACTIONS:   S=Snapshot  P=Preset  F12=Screenshot',
        '           H=Toggle HUD  M=This menu  Q=Quit',
        '',
        'THIS STIMULUS:',
        '  {}'.format(MENU_STIM_KEYS[state['stimulus_type']]),
    ]
    if state['mode'] == MODE_GAMMA:
        lines += ['', 'GAMMA MODE: LEFT/RIGHT = level | A = auto sweep']
    elif state['mode'] == MODE_UNIFORMITY:
        lines += ['', 'UNIFORMITY MODE: ARROWS = move patch across the grid']
    lines += ['', '[M] or [ESC] to dismiss']
    return '\n'.join(lines)


def hud_line_chars(state):
    """Characters that fit on one readout line on this screen."""
    width = min(state['aspect'] * 0.96, HUD_WRAP_W)
    return int(width / HUD_CHAR_W)


def wrap_hud_line(line, max_chars):
    """[line], or the line split in two at the last ' | ' that fits."""
    if len(line) <= max_chars:
        return [line]
    cut = line.rfind(' | ', 0, max_chars)
    if cut <= 0:
        # First field alone is too long (a long filename): still move the
        # rest down rather than push it further off screen.
        cut = line.find(' | ')
        if cut < 0:
            return [line]
    return [line[:cut], line[cut + 3:]]


def build_hud(state, resolution, refresh_hz, live_hz, screen_height_cm,
              sd_ms=None, drops=0, sweep=None, out_name=''):
    """The five lines of PRD 8, rebuilt every frame."""
    size_deg = visual_angle_deg(state['size'], screen_height_cm,
                                state['viewing_distance_cm'])
    ecc_deg = eccentricity_deg(state['x_pos'], screen_height_cm,
                               state['viewing_distance_cm'])
    px_x, px_y, px_size = to_pixels(state)
    ecc_label = 'Ecc'
    if state['multi']:
        # The selected copy's own distance from fixation, as in the JSON.
        sel_x, sel_y = ring_positions(state)[selected(state)]
        ecc_deg = eccentricity_deg(math.hypot(sel_x, sel_y),
                                   screen_height_cm,
                                   state['viewing_distance_cm'])
        ecc_label = 'Ecc(#{})'.format(selected(state) + 1)

    # While flickering, report what the active mode realises. Otherwise report
    # what the standing custom setting WOULD realise, marked idle so nobody
    # reads it as a live measurement.
    frames = mode_frames(state, refresh_hz)
    if frames is None:
        freq_text = 'Freq: {} idle'.format(
            flicker_text(state['stim_frames'][selected(state)], refresh_hz))
    else:
        freq_text = 'Freq: {}'.format(flicker_text(frames, refresh_hz))

    return '\n'.join([
        # Rolling rate, not the startup measurement: a panel that is dropping
        # frames should say so while it is happening.
        # The sigma is rendered by TextStim, never printed: the Windows console
        # is cp1252 and would raise UnicodeEncodeError on it.
        u'{}x{} | {:.2f} Hz ({}) | Drops: {} | PsychoPy {} | Dist: {} cm'.format(
            resolution[0], resolution[1], live_hz,
            u'σ=--' if sd_ms is None
            else u'σ={:.2f}ms'.format(sd_ms),
            drops, PSYCHOPY_VERSION, state['viewing_distance_cm']),
        mode_line(state) + ('' if not out_name
                            else ' | Out: {}'.format(out_name)),
        # Degrees need the monitor's physical size and go '--' without it;
        # pixels only need the window, so they are always available.
        'X: {:.2f} ({}px) | Y: {:.2f} ({}px) | Size: {:.2f} ({}px, {} deg) '
        '| {}: {} deg'.format(
            state['x_pos'], px_x, state['y_pos'], px_y, state['size'],
            px_size, _deg(size_deg), ecc_label, _deg(ecc_deg)),
        'BG: {:.3f} | Contrast: {:.3f} | {}'.format(
            state['bg_gray'], state['contrast'], freq_text),
    ] + wrap_hud_line(stim_line(state, sweep), hud_line_chars(state))
      + ring_lines(state, refresh_hz))


def ring_lines(state, refresh_hz):
    """Every copy's realised rate, selected one starred, as many lines as
    the screen width needs. Empty with multi off (line 4 says it all)."""
    if not state['multi'] or state['mode'] in (MODE_GAMMA, MODE_UNIFORMITY):
        return []
    frames = copy_frames(state, refresh_hz)
    if frames is None:
        frames = state['stim_frames'][:state['multi_count']]
    entries = []
    offscreen = offscreen_copies(state)
    for i, (n, copy_state) in enumerate(zip(frames, copy_states(state))):
        on, off = flicker_split(n)
        name = '{}{}{}'.format(i + 1, '*' if i == selected(state) else '',
                               '!' if offscreen[i] else '')
        if copy_state == 'steady':
            entries.append(name + ':STEADY')
        elif copy_state == 'off':
            entries.append(name + ':--')
        else:
            entries.append('{}:{:.2f}{}'.format(
                name, frames_to_hz(n, refresh_hz),
                ' ASYM' if on != off else ''))
    lines, line = [], 'Ring Hz:'
    budget = hud_line_chars(state)
    for entry in entries:
        if len(line) + 2 + len(entry) > budget:
            lines.append(line)
            line = '        '
        line += '  ' + entry
    return lines + [line]


# =============================================================================
# OUTPUT  (PRD 3.2)
# =============================================================================

def stimulus_specific(state):
    """Per-type parameters, including the RadialStim kwargs radial derives."""
    stim_type = state['stimulus_type']
    if stim_type == STIM_RADIAL:
        radial_cycles, angular_cycles = radial_cycles_for(state)
        record = {
            'rings': state['rings'],
            'wedges': state['wedges'],
            'radialCycles': radial_cycles,
            'angularCycles': angular_cycles,
            'radialPhase': RADIAL_PHASE,
        }
    elif stim_type == STIM_GABOR:
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
            'waveform': state['waveform'],
            'mask': state['mask'],
        }
    elif stim_type == STIM_TEXT:
        record = {
            'text_string': state['text_string'],
            'text_preset_index': state['text_index'],
            'letter_spacing': round(state['letter_spacing'], STORE_DP),
            'rotation_deg': round(state['rotation_deg'], STORE_DP),
            'font_family': state['font_family'],
            'font_requested': state['font_requested'],
            'font_rendered': state['font_rendered'],
            'font_fallback': (state['font_rendered'] is not None and
                              state['font_rendered'] !=
                              state['font_requested']),
            'alpha': round(state['alpha'], STORE_DP),
            'r': round(state['r'], STORE_DP),
            'g': round(state['g'], STORE_DP),
            'b': round(state['b'], STORE_DP),
        }
    elif stim_type == STIM_UNIFORM:
        record = {
            'r': round(state['r'], STORE_DP),
            'g': round(state['g'], STORE_DP),
            'b': round(state['b'], STORE_DP),
            'alpha': round(state['alpha'], STORE_DP),
            'shape': state['shape'],
        }
    elif stim_type == STIM_CUSTOM_PNG:
        record = {
            'filepath': state['image_path'],
            'alpha': round(state['alpha'], STORE_DP),
            'rotation_deg': round(state['rotation_deg'], STORE_DP),
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
            record['patch_shape'] = state['shape']

    return record


def stimuli_record(state, screen_height_cm, refresh_hz):
    """Every drawn copy: position, eccentricity from fixation, flicker.

    The cycle is the active flicker mode's, or each copy's mode 5 setting
    when nothing is flickering (flicker_active says which).
    """
    positions = ring_positions(state)
    frames = copy_frames(state, refresh_hz)
    if frames is None:
        frames = ([state['stim_frames'][0]] if not state['multi'] else
                  state['stim_frames'][:len(positions)])
    record = []
    states, offscreen = copy_states(state), offscreen_copies(state)
    for index, ((x, y), n) in enumerate(zip(positions, frames)):
        ecc = eccentricity_deg(math.hypot(x, y), screen_height_cm,
                               state['viewing_distance_cm'])
        on, off = flicker_split(n)
        record.append({'index': index, 'x': round(x, STORE_DP),
                       'y': round(y, STORE_DP),
                       'ecc_deg': None if ecc is None else round(ecc, 2),
                       'flicker_frames': n, 'on_frames': on,
                       'off_frames': off,
                       'realized_hz': round(frames_to_hz(n, refresh_hz), 3),
                       'flicker_state': states[index],
                       'offscreen': offscreen[index]})
    return record


def state_record(state, screen_height_cm, refresh_hz=None,
                 rolling_hz=None, drops=None, snapshot_number=None):
    angle = visual_angle_deg(state['size'], screen_height_cm,
                             state['viewing_distance_cm'])
    ecc = eccentricity_deg(state['x_pos'], screen_height_cm,
                           state['viewing_distance_cm'])
    refresh = state['refresh_hz'] if refresh_hz is None else refresh_hz
    frames = mode_frames(state, refresh)
    active = frames is not None
    if not active:
        frames = state['stim_frames'][selected(state)]
    on, off = flicker_split(frames)
    record = {
        'snapshot_number': snapshot_number,
        'timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
        'rolling_refresh_hz': (None if rolling_hz is None
                               else round(rolling_hz, 3)),
        'dropped_frames_total': drops,
        'stimulus_type': state['stimulus_type'],
        'mode': state['mode'],
        # Back-compat: the old dual flag is exactly the two-copy ring.
        'dual_stimulus': bool(state['multi'] and state['multi_count'] == 2),
        'multi_active': bool(state['multi']),
        'multi_count': state['multi_count'],
        'ring_offset_deg': round(state['ring_offset_deg'], STORE_DP),
        'ring_radius': round(abs(state['x_pos']), STORE_DP),
        'ring_center_y': round(state['y_pos'], STORE_DP),
        'selected_index': selected(state),
        'stimuli': stimuli_record(state, screen_height_cm, refresh),
        'x_position': round(state['x_pos'], STORE_DP),
        'y_position': round(state['y_pos'], STORE_DP),
        'background_gray': round(state['bg_gray'], STORE_DP),
        'disc_size': round(state['size'], STORE_DP),
        'contrast': round(state['contrast'], STORE_DP),
        # Back-compat: the REALISED rate of the selected copy's mode 5 frame
        # count, no longer a requested integer (PRD 3.2).
        'custom_frequency_hz': round(
            frames_to_hz(state['stim_frames'][selected(state)], refresh), 3),
        'visual_angle_deg': None if angle is None else round(angle, 2),
        'eccentricity_deg': None if ecc is None else round(ecc, 2),
        'stimulus_specific': stimulus_specific(state),
    }
    # The SELECTED copy's cycle in the active flicker mode, or its mode 5
    # setting when no flicker mode is on (flicker_active says which). The
    # rate is what the frame count delivers at refresh_hz_used.
    record.update({
        'flicker_active': active,
        'flicker_frames': frames,
        'flicker_on_frames': on,
        'flicker_off_frames': off,
        'flicker_realized_hz': round(frames_to_hz(frames, refresh), 3),
        'refresh_hz_used': round(refresh, 3),
    })
    return record


def session_header(win, mon, resolution, screen_height_cm, startup_hz,
                   image_arg, started=None, out_path=None, preset_arg=None,
                   text_arg=None, image_failed=False):
    """Everything about the rig that does not change during the session.

    Captured once, at startup, so a reader months later can tell what the
    numbers below were measured on -- which units and colour space they are
    in, how big the screen physically was, and whether the radial plugin was
    even available. Paths are recorded without directories (output_path_label)
    so a shared file carries no user or machine names.
    """
    try:
        width_cm = mon.getWidth()
    except Exception:                                        # noqa: BLE001
        width_cm = None
    vsync_on, vsync_info = vsync_state(win)
    return {
        'session_start': (started or datetime.datetime.now()).isoformat(
            timespec='seconds'),
        'session_end': None,
        'monical_version': MONICAL_VERSION,
        'monitor_name': MONITOR_NAME,
        'monitor_resolution': list(resolution),
        'monitor_width_cm': None if not width_cm else round(float(width_cm), 2),
        'monitor_height_cm': (None if screen_height_cm is None
                              else round(screen_height_cm, 2)),
        'monitor_dimension_warning': monitor_dimension_suspect(
            screen_height_cm),
        'color_space': 'rgb',
        'units': UNITS,
        'window_fullscreen': bool(getattr(win, 'fullscr', False)),
        'vsync': vsync_on,
        # Recorded because the rolling figure below is a LOOP rate, and only
        # equals the display's refresh rate while vsync is holding flip() to
        # the retrace. With vsync off the loop free-runs and the number means
        # something else entirely.
        'vsync_detail': vsync_info,
        'startup_refresh_hz': round(float(startup_hz), 3),
        'final_rolling_refresh_hz': None,
        'final_rolling_refresh_sd_ms': None,
        'total_dropped_frames': 0,
        'psychopy_version': str(PSYCHOPY_VERSION),
        'python_version': sys.version,
        'platform': sys.platform,
        'has_radial_stim': bool(HAS_RADIAL),
        'image_path': None if not image_arg else os.path.basename(image_arg),
        # True when --image was given but missing or undecodable, so the
        # session ran on the generated test pattern instead.
        'image_load_failed': bool(image_failed),
        'text_arg': text_arg,
        'preset_path': output_path_label(preset_arg),
        # The file these values are being written to, recorded inside the file
        # so a renamed copy still says where it came from.
        'output_file': None if out_path is None else os.path.basename(out_path),
    }


def timestamp_slug(when=None):
    """YYYY-MM-DD_HHMMSS, the stem every generated filename is built from."""
    return (when or datetime.datetime.now()).strftime(OUT_STAMP_FMT)


def session_out_path(slug):
    """monical_<slug>.json beside the script. Fixed once, at startup.

    Uniquified so two sessions launched inside the same second cannot write
    to one file.
    """
    return unique_path(os.path.join(OUT_DIR, OUT_NAME_FMT.format(slug)))


def start_crash_log(slug):
    """Point faulthandler at monical_crash_<slug>.log beside the script.

    A native crash (an access violation in the GL driver, say) kills the
    process without a Python traceback; faulthandler writes every thread's
    stack here first. On any clean exit -- core.quit() is sys.exit() -- the
    file is closed and, if nothing was written, deleted.
    """
    path = os.path.join(OUT_DIR, CRASH_NAME_FMT.format(slug))
    try:
        handle = open(path, 'w')
        faulthandler.enable(file=handle, all_threads=True)
    except Exception as err:                                 # noqa: BLE001
        print("Crash log unavailable ({}).".format(err))
        return None
    atexit.register(stop_crash_log, handle)
    return handle


def stop_crash_log(handle):
    """Clean exit: close the crash log, and delete it if it is empty."""
    faulthandler.disable()
    handle.close()
    try:
        if os.path.getsize(handle.name) == 0:
            os.remove(handle.name)
    except OSError:
        pass


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def unique_path(path):
    """`path`, or path_2 / path_3 ... if it is already taken.

    Filenames carry a whole-second timestamp, so two screenshots or two
    presets saved inside the same second would otherwise land on the same
    name and the second would silently destroy the first.
    """
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    for n in range(2, 1000):
        candidate = '{}_{}{}'.format(stem, n, ext)
        if not os.path.exists(candidate):
            return candidate
    return path


def write_json(state, session, path, final=None):
    """Rewritten in full on every [S] and on [Q], always to the same path.

    One file per session, named from session_start, so a later run cannot
    overwrite an earlier run's measurements.
    """
    payload = {
        'note': ('REFERENCE ONLY. Not loaded by any experiment. '
                 'Values are read by humans and entered manually.'),
    }
    payload.update(session)
    payload['viewing_distance_cm'] = float(state['viewing_distance_cm'])
    payload['stimulus_type'] = state['stimulus_type']
    payload['snapshots'] = state['snapshots']
    if final is not None:
        payload['final'] = final
    with open(path, 'w') as handle:
        json.dump(payload, handle, indent=2)
    return path


def save_screenshot(win, slug=None):
    """PNG of the frame currently on screen (PRD 11).

    getMovieFrame() grabs the FRONT buffer, which is the frame the operator is
    looking at -- the loop flips at the end of each pass, so by the time keys
    are polled the front buffer holds the completed frame.
    """
    ensure_dir(SCREENSHOT_DIR)
    path = unique_path(os.path.join(
        SCREENSHOT_DIR, SCREENSHOT_NAME_FMT.format(slug or timestamp_slug())))
    win.getMovieFrame()
    win.saveMovieFrames(path)
    return path


# =============================================================================
# AUTO GAMMA SWEEP  (PRD 6.5)
# =============================================================================

def start_sweep(state, clock):
    """Begin at level 0, remembering where to put the operator back."""
    sweep = {'return_index': state['gamma_step_index'],
             'level_started': clock.getTime(),
             'remaining': SETTLE_S}
    state['gamma_step_index'] = 0
    return sweep


def cancel_sweep(state, sweep):
    """Abandon the sweep and restore the level the operator was on."""
    state['gamma_step_index'] = sweep['return_index']
    return None


def sweep_due(sweep, clock):
    """True once the current level has settled long enough to be read.

    Also refreshes the countdown the HUD shows.
    """
    elapsed = clock.getTime() - sweep['level_started']
    sweep['remaining'] = SETTLE_S - elapsed
    return elapsed >= SETTLE_S


def sweep_step(state, sweep, clock):
    """Advance to the next level, or end the sweep after the last one.

    Called only AFTER the settled level has been snapshotted -- the reading
    belongs to the level that just settled, so the index must not move until
    it has been recorded. Returns the sweep, or None when complete.
    """
    if state['gamma_step_index'] >= len(GAMMA_LEVELS) - 1:
        return cancel_sweep(state, sweep)
    state['gamma_step_index'] += 1
    sweep['level_started'] = clock.getTime()
    sweep['remaining'] = SETTLE_S
    return sweep


# =============================================================================
# PRESETS  (PRD 10)
# =============================================================================

def preset_from_state(state):
    """Everything a preset carries: the stimulus, not the rig or the run.

    Only the active copies' frames: values remembered past the count are
    session memory, not part of the configuration.
    """
    preset = {key: value for key, value in state.items()
              if key not in PRESET_EXCLUDE}
    preset['stim_frames'] = list(state['stim_frames'][:state['multi_count']])
    preset['stim_states'] = list(state['stim_states'][:state['multi_count']])
    return preset


def save_preset(state, slug=None):
    """Write the current knobs to presets/preset_<stamp>.json."""
    ensure_dir(PRESET_DIR)
    path = unique_path(os.path.join(
        PRESET_DIR, PRESET_NAME_FMT.format(slug or timestamp_slug())))
    with open(path, 'w') as handle:
        json.dump(preset_from_state(state), handle, indent=2, sort_keys=True)
    return path


def load_preset(path):
    """Read a preset file. Returns {} and warns rather than dying.

    A preset is a convenience, not data: a broken one should cost you the
    preset, not the calibration session you were about to run.
    """
    try:
        with open(path) as handle:
            loaded = json.load(handle)
    except Exception as err:                                 # noqa: BLE001
        print("ERROR: could not read preset {}: {}".format(path, err))
        return {}
    if not isinstance(loaded, dict):
        print("ERROR: preset {} is not a JSON object.".format(path))
        return {}
    return loaded


def param_ranges(refresh_hz=60.0):
    """field -> (low, high, kind) for every knob-driven parameter.

    Built from the knob tables, so a range is still defined in one place, plus
    the two mode-local indices that a preset also carries. 'choice' fields
    have no range; their valid values are CHOICES.
    """
    ranges = {}
    for table in [knob_table(None, refresh_hz)] + list(STIM_KNOBS.values()):
        for field, _delta, low, high, kind in table.values():
            ranges[field] = (low, high, kind)
    ranges['gamma_step_index'] = (0, len(GAMMA_LEVELS) - 1, 'int')
    ranges['uniformity_grid_index'] = (0, len(UNIFORMITY_GRID) - 1, 'int')
    return ranges


EVEN_FIELDS = ('wedges',)         # an odd count would leave a half-cycle seam


def sanitize_param(field, value, default, ranges):
    """`value` forced into the field's range. Returns (value, reason or '')."""
    low, high, kind = ranges[field]
    if kind == 'choice':
        if value in CHOICES[field]:
            return value, ''
        return default, 'not one of {}, default used'.format(CHOICES[field])
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        return default, 'not a number, default used'
    if kind == 'wrap':
        fixed, reason = round(value % high, STORE_DP), 'wrapped into 0-{}'
        reason = reason.format(high)
    elif field in EVEN_FIELDS:
        # Half up, so every odd count moves the same way: 7 -> 8, not 6.
        fixed = int(clamp(2 * math.floor(value / 2.0 + 0.5), low, high))
        reason = 'rounded to even, range {}-{}'.format(low, high)
    elif kind == 'int':
        fixed = int(clamp(math.floor(value + 0.5), low, high))
        reason = 'whole number, range {}-{}'.format(low, high)
    else:
        fixed = clamp(value, low, high)
        reason = 'range {}-{}'.format(low, high)
    return fixed, ('' if fixed == value else reason)


REFRESH_TOLERANCE = 0.01          # presets re-derive frames beyond 1% drift


def is_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def preset_stim_frames(loaded, refresh_hz, count):
    """Per-copy mode 5 frames a preset asks for at THIS refresh, or None.

    Current presets carry stim_frames, a list; earlier ones a single
    flicker_frames, or only custom_freq_hz. Each value goes through the same
    refresh conversion. A list whose length does not match the count is
    padded with its last value or truncated, with a console note.
    """
    if isinstance(loaded.get('stim_frames'), list) and loaded['stim_frames']:
        values = [preset_flicker_frames(dict(loaded, flicker_frames=v),
                                        refresh_hz)
                  for v in loaded['stim_frames']]
    else:
        single = preset_flicker_frames(loaded, refresh_hz)
        if single is None:
            return None
        values = [single]
    if 'stim_frames' in loaded and len(values) != count:
        print("Preset: {} per-copy frame value(s) for {} copies -- {}".format(
            len(values), count, 'padded with the last' if len(values) < count
            else 'extra dropped'))
    while len(values) < count:
        values.append(values[-1])
    return values[:count]


def preset_stim_states(loaded, count):
    """Per-copy flicker/steady/off from a preset, or None if it has none.

    Unknown values become 'flicker'; a list that does not match the count is
    padded with its last value or truncated, each with a console note.
    """
    values = loaded.get('stim_states')
    if not isinstance(values, list) or not values:
        return None
    states = []
    for value in values:
        if value not in COPY_STATES:
            print("Preset: copy state {!r} -> 'flicker' (not one of {})"
                  .format(value, COPY_STATES))
            value = 'flicker'
        states.append(value)
    if len(states) != count:
        print("Preset: {} copy state(s) for {} copies -- {}".format(
            len(states), count, 'padded with the last' if len(states) < count
            else 'extra dropped'))
    while len(states) < count:
        states.append(states[-1])
    return states[:count]


def preset_flicker_frames(loaded, refresh_hz):
    """One mode 5 frame count a preset asks for at THIS refresh, or None.

    Frame counts come with the refresh they were saved at. On a panel more
    than 1% faster or slower the rate, not the count, is what was dialled
    in, so it is re-derived. Old presets carry only custom_freq_hz.
    """
    frames = loaded.get('flicker_frames')
    saved_refresh = loaded.get('refresh_hz')
    old_hz = loaded.get('custom_freq_hz')
    if is_number(frames) and frames > 0:
        if (is_number(saved_refresh) and saved_refresh > 0 and
                abs(saved_refresh - refresh_hz) / refresh_hz >
                REFRESH_TOLERANCE):
            new = hz_to_frames(saved_refresh / frames, refresh_hz)
            print("Preset: saved at {:.2f} Hz refresh, now {:.2f} Hz -- "
                  "custom flicker {} fr ({:.2f} Hz) -> {} fr ({:.2f} Hz)".format(
                      saved_refresh, refresh_hz, frames,
                      frames_to_hz(frames, saved_refresh), new,
                      frames_to_hz(new, refresh_hz)))
            return new
        return frames
    if frames is None and is_number(old_hz) and old_hz > 0:
        new = hz_to_frames(old_hz, refresh_hz)
        print("Preset: custom_freq_hz {} (old format) -> {} fr ({:.2f} Hz "
              "realised at {:.2f} Hz refresh)".format(
                  old_hz, new, frames_to_hz(new, refresh_hz), refresh_hz))
        return new
    return frames                 # absent, or junk for sanitize_param


def sanitize_report(field, value, default, ranges):
    """sanitize_param, printing one console line if it changed anything."""
    fixed, reason = sanitize_param(field, value, default, ranges)
    if reason:
        print("Preset: {} {!r} -> {!r} ({})".format(field, value, fixed,
                                                     reason))
    return fixed


def apply_preset(state, loaded, text_presets=None):
    """Overlay a preset onto a default state. Returns the keys applied.

    Forward and backward compatible on purpose: keys the preset omits keep
    their defaults, and keys it carries that this version no longer has are
    ignored. Neither case is an error -- presets outlive tool versions.

    Numeric values are forced into range, one console line per correction. A
    preset is a hand-editable file, and an out-of-range value would otherwise
    reach the stimulus constructor unchecked.
    """
    loaded = dict(loaded)
    if 'dual' in loaded:
        # Pre-ring presets: dual on is the two-copy ring at offset 0.
        if loaded.pop('dual') is True and 'multi' not in loaded:
            loaded.update(multi=True, multi_count=2, ring_offset_deg=0.0)
            print("Preset: dual -> multi-stimulus ring, 2 copies, offset 0")
    frames_source = dict(loaded)
    # refresh_hz describes the rig a preset was saved on, never this one.
    for key in ('stim_frames', 'stim_states', 'flicker_frames', 'refresh_hz',
                'custom_freq_hz', 'selected_index'):
        loaded.pop(key, None)
    ranges = param_ranges(state['refresh_hz'])
    applied, ignored = [], []
    for key, value in loaded.items():
        if key in PRESET_EXCLUDE or key not in state:
            ignored.append(key)
            continue
        if key in ranges:
            value = sanitize_report(key, value, state[key], ranges)
        state[key] = value
        applied.append(key)
    # Per-copy frames need the count, which the loop above may have set.
    frames = preset_stim_frames(frames_source, state['refresh_hz'],
                                state['multi_count'])
    if frames is not None:
        state['stim_frames'] = [
            sanitize_report('flicker_frames', value,
                            state['stim_frames'][0], ranges)
            for value in frames]
    states = preset_stim_states(frames_source, state['multi_count'])
    if states is not None:
        state['stim_states'] = states
    sync_stim_frames(state)
    index = frames_source.get('selected_index', 0)
    state['selected_index'] = (int(clamp(int(index), 0,
                                         state['multi_count'] - 1))
                               if is_number(index) else 0)
    if state['mode'] not in MODE_KEYS.values():
        print("Preset: mode {!r} -> {!r} (unknown mode)".format(
            state['mode'], MODE_STATIC_ON))
        state['mode'] = MODE_STATIC_ON
    if text_presets:
        # The cycle list comes from this session's --text, so the saved
        # STRING is matched first -- its index can mean another string here.
        # Only when it is missing does the index (wrapped) decide.
        saved = loaded.get('text_string')
        index = state['text_index']
        if not is_number(index):
            index = 0
        index = int(index)
        if saved in text_presets:
            if not (0 <= index < len(text_presets)
                    and text_presets[index] == saved):
                index = text_presets.index(saved)
        else:
            wrapped = index % len(text_presets)
            if wrapped != index:
                print("Preset: text_index {} -> {} (wrapped, {} strings in "
                      "this session's cycle)".format(
                          index, wrapped, len(text_presets)))
            index = wrapped
            if saved is not None:
                print("Preset: text {!r} is not in this session's cycle; "
                      "loaded {!r} instead".format(saved,
                                                   text_presets[index]))
        state['text_index'] = index
        state['text_string'] = text_presets[index]
    if ignored:
        print("Preset: ignored {} unknown key(s): {}".format(
            len(ignored), ', '.join(sorted(ignored)[:8])))
    return applied


# =============================================================================
# SCENE, FRAME, TIMING  (shared by the session loop and --bench)
# =============================================================================

def measure_refresh(win):
    """Refresh in Hz from getMsPerFrame's median, or 60.0 with a warning.

    getMsPerFrame returns (mean, std, median) in ms. Median is the robust one
    -- a single scheduler stall inflates the mean by most of a frame.
    """
    try:
        _mean_ms, _std_ms, median_ms = win.getMsPerFrame(nFrames=120)
        if median_ms and median_ms > 0:
            return 1000.0 / float(median_ms)
    except Exception as err:                                 # noqa: BLE001
        print("Refresh measurement failed ({}).".format(err))
    print("WARNING: could not measure refresh rate; assuming 60.00 Hz. "
          "Frame-count frequencies will NOT be the stated values.")
    return 60.0


def build_scene(win, state, image, verbose=True):
    """Every visual object one session draws, built once (PRD 4, 6, 8)."""
    scene = types.SimpleNamespace(stim=None, fonts=None, uniform_patches=None)
    stimulus_type = state['stimulus_type']
    if stimulus_type == STIM_RADIAL:
        if HAS_RADIAL:
            scene.stim = make_radial(win, state)
        elif verbose:
            print("RadialStim unavailable -- background and fixation only.")
    elif stimulus_type in (STIM_GABOR, STIM_GRATING):
        is_gabor = stimulus_type == STIM_GABOR
        scene.stim = visual.GratingStim(
            win=win, tex='sin' if is_gabor else state['waveform'],
            mask='gauss' if is_gabor else grating_mask(state),
            size=state['size'], sf=state['sf'], ori=state['ori'],
            phase=state['phase'], contrast=state['contrast'],
            pos=(state['x_pos'], state['y_pos']),
            maskParams=({'sd': gauss_sd_param(state['size'],
                                              state['envelope_sd'])}
                        if is_gabor else None),
            autoLog=False)
    elif stimulus_type == STIM_TEXT:
        # PRD 4.6. height is the universal size knob, so the letter height is
        # the thing the degree readout describes. Fonts are resolved once:
        # what each family will actually render on this machine.
        scene.fonts = {family: resolve_font(family)
                       for family in CHOICES['font_family']}
        for family, (requested, rendered) in scene.fonts.items():
            if verbose:
                print("Font {}: {}{}".format(
                    family, rendered, '' if rendered == requested else
                    ' (FALLBACK -- {} not installed)'.format(requested)))
        scene.stim = GlyphString(win)
    elif stimulus_type == STIM_UNIFORM:
        # Both shapes exist from the start; [B] only changes which is drawn.
        scene.uniform_patches = {shape: make_patch(win, state, shape)
                                 for shape in CHOICES['shape']}
        scene.stim = scene.uniform_patches[state['shape']]
    elif stimulus_type == STIM_CUSTOM_PNG:
        scene.stim = visual.ImageStim(
            win=win, image=image, size=state['size'],
            ori=state['rotation_deg'],
            contrast=state['contrast'], opacity=state['alpha'],
            pos=(state['x_pos'], state['y_pos']), autoLog=False)

    scene.fixation = visual.ShapeStim(
        win=win, name='fixation_cross', vertices='cross',
        size=FIXATION_SIZE, ori=0.0, pos=(0.0, 0.0), anchor='center',
        lineWidth=1.0, colorSpace='rgb', lineColor='white',
        fillColor='white', depth=0.0, interpolate=True, autoLog=False)

    # Full-screen patch for gamma stepping (PRD 6.2). Width is the aspect
    # ratio because in height units the screen is 1.0 tall and aspect wide.
    scene.gamma_patch = visual.Rect(
        win=win, width=state['aspect'], height=1.0, pos=(0, 0),
        lineWidth=0, lineColor=None,
        fillColor=[GAMMA_LEVELS[state['gamma_step_index']]] * 3,
        colorSpace='rgb', autoLog=False)

    # PRD 6.4 renders the uniform patch regardless of the selected type, so
    # these exist even when the session is running a Gabor. It takes the
    # current shape; gamma steps above stays a full-screen rect regardless.
    scene.uniformity_patches = {shape: make_patch(win, state, shape)
                                for shape in CHOICES['shape']}

    scene.marker = visual.ShapeStim(
        win=win, vertices=[(0, 0), (0, MARKER_LEN)], closeShape=False,
        lineWidth=2, lineColor=MARKER_COLOR, colorSpace='rgb',
        fillColor=None, interpolate=False, autoLog=False)

    scene.hud = HudLines(win)

    # PRD 8.2: always drawn, dimmer and smaller than the HUD so the two do
    # not read as one block.
    scene.status = visual.TextStim(
        win, text='', font=READOUT_FONT, height=STATUS_HEIGHT,
        color=STATUS_COLOR, pos=STATUS_POS, wrapWidth=1.9,
        alignText='center', anchorHoriz='center', autoLog=False)

    # PRD 8.3: semi-transparent panel so the stimulus stays visible behind.
    scene.menu_box = visual.Rect(
        win=win, width=state['aspect'] * MENU_BOX_W_FRAC,
        height=MENU_BOX_H_FRAC, pos=(0, 0), lineWidth=0, lineColor=None,
        fillColor=[-0.85, -0.85, -0.85], colorSpace='rgb',
        opacity=MENU_BOX_OPACITY, autoLog=False)
    # Anchored to the panel's left inner edge, not to screen centre: with
    # anchorHoriz='center' PsychoPy centres a box of width wrapWidth on pos,
    # so a wrapWidth wider than the screen pushes the first column off the
    # left edge entirely.
    menu_w = state['aspect'] * MENU_BOX_W_FRAC
    scene.menu_text = visual.TextStim(
        win, text='', font=READOUT_FONT, height=MENU_HEIGHT, color='white',
        pos=(-menu_w / 2.0 + MENU_PAD, 0), wrapWidth=menu_w - 2 * MENU_PAD,
        alignText='left', anchorHoriz='left', autoLog=False)

    scene.flash = visual.TextStim(
        win, text='', font=READOUT_FONT, height=0.030, color='yellow',
        pos=(0, 0.42), alignText='center', anchorHoriz='center',
        autoLog=False)

    # Rebuilding the Gaussian mask uploads a 256x256 texture, so it happens
    # only when the SD or the size it is relative to actually changes.
    scene.mask_sd = None
    # Same for the grating's waveform and mask: what the stim was built with.
    scene.grating_built = {'tex': state['waveform'], 'mask': state['mask']}
    # What the readout last showed of the timing figures, and when.
    scene.hud_clock = core.Clock()
    scene.hud_timing = {'at': -1.0, 'hz': None, 'sd': None, 'drops': 0}
    return scene


def apply_live_params(win, scene, state):
    """Push the current knobs into the stimulus objects (every frame)."""
    win.color = [state['bg_gray']] * 3
    stimulus_type = state['stimulus_type']
    if stimulus_type == STIM_UNIFORM:
        scene.stim = scene.uniform_patches[state['shape']]
    stim = scene.stim
    if stim is None:
        return
    stim.pos = (state['x_pos'], state['y_pos'])
    stim.contrast = state['contrast']
    if stimulus_type == STIM_UNIFORM:
        size_patch(stim, state['size'])
        stim.fillColor = [state['r'], state['g'], state['b']]
        stim.opacity = state['alpha']
    elif stimulus_type == STIM_TEXT:
        family = state['font_family']
        state['font_requested'], state['font_rendered'] = scene.fonts[family]
        stim.update(state)
        state['text_extent'] = stim.extent()
    else:
        stim.size = state['size']
    if stimulus_type in (STIM_GABOR, STIM_GRATING):
        stim.sf = state['sf']
        stim.ori = state['ori']
        stim.phase = state['phase']
    if stimulus_type == STIM_GABOR:
        sd = round(gauss_sd_param(state['size'], state['envelope_sd']), 6)
        if sd != scene.mask_sd:
            # Assigning maskParams re-runs the mask setter, which rebuilds
            # the texture -- so only do it when sd moves.
            stim.maskParams = {'sd': sd}
            scene.mask_sd = sd
    if stimulus_type == STIM_GRATING:
        # tex and mask setters rebuild textures, so only on change.
        built = scene.grating_built
        if state['waveform'] != built['tex']:
            stim.tex = built['tex'] = state['waveform']
        if state['mask'] != built['mask']:
            stim.mask = grating_mask(state)
            built['mask'] = state['mask']
    if stimulus_type == STIM_CUSTOM_PNG:
        stim.opacity = state['alpha']
        stim.ori = state['rotation_deg']
    if stimulus_type == STIM_RADIAL:
        # The setters rebuild the texture coords, so only on change.
        radial_cycles, angular_cycles = radial_cycles_for(state)
        if stim.radialCycles != radial_cycles:
            stim.radialCycles = radial_cycles
        if stim.angularCycles != angular_cycles:
            stim.angularCycles = angular_cycles


def render_frame(win, scene, state, refresh_hz, resolution, screen_height_cm,
                 timer, sweep=None, out_name='', flash_text=None):
    """Everything drawn in one frame, up to (not including) the flip."""
    apply_live_params(win, scene, state)
    mode = state['mode']
    stim = scene.stim

    if mode == MODE_GAMMA:
        scene.gamma_patch.width = state['aspect']
        scene.gamma_patch.fillColor = [
            GAMMA_LEVELS[state['gamma_step_index']]] * 3
        scene.gamma_patch.draw()
    elif mode == MODE_UNIFORMITY:
        name = UNIFORMITY_GRID[state['uniformity_grid_index']]
        patch = scene.uniformity_patches[state['shape']]
        size_patch(patch, state['size'])
        patch.pos = uniformity_xy(name, state['aspect'], state['size'])
        patch.fillColor = [state['r'], state['g'], state['b']]
        patch.opacity = state['alpha']
        patch.contrast = state['contrast']
        patch.draw()
    elif mode == MODE_STATIC_OFF:
        pass                      # background + fixation only (PRD 6)
    elif stim is not None:
        # static_on, or each copy's ON half of its own flicker cycle
        # (PRD 6.1, 6.3).
        for pos in drawn_positions(state, refresh_hz):
            stim.pos = pos
            stim.draw()
        stim.pos = (state['x_pos'], state['y_pos'])

    # Fixation cross in every mode EXCEPT the two measured ones. In gamma
    # steps (PRD 6.2) the photometer sits at screen centre; in spatial
    # uniformity it sits on the patch, which passes through centre at the
    # middle cell. Either way a cross under the aperture would corrupt the
    # reading, and the gamma curve is what everything else depends on.
    if mode not in FIXATION_HIDDEN_MODES:
        scene.fixation.draw()

    # The selection tick goes with the readout: [H] hides both, so a
    # photometer or screenshot frame never carries it (PRD 6.3).
    if (state['hud_visible'] and state['multi'] and
            mode not in (MODE_GAMMA, MODE_UNIFORMITY)):
        segment = marker_segment(state, footprint_radius(state))
        if segment is not None:
            scene.marker.vertices = list(segment)
            scene.marker.draw()

    if state['hud_visible']:
        # Timing figures refresh on the clock (HUD_TIMING_INTERVAL_S) and
        # live on line 1 only. Every line's string is rebuilt each frame, but
        # a line re-lays out only when it differs, so a knob change shows on
        # the next frame and a timing tick costs one line.
        shown = scene.hud_timing
        now = scene.hud_clock.getTime()
        if now - shown['at'] >= HUD_TIMING_INTERVAL_S:
            shown.update(at=now, hz=timer.rolling_hz, sd=timer.rolling_sd_ms,
                         drops=timer.dropped)
        lines = build_hud(
            state, resolution, refresh_hz, shown['hz'], screen_height_cm,
            sd_ms=shown['sd'], drops=shown['drops'], sweep=sweep,
            out_name=out_name).split('\n')
        extra = len(lines) - 5
        scene.hud.show(lines, HUD_POS_Y + max(0, extra) * HUD_LINE_PITCH / 2.0)
        scene.hud.draw()

    # Always drawn, whatever [H] says (PRD 8.2).
    set_text(scene.status, build_status_bar(state, out_name))
    scene.status.draw()

    if state['menu_visible']:
        scene.menu_box.width = state['aspect'] * MENU_BOX_W_FRAC
        scene.menu_box.draw()
        scene.menu_text.pos = (-scene.menu_box.width / 2.0 + MENU_PAD, 0)
        set_text(scene.menu_text, build_menu_text(state))
        scene.menu_text.draw()

    if flash_text is not None:
        set_text(scene.flash, flash_text)
        scene.flash.draw()


class FrameTimer(object):
    """Rolling refresh and dropped-frame count, measured at the flip.

    Call tick() right after every flip. A frame counts as dropped when its
    flip-to-flip interval exceeds DROP_FACTOR x the rolling median BEFORE it
    joins the window, so a long frame cannot raise the bar it has to clear.
    """

    def __init__(self, refresh_hz):
        self.refresh_hz = refresh_hz
        self.clock = core.Clock()
        self.intervals = collections.deque(maxlen=ROLLING_FRAMES)
        self.startup_threshold = DROP_FACTOR / refresh_hz
        self.dropped = 0
        self.flips = 0
        self.rolling_hz, self.rolling_sd_ms = refresh_hz, None
        self.divergence_warned = False

    def tick(self):
        """Interval since the last flip in seconds, or None for the first.

        The first interval spans setup (window, intro screen), so it is
        discarded rather than counted as a drop.
        """
        interval = self.clock.getTime()
        self.clock.reset()
        self.flips += 1
        if self.flips == 1:
            return None
        hz, sd_ms, median_s = rolling_stats(self.intervals)
        if median_s is not None and len(self.intervals) >= MIN_DROP_SAMPLES:
            threshold = DROP_FACTOR * median_s
        else:
            threshold = self.startup_threshold
        if interval > threshold:
            self.dropped += 1
        self.intervals.append(interval)
        hz, sd_ms, _median = rolling_stats(self.intervals)
        if hz is not None:
            self.rolling_hz, self.rolling_sd_ms = hz, sd_ms
            # Once only: a full window that disagrees with getMsPerFrame
            # means one of the two is wrong, and the frame counts driving
            # every flicker frequency are built on the startup figure.
            if (not self.divergence_warned
                    and len(self.intervals) >= ROLLING_FRAMES
                    and abs(self.rolling_hz - self.refresh_hz)
                    > DIVERGENCE_WARN_HZ):
                self.divergence_warned = True
                print("WARNING: rolling refresh ({:.1f} Hz) diverges from "
                      "startup measurement ({:.1f} Hz) -- timing may be "
                      "unreliable".format(self.rolling_hz, self.refresh_hz))
        return interval


# =============================================================================
# BENCHMARK  (--bench)
# =============================================================================

def gl_renderer():
    """{vendor, renderer, version} of the GL context, or {} if unavailable."""
    try:
        from pyglet.gl import gl_info
        return {'vendor': gl_info.get_vendor(),
                'renderer': gl_info.get_renderer(),
                'version': gl_info.get_version()}
    except Exception:                                        # noqa: BLE001
        return {}


def bench_state(stimulus_type, count, hud, refresh_hz, resolution,
                image_label):
    """A default session in flicker mode 3 with `count` copies."""
    state = default_state(stimulus_type, refresh_hz)
    state.update(image_path=image_label,
                 aspect=resolution[0] / float(resolution[1]),
                 win_w=resolution[0], win_h=resolution[1],
                 mode=MODE_FLICKER_15, hud_visible=hud,
                 multi=count > 1, multi_count=max(MULTI_MIN, count))
    sync_stim_frames(state)
    return state


def bench_config(win, state, image, refresh_hz, resolution,
                 screen_height_cm):
    """Run one configuration. Returns its result dict, or None on abort."""
    scene = build_scene(win, state, image, verbose=False)
    timer = FrameTimer(refresh_hz)
    clock = core.Clock()
    draws, intervals = [], []
    dropped_before = None
    for frame in range(BENCH_WARMUP + BENCH_FRAMES):
        if event.getKeys(keyList=['q', 'escape']):
            return None
        start = clock.getTime()
        render_frame(win, scene, state, refresh_hz, resolution,
                     screen_height_cm, timer)
        draw = clock.getTime() - start
        win.flip()
        state['frame_idx'] += 1
        interval = timer.tick()
        if frame == BENCH_WARMUP:
            dropped_before = timer.dropped
        if frame >= BENCH_WARMUP:
            draws.append(draw)
            if interval is not None:
                intervals.append(interval)
    draws.sort()
    budget_ms = 1000.0 / refresh_hz
    draw_mean = 1000 * sum(draws) / len(draws)
    return {
        'stimulus_type': state['stimulus_type'],
        'copies': len(ring_positions(state)),
        'hud': state['hud_visible'],
        'frames': len(draws),
        'draw_mean_ms': round(draw_mean, 3),
        'draw_p95_ms': round(1000 * draws[int(0.95 * len(draws))], 3),
        'draw_max_ms': round(1000 * draws[-1], 3),
        'interval_mean_ms': round(1000 * sum(intervals) / len(intervals), 3),
        'interval_max_ms': round(1000 * max(intervals), 3),
        'dropped_frames': timer.dropped - dropped_before,
        'budget_ms': round(budget_ms, 3),
        'draw_mean_pct_budget': round(100 * draw_mean / budget_ms, 1),
    }


def bench_flagged(result):
    """Dropped frames, or a draw p95 or max above 80% of the budget.

    The mean hides the frames that matter: one slow frame drops one cycle.
    """
    limit = BENCH_BUDGET_WARN * result['budget_ms']
    return (result['dropped_frames'] > 0 or result['draw_p95_ms'] > limit or
            result['draw_max_ms'] > limit)


def bench_table(results):
    lines = ['{:20} {:>3} {:>4} {:>8} {:>8} {:>8} {:>9} {:>9} {:>6} {:>6}'
             .format('type', 'N', 'hud', 'draw ms', 'p95', 'max', 'intv ms',
                     'intv max', 'drops', '%bud'),
             '-' * 92]
    for r in results:
        if 'skipped' in r:
            lines.append('{:20}  skipped: {}'.format(r['stimulus_type'],
                                                     r['skipped']))
            continue
        lines.append('{:20} {:>3} {:>4} {:>8.2f} {:>8.2f} {:>8.2f} {:>9.2f} '
                     '{:>9.2f} {:>6} {:>5.0f}% {}'.format(
                         r['stimulus_type'], r['copies'],
                         'on' if r['hud'] else 'off', r['draw_mean_ms'],
                         r['draw_p95_ms'], r['draw_max_ms'],
                         r['interval_mean_ms'], r['interval_max_ms'],
                         r['dropped_frames'], r['draw_mean_pct_budget'],
                         '!' if bench_flagged(r) else ''))
    return '\n'.join(lines)


def run_bench(args):
    """--bench: time every type at each copy count, write bench_*.json.

    Fullscreen and non-interactive; Q or ESC aborts, and whatever finished is
    still written (the file is rewritten after every configuration).
    """
    image, image_label, image_failure = resolve_image(args.image)
    started = datetime.datetime.now()
    start_crash_log(timestamp_slug(started))
    out_path = unique_path(os.path.join(
        OUT_DIR, BENCH_NAME_FMT.format(timestamp_slug(started))))
    mon = monitors.Monitor(MONITOR_NAME)
    win = visual.Window(
        size=REQUESTED_RESOLUTION, fullscr=True, screen=SCREEN_INDEX,
        monitor=mon, winType='pyglet', units=UNITS,
        color=[DEFAULT_BG] * 3, colorSpace='rgb',
        useFBO=True, allowStencil=False)
    win.mouseVisible = False
    resolution = (int(win.size[0]), int(win.size[1]))
    screen_height_cm = monitor_height_cm(mon, resolution)
    refresh_hz = measure_refresh(win)

    header = session_header(win, mon, resolution, screen_height_cm,
                            refresh_hz, args.image, started=started,
                            out_path=out_path,
                            image_failed=bool(image_failure))
    # Session-run fields (presets, final rolling rate, drop total) mean
    # nothing here; drops are per configuration in the results.
    for key in ('preset_path', 'text_arg', 'final_rolling_refresh_hz',
                'final_rolling_refresh_sd_ms', 'total_dropped_frames'):
        header.pop(key, None)
    header.update(bench=True, gl=gl_renderer(), frames_per_config=BENCH_FRAMES,
                  warmup_frames=BENCH_WARMUP, mode=MODE_FLICKER_15,
                  frame_budget_ms=round(1000.0 / refresh_hz, 3),
                  texture=image_label)
    payload = dict(header, aborted=False, results=[])
    configs = ([(t, n, False) for t in STIMULUS_TYPES for n in BENCH_COUNTS] +
               [(t, n, True) for t in STIMULUS_TYPES for n in BENCH_HUD_COUNTS])
    print("Benchmark: {} configurations x {} frames at {:.2f} Hz "
          "(budget {:.2f} ms). Q or ESC aborts.".format(
              len(configs), BENCH_FRAMES, refresh_hz, 1000.0 / refresh_hz))

    for stimulus_type, count, hud in configs:
        if stimulus_type == STIM_RADIAL and not HAS_RADIAL:
            if count == BENCH_COUNTS[0] and not hud:
                payload['results'].append({
                    'stimulus_type': stimulus_type,
                    'skipped': 'psychopy_visionscience missing ({})'.format(
                        RADIAL_ERR)})
            continue
        state = bench_state(stimulus_type, count, hud, refresh_hz,
                            resolution, image_label)
        result = bench_config(win, state, image, refresh_hz, resolution,
                              screen_height_cm)
        if result is None:
            payload['aborted'] = True
            break
        payload['results'].append(result)
        payload['session_end'] = datetime.datetime.now().isoformat(
            timespec='seconds')
        write_bench(payload, out_path)
        print("  {:20} N={:2} hud={:3} draw {:6.2f} ms ({:5.1f}%) drops {}"
              .format(stimulus_type, result['copies'],
                      'on' if hud else 'off', result['draw_mean_ms'],
                      result['draw_mean_pct_budget'],
                      result['dropped_frames']))

    payload['session_end'] = datetime.datetime.now().isoformat(
        timespec='seconds')
    write_bench(payload, out_path)
    win.close()
    print("")
    print(bench_table(payload['results']))
    print("! = dropped frames, or draw p95 or max above {:.0f}% of the "
          "{:.2f} ms frame budget.".format(100 * BENCH_BUDGET_WARN,
                                 1000.0 / refresh_hz))
    if payload['aborted']:
        print("ABORTED -- partial results.")
    print("Benchmark written to {}".format(out_path))
    core.quit()


def write_bench(payload, path):
    with open(path, 'w') as handle:
        json.dump(payload, handle, indent=2)


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
    parser.add_argument(
        '--text', metavar='STRING', default=None,
        help='String for stimulus type [6]. One character: [B]/[N] cycle '
             'the alphabet from it. Longer: they cycle the full string, each '
             'of its characters, then A-Z. Without it, the five built-in '
             'strings (ABCDEF ...). Monical has no on-screen text entry '
             '(keyboard-only, no widgets).')
    parser.add_argument(
        '--bench', action='store_true',
        help='Benchmark frame timing instead of running a session: every '
             'stimulus type at 1, 2, 8 and 16 copies with the readout off, '
             'and at 1 and 16 with it on, flicker mode 3, fullscreen, 600 '
             'frames each. Writes bench_YYYY-MM-DD_HHMMSS.json and prints a '
             'table. Q or ESC aborts.')
    parser.add_argument(
        '--preset', metavar='PATH', default=None,
        help='Preset JSON saved with [P]. Restores the knobs and preselects '
             'the stimulus type it was saved from.')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.bench:
        run_bench(args)
        return
    image, image_label, image_failure = resolve_image(args.image)

    # Fixed once, before anything can write: session_start, the output
    # filename and every generated name this run share one stamp.
    session_started = datetime.datetime.now()
    session_slug = timestamp_slug(session_started)
    out_path = session_out_path(session_slug)
    start_crash_log(session_slug)

    text_presets, text_start = text_cycle(args.text)
    preset = load_preset(args.preset) if args.preset else {}
    preset_name = os.path.basename(args.preset) if args.preset else ''

    mon = monitors.Monitor(MONITOR_NAME)

    win = visual.Window(
        size=REQUESTED_RESOLUTION, fullscr=True, screen=SCREEN_INDEX,
        monitor=mon, winType='pyglet', units=UNITS,
        color=[DEFAULT_BG] * 3, colorSpace='rgb',
        useFBO=True, allowStencil=False)
    win.mouseVisible = False

    resolution = (int(win.size[0]), int(win.size[1]))
    screen_height_cm = monitor_height_cm(mon, resolution)

    measured_refresh = measure_refresh(win)

    if monitor_dimension_suspect(screen_height_cm):
        print(monitor_warning_text(screen_height_cm))

    # A preset opens the selector on the type it was saved from.
    preset_index = 0
    if preset.get('stimulus_type') in STIMULUS_TYPES:
        preset_index = STIMULUS_TYPES.index(preset['stimulus_type'])

    stimulus_type = show_intro(win, resolution, measured_refresh, image_label,
                               out_name=os.path.basename(out_path),
                               preset_name=preset_name,
                               selected_index=preset_index,
                               warning=monitor_warning_text(screen_height_cm),
                               image_failure=image_failure)
    if stimulus_type is None:
        win.close()
        print("Aborted at intro screen. Nothing written.")
        core.quit()

    state = default_state(stimulus_type, measured_refresh)
    state['image_path'] = image_label
    state['aspect'] = resolution[0] / float(resolution[1])
    state['win_w'], state['win_h'] = resolution
    state['text_index'] = text_start
    state['text_string'] = text_presets[text_start]
    if preset:
        # Applied after default_state so omitted keys keep their defaults,
        # and after stimulus_type so the operator's choice at the selector
        # wins over the preset's if they changed it.
        applied = apply_preset(state, preset, text_presets)
        state['stimulus_type'] = stimulus_type
        print("Preset {}: applied {} value(s).".format(preset_name,
                                                       len(applied)))
    table = knob_table(state['stimulus_type'], measured_refresh)

    # ---- Stimuli, overlays (PRD 4, 6, 8) -------------------------------------
    scene = build_scene(win, state, image)
    flash_frames = 0
    flash_text = ''

    # Auto gamma sweep state: None when idle (PRD 6.5).
    sweep = None
    sweep_clock = core.Clock()

    def take_snapshot():
        """One snapshot appended and the session file rewritten."""
        state['snapshots'].append(state_record(
            state, screen_height_cm, measured_refresh,
            rolling_hz=timer.rolling_hz, drops=timer.dropped,
            snapshot_number=len(state['snapshots']) + 1))
        write_json(state, session, out_path)
        return len(state['snapshots'])

    flash_frames = 0

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

    repeat_names = repeat_key_names(stimulus_type)
    held_since = {}          # key name -> time it went down, for EVERY held key
    repeat_count = {}        # key name -> increments emitted so far this hold
    repeat_clock = core.Clock()

    # ---- Live frame timing (rolling, not the one-shot startup figure) -------
    session = session_header(win, mon, resolution, screen_height_cm,
                             measured_refresh, args.image,
                             started=session_started, out_path=out_path,
                             preset_arg=args.preset, text_arg=args.text,
                             image_failed=bool(image_failure))
    timer = FrameTimer(measured_refresh)

    # ---- Main loop -----------------------------------------------------------
    running = True
    while running:
        # ---- Input -----------------------------------------------------------
        for key in new_presses(event.getKeys(), held_since):
            # Precedence lives in key_claim, shared with the repeat loop.
            claim = key_claim(state, key, sweep is not None)

            # --- Mode switching (PRD 6). Phase resets on every switch. -------
            if claim == 'mode':
                if state['mode'] != MODE_KEYS[key]:
                    state['mode'] = MODE_KEYS[key]
                    state['frame_idx'] = 0
                continue
            if claim == 'dual':
                state['multi'] = not state['multi']
                continue
            if claim == 'select':
                if state['multi']:
                    step = 1 if key == SELECT_NEXT else -1
                    state['selected_index'] = (
                        (selected(state) + step) % state['multi_count'])
                continue
            if claim == 'copy_state':
                if state['multi']:
                    states, index = state['stim_states'], selected(state)
                    states[index] = COPY_STATES[
                        (COPY_STATES.index(states[index]) + 1) %
                        len(COPY_STATES)]
                continue

            # --- Auto gamma sweep (PRD 6.5). [A] is a knob on several stimulus
            # types, so gamma mode has to claim it the way it claims the
            # arrows -- otherwise starting a sweep would also nudge the
            # envelope SD or the blue channel underneath it.
            if claim == 'sweep_toggle':
                if sweep is None:
                    sweep = start_sweep(state, sweep_clock)
                else:
                    sweep = cancel_sweep(state, sweep)
                    flash_text, flash_frames = 'Auto gamma cancelled', \
                        FLASH_FRAMES
                continue
            # ESC cancels a running sweep rather than quitting, so a mistimed
            # press cannot end the session mid-ramp.
            if claim == 'sweep_cancel':
                sweep = cancel_sweep(state, sweep)
                flash_text, flash_frames = 'Auto gamma cancelled', FLASH_FRAMES
                continue

            # --- Arrows are claimed by two modes (PRD 6.2, 6.4) -------------
            if claim == 'mode_arrow':
                if state['mode'] == MODE_GAMMA:
                    if sweep is not None:
                        continue      # the sweep is driving the level
                    step = 1 if key == 'right' else -1
                    state['gamma_step_index'] = int(clamp(
                        state['gamma_step_index'] + step, 0,
                        len(GAMMA_LEVELS) - 1))
                else:
                    move_uniformity(state, key)
                continue

            if claim == 'menu':
                state['menu_visible'] = not state['menu_visible']
                continue
            # ESC is claimed in order: cancel a running sweep, else dismiss
            # the menu, else quit. Quitting is the last resort so neither
            # overlay can be closed by accidentally ending the session.
            if claim == 'menu_close':
                state['menu_visible'] = False
                continue

            if claim == 'hud':
                # Hides ONLY the readout. Stimulus, fixation and the gamma
                # patch keep drawing, so a photometer reading or a screenshot
                # is unobstructed (PRD 8.1).
                state['hud_visible'] = not state['hud_visible']
                continue

            if claim == 'text_cycle':
                step = 1 if key == TEXT_CYCLE_FWD else -1
                state['text_index'] = ((state['text_index'] + step)
                                       % len(text_presets))
                state['text_string'] = text_presets[state['text_index']]
                continue

            if claim == 'preset':
                path = save_preset(state, timestamp_slug())
                flash_text = 'Preset saved: {}'.format(os.path.basename(path))
                flash_frames = FLASH_FRAMES
                print("PRESET saved to {}".format(path))
                continue

            if claim == 'screenshot':
                path = save_screenshot(win, timestamp_slug())
                flash_text = 'Screenshot saved: {}'.format(
                    os.path.basename(path))
                flash_frames = FLASH_FRAMES
                print("SCREENSHOT saved to {}".format(path))
                continue

            if key in table:
                apply_knob(state, key, table)
            elif key == 's':
                count = take_snapshot()
                flash_text = 'Snapshot #{} saved'.format(count)
                flash_frames = FLASH_FRAMES
                print("SNAPSHOT {} saved.".format(count))
            elif key in ('q', 'escape'):
                running = False

        if not running:
            break

        # ---- Hold-to-repeat (PRD 5.1) ----------------------------------------
        if key_state is not None:
            down = {pyglet_key_name(symbol)
                    for symbol, is_down in key_state.items() if is_down}
            repeat_tick(state, table, repeat_names, down,
                        held_since, repeat_count, repeat_clock.getTime(),
                        sweeping=sweep is not None)

        # ---- Auto gamma sweep (PRD 6.5) --------------------------------------
        # Driven here rather than from the key handler so the dwell is wall
        # clock, not frame count, and holds at 2 s on any panel.
        if sweep is not None and sweep_due(sweep, sweep_clock):
            # Snapshot the level that just settled, THEN move on.
            count = take_snapshot()
            print("AUTO GAMMA snapshot {} (level {}/{}).".format(
                count, state['gamma_step_index'] + 1, len(GAMMA_LEVELS)))
            sweep = sweep_step(state, sweep, sweep_clock)
            if sweep is None:
                flash_text = 'Auto gamma complete: {} levels'.format(
                    len(GAMMA_LEVELS))
                flash_frames = FLASH_FRAMES

        # ---- Draw, flip, timing ----------------------------------------------
        render_frame(win, scene, state, measured_refresh, resolution,
                     screen_height_cm, timer, sweep=sweep,
                     out_name=os.path.basename(out_path),
                     flash_text=flash_text if flash_frames > 0 else None)
        if flash_frames > 0:
            flash_frames -= 1
        win.flip()
        state['frame_idx'] += 1
        timer.tick()

    # ---- Quit ----------------------------------------------------------------
    session['session_end'] = datetime.datetime.now().isoformat(
        timespec='seconds')
    session['final_rolling_refresh_hz'] = (
        None if timer.rolling_hz is None else round(timer.rolling_hz, 3))
    session['final_rolling_refresh_sd_ms'] = (
        None if timer.rolling_sd_ms is None
        else round(timer.rolling_sd_ms, 4))
    session['total_dropped_frames'] = timer.dropped

    final = state_record(state, screen_height_cm, measured_refresh,
                         rolling_hz=timer.rolling_hz, drops=timer.dropped)
    path = write_json(state, session, out_path, final=final)
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
