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
| pyglet | yes (ships with PsychoPy) | held-key auto-repeat, font lookup |
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
python monical.py --text "MYSTRING"
python monical.py --bench
```

`--image PATH` supplies the texture for stimulus type `[5]`. Without it, `[5]`
still works and uses a generated 256×256 checkerboard (8×8 cells). A path that
does not exist prints an error and falls back to the same generated pattern, so
a typo never ends the session.

`--preset PATH` restores knob settings saved earlier with `[P]` (§5f).

`--text STRING` sets what `[B]`/`[N]` cycle through for stimulus type `[6]`.
Without it they cycle five built-in strings: `ABCDEF`, `abcdef`, `123456`,
`XXXXXX`, `oOoOoO`. A single character cycles its alphabet, starting there. A longer string cycles the full string, then each of its
characters, then the whole alphabet. There is no on-screen text entry. The raw
value is recorded as `text_arg` in the session file.

`--bench` measures frame timing instead of running a session — see
§5i.

There is no config file, no build step, and no installer. Each session writes
one file, `monical_YYYY-MM-DD_HHMMSS.json`, next to the script — a new one
every run, so nothing you measured is ever overwritten.

---

## 3. Startup screen

White text on black. Five blocks:

1. **System info** — resolution, measured refresh rate, PsychoPy version, and
   whether `psychopy_visionscience` imported. A failure here is reported with
   the pip command, not a crash.
2. **Stimulus selector** — press `1`–`6` to choose:

   ```
   [1] Radial checkerboard (SSVEP standard)
   [2] Gabor patch (attention/perception)
   [3] Sinusoidal grating (contrast/SF tuning)
   [4] Uniform patch (color/luminance calibration)
   [5] Custom PNG (your own texture)
   [6] Text / letter string (reading/crowding)
   ```

3. **Workflow tutorial** — the recommended procedure and key legend for
   whichever type is selected. It redraws as you press `1`–`6`.
4. **Modes and actions** — the mode keys, the multi-stimulus ring keys,
   `S`, `P`, `F12`, `A` and `Q`. The same for every type.
5. **`Press SPACE to begin.`**

The header also shows `Output:` — the filename this session will write to —
and `Preset:` when one was loaded with `--preset`. Note the output name before
you start; it is fixed for the whole session.

`Q` or `ESC` here aborts without writing a file. You cannot change stimulus
type after `SPACE` — restart to switch.

If you select `[1]` without the plugin installed, the screen warns you and
still lets you proceed; the disc simply will not draw.

A **yellow warning** appears if the monitor's stored height is outside
15–80 cm or missing. It does not block, but every degree figure is wrong
until you fix the width in PsychoPy Monitor Center (§8).

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
| Custom flicker (mode 5) | `F` / `J` | ±1 frame (selected copy in multi) | 2 frames to round(refresh) frames | hold |
| Viewing distance | `;` / `'` | ±1 cm | 1 to 500 | single press |
| Ring copies (multi) | `[` / `]` | ±1 | 2 to 16 | single press |
| Ring offset (multi) | `,` / `.` | ±5° | wraps 0–360 | single press |
| Select copy (multi) | `9` / `0` | previous / next | wraps | single press |
| Selected copy state (multi) | `/` | flicker → steady → off | wraps | single press |

Custom flicker is a cycle length in **whole frames**. `F` raises the rate (one
frame fewer) and `J` lowers it, so every press changes the realized Hz. It
starts at the frame count nearest 15 Hz. The range runs from 2 frames
(refresh/2, 30 Hz on a 60 Hz panel) to about 1 Hz.

Arrows move the stimulus; the page keys adjust the background behind it.
Arrows follow their direction. For the other pairs the first key increases
the value, except `[` / `]`, where `]` adds a copy, and `F` / `J`, where `F`
raises the rate by removing a frame. Size also accepts `=` (the unshifted `+`
key) and the numpad `+` and `-`.

**Hold to scroll.** Keys marked *hold* auto-repeat after a 1-second delay, then
run at ~60 increments per second. On a 60 Hz panel that is about one step per
frame; on a 240 Hz panel, one step every four frames. The count is kept against
the moment the key went down, so a late frame catches up and the average holds
at 60/s on any panel.

Every other key acts **once per press**, however long you hold it. Holding `S`
takes one snapshot, holding `A` in gamma mode starts the sweep once, and
holding a single-press knob steps it once.

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
| `5` | Flicker at the custom frame count (`F` / `J`) |
| `G` | Gamma steps — fullscreen patch, 11 levels |
| `7` | Multi-stimulus ring — toggle, not a mode (`[` `]` copies, `,` `.` rotate) |
| `8` | Spatial uniformity — patch on a 3×3 grid |

