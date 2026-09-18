# Monical — User Manual

Version 0.1. For the design rationale, see [PRD.md](PRD.md); this document is
how to operate the tool.

---

## 1. What Monical is

Monical renders standard vision-science stimuli fullscreen with every parameter
adjustable from the keyboard, shows a live readout of those parameters, and
exports them to JSON so you can transcribe them into your experiment code.

It does not run experiments, collect data, or correct anything — you point the
photometer, you turn the knob, you save the snapshot.

---

## 2. Installation

| Dependency | Required | Needed for |
|---|---|---|
| PsychoPy | yes | everything |
| NumPy | yes (ships with PsychoPy) | textures, frame statistics |
| `psychopy_visionscience` | no | radial checkerboard only |

Install the optional plugin only if you need stimulus type `[1]`. Note the pip
name is hyphenated while the import is not:

```bash
pip install psychopy-visionscience
```

Run it:

```bash
python monical.py
python monical.py --image assets/texture.png
python monical.py --preset presets/preset_2026-09-18_143201.json
```

`--image PATH` supplies the texture for stimulus type `[5]`. Without it, `[5]`
still works and uses a generated 256×256 checkerboard (8×8 cells). A path that
does not exist prints an error and falls back to the same generated pattern, so
a typo never ends the session.

`--preset PATH` restores knob settings saved earlier with `[P]` (§5f).

There is no config file, no build step, and no installer. Each session writes
one file, `monical_YYYY-MM-DD_HHMMSS.json`, next to the script — a new one
every run, so nothing you measured is ever overwritten.

---

## 3. Startup screen

White text on black. Four blocks:

1. **System info** — resolution, measured refresh rate, PsychoPy version, and
   whether `psychopy_visionscience` imported. A failure here is reported with
   the pip command, not a crash.
2. **Stimulus selector** — press `1`–`5` to choose:

   ```
   [1] Radial checkerboard (SSVEP standard)
   [2] Gabor patch (attention/perception)
   [3] Sinusoidal grating (contrast/SF tuning)
   [4] Uniform patch (color/luminance calibration)
   [5] Custom PNG (your own texture)
   ```

3. **Workflow tutorial** — the recommended procedure and key legend for
   whichever type is selected. It redraws as you press `1`–`5`.
4. **`Press SPACE to begin.`**

The header also shows `Output:` — the filename this session will write to —
and `Preset:` when one was loaded with `--preset`. Note the output name before
you start; it is fixed for the whole session.

`Q` or `ESC` here aborts without writing a file. You cannot change stimulus
type after `SPACE` — restart to switch.

If you select `[1]` without the plugin installed, the screen warns you and
still lets you proceed; the disc simply will not draw.

---

## 4. Keybindings

### Universal — active in every mode and stimulus type

| Section | Keys | Step | Range | Repeat |
|---|---|---|---|---|
| Stimulus movement — X | `LEFT` / `RIGHT` | ±0.005 | −1.0 to 1.0 | hold |
| Stimulus movement — Y | `UP` / `DOWN` | ±0.005 | −0.5 to 0.5 | hold |
| Background gray | `PAGEUP` / `PAGEDN` | ±0.001 | −1.0 to 1.0 | hold |
| Size | `+` / `-` | ±0.01 | 0.01 to 2.0 | single press |
| Contrast | `C` / `V` | ±0.001 | 0.0 to 1.0 | hold |
| Custom frequency | `F` / `H` | ±1 Hz | 1 to 120 | single press |
| Viewing distance | `;` / `'` | ±1 cm | 1 to 500 | single press |

Arrows move the stimulus; the page keys adjust the background behind it. The
first key of each pair increases the value. Size also accepts the numpad `+`
and `-`.

**Hold to scroll.** Keys marked *hold* auto-repeat after a 1-second delay, then
run at ~60 increments per second. On a 60 Hz panel that is one step per frame,
which is the ceiling — expect slightly under 60/s there. On a 240 Hz panel it
is one step every four frames.

