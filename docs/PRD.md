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
- No other dependencies.

---

## 3. Architecture

Single-file script: `monical.py`. No submodules, no config files, no build step. Run it:

```
python monical.py
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

`calibration_values.json` — written on every `[S]` snapshot and on `[Q]` quit. Overwritten each run. Contains:

```json
{
  "monical_version": "0.1",
  "monitor_resolution": [1920, 1080],
  "measured_refresh_hz": 239.97,
  "psychopy_version": "2024.2.4",
  "viewing_distance_cm": 40.0,
  "snapshots": [
    {
      "timestamp": "2026-08-21T14:32:01",
      "stimulus_type": "radial_checkerboard",
      "mode": "static_on",
      "x_position": 0.66,
      "y_position": 0.00,
      "background_gray": 0.012,
      "disc_size": 0.225,
      "contrast": 1.000,
      "custom_frequency_hz": 15,
      "visual_angle_deg": 6.43,
      "stimulus_specific": {}
    }
  ],
  "final": { ... }
}
```

`stimulus_specific` holds per-type parameters (SF, ori, phase, SD, R, G, B, alpha — whichever apply).

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

---

## 5. Universal parameters

Active in all stimulus modes.

| Param | Key | Increment | Default | Range |
|-------|-----|-----------|---------|-------|
| X position | `[LEFT/RIGHT]` | ±0.01 | 0.66 | -1.0–1.0 |
| Y position | `[PAGEUP/PAGEDN]` | ±0.01 | 0.00 | -0.5–0.5 |
| Background gray | `[UP/DOWN]` | ±0.001 | 0.000 | -1.0–1.0 |
| Disc/patch size | `[+/-]` | ±0.01 | 0.225 | 0.01–2.0 |
| Contrast | `[C/V]` | ±0.001 | 1.000 | 0.0–1.0 |
| Custom frequency | `[F/H]` | ±1 Hz | 15 | 1–120 |
| Viewing distance | `[;/']` | ±1 cm | 40 | 1–500 |

### 5.1 Key repeat

Background gray, contrast, and color channels (R/G/B): after 1 second of holding the key, auto-repeat at ~20 increments per second. All other knobs are single-press.

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

---

## 7. Visual angle calculator

Active in all modes. Uses the current viewing distance and stimulus size to compute visual angle in degrees:

```
angle_deg = 2 * atan(size_cm / (2 * distance_cm)) * (180 / pi)
```

Where `size_cm` is derived from the stimulus size in height units and the monitor's physical height. If physical monitor dimensions aren't detectable, prompt for manual entry on the info screen.

Readout shows both stimulus size (degrees) and eccentricity (degrees) on screen at all times.

---

## 8. On-screen readout

Bottom center, small monospace text, updates every frame. Adapts to the current stimulus type.

```
Line 1: [resolution] | [refresh Hz avg] | PsychoPy [ver] | Dist: [cm] cm
Line 2: Mode: [name] | Stim: [type]
Line 3: X: [val] | Y: [val] | Size: [val] ([deg]°) | Ecc: [deg]°
Line 4: BG: [val] | Contrast: [val] | Freq: [realized] Hz ([frames] frames)
Line 5: [stimulus-specific params, e.g. SF: 4.0 | Ori: 0 | Phase: 0.50]
```

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
```

**Section 3 — Workflow tutorial (adapts to selection):**

Shows the recommended calibration workflow and the keybindings relevant to the selected stimulus type. Updates live as the user presses 1–4.

**Section 4 — Proceed:**
```
Press SPACE to begin.
```

---

## 10. What Monical is not

- Not an experiment. No EEG, eye tracking, trials, conditions, CSV data.
- Not a monitor profiler. It doesn't build or apply gamma tables — PsychoPy Monitor Center does that. Monical helps you collect the measurements.
- Not automatic. No photodiode input, no closed-loop correction. You read the photometer, you adjust the knob.
- No GUI widgets. Keyboard + on-screen text only.

---

## 11. Provenance

Seed file: `tools/test_stimulus.py` from the Odegaard Lab covert/overt SSVEP experiment repo (`covert_overt_2_stim`). The radial checkerboard construction, flicker logic, and JSON snapshot format originate there. Monical generalizes the tool to arbitrary stimulus types and adds color calibration, visual angle computation, spatial uniformity checking, and multi-stimulus verification.

---

## 12. Open questions

1. **Key bindings for stimulus-specific params.** The current mapping reuses R/T, E/W, D/A, Z/X across stimulus types with different meanings. This is compact but potentially confusing. Alternative: use a consistent semantic mapping and show a legend. Decide during implementation.

2. **Monitor physical dimensions.** Needed for visual angle. Auto-detect if possible (PsychoPy's Monitor object can store this). Fall back to manual entry on the info screen.

3. **Multiple monitor support.** `screen=0` hardcoded. Add a selector if labs routinely calibrate secondary displays.

4. **Repo structure.** Single file for now. If features grow (presets, automated gamma fitting, report generation), split into a package.
