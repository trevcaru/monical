# Monical — Monitor Calibration Tool for Vision Science

**Version:** 0.1 (PRD)
**Author:** Trevor Caruso
**License:** MIT
**Repo:** `C:\Users\glopu\Experiments\monical\monical` (GitHub TBD)

---

## 1. Purpose

Monical is a standalone keyboard-driven calibration tool for vision science labs. It renders standard visual stimuli with real-time adjustable parameters, on-screen readout, and JSON snapshot export. The user adjusts parameters while measuring with a photometer or oscilloscope, reads the values off screen, and enters them into their experiment code manually.

Monical does not run experiments, collect data, or apply corrections automatically. It characterizes and verifies.

---

## 2. Dependencies

- **PsychoPy** (required) — stimulus rendering, frame timing, window management. Every vision science lab using Python already has this.
- **psychopy_visionscience** (optional, guarded import) — needed only for the radial checkerboard stimulus. All other modes work without it. Failure reported on the info screen with the pip install command.
- **NumPy** (comes with PsychoPy)
- **argparse** (stdlib) — used for the `--image`, `--preset` and `--text` flags only.
- No other dependencies.

---

## 3. Architecture

Single-file script: `monical.py`. No submodules, no config files, no build step. Run it:

```
python monical.py
```

With a custom PNG texture for stimulus type `[5]` (see §4.5):

```
python monical.py --image assets/texture.png
```

Restoring saved knob settings (see §10):

```
python monical.py --preset presets/preset_2026-09-18_143201.json
```

### 3.1 Screen flow

```
┌─────────────────────┐
│   INTRO / SELECTOR   │  Select stimulus type (1–4), see tutorial,
│                      │  press SPACE to proceed
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│    TEST ROUTINE      │  Stimulus rendered, knobs active,
│                      │  readout visible, snapshots saveable
└─────────────────────┘
```

### 3.2 File output

`monical_YYYY-MM-DD_HHMMSS.json` — one file per session, named from `session_start` and written beside `monical.py`. Example: `monical_2026-09-18_143201.json`.

The name is fixed once at startup and shown on the intro screen, so the operator knows where the session's measurements are going before pressing SPACE. Every `[S]` snapshot and the `[Q]` final write go to that same file, rewritten in full each time.

**Nothing is ever overwritten.** A second run gets its own file; an interrupted session leaves whatever it had already written. Earlier versions wrote a single `calibration_values.json` that each run destroyed.

Contains:

```json
{
  "monical_version": "0.1",
  "session_start": "2026-08-21T14:30:12",
  "session_end": "2026-08-21T14:47:03",
  "monitor_name": "testMonitor",
  "monitor_resolution": [1920, 1080],
  "monitor_width_cm": 59.8,
  "monitor_height_cm": 33.6,
  "color_space": "rgb",
  "units": "height",
  "window_fullscreen": true,
  "vsync": true,
  "vsync_detail": {
    "wait_blanking": true,
    "pyglet_vsync": true,
    "context_get_vsync": false
  },
  "startup_refresh_hz": 239.97,
  "final_rolling_refresh_hz": 239.94,
  "final_rolling_refresh_sd_ms": 0.1203,
  "total_dropped_frames": 0,
  "psychopy_version": "2024.2.4",
  "python_version": "3.11.0 ...",
  "platform": "win32",
  "has_radial_stim": true,
  "image_path": null,
  "preset_path": null,
  "output_file": "monical_2026-08-21_143012.json",
  "viewing_distance_cm": 40.0,
  "stimulus_type": "radial_checkerboard",
  "snapshots": [
    {
      "snapshot_number": 1,
      "timestamp": "2026-08-21T14:32:01",
      "rolling_refresh_hz": 239.94,
      "dropped_frames_total": 0,
      "stimulus_type": "radial_checkerboard",
      "mode": "static_on",
      "dual_stimulus": false,
      "x_position": 0.66,
      "y_position": 0.00,
      "background_gray": 0.012,
      "disc_size": 0.225,
      "contrast": 1.000,
      "custom_frequency_hz": 15,
      "visual_angle_deg": 6.43,
      "eccentricity_deg": 28.57,
      "stimulus_specific": {}
    }
  ],
  "final": { ... }
}
```