All values are in PsychoPy units: position and size in `height` units (1.0 =
full screen height), color and contrast in `rgb` (−1 = black, 0 = mid-gray,
+1 = white).

### Modes

| Key | Mode |
|---|---|
| `1` | Static ON — stimulus drawn every frame |
| `2` | Static OFF — background and fixation only |
| `3` | Flicker 15 Hz |
| `4` | Flicker 20 Hz |
| `5` | Flicker at the current custom frequency |
| `G` | Gamma steps — fullscreen patch, 11 levels |
| `7` | Dual stimulus — toggle, not a mode |
| `8` | Spatial uniformity — patch on a 3×3 grid |

`6` is unassigned. Switching mode resets the flicker phase to frame 0.

`7` is a **toggle** that composes with whatever mode is active: turn it on
during `3` and you get two copies flickering in phase at 15 Hz. Every other
mode key replaces the current mode.

### Actions

| Key | Action |
|---|---|
| `S` | Save a snapshot and rewrite the session JSON. Confirms on screen. |
| `P` | Save the current knobs as a preset in `presets/`. Confirms with the filename. |
| `F12` | Save a PNG of the current frame to `screenshots/`. Confirms with the filename. |
| `A` | Gamma mode only: start or cancel the auto sweep (§5g). |
| `Q` or `ESC` | Write final state plus all snapshots, then exit. |

While an auto gamma sweep is running, `ESC` cancels the sweep instead of
quitting — a mistimed press cannot end the session mid-ramp.

### Keys that two modes take over

In **gamma steps** (`G`), `LEFT` / `RIGHT` step the gray level instead of
moving the stimulus. In **spatial uniformity** (`8`), all four arrows move the
patch around the grid. While those modes are active the arrows do not move the
stimulus and do not auto-repeat.

`PAGEUP` / `PAGEDN` are never taken over, so background gray stays adjustable
in every mode.

The fixation cross is hidden in both of those modes, because the photometer
sits where the cross would be.

### Stimulus-specific keys

The same four key pairs mean different things per stimulus type. The active
legend is always on HUD line 5.

**Gabor patch**

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Spatial frequency | `Z` / `X` | ±0.5 | 4.0 | 0.5–50.0 |
| Orientation | `R` / `T` | ±5° | 0.0 | wraps 0–360 |
| Phase | `E` / `W` | ±0.05 | 0.5 | 0.0–1.0 |
| Envelope SD | `D` / `A` | ±0.01 | 0.06 | 0.01–1.0 |

**Sinusoidal grating** — same as Gabor without the envelope:

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Spatial frequency | `Z` / `X` | ±0.5 | 4.0 | 0.5–50.0 |
| Orientation | `R` / `T` | ±5° | 0.0 | wraps 0–360 |
| Phase | `E` / `W` | ±0.05 | 0.5 | 0.0–1.0 |

**Uniform patch**

| Param | Keys | Step | Default | Range | Repeat |
|---|---|---|---|---|---|
| Red | `R` / `T` | ±0.001 | 0.0 | −1.0–1.0 | hold |
| Green | `E` / `W` | ±0.001 | 0.0 | −1.0–1.0 | hold |
| Blue | `D` / `A` | ±0.001 | 0.0 | −1.0–1.0 | hold |
| Alpha | `Z` / `X` | ±0.01 | 1.0 | 0.0–1.0 | single press |

**Custom PNG**

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Alpha | `Z` / `X` | ±0.01 | 1.0 | 0.0–1.0 |

**Radial checkerboard** — no extra keys. The construction is locked to the
SSVEP standard form; use the universal contrast knob.

---

## 5. Calibration workflows

Gamma-calibrate the display (workflow b) before any luminance work. Everything
else assumes a linearized panel.

### a) Luminance calibration with a photometer

