# Monical — Monitor Calibration Tool for Vision Science

**Version:** 0.1 (PRD)
**Author:** Trevor Caruso
**License:** MIT
**Repo:** https://github.com/trevcaru/monical

---

## 1. Purpose

Monical is a standalone keyboard-driven calibration tool for vision science labs. It renders standard visual stimuli with real-time adjustable parameters, on-screen readout, and JSON snapshot export. The user adjusts parameters while measuring with a photometer or oscilloscope, reads the values off screen, and enters them into their experiment code manually.

Monical does not run experiments, collect data, or apply corrections automatically. It characterizes and verifies.

---

## 2. Dependencies

- **PsychoPy** (required) — stimulus rendering, frame timing, window management. Every vision science lab using Python already has this.
- **psychopy_visionscience** (optional, guarded import) — needed only for the radial checkerboard stimulus. All other modes work without it. Failure reported on the info screen with the pip install command.
- **NumPy** (comes with PsychoPy)
- **pyglet** (comes with PsychoPy) — held-key state for auto-repeat, font lookup and glyph advances. The key-state import is guarded: without it only auto-repeat is lost.
- **argparse** (stdlib) — used for the `--image`, `--preset`, `--text` and `--bench` flags only.
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

Benchmarking frame timing on the rig instead of running a session:

```
python monical.py --bench
```

`--bench` opens fullscreen, measures the refresh as a session would, and needs no input; `Q` or `ESC` aborts. It runs each of the six types at 1, 2, 8 and 16 copies in flicker mode 3 with the readout off, 600 recorded frames each after a 30-frame warm-up. The radial type is skipped with a note if the plugin is missing, and the PNG type uses `--image` if given, otherwise the generated pattern held in memory. It then runs every type at 1 and 16 copies with the readout on, to show what reading the readout during a flicker check costs on that machine. Each configuration records draw time (mean, p95, max), flip-to-flip interval (mean, max), dropped frames (same rule as §3.2) and the draw mean as a percentage of the frame budget. Results go to `bench_YYYY-MM-DD_HHMMSS.json` beside the script (same timestamp format as the session files). The file carries the session file's system header without `note` and the run-only fields (`preset_path`, `text_arg`, `final_rolling_refresh_hz`, `final_rolling_refresh_sd_ms`, `total_dropped_frames`), plus `bench`, `gl` (GL vendor, renderer and version), `frames_per_config`, `warmup_frames`, `mode`, `frame_budget_ms`, `texture`, `aborted` and the `results` list (fields in MANUAL §5i). The file is rewritten after every configuration, so an aborted run keeps what finished. A console table at the end marks (`!`) any configuration that dropped frames, or whose draw p95 or max exceeded 80% of the budget. A single slow frame is enough to drop a cycle, so the mean is not the figure to judge by. The benchmark runs the same scene-building, per-frame drawing and frame-timing code as a session.

### 3.1 Screen flow

```
┌─────────────────────┐
│   INTRO / SELECTOR   │  Select stimulus type (1–6), see tutorial,
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
  "note": "REFERENCE ONLY. Not loaded by any experiment. Values are read by humans and entered manually.",
  "session_start": "2026-08-21T14:30:12",
  "session_end": "2026-08-21T14:47:03",
  "monical_version": "0.1",
  "monitor_name": "testMonitor",
  "monitor_resolution": [1920, 1080],
  "monitor_width_cm": 58.67,
  "monitor_height_cm": 33.0,
  "monitor_dimension_warning": false,
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
  "psychopy_version": "2026.2.2",
  "python_version": "3.11.0 ...",
  "platform": "win32",
  "has_radial_stim": true,
  "image_path": null,
  "text_arg": null,
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
  ],
  "final": { ... }
}
```

`stimulus_specific` holds per-type parameters (rings and wedges with the RadialStim kwargs they derive, SF, ori, phase, SD, R, G, B, alpha — whichever apply), plus the mode-local values: `gamma_level` and `gamma_step_index` in gamma steps; `grid_position`, `grid_x` and `grid_y` in spatial uniformity, with `patch_r`, `patch_g`, `patch_b`, `patch_alpha` and `patch_shape` when the session type is not the uniform patch (§6.4).

Every snapshot and the final record carry the flicker cycle: `flicker_frames`, `flicker_on_frames`, `flicker_off_frames`, `flicker_realized_hz` and `refresh_hz_used`. These describe the active flicker mode (3, 4 or 5) when one is on, and mode 5's standing setting otherwise; `flicker_active` says which. `refresh_hz_used` is the startup refresh measurement that every frame count is built on (§6.1). Earlier versions wrote `flicker_frames_per_cycle`, only in flicker modes.

`custom_frequency_hz` is kept for back-compatibility, but it now holds the **realised** rate of mode 5's frame count (e.g. `14.4` at 144 Hz), not a requested integer.

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
pattern = np.array([[1, -1], [-1, 1]])     # one full cycle per axis

RadialStim(win=win, tex=pattern, size=size,
           radialCycles=rings / 2, angularCycles=wedges / 2,
           radialPhase=0.25,
           texRes=256, opacity=1, contrast=contrast,
           pos=(x, y), autoLog=False)