`stimulus_specific` holds per-type parameters (SF, ori, phase, SD, R, G, B, alpha — whichever apply), plus the mode-local values: `gamma_level` in gamma steps, `grid_position` and coordinates in spatial uniformity.

Snapshots taken in a flicker mode also carry `flicker_frames_per_cycle` and `flicker_realized_hz`.

**Refresh rate vs frame rate.** `startup_refresh_hz` is the one-shot `getMsPerFrame` measurement taken before the intro screen. `final_rolling_refresh_hz` is the mean of actual flip-to-flip intervals over the last 120 frames, which is a *loop* rate — it equals the display's refresh rate only while vsync holds `flip()` to the retrace, which is why `vsync` is recorded beside it. If the two figures diverge by more than 5 Hz the tool warns on the console, since that usually means the startup measurement fell back to a default and every frame-count frequency in the session is built on a wrong number.

A frame counts toward `total_dropped_frames` when its flip-to-flip interval exceeds 1.5× the rolling median interval.

---

## 4. Stimulus types

Selected on the intro screen. Each type has universal parameters plus its own.

### 4.1 Radial checkerboard

**Requires:** psychopy_visionscience (guarded)

Standard SSVEP stimulus. Hard-edged circular disc, dartboard pattern.

**Construction:**
```python
pattern = np.ones((4, 4))
pattern[::2, ::2] = -1
pattern[1::2, 1::2] = -1

RadialStim(win=win, tex=pattern, size=size, radialCycles=1,
           texRes=256, opacity=1, contrast=contrast,
           pos=(x, y), autoLog=False)
```

No mask, no angularCycles. This matches the Odegaard Lab SSVEP experiment's v1 construction exactly.

**Stimulus-specific parameters:** None beyond universal. The construction is locked to the standard form. Contrast is adjustable via the universal knob.

### 4.2 Gabor patch

Most common stimulus in attention and perception research. Sinusoidal grating windowed by a Gaussian envelope.

**Construction:**
```python
GratingStim(win=win, tex='sin', mask='gauss',
            size=size, sf=sf, ori=ori, phase=phase,
            contrast=contrast, pos=(x, y), autoLog=False)
```

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Spatial frequency | `[Z/X]` | ±0.5 cycles | 4.0 | 0.5–50.0 |
| Orientation | `[R/T]` | ±5° | 0.0 | 0–360 |
| Phase | `[E/W]` | ±0.05 | 0.5 | 0.0–1.0 |
| Envelope SD | `[D/A]` | ±0.01 | 0.06 | 0.01–1.0 |

### 4.3 Sinusoidal grating

Full-field or sized grating without Gaussian envelope. Used for contrast sensitivity, spatial frequency tuning.

**Construction:**
```python
GratingStim(win=win, tex='sin', mask=None,
            size=size, sf=sf, ori=ori, phase=phase,
            contrast=contrast, pos=(x, y), autoLog=False)
```

**Stimulus-specific parameters:** Same as Gabor minus envelope SD.

### 4.4 Uniform patch

Solid rectangle at adjustable color. The color calibration surface. Use for gamma per-channel, channel independence, spatial uniformity, and any measurement requiring a uniform field.

**Construction:**
```python
Rect(win=win, width=w, height=h, fillColor=[r, g, b],
     opacity=alpha, pos=(x, y), autoLog=False)
```

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Red | `[R/T]` | ±0.001 | 0.0 | -1.0–1.0 |
| Green | `[E/W]` | ±0.001 | 0.0 | -1.0–1.0 |
| Blue | `[D/A]` | ±0.001 | 0.0 | -1.0–1.0 |
| Alpha | `[Z/X]` | ±0.01 | 1.0 | 0.0–1.0 |