`6` is unassigned. Switching mode resets the flicker phase to frame 0.

`7` is a **toggle** that composes with whatever mode is active: turn it on
during `3` and you get N copies flickering in phase at 15 Hz. Every other
mode key replaces the current mode.

The copies sit on a ring centred at (0, Y) through the stimulus position, so
its radius is |X|. `]` and `[` set the count from 2 to 16, and `,` and `.`
turn the ring in 5° steps. With 2 copies and no rotation you get the classic
±X pair. Readout line 2 shows `MULTI N r ... off ...` and adds `OVERLAP` when
neighbouring copies are closer than the stimulus size. Nothing is moved for
you. Gamma steps and spatial uniformity always draw one patch.

`9` and `0` select the previous and next copy; a small yellow tick points at
the selected one while the readout is visible (`H` hides it with the text).
In mode `5`, `F` / `J` change only the selected copy's frame count, so each
copy can flicker at its own rate. Modes `3` and `4` still flicker every copy
at 15 or 20 Hz. A new copy starts with the last copy's frames, and copies you
remove keep their values for the rest of the session if you add them back.
The readout lists every copy's rate, for example
`Ring Hz:  1:15.00  2:20.00 ASYM  3*:12.00`, with the selected one starred.

`/` cycles the selected copy through **flicker**, **steady** and **off**. A
steady copy stays on through every flicker mode, a constant-luminance
neighbour for comparison. An off copy is never drawn, so you can take one copy
out of the layout without changing the count. The ring line shows `STEADY` or
`--` for them.

Copies can land off screen: the ring's radius is |X|, so at the default
X = 0.66 copies above and below fixation sit past the top and bottom edges.
Line 2 shows `OFFSCREEN n` when any copy is cut off. **Text at its default
size is wider than the ring spacing allows**: `ABCDEF` at size 0.225 is about
0.8 units wide, so every copy reads off screen even at X = 0.66. For
multi-copy text, use a smaller size or a shorter string. A `!` after a copy's
number on the ring line marks it, and if it is the selected one the status
bar says `SELECTED #k OFF SCREEN`. Line 3's eccentricity becomes the
selected copy's, labelled `Ecc(#k)`.

### Actions

| Key | Action |
|---|---|
| `S` | Save a snapshot and rewrite the session JSON. Confirms on screen. |
| `P` | Save the current knobs as a preset in `presets/`. Confirms with the filename. |
| `F12` | Save a PNG of the current frame to `screenshots/`. Confirms with the filename. |
| `A` | Gamma mode only: start or cancel the auto sweep (§5g). |
| `H` | Show/hide the readout. Stimulus, fixation and the status bar keep rendering. |
| `M` | Show/hide the keybinding reference card for the current stimulus type. |
| `B` / `N` | Text type only: cycle preset strings forward/back. |
| `Q` or `ESC` | Write final state plus all snapshots, then exit. |

While an auto gamma sweep is running, `ESC` cancels the sweep instead of
quitting — a mistimed press cannot end the session mid-ramp.

**The HUD toggle is `H`.** Custom-frequency-down is `J`, not `H`.

`ESC` is claimed in order: cancel a running gamma sweep, else dismiss the
menu, else quit — so ESC never ends the session while a sweep or the menu is
active. Hiding the
readout hides only the text; the stimulus, fixation cross and gamma patch all
keep drawing, which is what you want for an unobstructed photometer reading or
a clean screenshot.

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

The same key pairs mean different things per stimulus type. HUD line 5 shows
the active type's values, and the `M` card lists its keys.

**Gabor patch**

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Spatial frequency | `Z` / `X` | ±0.5 | 4.0 | 0.5–50.0 |
| Orientation | `R` / `T` | ±5° | 0.0 | wraps 0–360 |
| Phase | `E` / `W` | ±0.05 | 0.5 | 0.0–1.0 |
| Envelope SD | `D` / `A` | ±0.01 | 0.06 | 0.01–1.0 |

**Sinusoidal grating** — the Gabor carrier without the envelope:

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Spatial frequency | `Z` / `X` | ±0.5 | 4.0 | 0.5–50.0 |
| Orientation | `R` / `T` | ±5° | 0.0 | wraps 0–360 |
| Phase | `E` / `W` | ±0.05 | 0.5 | 0.0–1.0 |
| Waveform | `D` / `A` | next / previous | `sin` | `sin`, `sqr`, `saw` (wraps) |
| Mask | `B` | toggle | `none` | `none`, `circle` |