Measures the ON and OFF luminance of the stimulus at its experiment position,
and lets you trim them to match.

1. Start with your experiment's stimulus type. Set `X`, `Y` and size to the
   values your experiment uses (arrows, `+`/`-`). Check HUD line 3 — the size
   and eccentricity in degrees should match your protocol.
2. Set viewing distance with `;` / `'` to match the rig.
3. Press `1` (static ON). Put the photometer on the stimulus. Record.
4. Press `2` (static OFF). Same spot, do not move the probe. Record.
5. For a nominally zero-mean stimulus the two should match. If they do not,
   trim `PAGEUP`/`PAGEDN` (background) or `C`/`V` (contrast) until they do.
   Hold the key to scroll.
6. Press `S`. Repeat from step 3 at each stimulus position your experiment
   uses.

### b) Gamma curve measurement

Produces the 11 points you enter into PsychoPy Monitor Center.

1. Press `G`. The screen fills with a uniform patch and the fixation cross
   disappears. Put the photometer at screen center.
2. `LEFT` / `RIGHT` step through the 11 levels. HUD line 2 shows which:

   | Step | rgb | 8-bit |
   |---|---|---|
   | 1/11 | −1.0 | 0 |
   | 2/11 | −0.8 | 25 |
   | 3/11 | −0.6 | 51 |
   | 4/11 | −0.4 | 76 |
   | 5/11 | −0.2 | 102 |
   | 6/11 | +0.0 | 128 |
   | 7/11 | +0.2 | 153 |
   | 8/11 | +0.4 | 178 |
   | 9/11 | +0.6 | 204 |
   | 10/11 | +0.8 | 230 |
   | 11/11 | +1.0 | 255 |

3. Press `S` at every level. Each snapshot records `gamma_level` and
   `gamma_step_index` in `stimulus_specific`.

   Or press `A` to let the tool do it — see workflow (g). With both hands on
   the probe, that is usually the better option.
4. Let the panel settle before reading each step — LCDs drift for a second or
   two after a large luminance change.
5. Fit the curve in Monitor Center. Monical does not build or apply gamma
   tables.

### c) Verifying flicker timing with an oscilloscope

1. Put a photodiode on the stimulus. Press `1` first to confirm it is aimed
   correctly.
2. Press `3` (15 Hz) or `4` (20 Hz). **Read the realized frequency from HUD
   line 4, not the mode name.** It shows `Freq: 14.998 Hz (16 frames, 8 on /
   8 off)` — frames per cycle, and the ON/OFF split.
3. For any other rate, set it with `F` / `H` and press `5`.
4. Confirm the scope trace matches the realized Hz and that the duty cycle is
   symmetric.

Frequencies are integer frame counts, so only divisors of the refresh rate are
exactly achievable. At 240 Hz, 15 Hz is 16 frames and 20 Hz is 12 — both exact
and symmetric. At 60 Hz the grid is coarse and odd counts are asymmetric:
20 Hz becomes 3 frames, 1 on and 2 off, a 33% duty cycle. Requesting 17 Hz at
60 Hz yields 4 frames — about 15 Hz. Always transcribe the realized value.

### d) Spatial uniformity check

1. Press `8`. A patch appears at screen center; the fixation cross is hidden.
   This uses the uniform patch whatever stimulus type you started with.
2. Set the patch color with `R`/`T`, `E`/`W`, `D`/`A` and its size with
   `+`/`-` before you start moving it — resizing changes the grid coordinates,
   because corner cells sit as far out as the patch fits without clipping.
3. Arrow keys move between the nine cells. HUD line 2 names the cell and gives
   its coordinates.
4. Photometer each cell, press `S` at each. Snapshots record
   `grid_position`, `grid_x`, `grid_y`, and — when your session type is not
   the uniform patch — `patch_r/g/b/alpha`, so the record describes what you
   actually measured.
5. Compare the nine readings. Centre-to-corner falloff of a few percent is
   normal for LCD; more than that constrains where you can place stimuli.