Note: PsychoPy color range is -1 to 1. Mid-gray = 0. Black = -1. White = 1.

### 4.5 Custom PNG

User-supplied texture loaded from a PNG file. For calibrating with experiment-specific stimuli, verifying custom patterns, or checking rendering of imported images.

**Construction:**
```python
ImageStim(win=win, image=filepath, size=size,
          contrast=contrast, opacity=alpha,
          pos=(x, y), autoLog=False)
```

**File selection:** Pass the image path as a command-line argument:

```
python monical.py --image assets/texture.png
```

If `--image` is provided, option `[5]` appears on the intro screen selector. If not provided, option `[5]` still appears but uses a generated 256×256 NumPy checkerboard test pattern (alternating black/white squares, 8×8 grid). No file dialogs, no mouse interaction — consistent with §13.

The path is stored in state and written to snapshots for reproducibility. If the file doesn't exist at runtime, print an error and fall back to the generated pattern.

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Alpha | `[Z/X]` | ±0.01 | 1.0 | 0.0–1.0 |

All universal parameters apply: position, size, contrast, background, flicker, viewing distance.

**Stimulus-specific snapshot fields:** `{"filepath": "...", "alpha": 1.0}`

### 4.6 Text stimulus

Letter strings for legibility, acuity and text-rendering checks. Monospaced so glyph width is uniform and letter height maps predictably onto the size knob.

**Construction:**
```python
TextStim(win=win, text=text_string, font='Courier New',
         height=size, color=[r, g, b], opacity=alpha,
         contrast=contrast, pos=(x, y), autoLog=False)
```

`height` is the universal size knob, so the degrees on readout line 3 describe the letter height.

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Preset string | `[B/N]` | cycle fwd/back | `ABCDEF` | see below |
| Red | `[R/T]` | ±0.001 | 0.0 | -1.0–1.0 |
| Green | `[E/W]` | ±0.001 | 0.0 | -1.0–1.0 |
| Blue | `[D/A]` | ±0.001 | 0.0 | -1.0–1.0 |
| Alpha | `[Z/X]` | ±0.01 | 1.0 | 0.0–1.0 |

Colour uses the uniform patch's bindings unchanged. String cycling takes its own `[B]`/`[N]` rather than overloading `[R/T]`, so no key means two things.

Preset strings: `ABCDEF`, `abcdef`, `123456`, `XXXXXX`, `oOoOoO`. A custom string is supplied with `--text "MYSTRING"`, which appends it to the cycle and selects it at startup — Monical has no on-screen text entry, and adding one would need a widget (§13).

PsychoPy's `TextStim` has **no `letterSpacing` parameter**, so there is no letter-spacing knob.

**Readout line 5:** `Text: 'ABCDEF' | R: 0.000 | G: 0.000 | B: 0.000 | Alpha: 1.000`

**Stimulus-specific snapshot fields:** `{"text_string": "ABCDEF", "font": "Courier New", "alpha": 1.0, "r": 0.0, "g": 0.0, "b": 0.0}`

Note the colour defaults are all 0.0, which is mid-gray — the same value as the default background, so at defaults the glyphs are invisible. Drive the channels up or the background down before expecting to see anything. The uniform patch (§4.4) behaves the same way for the same reason.

---

## 5. Universal parameters

Active in all stimulus modes.

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| X position | `[LEFT/RIGHT]` | ±0.005 | 0.66 | -1.0–1.0 |
| Y position | `[UP/DOWN]` | ±0.005 | 0.00 | -0.5–0.5 |
| Background gray | `[PAGEUP/PAGEDN]` | ±0.001 | 0.000 | -1.0–1.0 |
| Disc/patch size | `[+/-]` | ±0.01 | 0.225 | 0.01–2.0 |
| Contrast | `[C/V]` | ±0.001 | 1.000 | 0.0–1.0 |
| Custom frequency | `[F/J]` | ±1 Hz | 15 | 1–120 |
| Viewing distance | `[;/']` | ±1 cm | 40 | 1–500 |