`N` does nothing for this type. In gamma mode `A` starts the auto sweep, as
everywhere.

**Uniform patch**

| Param | Keys | Step | Default | Range | Repeat |
|---|---|---|---|---|---|
| Red | `R` / `T` | ±0.001 | 0.0 | −1.0–1.0 | hold |
| Green | `E` / `W` | ±0.001 | 0.0 | −1.0–1.0 | hold |
| Blue | `D` / `A` | ±0.001 | 0.0 | −1.0–1.0 | hold |
| Alpha | `Z` / `X` | ±0.01 | 1.0 | 0.0–1.0 | single press |
| Shape | `B` | toggle | `rect` | `rect`, `circle` | single press |

The circle's diameter is the size value. It renders exactly the same colour as
the rect (PRD 4.4). Multi (`7`) and spatial uniformity (`8`) use the current
shape; gamma steps (`G`) always fills the screen.

**Custom PNG**

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Alpha | `Z` / `X` | ±0.01 | 1.0 | 0.0–1.0 |
| Rotation | `R` / `T` | ±5° | 0 | wraps 0–360 |

**Text / letter string**

| Param | Keys | Step | Default | Range | Repeat |
|---|---|---|---|---|---|
| String | `B` / `N` | next / previous | `ABCDEF` | 5 built-in, or from `--text`; wraps | single press |
| Font family | `I` / `O` | next / previous | monospace | monospace, sans-serif, serif | single press |
| Letter spacing | `U` / `Y` | ±0.001 | 0.000 | −0.05–0.20 | hold |
| Rotation | `K` / `L` | ±5° | 0 | wraps 0–360 | single press |
| Red | `R` / `T` | ±0.001 | 1.0 | −1.0–1.0 | hold |
| Green | `E` / `W` | ±0.001 | 1.0 | −1.0–1.0 | hold |
| Blue | `D` / `A` | ±0.001 | 1.0 | −1.0–1.0 | hold |
| Alpha | `Z` / `X` | ±0.01 | 1.0 | 0.0–1.0 | single press |

Colour uses the same keys as the uniform patch, but defaults to **white** here
so the glyphs show at launch. The universal size knob sets letter height, so
the degrees on line 3 describe the letters.

The families map to Courier New, Arial and Times New Roman on Windows, with
macOS and Linux equivalents. The console lists what each family resolved to at
startup. If a font is missing, the readout says `FALLBACK` and names the face
actually drawn. A string is laid out one glyph at a time on the font's advance
widths, so at spacing 0 it is pixel-identical to a plain `TextStim`. Rotation
turns the whole string as one piece about its centre.

**Text never wraps here.** A plain PsychoPy `TextStim` wraps at its
`wrapWidth`, which defaults to one screen height in `height` units. A string
wider than that sits on one line in Monical but breaks onto several lines in
an experiment that keeps the default. It will only match if the experiment sets
`wrapWidth` wide enough.

**Radial checkerboard**

| Param | Keys | Step | Default | Range |
|---|---|---|---|---|
| Rings | `Z` / `X` | ±1 | 4 | 1–20 |
| Wedges | `R` / `T` | ±2 | 16 | 2–32, always even |

Both are single-press. The defaults are pixel-identical to the original SSVEP
construction (4x4 texture, `radialCycles=1`); see PRD 4.1.

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
   line 4, not the mode name.** It shows `Freq: 15.00 Hz (16 fr, 8 on/8 off)`:
   the frames per cycle and how many are ON and OFF.
3. For any other rate, press `5` and step the frame count with `F` / `J`
   (hold to scroll). Each press is one frame, so each press is a new rate.
4. Confirm the scope trace matches the realized Hz and the on/off split.

Frequencies are integer frame counts, so only divisors of the refresh rate are
exactly achievable. At 240 Hz, 15 Hz is 16 frames and 20 Hz is 12 — both exact
and symmetric. At 60 Hz the grid is coarse and odd counts are asymmetric:
20 Hz becomes 3 frames, 1 on and 2 off, marked `ASYM` on the readout. At
144 Hz, mode `3` is 10 frames (14.40 Hz) and mode `4` is 7 frames (20.57 Hz,
`ASYM`). Always transcribe the realized value.

All of these use the refresh measured once at startup, the same figure on
the intro screen, not the rolling rate on line 1.

