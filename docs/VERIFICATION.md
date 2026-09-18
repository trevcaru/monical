# Verification Protocol

Confirm that Monical's on-screen readout and JSON output match what the display
is physically doing.

---

## Equipment Needed

- Photometer (PR-655, i1Display, or equivalent)
- Photodiode + oscilloscope
- Ruler or calipers (stimulus dimensions on screen)
- Tape measure (viewing distance and monitor dimensions)

---

## Before You Start

- **Measure your monitor's physical height** with a tape measure. Compare
  against `monitor_height_cm` in the JSON. If they don't match, fix it in
  PsychoPy Monitor Center before proceeding — every visual angle and
  eccentricity value depends on this. The stored value comes from the Monitor
  object's *width*, so that is what you correct; height is derived from it and
  the pixel aspect ratio.
- **Warm the display up for 20+ minutes.** LCD luminance drifts on cold start.
- **Confirm `vsync` is `true`** in the JSON. If false, timing measurements are
  meaningless.
- Monical reports **frame rate** (flip-to-flip interval), which equals display
  refresh rate only under vsync. The JSON records both the vsync state and the
  raw measurements (`startup_refresh_hz`, `final_rolling_refresh_hz`) so you
  can judge which you are looking at.
- If the console printed a divergence warning at any point, stop and resolve it
  first — it means the startup measurement and the rolling average disagree by
  more than 5 Hz, and every flicker frame count derives from the startup value.

---

## 1. Timing Verification

a) Select any stimulus type. Enter flicker mode `3` (15 Hz).
b) Place the photodiode on the stimulus.
c) Read the oscilloscope. Measure the period and compute frequency.
d) Compare against the HUD's realized Hz (line 4) and the JSON's
   `flicker_realized_hz`.
e) Repeat for mode `4` (20 Hz) and mode `5` with at least three custom values
   (e.g. 6, 10, 30 Hz). Set the custom rate with `F` / `H` before pressing `5`.
f) Check duty cycle. At 240 Hz all modes are 50/50. At 60 Hz the 20 Hz mode is
   33/67 — 1 frame on, 2 off — because 60/20 = 3 frames and the on-half is
   `frames // 2`. Expected, not a bug.
g) Record for each frequency: requested Hz, realized Hz from the HUD, measured
   Hz from the scope. They should agree within scope measurement precision.
h) During a clean run the HUD drop counter should read `0`. If it increments
   during measurement, the timing data for that interval is unreliable.

**Read the realized value, never the requested one.** The HUD shows frames per
cycle beside it (`Freq: 14.998 Hz (16 frames, 8 on / 8 off)`). Only divisors of
the refresh rate are exactly achievable — at 60 Hz, a requested 17 Hz lands on
4 frames and delivers ~15 Hz.

**Pass criteria:** scope frequency matches realized Hz within ±0.1 Hz for every
tested frequency.

---

## 2. Luminance and Gamma Verification

a) Press `G` to enter gamma mode. Place the photometer at screen center — the
   fixation cross is hidden in this mode.
b) Step through all 11 levels with `LEFT` / `RIGHT`. At each level press `S` to
   snapshot, then record the photometer reading.
c) You now have 11 pairs: (PsychoPy gray value, measured cd/m²). Plot them.
d) Expected: a monotonic curve. The shape reveals the display's gamma. A
   straight line means gamma = 1 (linearized). A power curve means the
   display's native gamma is active.
e) Compare against what PsychoPy Monitor Center has stored for this display's
   gamma. If Monical's measurements don't match the stored correction, the
   correction is stale or wrong.

The snapshot records `gamma_level` (PsychoPy −1 to +1) and `gamma_step_index`
in `stimulus_specific`, so the JSON tells you which level each reading belongs
to. The HUD also shows the 8-bit equivalent:

| Step | rgb | 8-bit | | Step | rgb | 8-bit |
|---|---|---|---|---|---|---|
| 1/11 | −1.0 | 0 | | 7/11 | +0.2 | 153 |
| 2/11 | −0.8 | 25 | | 8/11 | +0.4 | 178 |
| 3/11 | −0.6 | 51 | | 9/11 | +0.6 | 204 |
| 4/11 | −0.4 | 76 | | 10/11 | +0.8 | 230 |
| 5/11 | −0.2 | 102 | | 11/11 | +1.0 | 255 |
| 6/11 | +0.0 | 128 | | | | |

Let the panel settle a second or two after each step before reading.

**Pass criteria:** monotonic increase with no reversals. Shape matches expected
gamma for this display's configuration.

---

## 3. Channel Independence

Select **uniform patch (type 4)** at startup. The R/G/B keys exist only for
that type — you cannot drive channels from a Gabor or checkerboard session.

Keys: `R`/`T` = red, `E`/`W` = green, `D`/`A` = blue, all ±0.001, hold to
scroll at ~60/s. Driving one channel the full 0 → −1 is 1000 steps, about 17
seconds of holding. Budget for it.

a) Select uniform patch (type 4). Mode `1`.
b) Set G = −1, B = −1. Sweep R from −1 to +1 in steps. Record photometer
   luminance at each step.
c) Repeat for G only (R = −1, B = −1) and B only (R = −1, G = −1).
d) Now set R = 1, G = −1, B = −1. Record luminance. Then set R = 1, G = 0,
   B = −1. If the luminance changes by more than the green channel's own
   contribution at that level, green is leaking into the red measurement — the
   channels are not independent.
e) Repeat the cross-channel checks for all three pairs.

Do **not** use gamma mode (`G`) for per-channel work. It drives all three
channels to the same level and only ever renders gray.