```

No mask. The 2x2 texture holds one check cycle per axis, so `rings` and `wedges` count individual checks: `radialCycles = rings / 2` and `angularCycles = wedges / 2`.

**Why `radialPhase=0.25`.** RadialStim's radial texture coordinate runs from `0.25 - radialPhase` at the centre to `0.25 + radialCycles - radialPhase` at the edge. That 0.25 offset was one texel on the original 4x4 texture, so v1's rings started cleanly at the centre. On a 2x2 texture it is half a texel. Left uncorrected, every ring boundary moves by half a ring width, and `rings=N` draws N+1 bands whose innermost and outermost are half-width. `radialPhase=0.25` cancels the offset, so `rings=N` draws exactly N full-width rings from the centre.

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Rings | `[Z/X]` | ±1 | 4 | 1–20 |
| Wedges | `[R/T]` | ±2 | 16 | 2–32 (always even) |

Both are single-press. Contrast is adjustable via the universal knob.

**Stimulus-specific snapshot fields:** `rings`, `wedges`, and the RadialStim kwargs they derive, `radialCycles`, `angularCycles`, `radialPhase`.

**Defaults reproduce v1.** The original Odegaard Lab SSVEP construction was a 4x4 texture with `radialCycles=1` and `angularCycles` left at the RadialStim default of 4 (4 rings, 16 wedges). Offscreen renders of v1 and of the default construction above (rings 4, wedges 16), on the same window, size, position, contrast and background, differ by **0 pixels**. That holds at the default size 0.225 at x=0.66 and at size 0.9 centred, on PsychoPy 2026.2.2. Ring counts 1–20 were also checked along radial rays; each draws exactly N equal-width bands.

### 4.2 Gabor patch

Most common stimulus in attention and perception research. Sinusoidal grating windowed by a Gaussian envelope.

**Construction:**
```python
GratingStim(win=win, tex='sin', mask='gauss',
            size=size, sf=sf, ori=ori, phase=phase,
            contrast=contrast, pos=(x, y),
            maskParams={'sd': (size / 2) / envelope_sd}, autoLog=False)
```

PsychoPy's `maskParams['sd']` is not an SD in stimulus units: it is the number of SDs between the centre and the patch edge. The envelope SD knob is in height units, so it is converted as above. At the defaults (size 0.225, SD 0.06) that is 1.875, which readout line 5 shows as `mask sd 1.88`.

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Spatial frequency | `[Z/X]` | ±0.5 cycles | 4.0 | 0.5–50.0 |
| Orientation | `[R/T]` | ±5° | 0.0 | 0–360, wraps |
| Phase | `[E/W]` | ±0.05 | 0.5 | 0.0–1.0 |
| Envelope SD | `[D/A]` | ±0.01 | 0.06 | 0.01–1.0 |

**Stimulus-specific snapshot fields:** `sf`, `ori`, `phase`, `envelope_sd`.

### 4.3 Sinusoidal grating

Full-field or sized grating without Gaussian envelope. Used for contrast sensitivity, spatial frequency tuning.

**Construction:**
```python
GratingStim(win=win, tex=waveform, mask=None if mask == 'none' else mask,
            size=size, sf=sf, ori=ori, phase=phase,
            contrast=contrast, pos=(x, y), autoLog=False)
```

`waveform` is PsychoPy's built-in `'sin'`, `'sqr'` or `'saw'` texture. `mask` is `'none'` (a square patch) or PsychoPy's hard-edged `'circle'`. `'none'` is stored as a string so it survives JSON and presets, and is passed to GratingStim as `None`.

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Spatial frequency | `[Z/X]` | ±0.5 cycles | 4.0 | 0.5–50.0 |
| Orientation | `[R/T]` | ±5° | 0.0 | 0–360, wraps |
| Phase | `[E/W]` | ±0.05 | 0.5 | 0.0–1.0 |
| Waveform | `[D/A]` | next / previous | `sin` | `sin`, `sqr`, `saw` (wraps) |
| Mask | `[B]` | toggle | `none` | `none`, `circle` |

Waveform and mask are single-press. `[N]` is unbound for this type. In gamma mode `[A]` is claimed by the auto sweep (§6.5), as it is for every type.

**Stimulus-specific snapshot fields:** `sf`, `ori`, `phase`, `waveform`, `mask`.

### 4.4 Uniform patch

Solid rectangle or circle at adjustable color. The color calibration surface. Use for gamma per-channel, channel independence, spatial uniformity, and any measurement requiring a uniform field.

**Construction:**
```python
# shape 'rect'
Rect(win=win, width=size, height=size, fillColor=[r, g, b],
     lineWidth=0, lineColor=None, colorSpace='rgb',
     opacity=alpha, contrast=contrast, pos=(x, y), autoLog=False)

# shape 'circle' -- diameter is the size value
Circle(win=win, radius=size / 2, edges=256, fillColor=[r, g, b],
       lineWidth=0, lineColor=None, colorSpace='rgb',
       opacity=alpha, contrast=contrast, pos=(x, y), autoLog=False)