### d) Spatial uniformity check

1. Press `8`. A patch appears at screen center; the fixation cross is hidden.
   This uses the uniform patch whatever stimulus type you started with.
2. Set the patch color with `R`/`T`, `E`/`W`, `D`/`A` and its size with
   `+`/`-` before you start moving it — resizing changes the grid coordinates,
   because corner cells sit as far out as the patch fits without clipping.

   The channels start at 0.000 (mid-gray) in every session except a **text**
   session, where they start at 1.0. Check readout line 5.
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

A preset holds the stimulus settings, not the rig: window aspect and size,
the `--image` path, the resolved font names and the live snapshot list are
excluded. Presets are
forward and backward compatible — missing keys fall back to defaults, and keys
this version does not recognise are ignored with a console note. A text
preset restores its string by name when the current `[B]`/`[N]` cycle contains
it. Otherwise it falls back to the saved position in the cycle and says on the
console which string it loaded instead. Mode `5` is
saved as a frame count plus the refresh it was saved at. On a panel more than
1% faster or slower, it converts to the nearest frame count for the same
rate. An older preset's `custom_freq_hz` converts the same way. Both print the
old and new rate. Values are
checked on load: anything out of range is clamped (wedges are also rounded to
an even number, 7 becoming 8), and each correction prints one console line. A corrupt
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

### h) Text legibility

1. Select `[6]` at startup. Press `1` (static ON).
2. Cycle to the string you want with `B` / `N`, or start with
   `--text "MYSTRING"`. Choose the font family with `I` / `O`; adjust
   spacing with `U` / `Y` and rotation with `K` / `L`.

   Text colour starts at **white** (R=G=B=1.000) so the glyphs are visible
   at launch. Drive the channels down with `T`/`W`/`A` for a coloured or
   darker string. The uniform patch still starts at mid-gray 0.000.
3. Set the size knob until line 3 reports the letter height you need in
   degrees. The pixel figure beside it tells you whether the glyphs have
   enough pixels to be rendered faithfully — below ~10 px tall, antialiasing
   dominates and the measurement is about the renderer, not the observer.
4. Step contrast with `C` / `V` for a legibility threshold, snapshotting
   with `S` at each step.
5. Press `H` to hide the readout before judging legibility, so HUD text is
   not in the observer's field.

---

### i) Verifying frame timing on your rig

Run this **fullscreen on the experiment display**, on the machine that will
run the experiment, before relying on any flicker measurement there:

```bash
python monical.py --bench
```

It needs no input and takes about 36 configurations × 10 s at 60 Hz, less at
higher refresh rates. `Q` or `ESC` stops it early and keeps what finished. It
runs every stimulus type at 1, 2, 8 and 16 copies in flicker mode `3` with the
readout off, then every type at 1 and 16 copies with the readout on, 600
frames each.

At the end it prints a table and writes `bench_YYYY-MM-DD_HHMMSS.json` beside
the script:

| Column | Meaning |
|---|---|
| `draw ms` / `p95` / `max` | CPU time to draw one frame, before the flip: mean, 95th percentile, worst |
| `intv ms` / `intv max` | flip-to-flip interval: mean (should be 1000 / refresh), worst |
| `drops` | frames whose interval ran past 1.5× the rolling median |
| `%bud` | mean draw time as a share of one frame (4.17 ms at 240 Hz) |
| `!` | dropped frames, or a draw p95 or max above 80% of the frame |

The JSON has the session file's system header (§6) without `note`,
`preset_path`, `text_arg`, `final_rolling_refresh_hz`,
`final_rolling_refresh_sd_ms` and `total_dropped_frames`, plus:

| Field | Meaning |
|---|---|
| `bench` | always `true` |
| `gl` | `vendor`, `renderer`, `version` of the OpenGL context |
| `frames_per_config`, `warmup_frames` | recorded frames (600) and unrecorded warm-up frames (30) per configuration |
| `mode` | `flicker_15hz`, the mode every configuration runs in |
| `frame_budget_ms` | 1000 / startup refresh |
| `texture` | the custom PNG source: the absolute `--image` path, or `<generated 8x8 checkerboard>` |
| `aborted` | `true` if `Q` or `ESC` stopped the run |
| `results` | one entry per configuration, below |

Each `results` entry: `stimulus_type`, `copies`, `hud`, `frames`,
`draw_mean_ms`, `draw_p95_ms`, `draw_max_ms`, `interval_mean_ms`,
`interval_max_ms`, `dropped_frames`, `budget_ms`, `draw_mean_pct_budget`. If
the radial plugin is missing, the radial type has a single entry with
`stimulus_type` and `skipped` (the reason) instead.