Arrows move the stimulus; the page keys adjust the background behind it.

### 5.1 Key repeat

X position, Y position, background gray, contrast, and color channels (R/G/B): after 1 second of holding the key, auto-repeat at ~60 increments per second — roughly one increment per frame at 60 Hz, one every four frames at 240 Hz. The coarser knobs (size, custom frequency, viewing distance) are single-press.

Repeat is measured against the moment the key went down, not against the last increment emitted. An increment can only land on a frame boundary, so "wait 1/rate since the last one" rounds every interval up to a whole frame and beats the realized rate below the target; accumulating against the hold start lets a short interval compensate for a long one.

Two modes claim the arrow keys for themselves — gamma steps takes LEFT/RIGHT, spatial uniformity takes all four (§6.2, §6.4). While those modes are active the arrows do not repeat and do not move the stimulus. The page keys are never claimed, so background gray stays adjustable in every mode.

### 5.2 Display precision

- Background gray, contrast, R, G, B, alpha: 3 decimal places
- Position, size: 2 decimal places
- Frequency: shows realized Hz from integer frame count (not requested)
- Visual angle: 2 decimal places, updates live when viewing distance or size changes

---

## 6. Modes

Toggled by number keys. Active across all stimulus types.

| Key | Mode | Description |
|-----|------|-------------|
| `[1]` | Static ON | Stimulus rendered at current position, no flicker. Photometer: measure ON luminance. |
| `[2]` | Static OFF | Background + fixation only. Photometer: measure OFF/background luminance. |
| `[3]` | Flicker 15 Hz | 16-frame cycle at 240 Hz. Oscilloscope check. |
| `[4]` | Flicker 20 Hz | 12-frame cycle at 240 Hz. Oscilloscope check. |
| `[5]` | Flicker custom | Uses current custom frequency value. Shows realized Hz. |
| `[G]` | Gamma steps | Full-screen uniform patch, 11 levels (0%–100%). LEFT/RIGHT to step. Fixation cross hidden. |
| `[7]` | Dual stimulus | Two stimuli at ±X eccentricity simultaneously. Matches two-stimulus experiment layout. |
| `[8]` | Spatial uniformity | Uniform patch movable to a 3×3 grid (center, corners, midpoints). Arrow keys move between grid positions. |

Non-mode action keys, active throughout the test routine:

| Key | Action |
|-----|--------|
| `[S]` | Snapshot to the session file |
| `[P]` | Save the current knobs as a preset (§10) |
| `[F12]` | Save a PNG of the current frame (§11) |
| `[A]` | Start or cancel the auto gamma sweep, gamma mode only (§6.5) |
| `[Q]` | Quit, writing final state |

### 6.1 Flicker logic

```python
def stim_is_on(frame_idx, frames):
    return (frame_idx % frames) < (frames // 2)
```

Stateless, pure in frame_idx. Phase resets on every mode switch. Identical to the SSVEP experiment's drive logic.

Custom frequency converts to nearest integer frame count at the detected refresh rate. Readout shows the realized frequency, not the requested one.

### 6.2 Gamma steps

Full-screen uniform gray patch. 11 levels: -1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0 (PsychoPy units). LEFT/RIGHT to step. Current level shown on screen.

Fixation cross is **hidden** in this mode — the photometer goes at screen center.

Snapshots in this mode include `gamma_level` in `stimulus_specific`.

### 6.3 Dual stimulus mode

Renders two instances of the current stimulus type at positions (x, y) and (-x, y). Both flicker at the same frequency if in a flicker mode. For verifying the full experiment display load.

### 6.4 Spatial uniformity mode

Renders the uniform patch (regardless of selected stimulus type) at preset grid positions. Arrow keys step through: center, top-left, top-center, top-right, mid-left, mid-right, bottom-left, bottom-center, bottom-right. Snapshot at each position to characterize panel uniformity.

