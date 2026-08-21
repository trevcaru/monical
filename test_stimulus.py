#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standalone stimulus calibration tool — photometer and oscilloscope verification.

COMPLETELY SEPARATE FROM THE EXPERIMENT. This script imports nothing from
EXP_2STIM_v1.py and the experiment imports nothing from here. The stimulus
construction below is a deliberate verbatim DUPLICATE of the experiment's, so
that photometer measurements taken here transfer directly to the real session.

    >>> IF THE EXPERIMENT'S STIMULUS CHANGES, CHANGE IT HERE TOO. <<<

Replicated from EXP_2STIM_v1.py (commit 8bf02eb) and verified against it:

    CHECKER_PATTERN   np.ones((4,4)); [::2,::2] = -1; [1::2,1::2] = -1
    RadialStim        tex=pattern, size=0.225, radialCycles=1, texRes=256,
                      opacity=1, no mask, no angularCycles, no colorSpace
    contrast          1.0 (RadialStim default; the experiment omits the kwarg,
                      this tool passes it explicitly so it can be tuned — at
                      1.0 the two are identical)
    stim_is_on        (frame_idx % frames) < (frames // 2)   [verbatim copy]
    Window            fullscr, winType='pyglet', units='height',
                      colorSpace='rgb', useFBO=True, allowStencil=False,
                      and NO monitor= argument

Writes exactly one file: tools/calibration_values.json, on [S] and on [Q].
No EEG, no eye tracker, no trials, no CSV, no markers, no GUI widgets.

The values it writes are REFERENCE ONLY. Nothing auto-loads them.
"""

import os
import sys
import json
import datetime
from collections import deque

import numpy as np

from psychopy import visual, core, event
from psychopy import __version__ as PSYCHOPY_VERSION

# Held-key detection for the two fine knobs. event.getKeys() is edge-triggered
# and cannot report that a key is STILL down, so auto-repeat needs the pyglet
# key state directly (the window is winType='pyglet'). Guarded: without it the
# tool loses auto-repeat only, and every knob still works one press at a time.
try:
    from pyglet.window import key as pyglet_key
    PYGLET_KEY_OK = True
except Exception:                                            # noqa: BLE001
    pyglet_key = None
    PYGLET_KEY_OK = False

# The plugin is imported defensively so the info screen can REPORT a failure
# rather than dying at import. Gamma stepping and static-OFF still work without
# it, and those are the two modes you need for the first calibration pass.
try:
    from psychopy_visionscience.radial import RadialStim
    PLUGIN_OK = True
    PLUGIN_ERR = ''
except Exception as _err:                                    # noqa: BLE001
    RadialStim = None
    PLUGIN_OK = False
    PLUGIN_ERR = '{}: {}'.format(type(_err).__name__, _err)


# =============================================================================
# CONSTANTS — mirrored from the experiment. Do not drift.
# =============================================================================

NOMINAL_REFRESH = 240             # Hz. Frame counts below assume this.
SCREEN_RESOLUTION = (1920, 1080)  # requested; actual is detected after open
SCREEN_INDEX = 0
UNITS = 'height'

DEFAULT_X = 0.66                  # experiment ECCENTRICITY
DEFAULT_BG = 0.0                  # experiment BACKGROUND_COLOR [0,0,0]
DEFAULT_SIZE = 0.225              # experiment STIM_SIZE
DEFAULT_CONTRAST = 1.0            # RadialStim default, matches v1
DEFAULT_CUSTOM_HZ = 15

FIXATION_SIZE = (0.07, 0.07)      # experiment FIXATION_SIZE

FRAMES_15HZ = 16                  # 240/16 = 15.000 Hz
FRAMES_20HZ = 12                  # 240/12 = 20.000 Hz

STEP_POS = 0.01
STEP_BG = 0.001                   # fine, for photometer luminance matching
STEP_SIZE = 0.01
STEP_CONTRAST = 0.001             # fine, for photometer luminance matching
STEP_FREQ = 1

# Hold-to-repeat, BG and contrast only. At 0.001 per press these two knobs need
# ~1000 presses to cross their range, so they auto-repeat; every other knob is
# coarse enough to stay single-press. Clock-driven rather than frame-driven, so
# the rate is the same whatever the panel refresh turns out to be (10/s is one
# increment every 6 frames at 60 Hz, every 24 at 240 Hz).
REPEAT_DELAY_S = 1.0              # hold this long before repeating starts
REPEAT_RATE_HZ = 10.0             # increments per second once it starts

GAMMA_LEVELS = list(range(0, 101, 10))   # 0,10,...,100 percent

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(OUT_DIR, 'calibration_values.json')

READOUT_FONT = 'Consolas'


# The 4x4 balanced checker texture. Every ROW carries two +1 and two -1, so each
# annulus of the radial warp is sign-balanced independently of unequal annulus
# areas — the disc is nominally zero-mean against a mid-gray background. That
# "nominally" is exactly what the photometer is here to test.
CHECKER_PATTERN = np.ones((4, 4))
CHECKER_PATTERN[::2, ::2] = -1
CHECKER_PATTERN[1::2, 1::2] = -1


def stim_is_on(frame_idx, frames):
    """VERBATIM COPY of EXP_2STIM_v1.stim_is_on. Do not 'improve' it.

    ON  for frames  0 .. frames//2 - 1  of each cycle,
    OFF for frames  frames//2 .. frames-1.
    Stateless integer arithmetic — no float-equality gate, no persistent
    counter. Duplicated rather than imported so this tool stays standalone.
    """
    return (frame_idx % frames) < (frames // 2)


# =============================================================================
# MODES
# =============================================================================

MODE_STATIC_ON = 'static_on'
MODE_STATIC_OFF = 'static_off'
MODE_FLICKER_15 = 'flicker_15hz'
MODE_FLICKER_20 = 'flicker_20hz'
MODE_FLICKER_CUSTOM = 'flicker_custom'
MODE_GAMMA = 'gamma_steps'

MODE_NEEDS_PLUGIN = {
    MODE_STATIC_ON: True,
    MODE_STATIC_OFF: False,
    MODE_FLICKER_15: True,
    MODE_FLICKER_20: True,
    MODE_FLICKER_CUSTOM: True,
    MODE_GAMMA: False,
}


def clamp(value, low, high):
    return max(low, min(high, value))


def hz_to_frames(hz):
    """Nearest integer frame count for a requested Hz at NOMINAL_REFRESH."""
    return max(2, int(round(NOMINAL_REFRESH / float(hz))))


def frames_to_hz(frames):
    """Realized Hz. Never a rounded literal — always derived from frames."""
    return NOMINAL_REFRESH / float(frames)


# =============================================================================
# INFO / TUTORIAL SCREEN
# =============================================================================

def build_info_text(resolution, refresh_hz):
    plugin_line = ('psychopy_visionscience  [imported OK]' if PLUGIN_OK
                   else 'psychopy_visionscience  [FAILED]')

    lines = [
        "STIMULUS CALIBRATION TOOL",
        "-------------------------------------------------------------",
        "Monitor:    {} x {}  @  {:.2f} Hz".format(
            resolution[0], resolution[1], refresh_hz),
        "PsychoPy:   {}".format(PSYCHOPY_VERSION),
        "Plugin:     {}".format(plugin_line),
    ]

    if not PLUGIN_OK:
        lines += [
            "",
            "!! RadialStim unavailable -- the checkerboard cannot be drawn.",
            "!! {}".format(PLUGIN_ERR[:60]),
            "!! Modes [2] and [G] still work. Install with:",
            "!!     pip install psychopy-visionscience",
        ]

    lines += [
        "",
        "WORKFLOW",
        "1. Gamma calibrate the monitor first (Mode G below).",
        "   Step through gray levels, measure each with photometer,",
        "   enter curve in PsychoPy Monitor Center.",
        "2. Switch to verification modes. Render the checkerboard",
        "   static ON and static OFF at each stimulus position.",
        "   Measure with photometer. They should match.",
        "3. If residual mismatch: adjust background gray or stimulus",
        "   contrast with the on-screen knobs until matched.",
        "4. Save a snapshot [S] at each position once matched.",
        "5. Oscilloscope check: flicker modes. Photodiode on screen,",
        "   confirm clean symmetric waveform at 15 and 20 Hz.",
        "",
        "CONTROLS",
        "[1] Static ON      [2] Static OFF      [3] Flicker 15 Hz",
        "[4] Flicker 20 Hz  [5] Flicker custom  [G] Gamma steps",
        "[LEFT/RIGHT] X position +/-0.01   [UP/DOWN] Background gray +/-0.001",
        "[+/-] Disc size +/-0.01           [C/V] Contrast +/-0.001",
        "[F/H] Custom freq +/-1 Hz         [S] Save snapshot",
        "[Q] Quit (saves final state)",
        "",
        "Hold [UP/DOWN] or [C/V] for 1 s to auto-repeat at 10 steps/sec.",
        "The other knobs are single-press only.",
        "",
        "Press SPACE to begin.",
    ]
    return "\n".join(lines)


def show_info_screen(win, resolution, refresh_hz):
    """White on black. Blocks until SPACE. Escape/Q aborts before any work."""
    previous_color = win.color
    win.color = [-1, -1, -1]
    # Window colour needs a flip to take: two clears the FBO's stale buffer.
    win.flip()
    win.flip()

    text = visual.TextStim(
        win, text=build_info_text(resolution, refresh_hz),
        font=READOUT_FONT, height=0.020, color='white',
        pos=(0, 0), wrapWidth=1.7, alignText='left', anchorHoriz='center')

    event.clearEvents()
    proceed = True
    while True:
        text.draw()
        win.flip()
        keys = event.getKeys(keyList=['space', 'q', 'escape'])
        if 'space' in keys:
            break
        if 'q' in keys or 'escape' in keys:
            proceed = False
            break

    win.color = previous_color
    win.flip()
    win.flip()
    return proceed


# =============================================================================
# OUTPUT
# =============================================================================

def write_json(state, snapshots, resolution, refresh_hz, final=None):
    payload = {
        'note': ('REFERENCE ONLY. Not auto-loaded by EXP_2STIM_v1.py. '
                 'Produced by tools/test_stimulus.py.'),
        'generated_utc': datetime.datetime.utcnow().isoformat(),
        'monitor_resolution': list(resolution),
        'measured_refresh_hz': round(float(refresh_hz), 3),
        'nominal_refresh_hz': NOMINAL_REFRESH,
        'psychopy_version': str(PSYCHOPY_VERSION),
        'plugin_import_ok': PLUGIN_OK,
        'snapshots': snapshots,
    }
    if final is not None:
        payload['final'] = final
    with open(OUT_PATH, 'w') as handle:
        json.dump(payload, handle, indent=2)
    return OUT_PATH


def state_record(state):
    """The seven spec'd fields, plus gamma level when it is meaningful."""
    record = {
        'timestamp': datetime.datetime.now().isoformat(),
        'mode': state['mode'],
        'x_position': round(state['x'], 4),
        'background_gray': round(state['bg'], 4),
        'disc_size': round(state['size'], 4),
        'contrast': round(state['contrast'], 4),
        'custom_frequency': state['custom_hz'],
    }
    if state['mode'] == MODE_GAMMA:
        # Without this a gamma snapshot cannot be matched to a photometer
        # reading. Additive only; the seven fields above are always present.
        record['gamma_level_percent'] = GAMMA_LEVELS[state['gamma_idx']]
    return record


# =============================================================================
# MAIN
# =============================================================================

def main():
    win = visual.Window(
        size=SCREEN_RESOLUTION, fullscr=True, screen=SCREEN_INDEX,
        winType='pyglet', units=UNITS, color=[DEFAULT_BG] * 3,
        colorSpace='rgb', useFBO=True, allowStencil=False)
    win.mouseVisible = False

    resolution = (int(win.size[0]), int(win.size[1]))
    aspect = resolution[0] / float(resolution[1])

    # Held-key state for auto-repeat. KeyStateHandler only observes events, so
    # it coexists with PsychoPy's own handlers behind event.getKeys().
    key_state = None
    if PYGLET_KEY_OK:
        try:
            key_state = pyglet_key.KeyStateHandler()
            win.winHandle.push_handlers(key_state)
        except Exception as err:                             # noqa: BLE001
            key_state = None
            print("Hold-to-repeat unavailable ({}). Single presses still work."
                  .format(err))

    measured = win.getActualFrameRate(nIdentical=20, nMaxFrames=200)
    if measured is None:
        print("WARNING: could not measure refresh rate; using nominal {} Hz."
              .format(NOMINAL_REFRESH))
        measured = float(NOMINAL_REFRESH)
    if abs(measured - NOMINAL_REFRESH) > 2.0:
        print("*** WARNING: measured refresh {:.2f} Hz != nominal {} Hz. "
              "Frame-count frequencies will NOT be the stated values. ***"
              .format(measured, NOMINAL_REFRESH))

    if not show_info_screen(win, resolution, measured):
        win.close()
        print("Aborted at info screen. Nothing written.")
        core.quit()

    state = {
        'mode': MODE_STATIC_ON if PLUGIN_OK else MODE_GAMMA,
        'x': DEFAULT_X,
        'bg': DEFAULT_BG,
        'size': DEFAULT_SIZE,
        'contrast': DEFAULT_CONTRAST,
        'custom_hz': DEFAULT_CUSTOM_HZ,
        'gamma_idx': 0,
    }
    snapshots = []

    # ---- Stimuli -------------------------------------------------------------
    disc = None
    if PLUGIN_OK:
        # EXACT experiment kwargs, plus explicit contrast so it can be tuned.
        disc = RadialStim(
            win=win, tex=CHECKER_PATTERN, size=state['size'],
            radialCycles=1, texRes=256, opacity=1,
            contrast=state['contrast'], pos=(state['x'], 0.0),
            name='calib_disc', autoLog=False)

    fixation = visual.ShapeStim(
        win=win, name='fixation_cross', vertices='cross',
        size=FIXATION_SIZE, ori=0.0, pos=(0.0, 0.0), anchor='center',
        lineWidth=1.0, colorSpace='rgb', lineColor='white', fillColor='black',
        opacity=None, depth=0.0, interpolate=True, autoLog=False)

    # Full-screen uniform patch for gamma stepping.
    gamma_patch = visual.Rect(
        win=win, width=aspect, height=1.0, pos=(0, 0),
        lineWidth=0, lineColor=None, fillColor=[-1, -1, -1],
        colorSpace='rgb', autoLog=False)

    readout = visual.TextStim(
        win, text='', font=READOUT_FONT, height=0.021, color='white',
        pos=(0, -0.42), wrapWidth=1.8, alignText='center',
        anchorHoriz='center', autoLog=False)

    flash = visual.TextStim(
        win, text='', font=READOUT_FONT, height=0.030, color='yellow',
        pos=(0, 0.42), alignText='center', anchorHoriz='center',
        autoLog=False)

    # ---- Loop state ----------------------------------------------------------
    frame_idx = 0            # resets on every mode change, like a trial onset
    flash_frames = 0
    flash_text = ''
    intervals = deque(maxlen=60)
    clock = core.Clock()
    clock.reset()
    running = True

    def set_mode(new_mode):
        """Switch mode and reset flicker phase, mirroring per-trial reset."""
        if MODE_NEEDS_PLUGIN[new_mode] and not PLUGIN_OK:
            return None, 'RadialStim unavailable - mode blocked'
        return new_mode, None

    # ---- Fine knobs: one code path for press and for auto-repeat -------------
    def adjust_bg(delta):
        state['bg'] = round(clamp(state['bg'] + delta, -1.0, 1.0), 4)
        win.color = [state['bg']] * 3

    def adjust_contrast(delta):
        state['contrast'] = round(
            clamp(state['contrast'] + delta, 0.0, 1.0), 4)

    held_since = {}          # pyglet symbol -> time it went down
    last_repeat = {}         # pyglet symbol -> time of last emitted repeat
    repeat_clock = core.Clock()

    repeat_specs = []
    key_symbol = {}
    if key_state is not None:
        repeat_specs = [
            (pyglet_key.UP, lambda: adjust_bg(+STEP_BG)),
            (pyglet_key.DOWN, lambda: adjust_bg(-STEP_BG)),
            (pyglet_key.C, lambda: adjust_contrast(+STEP_CONTRAST)),
            (pyglet_key.V, lambda: adjust_contrast(-STEP_CONTRAST)),
        ]
        key_symbol = {'up': pyglet_key.UP, 'down': pyglet_key.DOWN,
                      'c': pyglet_key.C, 'v': pyglet_key.V}

    def is_os_autorepeat(name):
        """True when this key is already tracked as held.

        Windows generates its own auto-repeat key events while a key is down,
        and PsychoPy delivers them through event.getKeys() exactly like real
        presses. Without this guard a held key would advance at the OS repeat
        rate AND at our clock-driven rate simultaneously. Only the first press
        of a hold gets through here; the rest are ours to time.
        """
        symbol = key_symbol.get(name)
        return symbol is not None and symbol in held_since

    while running:
        # ---- Input -----------------------------------------------------------
        for key in event.getKeys():
            new_mode = None
            if key == '1':
                new_mode = MODE_STATIC_ON
            elif key == '2':
                new_mode = MODE_STATIC_OFF
            elif key == '3':
                new_mode = MODE_FLICKER_15
            elif key == '4':
                new_mode = MODE_FLICKER_20
            elif key == '5':
                new_mode = MODE_FLICKER_CUSTOM
            elif key == 'g':
                new_mode = MODE_GAMMA

            if new_mode is not None:
                resolved, err = set_mode(new_mode)
                if resolved is None:
                    flash_text, flash_frames = err, 90
                else:
                    state['mode'] = resolved
                    frame_idx = 0
                continue

            if key in ('right',):
                if state['mode'] == MODE_GAMMA:
                    state['gamma_idx'] = min(state['gamma_idx'] + 1,
                                             len(GAMMA_LEVELS) - 1)
                else:
                    state['x'] = round(
                        clamp(state['x'] + STEP_POS, -aspect / 2.0,
                              aspect / 2.0), 4)
            elif key in ('left',):
                if state['mode'] == MODE_GAMMA:
                    state['gamma_idx'] = max(state['gamma_idx'] - 1, 0)
                else:
                    state['x'] = round(
                        clamp(state['x'] - STEP_POS, -aspect / 2.0,
                              aspect / 2.0), 4)
            elif key == 'up':
                if not is_os_autorepeat('up'):
                    adjust_bg(+STEP_BG)
            elif key == 'down':
                if not is_os_autorepeat('down'):
                    adjust_bg(-STEP_BG)
            elif key in ('equal', 'plus', 'add'):
                state['size'] = round(
                    clamp(state['size'] + STEP_SIZE, 0.01, 1.0), 4)
            elif key in ('minus', 'subtract'):
                state['size'] = round(
                    clamp(state['size'] - STEP_SIZE, 0.01, 1.0), 4)
            elif key == 'c':
                if not is_os_autorepeat('c'):
                    adjust_contrast(+STEP_CONTRAST)
            elif key == 'v':
                if not is_os_autorepeat('v'):
                    adjust_contrast(-STEP_CONTRAST)
            elif key == 'f':
                state['custom_hz'] = int(clamp(
                    state['custom_hz'] + STEP_FREQ, 1, 120))
            elif key == 'h':
                state['custom_hz'] = int(clamp(
                    state['custom_hz'] - STEP_FREQ, 1, 120))
            elif key == 's':
                snapshots.append(state_record(state))
                write_json(state, snapshots, resolution, measured)
                flash_text = 'SNAPSHOT {} SAVED'.format(len(snapshots))
                flash_frames = 60
            elif key in ('q', 'escape'):
                running = False

        if not running:
            break

        # ---- Hold-to-repeat: BG and contrast only ----------------------------
        # Clock-driven, not frame-driven, so the rate holds at any refresh.
        if key_state is not None:
            now = repeat_clock.getTime()
            for symbol, apply_delta in repeat_specs:
                if key_state[symbol]:
                    if symbol not in held_since:
                        # First frame down. event.getKeys() already applied the
                        # initial increment above; just start the hold timer.
                        held_since[symbol] = now
                    elif now - held_since[symbol] >= REPEAT_DELAY_S:
                        if now - last_repeat.get(symbol, 0.0) >= \
                                1.0 / REPEAT_RATE_HZ:
                            apply_delta()
                            last_repeat[symbol] = now
                else:
                    held_since.pop(symbol, None)
                    last_repeat.pop(symbol, None)

        # ---- Live parameter application --------------------------------------
        if disc is not None:
            disc.size = state['size']
            disc.contrast = state['contrast']
            disc.pos = (state['x'], 0.0)

        # ---- Draw ------------------------------------------------------------
        mode = state['mode']
        frames = None

        if mode == MODE_GAMMA:
            percent = GAMMA_LEVELS[state['gamma_idx']]
            level = -1.0 + 2.0 * (percent / 100.0)
            gamma_patch.fillColor = [level] * 3
            gamma_patch.draw()
        elif mode == MODE_STATIC_ON:
            disc.draw()
        elif mode == MODE_STATIC_OFF:
            pass                      # background + fixation only
        else:
            if mode == MODE_FLICKER_15:
                frames = FRAMES_15HZ
            elif mode == MODE_FLICKER_20:
                frames = FRAMES_20HZ
            else:
                frames = hz_to_frames(state['custom_hz'])
            if stim_is_on(frame_idx, frames):
                disc.draw()

        # Fixation cross in every mode EXCEPT gamma. In Mode G the screen is a
        # uniform patch being measured by a photometer usually sat at screen
        # centre -- a ~75px cross right under the aperture would corrupt the
        # gamma curve, and everything downstream depends on that curve.
        if mode != MODE_GAMMA:
            fixation.draw()

        # ---- Readout ---------------------------------------------------------
        if len(intervals) >= 2:
            mean_interval = sum(intervals) / float(len(intervals))
            live_hz = (1.0 / mean_interval) if mean_interval > 0 else 0.0
        else:
            live_hz = measured

        if mode == MODE_GAMMA:
            percent = GAMMA_LEVELS[state['gamma_idx']]
            level = -1.0 + 2.0 * (percent / 100.0)
            mode_line = ('GAMMA STEPS  |  level {}/{}  =  {}%  |  '
                         'rgb {:+.2f}  |  8-bit {}  |  cross hidden'.format(
                             state['gamma_idx'] + 1, len(GAMMA_LEVELS),
                             percent, level, int(round(255 * percent / 100.0))))
        elif frames is not None:
            mode_line = ('{}  |  {} frames/cycle  ({} on / {} off)  |  '
                         'realized {:.3f} Hz'.format(
                             mode.upper(), frames, frames // 2,
                             frames - frames // 2, frames_to_hz(frames)))
        else:
            mode_line = mode.upper()

        readout.text = (
            "{}x{}  |  {:.2f} Hz (60-frame avg)  |  PsychoPy {}\n"
            "Mode: {}\n"
            "X: {:.2f} | BG: {:.3f} | Size: {:.2f} | "
            "Contrast: {:.3f} | Freq: {:.2f} Hz".format(
                resolution[0], resolution[1], live_hz, PSYCHOPY_VERSION,
                mode_line,
                state['x'], state['bg'], state['size'],
                state['contrast'], float(state['custom_hz'])))
        readout.draw()

        if flash_frames > 0:
            flash.text = flash_text
            flash.draw()
            flash_frames -= 1

        win.flip()
        intervals.append(clock.getTime())
        clock.reset()
        frame_idx += 1

    # ---- Quit ----------------------------------------------------------------
    final = state_record(state)
    path = write_json(state, snapshots, resolution, measured, final=final)
    win.close()

    print("")
    print("Calibration values written to:")
    print("  {}".format(path))
    print("  {} snapshot(s), final state recorded.".format(len(snapshots)))
    print("  REFERENCE ONLY - the experiment does not read this file.")
    core.quit()


if __name__ == '__main__':
    main()
