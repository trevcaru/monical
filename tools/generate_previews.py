#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate the stimulus and screen previews used by README.md and docs/MANUAL.md.

Development tool, not part of Monical. It deliberately does NOT import
monical.py or PsychoPy: no window is opened, nothing is measured, and it can
run headless in CI. matplotlib is already a declared PsychoPy dependency, so
this adds nothing to the runtime requirements.

    python tools/generate_previews.py

Writes eight 800x500 PNGs into docs/img/, overwriting them.

The stimulus maths below mirrors PsychoPy's own texture construction so the
previews are faithful rather than decorative:

  * radial     RadialStim polar mapping of the 4x4 checker texture
  * gabor      sin grating multiplied by a Gaussian alpha mask
  * grating    the same sin grating with a hard square edge
  * custom     the 8x8 fallback pattern monical generates without --image
  * text       the default ABCDEF string in the monospaced face

The HUD and intro text are verbatim snapshots of what monical.py prints, taken
from build_hud() and build_intro_text(). If either of those changes, re-run
this script and the images follow.
"""

import os

import numpy as np
import matplotlib
matplotlib.use('Agg')                     # no display needed
import matplotlib.pyplot as plt           # noqa: E402


# PsychoPy renders rgb 0.0 as mid-gray, which is 0.5 in matplotlib's 0-1
# floats. Every stimulus preview sits on that so the grays are comparable to
# what the tool actually shows.
PSYCHOPY_GRAY = 0.5
# The uniform patch defaults to rgb 0.0 -- the same mid-gray as the background,
# so on PSYCHOPY_GRAY it would be genuinely invisible. Its preview gets a
# darker ground, and shows the green channel driven up rather than the
# all-zero default, so the patch reads as a shape and as a colour surface.
UNIFORM_BG = 0.25
UNIFORM_RGB = (0.0, 0.7, 0.0)             # PsychoPy signed rgb, -1..+1
TEXT_BG = 0.0                             # intro and HUD are white on black
# Matches monical's default for this type: text starts white (rgb 1.0), unlike
# the uniform patch which starts at mid-gray 0.0.
TEXT_STIM_RGB = (1.0, 1.0, 1.0)
TEXT_STIM_STRING = 'ABCDEF'

WIDTH_PX, HEIGHT_PX = 800, 500
DPI = 100

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'img')

# Monical's own defaults, so the previews show the stimulus you actually get.
SF_CYCLES = 4.0          # sf = 4.0 cycles per height unit
PHASE = 0.5
ENVELOPE_SD = 0.06       # height units -- monical's default
PREVIEW_SD_PARAM = 3.0   # SDs from centre to patch edge, for the preview
STIM_SIZE = 0.225        # height units
CHECKER_CELLS = 8        # the --image fallback pattern
RADIAL_CELLS = 4         # the 4x4 dartboard texture

FONT = ['DejaVu Sans Mono', 'Consolas', 'Courier New', 'monospace']


# ---------------------------------------------------------------------------
# Figure plumbing
# ---------------------------------------------------------------------------

def new_canvas(bg):
    """Figure with a single axes filling it edge to edge. No chrome."""
    fig = plt.figure(figsize=(WIDTH_PX / float(DPI), HEIGHT_PX / float(DPI)),
                     dpi=DPI, facecolor=str(bg))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(str(bg))
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig, ax


def save(fig, name, bg):
    path = os.path.join(OUT_DIR, name)
    # pad_inches=0 with an axes that already fills the figure keeps the output
    # at exactly WIDTH_PX x HEIGHT_PX; a nonzero pad would shrink the content.
    fig.savefig(path, dpi=DPI, facecolor=str(bg), edgecolor='none',
                transparent=False, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    print('  wrote {}'.format(os.path.relpath(path, os.getcwd())))
    return path


def psychopy_rgb(rgb):
    """PsychoPy's signed -1..+1 colour to matplotlib's 0..1.

    rgb 0.0 is mid-gray, not black: [0, 0.7, 0] is green added to a mid-gray
    base, which is what the tool actually puts on screen for that fillColor.
    """
    return (np.asarray(rgb, dtype=float) + 1.0) / 2.0


def show_field(ax, field, bg):
    """Draw a 2-D luminance array or a 3-D RGB array, 0-1, no interpolation."""
    if field.ndim == 3:
        ax.imshow(np.clip(field, 0.0, 1.0),
                  interpolation='nearest', origin='lower')
    else:
        ax.imshow(field, cmap='gray', vmin=0.0, vmax=1.0,
                  interpolation='nearest', origin='lower')
    ax.set_xlim(0, field.shape[1])
    ax.set_ylim(0, field.shape[0])


def square_grid(px):
    """Coordinates in [-1, 1] over a px-by-px square patch."""
    axis = np.linspace(-1.0, 1.0, px)
    return np.meshgrid(axis, axis)


def gray_canvas_array(bg, patch, px):
    """Drop a px-by-px patch, centred, into an 800x500 field of `bg`.

    An RGB patch promotes the whole field to RGB so a coloured stimulus can
    sit on a gray ground.
    """
    if patch.ndim == 3:
        field = np.empty((HEIGHT_PX, WIDTH_PX, 3))
        field[:, :] = float(bg)
    else:
        field = np.full((HEIGHT_PX, WIDTH_PX), float(bg))
    top = (HEIGHT_PX - px) // 2
    left = (WIDTH_PX - px) // 2
    field[top:top + px, left:left + px] = patch
    return field


# ---------------------------------------------------------------------------
# Stimuli
# ---------------------------------------------------------------------------

def checker_texture(n=RADIAL_CELLS):
    """monical's CHECKER_PATTERN: n x n, sign-balanced per row."""
    pattern = np.ones((n, n))
    pattern[::2, ::2] = -1
    pattern[1::2, 1::2] = -1
    return pattern