**Any dropped frames at a given copy count mean flicker verification on that
machine is unreliable at that N.** A dropped frame stretches one cycle, which
is exactly the error an oscilloscope check is meant to catch, so it would read
as a display fault. Reduce the copy count, or fix the machine (power plan,
background load, driver vsync settings), and re-run until the row is clean.
A p95 or max above 80% leaves no headroom: it may pass the benchmark and
still drop under real conditions.

**The readout-on rows** (`hud on`) show the cost of reading the readout
during a flicker check. Its timing figures refresh ten times a second, and
each refresh re-lays out a line of text. **If a readout-on row drops frames
or is marked, hide the readout with `H` while scoping**, and read the values
between measurements. `H` hides only the text; the stimulus and its timing
are untouched.

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
| `note` | the REFERENCE ONLY reminder |
| `session_start`, `session_end` | ISO timestamps; `session_end` is null until quit |
| `monical_version` | tool version |
| `monitor_name` | PsychoPy Monitor used (`testMonitor`) |
| `monitor_resolution` | `[width, height]` in pixels |
| `monitor_width_cm`, `monitor_height_cm` | physical size; height is derived from width and pixel aspect. `null` if unset |
| `monitor_dimension_warning` | `true` when the height is missing or outside 15–80 cm, meaning the angles are suspect |
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
| `text_arg` | the `--text` argument as given, or `null` |
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
  "multi_active": false,
  "multi_count": 2,
  "ring_offset_deg": 0.0,
  "ring_radius": 0.66,
  "ring_center_y": 0.0,
  "selected_index": 0,
  "stimuli": [
    {"index": 0, "x": 0.66, "y": 0.0, "ecc_deg": 28.57,
     "flicker_frames": 16, "on_frames": 8, "off_frames": 8,
     "realized_hz": 14.998, "flicker_state": "flicker",
     "offscreen": false}
  ],
  "x_position": 0.66,
  "y_position": 0.0,
  "background_gray": 0.012,
  "disc_size": 0.225,
  "contrast": 1.0,
  "custom_frequency_hz": 14.998,
  "visual_angle_deg": 10.61,
  "eccentricity_deg": 28.57,
  "stimulus_specific": {
    "rings": 4,
    "wedges": 16,
    "radialCycles": 2.0,
    "angularCycles": 8.0,
    "radialPhase": 0.25
  },
  "flicker_active": false,
  "flicker_frames": 16,
  "flicker_on_frames": 8,
  "flicker_off_frames": 8,
  "flicker_realized_hz": 14.998,
  "refresh_hz_used": 239.97
}
```

`snapshot_number` is `null` in `final`.

`rolling_refresh_hz` and `dropped_frames_total` are the values at the moment
of that snapshot, so you can tell whether timing was healthy when you took the
reading.

Knob values are stored to 4 decimal places — finer than the HUD displays, so
nothing you dialed in is lost to rounding.

`stimulus_specific` carries whatever applies:

| Type | Keys in `stimulus_specific` |
|---|---|
| `radial_checkerboard` | `rings`, `wedges`, `radialCycles`, `angularCycles`, `radialPhase` |
| `gabor` | `sf`, `ori`, `phase`, `envelope_sd` |
| `grating` | `sf`, `ori`, `phase`, `waveform`, `mask` |
| `uniform_patch` | `r`, `g`, `b`, `alpha`, `shape` |
| `custom_png` | `filepath`, `alpha`, `rotation_deg` |
| `text` | `text_string`, `text_preset_index`, `letter_spacing`, `rotation_deg`, `font_family`, `font_requested`, `font_rendered`, `font_fallback`, `alpha`, `r`, `g`, `b` |

Plus, depending on mode: `gamma_level` and `gamma_step_index` in gamma steps;
`grid_position`, `grid_x`, `grid_y` (and `patch_*`) in spatial uniformity.

Every snapshot also carries the flicker cycle: `flicker_frames`,
`flicker_on_frames`, `flicker_off_frames`, `flicker_realized_hz` and
`refresh_hz_used`. These describe the active flicker mode, or mode `5`'s
setting when none is on (`flicker_active` says which).
`custom_frequency_hz` now holds mode `5`'s *realized* rate. Older files wrote
`flicker_frames_per_cycle`, and only while flickering. With multi on, the
top-level flicker fields and `custom_frequency_hz` describe the selected copy.

The ring fields are written whether or not multi is on: `multi_active`,
`multi_count`, `ring_offset_deg`, `ring_radius`, `ring_center_y`,
`selected_index` (0-based), and `stimuli`, one entry per drawn copy with its
position, eccentricity, flicker cycle, `flicker_state` (`flicker`, `steady`
or `off`) and `offscreen`. With multi off, `stimuli` has one entry.
`dual_stimulus` is `true` only with multi on at 2 copies.

### Using it in experiment code

Transcribe by hand — these are the numbers, not a loadable config:

```python
ECCENTRICITY   = 0.66      # x_position
STIM_SIZE      = 0.225     # disc_size
BACKGROUND     = 0.012     # background_gray, matched to stimulus ON
CONTRAST       = 1.0       # contrast
FLICKER_FRAMES = 16        # flicker_frames, NOT 240/15
```

Take the frame count from `flicker_frames` rather than recomputing
it from a nominal refresh rate. That count is what produced the waveform you
verified on the scope.

---

## 7. HUD readout

Five lines, bottom center, updated every frame.

```
1920x1080 | 239.94 Hz (σ=0.12ms) | Drops: 0 | PsychoPy 2026.2.2 | Dist: 40 cm
Mode: static_on | Stim: gabor | Out: monical_2026-09-18_143201.json
X: 0.66 (1672px) | Y: 0.00 (540px) | Size: 0.23 (243px, 10.61 deg) | Ecc: 28.57 deg
BG: 0.000 | Contrast: 1.000 | Freq: 15.00 Hz (16 fr, 8 on/8 off) idle
SF: 4.00 c/unit | Ori: 0.0 deg | Phase: 0.50 | SD: 0.060 (mask sd 1.88)
```

The timing figures on line 1 (rolling refresh, σ, drop count) update ten
times a second; everything else updates on the next frame. Every dropped frame
is still counted, and a new drop shows within about 0.1 s.

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
`Cell: top_left (-0.78, 0.39)`. `MULTI 4 r 0.66 off 0` appears when `7` is on,
with `OVERLAP` if neighbouring copies collide and `OFFSCREEN n` if any are cut
off. The session's output filename comes last (`Out:`). Modes `3` and `4` show
their target and realized rate, e.g. `Flicker 15 (14.40 Hz)`.

**Line 3 — geometry.** Position in height units with the pixel coordinate
beside it, then size and eccentricity in degrees, with size also in pixels.
Pixels need only the window, so they show even when the monitor's physical
size is unknown. Size uses the extent formula, eccentricity the displacement formula —
they are not the same calculation. Both show `--` when physical monitor
dimensions are unknown.

**Line 4 — luminance and timing.** Background and contrast to three decimals.
`Freq` is always the **realized** frequency from the integer frame count, with
the count and the ON/OFF split, `frames // 2` ON. An odd count cannot split
evenly, so the shorter half is ON and the line ends `ASYM`:
`Freq: 48.00 Hz (5 fr, 2 on/3 off) ASYM`. In a non-flicker mode it ends
`idle` and shows what mode `5` *would* produce.