```

The circle is a ShapeStim fill, the same render path as the rect. It is not a masked GratingStim, whose texture and mask stages could change the colour. Multi-stimulus (§6.3) and spatial uniformity (§6.4) draw the current shape. Gamma steps (§6.2) is always the full-screen rect.

**Colour equivalence (measured).** Rect and circle were rendered offscreen at the same parameters, and a central 100×100 px region well inside both shapes was compared. They were identical (0 differing pixels) in every case: mid-gray on a −0.5 background, near-black −0.95, pure red, pure green, pure blue, green at alpha 0.5 over a 0.3 background, and 0.4 gray at contrast 0.5 over −0.2. The circle at size 0.225 measures 242 px across on a 1080-px-tall window (0.225 × 1080 = 243).

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Red | `[R/T]` | ±0.001 | 0.0 | -1.0–1.0 |
| Green | `[E/W]` | ±0.001 | 0.0 | -1.0–1.0 |
| Blue | `[D/A]` | ±0.001 | 0.0 | -1.0–1.0 |
| Alpha | `[Z/X]` | ±0.01 | 1.0 | 0.0–1.0 |
| Shape | `[B]` | toggle | `rect` | `rect`, `circle` |

Shape is single-press. `[N]` is unbound for this type.

**Stimulus-specific snapshot fields:** `r`, `g`, `b`, `alpha`, `shape`.

Note: PsychoPy color range is -1 to 1. Mid-gray = 0. Black = -1. White = 1.

### 4.5 Custom PNG

User-supplied texture loaded from a PNG file. For calibrating with experiment-specific stimuli, verifying custom patterns, or checking rendering of imported images.

**Construction:**
```python
ImageStim(win=win, image=filepath, size=size, ori=rotation_deg,
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
| Rotation | `[R/T]` | ±5° | 0 | 0–360, wraps (355 + 5 = 0, 0 − 5 = 355) |

Rotation is single-press and sets ImageStim `ori` (clockwise, PsychoPy's convention).

All universal parameters apply: position, size, contrast, background, flicker, viewing distance.

**Stimulus-specific snapshot fields:** `{"filepath": "...", "alpha": 1.0, "rotation_deg": 0.0}`

### 4.6 Text stimulus

Letter strings for legibility, acuity, crowding and text-rendering checks.

**Construction.** A single character is one ordinary TextStim:

```python
TextStim(win=win, text=char, font=font_requested,
         height=size, color=[r, g, b], colorSpace='rgb', opacity=alpha,
         contrast=contrast, ori=rotation_deg, pos=(x, y), autoLog=False)
```

A string of two or more characters is drawn as **one TextStim per glyph**, each anchored at its pen origin (`anchorHoriz='left'`, `alignText='left'`) with the same font, height, colour, opacity, contrast and `ori`. PsychoPy's TextStim has no letter-spacing parameter and rotates only about its own anchor, so per-glyph layout is the only way to offer spacing and rigid rotation.

`height` is the universal size knob, so the degrees on readout line 3 describe the letter height.

**Layout from advance widths.** Glyph positions come from the font's advance widths, not ink bounding boxes. They are read from the same pyglet font object TextStim draws with (`pyglet.font.load(font, int(height_px * 0.75))`, then `get_glyphs()`), so no new dependency is involved. Glyph *i*'s pen position is the sum of the advances of glyphs 0..*i*−1 plus *i* × spacing. The string's full advance extent is centred on (x, y) using pyglet's own integer arithmetic for a centred line, `-(W // 2) + (W - width) // 2` with W the TextStim wrap width in px. A plain `-width / 2` puts odd widths on a half pixel, 1 px off a single TextStim.

*Measured:* at spacing 0, the per-glyph layout is **pixel-identical** to a single TextStim of the same string. That held for "AHO" and "WAVE" in all three fonts at size 0.225 centred (0 differing pixels, per-glyph offset 0 px), and for "WAVE", "AHO" and "Hamburgefonts" at three other sizes and fractional positions. pyglet 1.4 applies no kerning, so the kerning-prone "WAVE" shows no pair adjustment in either rendering. The five default strings are pixel-identical too, in all three fonts.

**Fast path.** When letter spacing is 0, rotation is 0 and the string fits a TextStim's wrap width, the copy is drawn as **one TextStim** with the whole string rather than one per glyph. The per-glyph layout is pixel-identical to it there, and one draw costs a fraction of six. Any nonzero spacing or rotation switches to the per-glyph path, and so does a string wider than the wrap width, which a single TextStim would wrap. *Verified* pixel-identical for the five built-in strings and two `--text` strings, in all three fonts, at sizes 0.1 and 0.225, centred and at a half-pixel position: 84 comparisons, 72 on the fast path. The width used for off-screen detection comes from the glyph advances, so it is the same on either path.

**No wrapping.** Monical's per-glyph text never wraps. A plain PsychoPy TextStim wraps at its `wrapWidth`, which defaults to one screen height in `height` units. A string wider than that renders on one line here but on several in an experiment that leaves `wrapWidth` at its default. Measurements of such a string transfer only if the experiment sets `wrapWidth` wide enough to keep it on one line.

**Rotation** turns each glyph's `ori` and also rotates its offset about the string centre (clockwise, PsychoPy's convention), so the string turns as a rigid unit. *Measured:* at 90° the ink-box centres of "AHO" lie on one vertical line (0 px spread), in reading order top to bottom.

**Font family** maps to the first installed name on the machine:

| Family | Candidates, in order |
|---|---|
| monospace | Courier New, Menlo, DejaVu Sans Mono, Liberation Mono |
| sans-serif | Arial, Helvetica, DejaVu Sans, Liberation Sans |
| serif | Times New Roman, Times, DejaVu Serif, Liberation Serif |

pyglet silently substitutes its default face (Arial on Windows) for a name it cannot find. So each family is resolved at startup with `pyglet.font.have_font()`, and the console prints what each will render. If no candidate is installed, the readout says so explicitly, for example `Font: serif (FALLBACK Arial: Times New Roman not installed)`, and the snapshot records `font_rendered` as the substitute with `font_fallback: true`. It never claims the requested face. *Verified* by forcing a missing name: it rendered pixel-identical to Arial, and was reported as such.

**Stimulus-specific parameters:**

| Param | Key | Increment | Default | Range | Repeat |
|-------|-----|-----------|---------|-------|--------|
| String | `[B/N]` | next / previous | see below | wraps | single press |
| Font family | `[I/O]` | next / previous | monospace | monospace, sans-serif, serif (wraps) | single press |
| Letter spacing | `[U/Y]` | ±0.001 height units | 0.000 | −0.05–0.20 | hold |
| Rotation | `[K/L]` | ±5° | 0 | 0–360, wraps (355 + 5 = 0, 0 − 5 = 355) | single press |
| Red | `[R/T]` | ±0.001 | 1.0 | -1.0–1.0 | hold |
| Green | `[E/W]` | ±0.001 | 1.0 | -1.0–1.0 | hold |
| Blue | `[D/A]` | ±0.001 | 1.0 | -1.0–1.0 | hold |
| Alpha | `[Z/X]` | ±0.01 | 1.0 | 0.0–1.0 | single press |

The first key of each pair increases (U, K) or steps forward (I, B). Spacing is inert for a single character, but the readout still shows its value. Colour and alpha apply to every glyph.

**`--text` and the `[B/N]` cycle.** Monical has no on-screen text entry, since that would need a widget (§13), so strings come from the command line:

| `--text` | `[B/N]` cycle | Starts at |
|---|---|---|
| absent | `ABCDEF`, `abcdef`, `123456`, `XXXXXX`, `oOoOoO` | `ABCDEF` |
| one character | its alphabet, single characters (a–z for a lowercase letter; any other character is placed before A–Z) | that character |
| two or more | the full string, then each of its characters, then `ABCDEFGHIJKLMNOPQRSTUVWXYZ` as one string | the full string |

The current entry is always displayed in full. The raw `--text` value is recorded as `text_arg` in the session header (`null` when absent).

**Readout line 5:** `Text: AHO | Font: monospace (Courier New) | Spacing: 0.000 | Rot: 0 | R 1.000 G 1.000 B 1.000 A 1.000`. Strings over 24 characters are truncated with `...` in the readout only. It wraps onto line 6 if wider than the screen (§8).

**Stimulus-specific snapshot fields:** `text_string` (the string displayed, in full), `text_preset_index`, `letter_spacing`, `rotation_deg`, `font_family`, `font_requested`, `font_rendered`, `font_fallback`, `alpha`, `r`, `g`, `b`.

**Presets** carry the displayed string and its index, spacing, family and rotation. The resolved font names are not carried; they belong to the machine. On load the saved **string** is matched against this session's cycle first, because the same index can mean a different string under another `--text`. If the saved index still points at that string, the index is kept, so a duplicate entry stays the one that was saved. If the string is not in the cycle, the index decides, wrapped modulo the cycle length, and a console line names the saved string and the one loaded. An unknown `mode` falls back to `static_on`. Every correction prints a console line.

**Colour defaults to white (1.0) for this type only.** rgb 0.0 is the same mid-gray as the default background, which rendered the glyphs invisible at launch. The uniform patch (§4.4) keeps 0.0, because there mid-gray is the calibration starting point the patch is meant to be driven away from. The default is chosen in `default_state()` from the stimulus type, so state, readout and snapshot never disagree with what is on screen.

One consequence: spatial uniformity mode (§6.4) draws the uniform patch from the same `r`/`g`/`b` state, so in a **text** session that patch starts white rather than mid-gray. The snapshot records `patch_r/g/b/alpha`, so the reading is still self-describing.

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
| Custom flicker (mode 5) | `[F/J]` | ±1 frame | nearest to 15 Hz | 2 frames (refresh/2) to round(refresh) frames (~1 Hz) |
| Viewing distance | `[;/']` | ±1 cm | 40 | 1–500 |
| Ring copies (multi) | `[ / ]` | ±1 | 2 | 2–16 |
| Ring offset (multi) | `[, / .]` | ±5° | 0 | 0–360, wraps |

Arrows move the stimulus; the page keys adjust the background behind it. Size also takes `=` (the unshifted `+` key) and the numpad `+` and `-`.

Custom flicker is stored as a cycle length in whole frames, not Hz. `[F]` raises the rate, which means one frame *fewer*; `[J]` lowers it. Because the frame count is what changes, every press moves the realised rate. A Hz knob rounding to frames left most presses doing nothing: at 60 Hz, 106 of 119 steps of the old 1–120 Hz knob landed on an unchanged count.

### 5.1 Key repeat

X position, Y position, background gray, contrast, color channels (R/G/B), text letter spacing and custom flicker frames (`[F/J]`): after 1 second of holding the key, auto-repeat at ~60 increments per second — roughly one increment per frame at 60 Hz, one every four frames at 240 Hz. Custom flicker repeats because its range runs to hundreds of frames on a fast panel. The coarser knobs (size, viewing distance) are single-press.

Repeat is measured against the moment the key went down, not against the last increment emitted. An increment can only land on a frame boundary, so "wait 1/rate since the last one" rounds every interval up to a whole frame and beats the realized rate below the target; accumulating against the hold start lets a short interval compensate for a long one.

Every other key acts once per press, however long it is held. A press event for a key that is already down is dropped for every key, so an OS that delivers its own autorepeat as press events cannot fire a snapshot, a mode switch or a single-press knob more than once per hold. The repeat timer above is the only source of repeats. (pyglet 1.4 on Windows already filters OS autorepeat; the guard keeps this true on any backend that does not.)

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
| `[3]` | Flicker 15 Hz | Nearest whole-frame cycle: 16 frames at 240 Hz, 4 at 60 Hz, 10 at 144 Hz (14.40 Hz). Oscilloscope check. |
| `[4]` | Flicker 20 Hz | Nearest whole-frame cycle: 12 frames at 240 Hz, 3 at 60 Hz (1 on/2 off), 7 at 144 Hz (20.57 Hz, 3 on/4 off). Oscilloscope check. |
| `[5]` | Flicker custom | Cycle of `[F/J]` whole frames. Shows realized Hz and the on/off split. |
| `[G]` | Gamma steps | Full-screen uniform patch, 11 levels (0%–100%). LEFT/RIGHT to step. Fixation cross hidden. |
| `[7]` | Multi-stimulus | Toggles N copies on a ring through (X, Y); `[ / ]` set N (2–16), `[, / .]` rotate, `[9 / 0]` select a copy whose mode 5 frames `[F/J]` then set, `[/]` cycles it flicker/steady/off (§6.3). N = 2 is the original ±X dual layout. |
| `[8]` | Spatial uniformity | Uniform patch movable to a 3×3 grid (center, corners, midpoints). Arrow keys move between grid positions. |

Non-mode action keys, active throughout the test routine:

| Key | Action |
|-----|--------|
| `[S]` | Snapshot to the session file |
| `[P]` | Save the current knobs as a preset (§10) |
| `[F12]` | Save a PNG of the current frame (§11) |
| `[A]` | Start or cancel the auto gamma sweep, gamma mode only (§6.5) |
| `[H]` | Show or hide the readout (§8.1) |
| `[M]` | Show or hide the keybinding card (§8.3) |
| `[B/N]` | Text type only: cycle strings (§4.6) |
| `[Q]` | Quit, writing final state |
| `[ESC]` | Cancel a running sweep, else dismiss the menu, else quit (§8.3) |

### 6.1 Flicker logic

```python
def stim_is_on(frame_idx, frames):
    return (frame_idx % frames) < (frames // 2)
```

Stateless, pure in frame_idx. Phase resets on every mode switch. Identical to the SSVEP experiment's drive logic.

With multi-stimulus on (§6.3), each copy *i* has its own count and is ON iff `(frame_idx % frames_i) < frames_i // 2`. That is the same `stim_is_on`, with one shared `frame_idx` that resets on every mode switch, so the copies stay stateless and their phases are fixed relative to each other. This applies to copies in the `flicker` state; a `steady` copy is drawn on every frame and an `off` copy never (§6.3).

Each cycle is `on = frames // 2` frames ON and `off = frames - on` frames OFF. An odd count is asymmetric, with the shorter half ON, and the readout marks it `ASYM`.

**Which refresh.** Every frame count and every realised rate uses the refresh measured once at startup (`getMsPerFrame`, median of 120 frames; 60.00 Hz with a console warning if that fails). Modes 3 and 4 take the nearest whole-frame cycle to 15 and 20 Hz at that refresh. Mode 5 *is* a frame count, one per copy in multi-stimulus mode, from 2 frames (refresh/2) to round(refresh) frames (~1 Hz). It defaults to the count nearest 15 Hz. The rolling rate on readout line 1 is not used for these, because a fluctuating denominator would make a fixed frame count report a wandering frequency. If the two disagree by more than 5 Hz, the console warns (§3.2). Realised Hz = refresh / frames, never a requested value.

### 6.2 Gamma steps

Full-screen uniform gray patch. 11 levels: -1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0 (PsychoPy units). LEFT/RIGHT to step. Current level shown on screen.

Fixation cross is **hidden** in this mode — the photometer goes at screen center.

Snapshots in this mode include `gamma_level` and `gamma_step_index` in `stimulus_specific`.

### 6.3 Multi-stimulus mode

`[7]` toggles multi-stimulus rendering: **N copies of the current stimulus on a ring**, for verifying the full display load of a multi-stimulus experiment. It is a flag, not a mode, so it composes with static ON, static OFF and every flicker mode. Gamma steps and spatial uniformity always draw their single patch, as before.

**Geometry.** The ring is centred at (0, Y) with radius |X|, so it passes through the single stimulus's position. Copy *i* sits at angle `base + offset + i * 360 / N` degrees, counter-clockwise, where `base` points toward the sign of X: 0° for X ≥ 0, 180° for X < 0.

```python
x_i = r * cos(a_i)        y_i = Y + r * sin(a_i)      # r = |X|
```

Positions are rounded to 12 decimal places so that **N = 2 at offset 0 reproduces the original dual layout exactly**, (X, Y) and (−X, Y). *Verified* bit-identical against the pre-ring code for every X the knob can reach and six Y values, and in F12 screenshots of the real loop for all six types (0 differing pixels). With multi off, the stimulus is drawn once at (X, Y), as before.

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| Multi on/off | `[7]` | toggle | off | — |
| Copies (N) | `[ / ]` | ±1 | 2 | 2–16 |
| Ring offset | `[, / .]` | ±5° | 0 | 0–360, wraps |

`]` adds a copy and `[` removes one. `,` turns the ring +5° (counter-clockwise) and `.` turns it back. All are single-press. The count and offset are kept while multi is off.

All copies share every parameter except their mode 5 frame count.

**Selection and independent flicker.** `[9]` and `[0]` select the previous and next copy, wrapping. They are single-press and do nothing while multi is off, when the selection is always copy 1. In mode 5 each copy has its own `flicker_frames`, and `[F/J]` step only the **selected** copy's, with the same whole-frame stepping and hold-repeat as §5. Modes 3 and 4 still drive every copy at their shared target rate.

Raising the count gives a new copy the frames of the current last copy. Lowering it drops copies from the end, but their frame counts are remembered for the rest of the session, so raising the count again brings them back. Only the active copies' values go into a preset.

**Per-copy state.** Each copy is `flicker` (the default), `steady` or `off`. `[/]` cycles the selected copy through flicker → steady → off → flicker; it is single-press and does nothing while multi is off.

| State | Static ON (1) | Flicker modes (3, 4, 5) | Static OFF (2) |
|---|---|---|---|
| flicker | drawn | follows its frame count exactly as §6.1 | not drawn |
| steady | drawn | drawn on every frame | not drawn |
| off | not drawn | not drawn | not drawn |

The flicker formula is unchanged for `flicker` copies. Raising and lowering the count treats states like frame counts: a new copy takes the last copy's state, and dropped states come back if the count is raised again in the same session. *Verified* with N = 4, states [flicker, steady, off, flicker] and frames [3, 4, 5, 6] in mode 5, over 120 rendered frames (two LCM cycles). The flicker copies matched their formula on every frame, the steady copy was on in all 120 and the off copy in none. Modes 3 and 4 behaved the same.

**Off-screen copies.** The ring radius is |X|, so at the default X = 0.66 copies at the top and bottom of the ring sit beyond the screen (half-height 0.5). A copy counts as off screen if any part of its bounding box falls outside the window. The box is the size square, or the string's advance box for text, turned with the copy's rotation (text, PNG) or orientation (grating, Gabor). Line 2 shows `OFFSCREEN n` when any copy is affected. A selected copy that is off screen is marked `!` on the ring line (`2*!`), and the status bar adds `SELECTED #2 OFF SCREEN`. *Verified* against rendered pixel area: at X = 0.66, N = 3 it flags 2 copies, at X = 0.2, N = 8 with size 0.05 it flags 0, and the flags matched clipping in every case tested.

**Selection marker.** A short thin yellow tick points at the selected copy. It is drawn only while the readout is visible, so `[H]` removes it from photometer readings and screenshots. It is placed radially outward first, then swung round in 30° steps, and used only where it stays clear of **every** copy's footprint circle: half the diagonal of the size square, or of the string's advance box for text. If no direction is clear, it is not drawn. *Verified* with a stimuli-only mask against a marker-only mask: no shared pixel in 102 square-footprint ring layouts (N 2–16, three sizes, both signs of X, several selections) or in text rings. With `[H]` off, the real loop's frame has zero marker pixels.

**Overlap warning.** When the chord between neighbours, `2 * r * sin(pi / N)`, is less than the stimulus size, readout line 2 shows `OVERLAP`. Nothing is moved; the operator decides.

**Eccentricity.** Each copy's eccentricity is the existing displacement formula (§7) applied to its own distance from fixation, `sqrt(x_i^2 + y_i^2)`. With multi on, readout line 3 shows the selected copy's value, labelled `Ecc(#3)`, the same number as its JSON entry. With multi off, line 3 is unchanged.

**Snapshot fields:** `multi_active`, `multi_count`, `ring_offset_deg`, `ring_radius`, `ring_center_y`, `selected_index`, and `stimuli`, a list of `{index, x, y, ecc_deg, flicker_frames, on_frames, off_frames, realized_hz, flicker_state, offscreen}` (one entry when multi is off). Each entry's cycle is the active flicker mode's, or the copy's mode 5 setting when nothing is flickering. The top-level `flicker_*` fields and `custom_frequency_hz` describe the selected copy. `dual_stimulus` is kept for back-compatibility: it is true only when multi is on with N = 2, the layout the old flag meant.

**Presets** save `multi`, `multi_count`, `ring_offset_deg`, `selected_index`, `stim_states` and `stim_frames`, the active copies' frame counts, with the refresh they were saved at. Each count gets the same refresh-mismatch conversion as §10. A list that does not match the count is padded with its last value or truncated, with a console note. An older preset's single `flicker_frames` or `custom_freq_hz` applies to every copy. States are sanitized: an unknown value becomes `flicker` and a length mismatch is padded or truncated, each with a console note. A preset without states loads every copy as `flicker`. A preset from before the ring with `dual: true` loads as multi on, N = 2, offset 0, with a console line. The count is clamped to 2–16 and the offset wraps into 0–360.

### 6.4 Spatial uniformity mode

Renders the uniform patch (regardless of selected stimulus type) at nine grid positions: center, top-left, top-center, top-right, mid-left, mid-right, bottom-left, bottom-center, bottom-right. It starts at center. The arrow keys move one cell left, right, up or down on the 3×3 grid and stop at the edges. Edge and corner cells sit as far out as the patch fits without clipping, so the coordinates depend on the size knob. The patch uses the current shape, `r`/`g`/`b`, alpha, contrast and size. Fixation is hidden. Snapshot at each position to characterize panel uniformity.

Snapshots in this mode include `grid_position`, `grid_x` and `grid_y` in `stimulus_specific`, plus `patch_r`, `patch_g`, `patch_b`, `patch_alpha` and `patch_shape` when the session type is not the uniform patch.

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
Line 1: [resolution] | [rolling Hz] Hz (σ=[sd]ms) | Drops: [n] | PsychoPy [ver] | Dist: [cm] cm
Line 2: Mode: [name] | Stim: [type] [| MULTI N r [radius] off [deg] [OVERLAP] [OFFSCREEN n]] | Out: [file]
Line 3: X: [val] ([px]px) | Y: [val] ([px]px) | Size: [val] ([px]px, [deg] deg) | Ecc: [deg] deg   (multi: Ecc(#k), the selected copy)
Line 4: BG: [val] | Contrast: [val] | Freq: [realized] Hz ([frames] fr, [on] on/[off] off) [ASYM] [idle]
Line 5: [stimulus-specific params, e.g. SF: 4.00 c/unit | Ori: 0.0 deg | Phase: 0.50 | SD: 0.060 (mask sd 1.88)]
```

In gamma steps line 2 shows `Level k/11: [rgb] rgb ([8-bit] 8-bit)` in place of `Stim:`, and in spatial uniformity `Cell: [name] ([x], [y])`. Line 5 then describes the mode's keys instead of the stimulus.

With multi on, the readout adds a ring line listing every copy's realised rate, with `ASYM` marks and the selected copy starred, wrapped onto as many lines as the screen width needs: `Ring Hz:  1:20.00 ASYM  2:STEADY  3*:--  4:10.00`. A steady copy shows `STEADY`, an off copy `--`, and an off-screen copy `!` after its number. The readout grows upward, so its bottom edge stays clear of the status bar. Line 4 and the status bar's `[F/J] Custom` field show the selected copy.

Modes 3 and 4 show their target and the realised rate in the mode name, on line 2 and in the status bar: `Flicker 15 (14.40 Hz)` or `Flicker 20 (20.57 Hz ASYM)` at 144 Hz. The JSON `mode` field keeps the plain identifier (`flicker_15hz`). Mode 5's rate is on line 4 and in the status bar's `[F/J] Custom` field.

If line 5 is wider than the screen (a long `--text` string or PNG filename), it wraps at a ` | ` boundary onto a line 6. The font never shrinks. A wrapped readout moves up half a line so its bottom edge stays clear of the status bar.

**Readout cost.** Re-laying out text costs real time at 240 Hz (4.17 ms per frame), so the readout is drawn as **one TextStim per line**, and each line, the status bar, the menu and the flash text are re-laid out only when their own string changes. Each line sits exactly where pyglet placed it in the former single multi-line block: same positions, spacing, wrapping and font. *Verified* pixel-identical in 15 real-loop scenarios with the readout visible, including a wrapped line 5 and a 16-copy ring wrapped onto two lines. All the timing figures live on line 1, so a timing tick re-lays out one short line: about 1.5 ms mean and 2.5 ms worst on the development machine, against 3.9–5.5 ms mean and 6–7 ms worst for the whole block. The strings themselves are rebuilt every frame. The figures that change on every frame by nature (rolling refresh, σ and the drop count, all on line 1) refresh at most 10 times a second, on the clock. Every other field, including any knob, mode, selection or state change, shows on the very next frame. The drop counter itself still counts every frame; only its display is throttled. *Measured* in the real loop: a knob, mode, multi or count key showed in the same frame that handled it, an idle readout re-laid out about 8 times a second instead of every frame, and three injected 100 ms stalls were each counted once and appeared on line 1 within 0.10–0.12 s.

The on/off split is the one `stim_is_on` draws: `frames // 2` ON, the rest OFF. An odd count cannot split evenly, so it is marked `ASYM`: `Freq: 48.00 Hz (5 fr, 2 on/3 off) ASYM`. This appears in every flicker mode (3, 4 and 5). In a non-flicker mode the field ends `idle` and shows mode 5's standing setting.

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
[H] Text: ON | [M] Menu: OFF | [F/J] Custom: 15.00 Hz (16 fr, 8 on/8 off) | Mode: static_on | File: monical_2026-09-18_143201.json
```

It updates live and carries:

- `[H] Text: ON/OFF` — whether the readout is visible, with the key that changes it
- `[M] Menu: ON/OFF` — whether the keybinding overlay is showing
- `[F/J] Custom` — mode 5's realised rate, frame count and on/off split, **and the keys that adjust it**. This is the discoverability mode 5 otherwise lacks: nothing else on screen says how to change the rate it flickers at
- the mode name
- `SELECTED #k OFF SCREEN`, in multi mode, when the selected copy is off screen (§6.3)
- the session output filename, truncated from the left when long

The point is that even with the readout hidden, the operator can still see which toggles are on, what the custom rate is, and where the data is going.

### 8.3 Keybinding menu overlay

`[M]` toggles a reference card listing every binding for the current stimulus type: a dark panel at about 60% of the screen, centred, at 88% opacity so **the stimulus keeps rendering and stays visible behind it**.

```
KEYBINDINGS -- Text / letter string (reading/crowding)

MOVEMENT:  LEFT/RIGHT = X position | UP/DOWN = Y position
DISPLAY:   PAGEUP/DN = Background | +/- = Size | C/V = Contrast
FREQUENCY: F/J = Custom flicker +/-1 frame (selected copy) | ;/' = Viewing distance
MODES:     1=ON  2=OFF  3=15Hz  4=20Hz  5=Custom
           G=Gamma  7=Multi on/off  8=Uniformity
RING:      [ ] = Copies 2-16 | ,/. = Rotate +/-5 deg | 9/0 = Select copy
           / = Selected copy: flicker -> steady -> off
ACTIONS:   S=Snapshot  P=Preset  F12=Screenshot
           H=Toggle HUD  M=This menu  Q=Quit

THIS STIMULUS:
  B/N = Cycle string | I/O = Font | U/Y = Spacing | K/L = Rotation
  R/T = Red | E/W = Green | D/A = Blue | Z/X = Alpha

[M] or [ESC] to dismiss
```

The `THIS STIMULUS` block changes with the selected type, and gamma steps and spatial uniformity add a line for the keys those modes take over. Knobs stay live while the card is up, so a value can be adjusted while reading how.

**`[ESC]` is claimed in order:** cancel a running auto gamma sweep, else dismiss the menu, else quit. A running sweep is the most time-sensitive state, so it takes priority. Quitting is last, so ESC can never end the session while either a sweep or the menu is active.

Line 5 for `custom_png` shows:

```
File: [filename] | Alpha: [a:.3f] | Rot: [deg] deg
```

Filename only, not the full path — the path can be arbitrarily long and Line 5 is a single readout line. The full path is recorded in the snapshot.

---

## 9. Intro screen

White text on black background.

**Section 1 — System info:**
```
MONICAL -- Monitor Calibration Tool  v0.1
-----------------------------------------
Monitor:    [resolution] @ [refresh Hz]
PsychoPy:   [version]
Plugin:     psychopy_visionscience [OK / FAILED -- pip install psychopy-visionscience]
Output:     [session filename, §3.2]
Preset:     [preset filename, only with --preset]
```

A yellow monitor-dimension warning (§12) appears at the bottom when it applies.

**Section 2 — Stimulus selector:**
```
SELECT STIMULUS TYPE:
  [1] Radial checkerboard (SSVEP standard)
  [2] Gabor patch (attention/perception)
  [3] Sinusoidal grating (contrast/SF tuning)
  [4] Uniform patch (color/luminance calibration)
  [5] Custom PNG (your own texture)
  [6] Text / letter string (reading/crowding)
```

**Section 3 — Workflow tutorial (adapts to selection):**

Shows the recommended calibration workflow and the keybindings relevant to the selected stimulus type. Updates live as the user presses 1–6.

Custom PNG workflow block:

```
Load your experiment texture, verify rendering at target
size/position/contrast.
```

**Section 4 — Modes and actions** (the same for every type):
```
MODES: [1] static ON  [2] static OFF  [3] 15 Hz  [4] 20 Hz
       [5] custom Hz  [G] gamma steps  [8] spatial uniformity
       [7] MULTI ring on/off  [ / ] copies 2-16  [,/.] rotate
       [9/0] select copy -- [F/J] then sets ITS mode 5 frames
       [/] selected copy: flicker -> steady -> off
[S] snapshot  [P] save preset  [F12] screenshot  [A] auto gamma
[Q] quit (saves final state)
```

**Section 5 — Proceed:**
```
Press SPACE to begin.
```

`Q` or `ESC` on this screen aborts without writing a file.

---

## 10. Presets

A preset is a snapshot of the knobs, saved so a rig can be brought back to a known configuration without re-dialling every value.

**Save:** `[P]` during the test routine writes `presets/preset_YYYY-MM-DD_HHMMSS.json`, creating `presets/` if needed. The readout confirms with the filename.

**Load:** `--preset path/to/preset.json` applies the values before the main loop starts, and opens the intro selector on the stimulus type the preset was saved from. The operator can still change type before pressing SPACE; their choice wins.

```
python monical.py --preset presets/preset_2026-09-18_143201.json
```

A preset carries the stimulus, not the rig or the run. These keys are excluded: `frame_idx` and `snapshots` (live loop bookkeeping), `aspect`, `win_w` and `win_h` (come from the window), `image_path` (comes from `--image`), `font_requested` and `font_rendered` (resolved on each machine), and `text_extent` (measured each frame). `refresh_hz` is saved but only describes the rig the preset came from (below).

**Compatibility is deliberate in both directions.** Keys the preset omits keep their defaults, so a preset written by an older version still loads. Keys it carries that this version no longer recognises are ignored with a console note. Neither is an error — presets outlive tool versions.

**Values are sanitized on load.** Every numeric parameter is clamped to its knob range (§4, §5), whole-number knobs are rounded, orientation, rotation and ring offset wrap into 0–360, and `wedges` is rounded to the nearest even number, with ties going up (7 → 8), within 2–32. Non-numeric values fall back to the default. Each correction prints one console line, for example `Preset: wedges 7 -> 8 (rounded to even, range 2-32)`.

**Custom flicker in presets.** A preset stores mode 5 as `flicker_frames` together with `refresh_hz`, the refresh it was saved at. Loaded on a panel within 1% of that refresh, the frame count is used as is. Beyond 1%, the *rate* is what was dialled in, so it converts to the nearest frame count at the new refresh. A console line shows both, for example `custom flicker 16 fr (15.00 Hz) -> 4 fr (15.00 Hz)`. A preset from before frame stepping carries only `custom_freq_hz`, which converts to the nearest frame count with a console line. The saved `refresh_hz` never replaces the session's measured refresh.

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

Monical grew out of a single-stimulus photometer and oscilloscope calibration tool written for an Odegaard Lab SSVEP experiment. The radial checkerboard construction, flicker logic, and JSON snapshot format originate there. Monical generalizes the tool to arbitrary stimulus types and adds color calibration, visual angle computation, spatial uniformity checking, and multi-stimulus verification.

---

## 15. Open questions

1. ~~**Key bindings for stimulus-specific params.**~~ **Settled.** Pairs are reused across types, the readout and the `[M]` card always show the active legend, and alpha is `[Z/X]` on every type that has it:

   | Type | Z/X | R/T | E/W | D/A | B / N | U/Y | I/O | K/L |
   |---|---|---|---|---|---|---|---|---|
   | Radial | rings | wedges | – | – | – | – | – | – |
   | Gabor | SF | orientation | phase | envelope SD | – | – | – | – |
   | Grating | SF | orientation | phase | waveform | mask / – | – | – | – |
   | Uniform | alpha | red | green | blue | shape / – | – | – | – |
   | Custom PNG | alpha | rotation | – | – | – | – | – | – |
   | Text | alpha | red | green | blue | string fwd / back | spacing | font | rotation |

   The first key of each pair increases or steps forward. In gamma mode `[A]` is the auto sweep on every type (§6.5).

2. ~~**Monitor physical dimensions.**~~ **Settled.** Read from the PsychoPy Monitor object's stored width, with height derived from the pixel aspect (§7). A missing or implausible height shows a non-blocking warning on the intro screen and is recorded as `monitor_dimension_warning` (§12). There is no manual entry on the intro screen; the fix is in PsychoPy Monitor Center (MANUAL §8).

3. **Multiple monitor support.** `screen=0` hardcoded. Add a selector if labs routinely calibrate secondary displays.

4. ~~**Repo structure.**~~ **Settled.** Monical stays a single self-contained file, `monical.py`: no submodules, no config files, no build step (§3). Splitting it is out of scope. Presets (§10) and the auto gamma sweep (§6.5) landed in `monical.py`.