### 6.5 Auto gamma sweep

`[A]` in gamma steps runs the 11-level ramp unattended so the operator can keep both hands on the photometer.

- Starts at level 1 and steps to level 11.
- Dwells 2.0 s at each level before reading, giving the panel and the probe time to settle. The dwell is wall clock, not frame count, so it holds at 2 s on any refresh rate.
- Takes a snapshot automatically at each level, into the session file. A completed sweep therefore adds exactly 11 snapshots.
- The readout shows progress and the countdown: `Auto gamma: level 3/11 -- settling (1.2s)`.
- `[A]` again or `[ESC]` cancels mid-sweep. While a sweep is running `[ESC]` cancels rather than quitting, so a mistimed press cannot end the session mid-ramp.
- On completion or cancellation the level the operator was on before `[A]` is restored.

The reading belongs to the level that has just settled, so the snapshot is taken **before** the index advances. Manual `LEFT`/`RIGHT` stepping is ignored while a sweep is running.

`[A]` is an envelope-SD knob on the Gabor and a blue-channel knob on the uniform patch. Gamma mode claims it the same way it claims `LEFT`/`RIGHT`, so starting a sweep cannot also nudge a stimulus parameter underneath it.
---

## 7. Visual angle calculator

Active in all modes. Uses the current viewing distance with the stimulus size and position to compute two different angles in degrees.

**Size — an extent.** The stimulus straddles the line of sight, half falling either side, so the extent is halved and the resulting angle doubled:

```
angle_deg = 2 * atan(size_cm / (2 * distance_cm)) * (180 / pi)
```

**Eccentricity — a displacement.** The offset from fixation falls entirely on one side, so there is no factor of 2:

```
ecc_deg = atan(x_cm / distance_cm) * (180 / pi)
```

Using the extent formula for eccentricity overstates it, and the error grows with distance from fixation: at x = 0.66 height units on a 33 cm-tall panel at 40 cm it reports 30.46° against the correct 28.57°, and at x = 1.0 it reports 44.83° against 39.52°.

Where `size_cm` and `x_cm` are derived from the stimulus size and x position in height units and the monitor's physical height. If physical monitor dimensions aren't detectable, both readouts show `--` rather than a guess.

Readout shows both stimulus size (degrees) and eccentricity (degrees) on screen at all times.

---

## 8. On-screen readout

Bottom center, small monospace text, updates every frame. Adapts to the current stimulus type.

```
Line 1: [resolution] | [refresh Hz avg] | PsychoPy [ver] | Dist: [cm] cm
Line 2: Mode: [name] | Stim: [type]
Line 3: X: [val] | Y: [val] | Size: [val] ([deg]°) | Ecc: [deg]°
Line 4: BG: [val] | Contrast: [val] | Freq: [realized] Hz ([frames] frames, [duty]% duty)
Line 5: [stimulus-specific params, e.g. SF: 4.0 | Ori: 0 | Phase: 0.50]
```

Duty cycle is `(frames // 2) / frames`, the same split `stim_is_on` uses. Only an even frame count can give 50%; an odd one puts the shorter half ON, so 3 frames reads `33% duty`. In a non-flicker mode the field is marked `idle` and shows what the standing custom setting would produce.

Line 3 carries pixel coordinates beside the height units, derived from the window:

```
px_x = int(x_pos * win_height + win_width / 2)
px_y = int(y_pos * win_height + win_height / 2)
px_size = int(size * win_height)
```

Height units scale by screen HEIGHT on both axes, so both coordinates use `win_height`; only the origin offset differs. Note `px_y` grows downward while PsychoPy's `+y` is up, so a positive `y_pos` reports a pixel row below centre. Degrees need the monitor's physical size and read `--` without it; pixels only need the window, so they are always available.

Line 2 ends with the session's output filename.

### 8.1 Hiding the readout

**`[H]`** toggles the readout. It hides *only* the multi-line readout text — stimulus, fixation cross, the gamma patch and the bottom status bar (§8.2) all keep rendering. For photometer readings and screenshots with no text overlay. Default visible; tracked as `hud_visible`.