def radial_checkerboard(px=420):
    """RadialStim's polar mapping: radius picks the row, angle the column.

    With radialCycles=1 and angularCycles=1 the 4x4 texture spans the radius
    once and the full 360 degrees once, giving 4 rings by 4 wedges. Outside
    r = 1 the disc is hard-edged -- no mask, matching the SSVEP construction.
    """
    pattern = checker_texture(RADIAL_CELLS)
    x, y = square_grid(px)
    radius = np.hypot(x, y)
    theta = np.arctan2(y, x) % (2.0 * np.pi)

    ring = np.clip((radius * RADIAL_CELLS).astype(int), 0, RADIAL_CELLS - 1)
    wedge = np.clip((theta / (2.0 * np.pi) * RADIAL_CELLS).astype(int),
                    0, RADIAL_CELLS - 1)

    # -1..+1 texture -> 0..1 luminance, then punch out everything past r = 1.
    disc = (pattern[ring, wedge] + 1.0) / 2.0
    return np.where(radius <= 1.0, disc, PSYCHOPY_GRAY)


def sin_grating(px, envelope):
    """sf cycles across the patch, ori 0 (vertical bars), phase 0.5.

    Alpha-blended toward the background exactly as PsychoPy's mask does:
    displayed = bg + alpha * (stim - bg).
    """
    x, _y = square_grid(px)
    # SF_CYCLES cycles ACROSS THE PATCH, which is what makes a legible preview.
    #
    # Note this is not Monical's default patch. There sf is quoted per HEIGHT
    # UNIT, so sf=4.0 on a size=0.225 patch puts only 4 * 0.225 = 0.9 cycles
    # inside the envelope -- under one full cycle, which previews as a blob
    # rather than a grating. These images show the carrier at 4 cycles per
    # patch so the structure is visible; read the real cycle count off HUD
    # line 5, not off these pictures.
    carrier = np.sin(2.0 * np.pi * (SF_CYCLES * (x + 1.0) / 2.0 + PHASE))
    stim = (carrier + 1.0) / 2.0
    return PSYCHOPY_GRAY + envelope * (stim - PSYCHOPY_GRAY)


def gabor(px=420):
    """Gaussian envelope, drawn with 3 SDs between centre and edge.

    PsychoPy's maskParams 'sd' counts how many SDs fit between centre and the
    patch edge, so 1 SD sits at 1 / sd in the patch's own -1..1 coordinates.
    PREVIEW_SD_PARAM = 3 is PsychoPy's own default and the conventional Gabor:
    alpha is down to ~1% by the edge, so the envelope vanishes into the
    background and no patch boundary is visible.

    Monical's default is wider. ENVELOPE_SD = 0.06 height units on a
    STIM_SIZE = 0.225 patch works out to sd = (0.225 / 2) / 0.06 = 1.875,
    which leaves alpha at ~17% where the square patch ends -- so the real
    stimulus at defaults has a faintly visible square edge. Lower the SD knob
    with [A] to about 0.035 to get the clean taper shown here.
    """
    sd_param = PREVIEW_SD_PARAM
    x, y = square_grid(px)
    radius = np.hypot(x, y)
    envelope = np.exp(-(radius ** 2) / (2.0 * (1.0 / sd_param) ** 2))
    return sin_grating(px, envelope)


def grating(px=420):
    """Same carrier, mask=None: full amplitude to a hard square edge."""
    return sin_grating(px, np.ones((px, px)))


def uniform_patch(px=420):
    """Solid colour at UNIFORM_RGB, on a darker ground.

    Shows the green channel driven up from the all-zero default, since three
    zeros render as the same mid-gray as the background.
    """
    patch = np.empty((px, px, 3))
    patch[:, :] = psychopy_rgb(UNIFORM_RGB)
    return patch