### e) Channel independence

Checks whether the panel's channels sum linearly.

1. Select stimulus type `[4]` (uniform patch) at startup. Press `1`.
2. Zero all three channels: `R`/`T`, `E`/`W`, `D`/`A` all to 0.000. Hold to
   scroll; HUD line 5 shows all three to three decimals.
3. Drive red alone to +1.0. Photometer, press `S`. Return it to 0.
4. Repeat for green, then blue.
5. Drive all three to +1.0 together. Photometer, press `S`.
6. The combined reading should equal the sum of the three single-channel
   readings. A shortfall means channel interaction and your color calibration
   cannot assume additivity.

### f) Saving and reusing a configuration

Once a rig is dialled in, save it so the next session starts there.

1. Set every knob the way you want it.
2. Press `P`. The readout confirms `Preset saved: preset_2026-09-18_143201.json`
   and the file lands in `presets/`.
3. Next session, pass it back:

   ```bash
   python monical.py --preset presets/preset_2026-09-18_143201.json
   ```

The intro screen opens on the stimulus type the preset was saved from, and
shows `Preset:` in the header so you can confirm it loaded. You can still pick
a different type before `SPACE` — your choice at the selector wins.

A preset holds the stimulus settings, not the rig: window aspect, the
`--image` path, and the live snapshot list are excluded. Presets are
forward and backward compatible — missing keys fall back to defaults, and keys
this version does not recognise are ignored with a console note. A corrupt
preset prints an error and the session continues with defaults rather than
dying.

Use `F12` at any point to capture a PNG of the screen into `screenshots/`,
which is useful for pasting a configuration into lab notes.

### g) Automatic gamma sweep

Runs workflow (b) unattended so you can keep both hands on the photometer.

1. Press `G` to enter gamma mode. Position the probe at screen center.
2. Press `A`. The sweep starts at level 1 and walks to level 11.
3. It dwells **2.0 seconds** at each level, then snapshots automatically. The
   readout counts down: `Auto gamma: level 3/11 -- settling (1.2s)`.
4. Take your photometer reading during each dwell.
5. A completed sweep adds exactly 11 snapshots and returns you to the level you
   were on before pressing `A`.

Press `A` again or `ESC` to cancel mid-sweep; the level you started from comes
back either way. `ESC` will not quit the session while a sweep is running.

Manual `LEFT`/`RIGHT` stepping is ignored during a sweep. If 2 seconds is not
long enough for your probe to settle, step manually with `S` instead.

---

## 6. Output file

`monical_YYYY-MM-DD_HHMMSS.json`, written beside `monical.py` — for example
`monical_2026-09-18_143201.json`. The name is fixed at startup from
`session_start` and shown on the intro screen.

Rewritten in full on every `S` and again on `Q`, always to that same file.
**A new file every run**, so a later session cannot destroy an earlier one's
measurements. Nothing ever reads it back; it exists for you to read.

### Session fields

| Field | Meaning |
|---|---|
| `session_start`, `session_end` | ISO timestamps; `session_end` is null until quit |
| `monical_version` | tool version |
| `monitor_name` | PsychoPy Monitor used (`testMonitor`) |
| `monitor_resolution` | `[width, height]` in pixels |
| `monitor_width_cm`, `monitor_height_cm` | physical size; height is derived from width and pixel aspect. `null` if unset |
| `color_space` | `"rgb"` — the −1 to +1 space all colors below are in |
| `units` | `"height"` — the unit all positions and sizes below are in |
| `window_fullscreen` | whether the window was fullscreen |
| `vsync` | whether `flip()` was held to the retrace |
| `vsync_detail` | `wait_blanking`, `pyglet_vsync`, `context_get_vsync` — these can disagree; see §8 |
| `startup_refresh_hz` | one-shot `getMsPerFrame` measurement at launch |
| `final_rolling_refresh_hz` | mean of real flip-to-flip intervals over the last 120 frames |
| `final_rolling_refresh_sd_ms` | SD of those intervals |
| `total_dropped_frames` | frames whose interval exceeded 1.5× the rolling median |
| `psychopy_version`, `python_version`, `platform` | provenance |
| `has_radial_stim` | whether the plugin was available |
| `image_path` | the `--image` argument as given, or `null` |
| `preset_path` | the `--preset` argument as given, or `null` |
| `output_file` | this file's own name, so a renamed copy still says where it came from |
| `viewing_distance_cm` | distance at quit |
| `stimulus_type` | type chosen at startup |
| `snapshots` | list, in order |
| `final` | same shape as a snapshot, captured at quit |