Custom-frequency-down moved from `[H]` to `[J]` to free the key, so the frequency pair is `[F/J]` (§5).

### 8.2 Bottom status bar

A separate single line at the very bottom, below the readout, in smaller dimmer text so the two do not read as one block. **It is always drawn and does NOT hide with `[H]`.**

```
[H] Text: ON | [M] Menu: OFF | [F/J] Custom Hz: 15 | Mode: static_on | File: monical_2026-09-18_143201.json
```

It updates live and carries:

- `[H] Text: ON/OFF` — whether the readout is visible, with the key that changes it
- `[M] Menu: ON/OFF` — whether the keybinding overlay is showing
- `[F/J] Custom Hz` — the current custom frequency **and the keys that adjust it**. This is the discoverability mode 5 otherwise lacks: nothing else on screen says how to change the rate it flickers at
- the mode name
- the session output filename, truncated from the left when long

The point is that even with the readout hidden, the operator can still see which toggles are on, what the custom rate is, and where the data is going.

### 8.3 Keybinding menu overlay

`[M]` toggles a reference card listing every binding for the current stimulus type: a dark panel at about 60% of the screen, centred, at 88% opacity so **the stimulus keeps rendering and stays visible behind it**.

```
KEYBINDINGS -- Text / letter string

MOVEMENT:  LEFT/RIGHT = X position | UP/DOWN = Y position
DISPLAY:   PAGEUP/DN = Background | +/- = Size | C/V = Contrast
FREQUENCY: F/J = Custom Hz | ;/' = Viewing distance
MODES:     1=ON  2=OFF  3=15Hz  4=20Hz  5=Custom
           G=Gamma  7=Dual  8=Uniformity
ACTIONS:   S=Snapshot  P=Preset  F12=Screenshot
           H=Toggle HUD  M=This menu  Q=Quit

THIS STIMULUS:
  B/N = Cycle string | R/T = Red | E/W = Green | D/A = Blue | Z/X = Alpha

[M] or [ESC] to dismiss
```

The `THIS STIMULUS` block changes with the selected type, and gamma steps and spatial uniformity add a line for the keys those modes take over. Knobs stay live while the card is up, so a value can be adjusted while reading how.

**`[ESC]` is claimed in order:** dismiss the menu, else cancel a running auto gamma sweep, else quit. Quitting is last so neither overlay can be closed by accidentally ending the session.

Line 5 for `custom_png` shows:

```
File: [filename] | Alpha: [a:.3f]
```

Filename only, not the full path — the path can be arbitrarily long and Line 5 is a single readout line. The full path is recorded in the snapshot.

---

## 9. Intro screen

White text on black background.

**Section 1 — System info:**
```
MONICAL — Monitor Calibration Tool
───────────────────────────────────
Monitor:    [resolution] @ [refresh Hz]
PsychoPy:   [version]
Plugin:     psychopy_visionscience [OK / FAILED — pip install psychopy-visionscience]
```

**Section 2 — Stimulus selector:**
```
SELECT STIMULUS TYPE:
  [1] Radial checkerboard (SSVEP standard)
  [2] Gabor patch (attention/perception)
  [3] Sinusoidal grating (contrast/SF tuning)
  [4] Uniform patch (color/luminance calibration)
  [5] Custom PNG (your own texture)
  [6] Text / letter string
```

**Section 3 — Workflow tutorial (adapts to selection):**

Shows the recommended calibration workflow and the keybindings relevant to the selected stimulus type. Updates live as the user presses 1–6.

Custom PNG workflow block:

```
Load your experiment texture, verify rendering at target
size/position/contrast.
```

**Section 4 — Proceed:**
```
Press SPACE to begin.
```

---

## 10. Presets

A preset is a snapshot of the knobs, saved so a rig can be brought back to a known configuration without re-dialling every value.