def text_stimulus_figure():
    """The default string in the monospaced face, on PsychoPy gray.

    Drawn with matplotlib's own text rather than a pixel array: this preview
    is about the glyphs, and rasterising them by hand would misrepresent the
    face monical actually renders.
    """
    fig, ax = new_canvas(PSYCHOPY_GRAY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    grey = psychopy_rgb(TEXT_STIM_RGB)
    ax.text(0.5, 0.5, TEXT_STIM_STRING, transform=ax.transAxes,
            family=FONT, fontsize=64, color=tuple(grey),
            va='center', ha='center')
    return fig


def fallback_checker(px=416):
    """The 8x8 pattern monical generates when --image is absent."""
    block = px // CHECKER_CELLS
    index = np.arange(px) // block
    pattern = np.where((index[:, None] + index[None, :]) % 2 == 0, 1.0, -1.0)
    return (pattern + 1.0) / 2.0


# ---------------------------------------------------------------------------
# Text screens -- verbatim from monical.py
# ---------------------------------------------------------------------------

HUD_TEXT = u"""\
1920x1080 | 239.94 Hz (σ=0.12ms) | Drops: 0 | PsychoPy 2026.2.2 | Dist: 40 cm
Mode: static_on | Stim: gabor | Out: monical_2026-09-18_143201.json
X: 0.66 (1672px) | Y: 0.00 (540px) | Size: 0.23 (243px, 10.61 deg) | Ecc: 28.57 deg
BG: 0.000 | Contrast: 1.000 | Freq: 15.00 Hz (16 frames, 50% duty, idle)
SF: 4.00 c/unit | Ori: 0.0 deg | Phase: 0.50 | SD: 0.060 (mask sd 1.88)
[H] Text: ON | [M] Menu: OFF | [F/J] Custom Hz: 15 | Mode: static_on | File: monical_2026-09-18_143201.json"""

INTRO_TEXT = u"""\
MONICAL -- Monitor Calibration Tool  v0.1
-------------------------------------------------------------
Monitor:    1920 x 1080  @  239.97 Hz
PsychoPy:   2026.2.2
Plugin:     psychopy_visionscience  [OK]

SELECT STIMULUS TYPE:
    [1] Radial checkerboard (SSVEP standard)
  > [2] Gabor patch (attention/perception)
    [3] Sinusoidal grating (contrast/SF tuning)
    [4] Uniform patch (color/luminance calibration)
    [5] Custom PNG (your own texture)

1. Gamma calibrate first [G]. Grating luminance is only
   meaningful on a linearized display.
2. Static ON [1]: set SF, orientation, phase and envelope
   SD to the values your experiment uses.
3. Photometer the mean luminance; it should equal the
   background at contrast 1.0 if gamma is correct.
4. Sweep contrast [C/V] and record the curve. Snapshot [S].

KNOBS: [Z/X] SF   [R/T] orientation   [E/W] phase   [D/A] SD
       plus the universal knobs.

MODES: [1] static ON  [2] static OFF  [3] 15 Hz  [4] 20 Hz
       [5] custom Hz  [G] gamma steps  [8] spatial uniformity
       [7] toggles DUAL (two copies at +/-X, same flicker)
[S] snapshot   [Q] quit (saves final state)

Press SPACE to begin."""


def text_screen(text, fontsize, linespacing=1.35):
    """White monospace on black, top-left anchored, like the real screens.

    Keep fontsize x linespacing x line count inside HEIGHT_PX: text that
    overflows the axes makes bbox_inches='tight' grow the saved image past
    800x500 instead of clipping.
    """
    fig, ax = new_canvas(TEXT_BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.03, 0.97, text, transform=ax.transAxes,
            family=FONT, fontsize=fontsize, color='white',
            va='top', ha='left', linespacing=linespacing)
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

STIMULI = [
    ('radial_checkerboard.png', radial_checkerboard, PSYCHOPY_GRAY),
    ('gabor.png', gabor, PSYCHOPY_GRAY),
    ('grating.png', grating, PSYCHOPY_GRAY),
    ('uniform.png', uniform_patch, UNIFORM_BG),
    ('custom_png.png', fallback_checker, PSYCHOPY_GRAY),
]


def main():
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    print('Writing previews to {}'.format(OUT_DIR))

    for name, builder, bg in STIMULI:
        patch = builder()
        field = gray_canvas_array(bg, patch, patch.shape[0])
        fig, ax = new_canvas(bg)
        show_field(ax, field, bg)
        save(fig, name, bg)

    save(text_stimulus_figure(), 'text.png', PSYCHOPY_GRAY)

    # 6 lines, longest 105 chars: 8.2pt keeps it inside 800px.
    save(text_screen(HUD_TEXT, 8.2), 'hud_example.png', TEXT_BG)
    # 31 lines: 9.2pt at 1.22 spacing fills the canvas without overflowing it.
    save(text_screen(INTRO_TEXT, 9.2, linespacing=1.22),
         'intro_screen.png', TEXT_BG)

    print('Done: {} images.'.format(len(STIMULI) + 3))


if __name__ == '__main__':
    main()