### Snapshot fields

```json
{
  "snapshot_number": 1,
  "timestamp": "2026-08-21T14:32:01",
  "rolling_refresh_hz": 239.94,
  "dropped_frames_total": 0,
  "stimulus_type": "radial_checkerboard",
  "mode": "static_on",
  "dual_stimulus": false,
  "x_position": 0.66,
  "y_position": 0.0,
  "background_gray": 0.012,
  "disc_size": 0.225,
  "contrast": 1.0,
  "custom_frequency_hz": 15,
  "visual_angle_deg": 6.43,
  "eccentricity_deg": 28.57,
  "stimulus_specific": {}
}
```

`rolling_refresh_hz` and `dropped_frames_total` are the values at the moment
of that snapshot, so you can tell whether timing was healthy when you took the
reading.

Knob values are stored to 4 decimal places — finer than the HUD displays, so
nothing you dialed in is lost to rounding.

`stimulus_specific` carries whatever applies:

| Type | Keys in `stimulus_specific` |
|---|---|
| `radial_checkerboard` | *(empty)* |
| `gabor` | `sf`, `ori`, `phase`, `envelope_sd` |
| `grating` | `sf`, `ori`, `phase` |
| `uniform_patch` | `r`, `g`, `b`, `alpha` |
| `custom_png` | `filepath`, `alpha` |

Plus, depending on mode: `gamma_level` and `gamma_step_index` in gamma steps;
`grid_position`, `grid_x`, `grid_y` (and `patch_*`) in spatial uniformity;
`flicker_frames_per_cycle` and `flicker_realized_hz` in any flicker mode.

### Using it in experiment code

Transcribe by hand — these are the numbers, not a loadable config:

```python
ECCENTRICITY   = 0.66      # x_position
STIM_SIZE      = 0.225     # disc_size
BACKGROUND     = 0.012     # background_gray, matched to stimulus ON
CONTRAST       = 1.0       # contrast
FLICKER_FRAMES = 16        # flicker_frames_per_cycle, NOT 240/15
```

Take the frame count from `flicker_frames_per_cycle` rather than recomputing
it from a nominal refresh rate. That count is what produced the waveform you
verified on the scope.

---

## 7. HUD readout

Five lines, bottom center, updated every frame.

```
1920x1080 | 239.94 Hz (σ=0.12ms) | Drops: 0 | PsychoPy 2026.2.2 | Dist: 40 cm
Mode: static_on | Stim: gabor
X: 0.66 | Y: 0.00 | Size: 0.23 (10.61 deg) | Ecc: 28.57 deg
BG: 0.000 | Contrast: 1.000 | Freq: 14.998 Hz (16 frames, idle)
SF: 4.00 c/unit | Ori: 0.0 deg | Phase: 0.50 | SD: 0.060 (mask sd 1.88)
```

**Line 1 — the display.** Resolution, then the *rolling* refresh rate measured
from real flip-to-flip intervals over the last 120 frames, not the startup
measurement.

- **σ** is the standard deviation of those frame intervals in milliseconds.
  Tenths of a millisecond is healthy. A whole millisecond or more means the
  loop is not landing cleanly on the retrace, and flicker edges will jitter.
  It reads `σ=--` for the first couple of frames, before there is a window.