**Save:** `[P]` during the test routine writes `presets/preset_YYYY-MM-DD_HHMMSS.json`, creating `presets/` if needed. The readout confirms with the filename.

**Load:** `--preset path/to/preset.json` applies the values before the main loop starts, and opens the intro selector on the stimulus type the preset was saved from. The operator can still change type before pressing SPACE; their choice wins.

```
python monical.py --preset presets/preset_2026-09-18_143201.json
```

A preset carries the stimulus, not the rig or the run. These keys are excluded: `frame_idx` and `snapshots` (live loop bookkeeping), `aspect` (comes from the window), and `image_path` (comes from `--image`).

**Compatibility is deliberate in both directions.** Keys the preset omits keep their defaults, so a preset written by an older version still loads. Keys it carries that this version no longer recognises are ignored with a console note. Neither is an error — presets outlive tool versions.

An unreadable or malformed preset prints an error and the session continues with defaults. A preset is a convenience; a broken one should cost you the preset, not the calibration session.

`presets/` is gitignored.

---

## 11. Screenshots

`[F12]` saves a PNG of the frame currently on screen to `screenshots/monical_screenshot_YYYY-MM-DD_HHMMSS.png`, creating `screenshots/` if needed. The readout confirms with the filename.

Implemented with `win.getMovieFrame()` followed by `win.saveMovieFrames()`. `getMovieFrame()` reads the front buffer, which is the completed frame the operator is looking at — the loop flips at the end of each pass, so by the time keys are polled the front buffer holds it.

For documenting a configuration visually, or capturing an on-screen readout to paste into lab notes. `screenshots/` is gitignored.

---

## 12. Monitor dimension warning

Every visual angle derives from the Monitor object's physical size, which PsychoPy takes from its stored width — not from the display. A stale or default value produces angles that look plausible and are wrong.

At startup the derived screen height is checked. Outside **15–80 cm**, or absent entirely, the intro screen shows a yellow warning and the console prints the same line:

```
WARNING: monitor height 12.6 cm looks wrong. Set physical dimensions in
PsychoPy Monitor Center. Visual angles will be incorrect.
```

It does not block. The session runs; the angles are simply not to be trusted until the Monitor is fixed.

The session JSON records `"monitor_dimension_warning": true/false`, so a reader can tell whether the angles in a file were taken under a suspect geometry. An absent height sets the flag too: unavailable angles and confidently wrong ones both warrant the warning, and the second is worse.

---

## 13. What Monical is not

- Not an experiment. No EEG, eye tracking, trials, conditions, CSV data.
- Not a monitor profiler. It doesn't build or apply gamma tables — PsychoPy Monitor Center does that. Monical helps you collect the measurements.
- Not automatic. No photodiode input, no closed-loop correction. You read the photometer, you adjust the knob.
- No GUI widgets. Keyboard + on-screen text only.
- No mouse. No file dialogs. Image files are passed via command-line arguments.

---

## 14. Provenance

Seed file: `tools/test_stimulus.py` from the Odegaard Lab covert/overt SSVEP experiment repo (`covert_overt_2_stim`). The radial checkerboard construction, flicker logic, and JSON snapshot format originate there. Monical generalizes the tool to arbitrary stimulus types and adds color calibration, visual angle computation, spatial uniformity checking, and multi-stimulus verification.

---

## 15. Open questions

1. **Key bindings for stimulus-specific params.** The current mapping reuses R/T, E/W, D/A, Z/X across stimulus types with different meanings. This is compact but potentially confusing. Alternative: use a consistent semantic mapping and show a legend. Decide during implementation.

2. **Monitor physical dimensions.** Needed for visual angle. Auto-detect if possible (PsychoPy's Monitor object can store this). Fall back to manual entry on the info screen.

3. **Multiple monitor support.** `screen=0` hardcoded. Add a selector if labs routinely calibrate secondary displays.

4. **Repo structure.** Single file for now. If features grow (presets, automated gamma fitting, report generation), split into a package.
