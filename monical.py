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


# =============================================================================
# CONSTANTS
# =============================================================================

MONICAL_VERSION = '0.1'

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

STIMULUS_TYPES = [STIM_RADIAL, STIM_GABOR, STIM_GRATING, STIM_UNIFORM]

STIMULUS_LABELS = {
    STIM_RADIAL: 'Radial checkerboard (SSVEP standard)',
    STIM_GABOR: 'Gabor patch (attention/perception)',
    STIM_GRATING: 'Sinusoidal grating (contrast/SF tuning)',
    STIM_UNIFORM: 'Uniform patch (color/luminance calibration)',
}

# Modes. Named here so the scaffold's state dict and JSON records already use
# the final vocabulary; only static_on is reachable until modes land.
MODE_STATIC_ON = 'static_on'
MODE_STATIC_OFF = 'static_off'
MODE_FLICKER_15 = 'flicker_15hz'
MODE_FLICKER_20 = 'flicker_20hz'
MODE_FLICKER_CUSTOM = 'flicker_custom'
MODE_GAMMA = 'gamma_steps'
MODE_DUAL = 'dual_stimulus'
MODE_UNIFORMITY = 'spatial_uniformity'

# PRD 6.2 -- 11 levels in PsychoPy rgb units, index 5 is mid-gray.
GAMMA_LEVELS = [-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

# PRD 6.4 -- center first, then the eight surround positions.
UNIFORMITY_GRID = [
    'center', 'top_left', 'top_center', 'top_right',
    'mid_left', 'mid_right', 'bottom_left', 'bottom_center', 'bottom_right',
]


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

        # Mode-local indices
        'gamma_step_index': 5,
        'uniformity_grid_index': 0,

        # Loop bookkeeping
        'frame_idx': 0,
        'snapshots': [],
    }


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
    """Degrees subtended by an extent given in 'height' units.

    In height units 1.0 spans the full screen height, so size_cm is just
    height_units * screen_height_cm.
    """
    if not screen_height_cm or not distance_cm:
        return None
    size_cm = abs(float(height_units)) * float(screen_height_cm)
    return 2.0 * np.degrees(np.arctan(size_cm / (2.0 * float(distance_cm))))


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
}


def build_intro_text(resolution, refresh_hz, selected_index):
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

    lines += [""] + WORKFLOWS[selected]
    lines += [
        "",
        "[S] snapshot   [Q] quit (saves final state)",
        "",
        "Press SPACE to begin.",
    ]
    return "\n".join(lines)


def show_intro(win, resolution, refresh_hz):
    """White on black. Returns the chosen stimulus type, or None if aborted."""
    previous_color = win.color
    win.color = [-1, -1, -1]
    # Window colour needs a flip to take; two clears the FBO's stale buffer.
    win.flip()
    win.flip()

    selected_index = 0
    text = visual.TextStim(
        win, text=build_intro_text(resolution, refresh_hz, selected_index),
        font=READOUT_FONT, height=0.020, color='white',
        pos=(0, 0), wrapWidth=1.7, alignText='left', anchorHoriz='center',
        autoLog=False)

    event.clearEvents()
    while True:
        text.draw()
        win.flip()

        dirty = False
        for key in event.getKeys(keyList=['1', '2', '3', '4',
                                          'space', 'q', 'escape']):
            if key in ('1', '2', '3', '4'):
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
                resolution, refresh_hz, selected_index)


# =============================================================================
# OUTPUT  (PRD 3.2)
# =============================================================================

# PRD 5.2 fixes DISPLAY precision, which is coarser than some defaults are
# (size 0.225 -> "0.23"). The JSON is a record, not a readout, so knob values
# are stored at 4 dp -- the seed tool's precedent -- and rounded only for the
# HUD. Rounding the file to display precision would lose the value the
# scientist actually dialled in.
STORE_DP = 4


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
    else:
        record = {}

    # Mode-local values, without which a reading cannot be matched back to the
    # screen it was taken from.
    if state['mode'] == MODE_GAMMA:
        record['gamma_level'] = GAMMA_LEVELS[state['gamma_step_index']]
    elif state['mode'] == MODE_UNIFORMITY:
        record['grid_position'] = UNIFORMITY_GRID[
            state['uniformity_grid_index']]

    return record


def state_record(state, screen_height_cm):
    angle = visual_angle_deg(state['size'], screen_height_cm,
                             state['viewing_distance_cm'])
    return {
        'timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
        'stimulus_type': state['stimulus_type'],
        'mode': state['mode'],
        'x_position': round(state['x_pos'], STORE_DP),
        'y_position': round(state['y_pos'], STORE_DP),
        'background_gray': round(state['bg_gray'], STORE_DP),
        'disc_size': round(state['size'], STORE_DP),
        'contrast': round(state['contrast'], STORE_DP),
        'custom_frequency_hz': state['custom_freq_hz'],
        'visual_angle_deg': None if angle is None else round(angle, 2),
        'stimulus_specific': stimulus_specific(state),
    }


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

def main():
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

    stimulus_type = show_intro(win, resolution, measured_refresh)
    if stimulus_type is None:
        win.close()
        print("Aborted at intro screen. Nothing written.")
        core.quit()

    state = default_state(stimulus_type)

    # ---- Main loop -----------------------------------------------------------
    running = True
    while running:
        win.color = [state['bg_gray']] * 3

        # --- STIMULUS RENDERING HERE ---

        # --- HUD RENDERING HERE ---

        win.flip()
        state['frame_idx'] += 1

        for key in event.getKeys():
            if key == 's':
                state['snapshots'].append(
                    state_record(state, screen_height_cm))
                write_json(state, resolution, measured_refresh,
                           screen_height_cm)
                print("SNAPSHOT {} saved.".format(len(state['snapshots'])))
            elif key in ('q', 'escape'):
                running = False

    # ---- Quit ----------------------------------------------------------------
    final = state_record(state, screen_height_cm)
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
