# Monical

Keyboard-driven monitor calibration for vision science: renders standard stimuli with every parameter adjustable live, and exports the values you measure to JSON.

![Intro screen](docs/img/intro_screen.png)

## Install

PsychoPy is the only requirement. `psychopy_visionscience` is optional and needed only for the radial checkerboard:

```bash
pip install psychopy-visionscience
```

## Run

```bash
python monical.py
python monical.py --image assets/texture.png
```

Pick a stimulus type with `1`–`5`, press `SPACE`. No config files, no build step. Writes one file, `calibration_values.json`, beside the script.

## Stimulus types

| | |
|---|---|
| **Radial checkerboard** — SSVEP standard, locked to the 4×4 dartboard construction. Needs the plugin. | **Gabor patch** — sinusoidal carrier under a Gaussian envelope. SF, orientation, phase, envelope SD. |
| ![Radial checkerboard](docs/img/radial_checkerboard.png) | ![Gabor patch](docs/img/gabor.png) |
| **Sinusoidal grating** — the same carrier, no envelope. Contrast sensitivity, SF tuning. | **Uniform patch** — per-channel R/G/B and alpha. The color and luminance surface. |
| ![Sinusoidal grating](docs/img/grating.png) | ![Uniform patch](docs/img/uniform.png) |
| **Custom PNG** — your own texture via `--image`. Without it, this generated 8×8 checkerboard. | |
| ![Custom PNG fallback](docs/img/custom_png.png) | |

## Modes

`1` static ON · `2` static OFF · `3` flicker 15 Hz · `4` flicker 20 Hz · `5` flicker at the custom rate · `G` gamma steps (11 levels) · `8` spatial uniformity (3×3 grid) · `7` toggles dual stimuli at ±X

Flicker is driven by integer frame counts, so the readout always reports the **realized** frequency, never the requested one.

## Keys

| | |
|---|---|
| Arrows | move the stimulus, X/Y ±0.005 |
| `PAGEUP`/`PAGEDN` | background gray ±0.001 |
| `+`/`-` | size ±0.01 |
| `C`/`V` | contrast ±0.001 |
| `F`/`H` | custom frequency ±1 Hz |
| `;`/`'` | viewing distance ±1 cm |
| `Z/X` `R/T` `E/W` `D/A` | stimulus-specific (SF, orientation, phase, SD — or R, G, B, alpha) |
| `S` / `Q` | snapshot / quit and save |

Position, background, contrast and the color channels auto-repeat at ~60/s after a 1-second hold. Full table in [docs/MANUAL.md](docs/MANUAL.md#4-keybindings).

## Readout

![HUD readout](docs/img/hud_example.png)

Five lines, updated every frame: measured refresh with frame-interval σ and a dropped-frame counter, mode, geometry in degrees, luminance and realized flicker rate, then the active stimulus parameters.

The refresh figure is a rolling 120-frame average of real flip-to-flip intervals, not the startup measurement — if the two disagree by more than 5 Hz the tool says so, because every flicker frame count depends on getting it right.

## Output

`calibration_values.json`, rewritten on every snapshot and on quit. **Overwritten each run** — copy it out between sessions.

```json
{
  "startup_refresh_hz": 239.97,
  "final_rolling_refresh_hz": 239.94,
  "total_dropped_frames": 0,
  "vsync": true,
  "monitor_width_cm": 59.8,
  "snapshots": [
    {
      "snapshot_number": 1,
      "mode": "static_on",
      "x_position": 0.66,
      "background_gray": 0.012,
      "contrast": 1.0,
      "visual_angle_deg": 6.43,
      "eccentricity_deg": 28.57,
      "stimulus_specific": {}
    }
  ]
}
```

Alongside the parameters, each session records the rig it was measured on — resolution, physical size, units, color space, vsync state, PsychoPy and Python versions — so the numbers stay interpretable later. Snapshots carry the rolling refresh rate and drop count at the moment they were taken, so you can tell whether timing was healthy for that reading.

Nothing reads this file back. You transcribe the values into your experiment by hand.

## Documentation

- [docs/MANUAL.md](docs/MANUAL.md) — operating manual: full keybindings, five step-by-step calibration workflows, output reference, troubleshooting.
- [docs/PRD.md](docs/PRD.md) — design authority: what each stimulus is, why, and the exact construction.

## What it is not

Not an experiment, not a monitor profiler, not automatic. It does not build or apply gamma tables — PsychoPy Monitor Center does that; Monical helps you collect the measurements. No photodiode input, no closed loop, no mouse, no GUI widgets.

## License

MIT.
