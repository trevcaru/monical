# CLAUDE.md — Monical

Operating agreement for Claude Code in this repo.

## What this is

Monical is a standalone keyboard-driven monitor calibration tool for
vision science labs. Single Python script, PsychoPy dependency, MIT
license. It renders standard visual stimuli with real-time adjustable
parameters so scientists can measure with photometers and oscilloscopes.

## Repo structure

```
monical/
  monical.py              # The tool. Single file.
  docs/PRD.md             # Design authority. If code and PRD disagree, RAISE.
  calibration_values.json # Output file. Gitignored. Per-session rig data.
  README.md
  LICENSE
  CLAUDE.md               # This file.
```

## Working style

- **One task per prompt.** Do not bundle.
- **Read before writing.** Read the actual file, never infer contents.
- **Report findings before making changes.** If asked to read-and-report,
  do not make changes.
- **Raise, don't reconcile.** If code and PRD disagree, or if a request
  conflicts with an existing constraint, RAISE it. Do not silently fix.
- **Brief.** No gold-plating, no verbose explanations in code comments.
- **Sonnet** for read-and-report tasks.
- **Opus** for code generation.

## Hard invariants

These do not change without explicit discussion:

1. **Single file.** monical.py is self-contained. No submodules, no
   config files, no build step.
2. **PsychoPy is the only required dependency.** psychopy_visionscience
   is optional (guarded import, radial checkerboard only). If it's
   missing, all other modes still work.
3. **No experiment logic.** No EEG, eye tracking, trials, conditions,
   data collection. This is a measurement tool.
4. **No auto-correction.** Monical does not apply gamma tables, adjust
   parameters automatically, or close any feedback loop. The scientist
   reads the photometer, adjusts the knob, saves a snapshot.
5. **Keyboard + on-screen text only.** No GUI frameworks, no widgets,
   no mouse interaction.
6. **Output is reference only.** calibration_values.json is not loaded
   by any experiment. Values are read by humans and entered manually.

## Stimulus construction rules

- Each stimulus type must render identically to how it would in a
  PsychoPy experiment using the same parameters. The point of the
  tool is that measurements transfer.
- Do not add stimulus-specific rendering tricks, antialiasing, or
  visual enhancements that a standard PsychoPy experiment would not
  have.
- stim_is_on flicker logic: `return (frame_idx % frames) < (frames // 2)`.
  Stateless, integer arithmetic. Do not change this.
- Custom frequency always shows REALIZED Hz from integer frame count,
  not the requested value.

## Key repeat

Background gray, contrast, and color channels (R/G/B) support key
repeat: 1 second hold delay, then ~20 increments per second. All
other knobs are single-press only.

## Display precision

- Background gray, contrast, R, G, B, alpha: 3 decimal places
- Position, size: 2 decimal places
- Frequency: realized Hz from frame count
- Visual angle: 2 decimal places

## What not to do

- Do not add dependencies beyond PsychoPy and psychopy_visionscience.
- Do not split monical.py into multiple files without explicit approval.
- Do not add mouse interaction or GUI widgets.
- Do not make calibration_values.json auto-loadable by experiments.
- Do not add automated measurement (photodiode input, closed-loop).