**Pass criteria:** activating an off-channel should not change the measured
luminance of the on-channel by more than your photometer's noise floor, once
the off-channel's own emission is accounted for.

---

## 4. Contrast Verification

a) Select any stimulus. Mode `1` (static ON). Photometer on stimulus center.
b) Set contrast to 1.0. Record luminance (`L_on`).
c) Mode `2` (static OFF). Record luminance (`L_off`).
d) Mode `1` again. Step contrast down to 0.5 with `C` / `V`. Record
   (`L_half`).
e) Michelson contrast = (L_on − L_off) / (L_on + L_off). At contrast 1.0 this
   should be the display's maximum. At contrast 0.5 it should be roughly half
   (linear) or follow the gamma curve (uncorrected).
f) Step through several contrast values (0.0, 0.25, 0.5, 0.75, 1.0), snapshot
   and measure each.

Contrast steps at ±0.001 and auto-repeats — hold `V` for about 8 seconds to go
from 1.0 to 0.5. Do not move the probe between the ON and OFF readings.

**Pass criteria:** measured contrast tracks the contrast knob monotonically.
The exact relationship depends on whether gamma correction is active.

---

## 5. Spatial Verification

a) Select any stimulus. Mode `1`. Set a visible size (e.g. 0.225).
b) Measure the stimulus diameter on screen with a ruler, in cm.
c) Expected diameter = `disc_size` × `monitor_height_cm`. Size is in height
   units, so 0.225 means 22.5% of monitor height.
d) Compare measured against expected. They should agree within 1 mm.
e) **Eccentricity:** place the stimulus off-center (e.g. x = 0.66). Measure the
   distance from screen center to stimulus center, in cm. Expected =
   `x_position` × `monitor_height_cm`. Note this is monitor *height*, not
   width — height units are the same in both axes.
f) **Visual angle:** with your known viewing distance, compute
   `angle = 2 * atan(diameter_cm / (2 * distance_cm)) * (180/pi)` and compare
   against the HUD readout.

Size and eccentricity use different formulas, and the HUD reports them
separately. Size is an extent straddling the line of sight, so it carries the
factor of 2 above. Eccentricity is a displacement that falls entirely on one
side, so it does not: `ecc = atan(x_cm / distance_cm) * (180/pi)`. Check each
against its own formula.

**Pass criteria:** physical measurements agree with computed values within 1 mm
(size) and 0.1 degrees (angle).

---

## 6. Spatial Uniformity

a) Enter mode `8`. Set the uniform patch to mid-gray (R = G = B = 0,
   alpha = 1 — these are the defaults, so no adjustment is needed unless you
   changed them).
b) Step through all 9 grid positions with the arrow keys. Snapshot and record
   the photometer reading at each.
c) Compute the max/min ratio across all 9 positions.

The fixation cross is hidden here too. Arrow keys move the patch, not the
stimulus, so position knobs are unavailable in this mode; `PAGEUP`/`PAGEDN`
still adjust background gray. The snapshot records `grid_position`, `grid_x`,
`grid_y`, and — if your session type is not the uniform patch — the patch
colour as `patch_r/g/b/alpha`.

**Pass criteria:** depends on your display, but a uniformity ratio > 0.85 is
typical for a decent LCD. Corner falloff is normal. The point is to document
it, not to pass or fail — you will use these values to decide whether your
experiment's stimulus positions see meaningfully different luminance.

---

## 7. Dual Stimulus Symmetry

a) Toggle dual mode (key `7`) in static ON. Copies appear at +x and −x.
b) Measure the luminance of both stimuli. They should match within photometer
   precision.
c) Enter a flicker mode. Dual is a toggle, not a mode, so it stays on. Verify
   on the oscilloscope that both stimuli flicker in sync — same phase, same
   frequency.

Both copies are drawn in the same frame from the same on/off test, so any phase
offset you measure is the display's (scanout, local dimming), not Monical's.

**Pass criteria:** luminance difference < 1% between the two positions. Zero
phase offset on the scope trace.

---

## Recording Results

Every `S` press writes the current state to this session's output file,
`monical_YYYY-MM-DD_HHMMSS.json`, named at startup and shown on the intro
screen. A
complete verification session should produce ~40–60 snapshots covering all the
checks above. The JSON is the record — take snapshots in a consistent order,
since the file records the sequence with timestamps and `snapshot_number`.

**Each run gets its own file**, so an earlier verification is never destroyed
by a later one. The filename carries the start time; note which file belongs to
which run.

For the gamma section, `A` runs the 11-level ramp automatically at 2 s per
level and snapshots each one — see MANUAL workflow (g). `P` saves the current
knobs as a preset so a verified configuration can be restored with `--preset`,
and `F12` captures the screen to `screenshots/`.

Each snapshot also carries `rolling_refresh_hz` and `dropped_frames_total` at
the moment it was taken, so you can tell afterwards whether timing was healthy
for that particular reading.

---

## Quick Sanity Checks (5 minutes)

If you don't have time for the full protocol:

1. **Gamma mode:** do the 11 levels go dark-to-bright monotonically? Eyes only,
   no photometer.
2. **Flicker 15 Hz:** does it look like 15 Hz? Subjective, but catches gross
   errors.
3. **Check `monitor_height_cm`.** If it's 12.56 or 20.0 — or if
   `monitor_width_cm` is exactly 30.0 — it's the PsychoPy `testMonitor`
   default and every angle is wrong.
4. **Check `startup_refresh_hz`.** If it's exactly 60.0, `getMsPerFrame`
   probably returned the fallback; a real measurement never lands on a round
   number.
5. **Drops counter should be 0** during normal operation.