- **Drops** counts frames whose interval exceeded 1.5× the rolling median.
  This should stay at 0 during a measurement. A climbing count means the
  stimulus is not on screen for the durations the HUD claims, and any
  oscilloscope reading taken now is suspect.

**Line 2 — mode.** Mode name, then either the stimulus type or, in the two
modes that own the screen, what that mode owns — in gamma steps
`Level 9/11: +0.6 rgb (204 8-bit)`, in spatial uniformity
`Cell: top_left (-0.78, 0.39)`. `DUAL +/-X` appears when `7` is on.

**Line 3 — geometry.** Position in height units, then size and eccentricity in
degrees. Size uses the extent formula, eccentricity the displacement formula —
they are not the same calculation. Both show `--` when physical monitor
dimensions are unknown.

**Line 4 — luminance and timing.** Background and contrast to three decimals.
`Freq` is always the **realized** frequency from the integer frame count, with
the count and the ON/OFF split. In a non-flicker mode it is marked `idle` and
shows what the current custom setting *would* produce.

**Line 5 — stimulus-specific.** The active key legend's values. For a Gabor it
shows the envelope SD in height units plus the PsychoPy `mask sd` it converts
to, since those are different quantities.

---

## 8. Troubleshooting

**Radial checkerboard unavailable.** The startup screen reports
`psychopy_visionscience [FAILED]` and stimulus `[1]` draws nothing. Install it:

```bash
pip install psychopy-visionscience
```

Note the hyphen. Every other stimulus type and every mode works without it, and
`has_radial_stim` in the JSON records whether it was present.

**Wrong refresh rate displayed.** Two numbers exist: `startup_refresh_hz`
(measured once at launch) and the rolling rate on HUD line 1. If they disagree
by more than 5 Hz the tool prints once to the console:

```
WARNING: rolling refresh (50.0 Hz) diverges from startup measurement (59.8 Hz) -- timing may be unreliable
```

This usually means the startup measurement failed and fell back to a default —
a value of exactly `60.0` in `startup_refresh_hz` is the giveaway, since a real
measurement never lands on a round number. **Every flicker frame count is
derived from the startup figure**, so if it is wrong, all your flicker rates
are wrong. Restart, and if it persists check that vsync is enabled in your
driver control panel.

Also check `vsync` in the JSON. The rolling rate is a *loop* rate; it equals
the display's refresh rate only while vsync holds each flip to the retrace.
With vsync off the loop free-runs and the number means something else. The
three values in `vsync_detail` can disagree — `wait_blanking` is the one that
governs PsychoPy's behavior, and a driver-level `context_get_vsync: false`
alongside `wait_blanking: true` is a known Windows quirk rather than a fault.

**Visual angle showing wrong values, or `--`.** Both figures on HUD line 3 need
the monitor's physical size, which PsychoPy takes from the named Monitor
(`testMonitor`), not from the display itself. `--` means no width is stored.

Worse than `--` is a wrong width, which produces plausible but incorrect
degrees. `testMonitor`'s stock width is 30 cm, which is wrong for nearly every
real display. Check `monitor_width_cm` and `monitor_height_cm` in the JSON
against a tape measure; if a 34-inch ultrawide reports `monitor_height_cm:
12.56`, the stock value is in use. Fix it in PsychoPy Monitor Center by
setting the real screen width for `testMonitor`, then restart.

**Dropped frames.** The Drops counter on line 1 climbing during a measurement
means frames are missing their deadline. In order of likelihood: close other
applications, especially browsers and anything compositing or recording;
confirm vsync is on; check the display is running at its rated refresh rate in
the OS, not a lower default.

Taking a snapshot writes a file from inside the render loop, so `S` can itself
cost a frame — a drop or two appearing exactly when you press `S` is the tool,
not the panel. Judge the counter by whether it climbs while you are *not*
pressing keys.