**Line 5 — stimulus-specific.** The active key legend's values. For a Gabor it
shows the envelope SD in height units plus the PsychoPy `mask sd` it converts
to, since those are different quantities. A line 5 wider than the screen wraps
onto a line 6.

**Ring lines.** With multi on, outside gamma steps and spatial uniformity, a
`Ring Hz:` line lists every copy's realized rate, wrapping onto as many lines
as it needs (§4). The readout grows upward, clear of the status bar.

### The status bar

Below the readout, in smaller dimmer text, one line that is **always visible —
it does not hide with `H`**:

```
[H] Text: ON | [M] Menu: OFF | [F/J] Custom: 15.00 Hz (16 fr, 8 on/8 off) | Mode: static_on | File: monical_2026-09-18_143201.json
```

Both toggle states, mode `5`'s rate and frames with the keys that change them,
the mode, and where the session is writing. With the readout hidden you can
still see all of it. The `[F/J] Custom` field is the only place on screen that
tells you how to change the rate mode `5` flickers at.

### The keybinding card

`M` overlays a reference card for the current stimulus type on a dark panel at
88% opacity — the stimulus keeps rendering behind it. The card lists movement,
display, frequency, modes and actions, plus a `THIS STIMULUS` block that
changes per type and a line for whichever keys the active mode has taken over.

Knobs stay live while the card is up, so you can adjust a value while reading
how. `M` again or `ESC` dismisses it.

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
