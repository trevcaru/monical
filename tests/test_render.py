"""Rendering tests: draw into a hidden PsychoPy window and compare pixels.

Needs an OpenGL context. Without one -- or with MONICAL_SKIP_RENDER=1 set --
the whole module is skipped with the reason.

Python's cyclic garbage collector is off for the whole module. With it on,
collecting discarded PsychoPy/pyglet stimuli -- at any point, even between
tests -- intermittently left the next draw to crash with an access violation
in the GL driver (seen on Windows, PsychoPy 2026.2.2, pyglet 1.4). With it
off the module ran clean every time.

    python -m unittest tests.test_render
"""
import gc
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import monical as m  # noqa: E402

W, H = 1920, 1080                 # the resolution the PRD's claims assume
WIN = None
# Every window stays open until the module ends: closing one mid-run can
# release the GL context the others draw with.
WINDOWS = []


def setUpModule():
    global WIN
    if os.environ.get('MONICAL_SKIP_RENDER'):
        raise unittest.SkipTest('MONICAL_SKIP_RENDER is set')
    try:
        WIN = make_window((W, H))
    except Exception as err:                                 # noqa: BLE001
        raise unittest.SkipTest('no OpenGL window available ({}: {})'.format(
            type(err).__name__, err))
    gc.disable()


def tearDownModule():
    while WINDOWS:
        WINDOWS.pop().close()
    gc.enable()


def make_window(size, color=0.0):
    from psychopy import visual
    win = visual.Window(size=size, fullscr=False, units='height',
                        color=[color] * 3, colorSpace='rgb', useFBO=True,
                        allowStencil=False, winType='pyglet',
                        checkTiming=False, autoLog=False)
    win.winHandle.set_visible(False)
    WINDOWS.append(win)
    return win


_bg = {'value': 0.0}


def grab(*stims, bg=0.0, win=None):
    """Draw `stims` on a cleared back buffer over `bg`; return int RGB."""
    win = win or WIN
    if win is WIN and _bg['value'] != bg:
        win.color = [bg] * 3
        win.flip()                  # the window colour takes on a flip
        _bg['value'] = bg
    win._setCurrent()               # several windows share the process
    win.clearBuffer()
    for stim in stims:
        stim.draw()
    img = np.asarray(win.getMovieFrame(buffer='back')).astype(int)
    win.movieFrames = []
    return img


class CopyAt(object):
    """Draws `stim` at `pos`, so one grab can hold every ring copy."""

    def __init__(self, stim, pos):
        self.stim, self.pos = stim, pos

    def draw(self):
        self.stim.pos = self.pos
        self.stim.draw()


class RenderCase(unittest.TestCase):
    """Makes the main window's GL context current before every test.

    Stimuli are built in whichever context is current, and the intro test
    opens windows of its own.
    """

    def setUp(self):
        WIN._setCurrent()


def differing(a, b):
    return int((np.abs(a - b).max(axis=2) > 0).sum())


def state(stim, **kwargs):
    s = m.default_state(stim)
    s.update(aspect=W / float(H), win_w=W, win_h=H)
    s.update(kwargs)
    return s


def lit(img, bg_px):
    """Mask of pixels more than 2 levels from the background pixel value
    (0 on black, 128 on PsychoPy mid-gray)."""
    return np.abs(img - bg_px).max(axis=2) > 2


# =============================================================================
# Radial checkerboard (PRD 4.1)
# =============================================================================

@unittest.skipUnless(m.HAS_RADIAL, 'psychopy_visionscience not installed')
class RadialTests(RenderCase):

    def test_defaults_pixel_identical_to_v1(self):
        # v1: the original SSVEP construction, a 4x4 texture with
        # radialCycles=1 and angularCycles left at RadialStim's default.
        v1_tex = np.ones((4, 4))
        v1_tex[::2, ::2] = -1
        v1_tex[1::2, 1::2] = -1
        for size, pos in ((0.225, (0.66, 0.0)), (0.9, (0.0, 0.0))):
            v1 = m.RadialStim(win=WIN, tex=v1_tex, size=size, radialCycles=1,
                              texRes=256, opacity=1, contrast=1.0, pos=pos,
                              autoLog=False)
            new = m.make_radial(WIN, state(m.STIM_RADIAL, size=size,
                                           x_pos=pos[0], y_pos=pos[1]))
            self.assertEqual(differing(grab(v1), grab(new)), 0, (size, pos))

    def test_n_equal_width_rings(self):
        radius = 0.9 * H / 2.0
        r = np.arange(4, int(radius) - 1)          # skip the wedge apex
        for rings in range(1, 21):
            img = grab(m.make_radial(WIN, state(
                m.STIM_RADIAL, size=0.9, x_pos=0.0, y_pos=0.0, rings=rings)))
            counts, widths = [], None
            for theta in np.linspace(0, 2 * np.pi, 90, endpoint=False) + 0.013:
                xs = np.round(W / 2 + r * np.cos(theta)).astype(int)
                ys = np.round(H / 2 + r * np.sin(theta)).astype(int)
                v = img[ys, xs, 0] > 128
                edges = np.flatnonzero(np.diff(v.astype(int))) + 1
                w = np.diff(np.concatenate([[0], edges, [len(v)]]))
                w[0] += 4
                counts.append(len(w))
                if len(w) == rings and widths is None:
                    widths = w
            self.assertEqual(int(np.median(counts)), rings)
            self.assertLessEqual(int(widths.max() - widths.min()), 3, rings)

    def test_live_setters_match_fresh_construction(self):
        live = m.make_radial(WIN, state(m.STIM_RADIAL, size=0.9, x_pos=0.0))
        for rings, wedges in ((1, 2), (20, 32), (3, 10), (4, 16)):
            s = state(m.STIM_RADIAL, size=0.9, x_pos=0.0, rings=rings,
                      wedges=wedges)
            live.radialCycles, live.angularCycles = m.radial_cycles_for(s)
            self.assertEqual(differing(grab(live),
                                       grab(m.make_radial(WIN, s))), 0)


# =============================================================================
# Uniform patch (PRD 4.4)
# =============================================================================

class UniformPatchTests(RenderCase):

    CASES = [
        ('mid-gray on -0.5', dict(r=0.0, g=0.0, b=0.0), -0.5),
        ('near-black', dict(r=-0.95, g=-0.95, b=-0.95), 0.0),
        ('pure red', dict(r=1.0, g=-1.0, b=-1.0), 0.0),
        ('pure green', dict(r=-1.0, g=1.0, b=-1.0), 0.0),
        ('pure blue', dict(r=-1.0, g=-1.0, b=1.0), 0.0),
        ('green alpha 0.5 over 0.3', dict(r=-1.0, g=0.7, b=-1.0, alpha=0.5),
         0.3),
        ('0.4 gray contrast 0.5 over -0.2',
         dict(r=0.4, g=0.4, b=0.4, contrast=0.5), -0.2),
    ]

    def test_rect_and_circle_render_identical_colour(self):
        cy, cx = H // 2, int(W / 2 + 0.66 * H)
        for label, kwargs, bg in self.CASES:
            s = state(m.STIM_UNIFORM, **kwargs)
            rect = grab(m.make_patch(WIN, s, 'rect'), bg=bg)
            circ = grab(m.make_patch(WIN, s, 'circle'), bg=bg)
            a = rect[cy - 50:cy + 50, cx - 50:cx + 50]
            b = circ[cy - 50:cy + 50, cx - 50:cx + 50]
            self.assertEqual(differing(a, b), 0, label)

    def test_circle_diameter_is_size(self):
        s = state(m.STIM_UNIFORM, r=1.0, g=1.0, b=1.0, x_pos=0.0)
        row = grab(m.make_patch(WIN, s, 'circle'))[H // 2]
        self.assertLessEqual(abs(int((row[:, 0] > 200).sum()) - 0.225 * H),
                             1.5)


# =============================================================================
# Text (PRD 4.6)
# =============================================================================

def text_state(text, family, size, pos=(0.0, 0.0), **kwargs):
    s = state(m.STIM_TEXT, text_string=text, font_family=family, size=size,
              x_pos=pos[0], y_pos=pos[1], **kwargs)
    s['font_requested'], s['font_rendered'] = m.resolve_font(family)
    return s


def glyph_string(s, fast=True):
    g = m.GlyphString(WIN, fast=fast)
    g.pos = (s['x_pos'], s['y_pos'])
    g.update(s)
    return g


class TextTests(RenderCase):

    STRINGS = list(m.TEXT_PRESETS) + ['AHO', 'Hamburgefonts']

    def test_fast_path_matches_per_glyph(self):
        half = 0.5 / H
        fast_used = 0
        for text in self.STRINGS:
            for family in m.CHOICES['font_family']:
                for size in (0.1, 0.225):
                    for pos in ((0.0, 0.0), (half, half)):
                        s = text_state(text, family, size, pos)
                        fast = glyph_string(s, fast=True)
                        slow = glyph_string(s, fast=False)
                        self.assertGreater(len(slow.glyphs), 1)
                        fast_used += len(fast.glyphs) == 1
                        self.assertEqual(
                            differing(grab(fast), grab(slow)), 0,
                            (text, family, size, pos))
        self.assertGreater(fast_used, 0)

    def test_per_glyph_matches_single_textstim(self):
        from psychopy import visual
        cases = [(text, 0.225, (0.0, 0.0))
                 for text in ['AHO', 'WAVE'] + list(m.TEXT_PRESETS)]
        # Other sizes, at fractional positions.
        cases += [('WAVE', 0.225, (0.66, 0.0)), ('AHO', 0.1, (-0.4137, 0.123)),
                  ('Hamburgefonts', 0.05, (0.2, -0.3))]
        for text, size, pos in cases:
            for family in m.CHOICES['font_family']:
                s = text_state(text, family, size, pos)
                one = visual.TextStim(WIN, text=text, font=s['font_requested'],
                                      height=size, pos=pos, colorSpace='rgb',
                                      autoLog=False)
                self.assertEqual(
                    differing(grab(glyph_string(s, fast=False)), grab(one)),
                    0, (text, family, size, pos))

    def test_rotation_turns_string_rigidly(self):
        s = text_state('AHO', 'monospace', 0.225, rotation_deg=90.0)
        g = glyph_string(s, fast=False)
        centres_x, centres_y = [], []
        for glyph, (dx, dy) in zip(g.glyphs, g.offsets):
            glyph.pos = (dx, dy)
            ys, xs = np.nonzero(lit(grab(glyph), 128))
            centres_x.append((xs.min() + xs.max()) / 2.0)
            centres_y.append((ys.min() + ys.max()) / 2.0)
        self.assertLessEqual(max(centres_x) - min(centres_x), 0.5)
        self.assertEqual(centres_y, sorted(centres_y))  # reading order, down

    def test_missing_font_reports_and_renders_fallback(self):
        from psychopy import visual
        saved = m.FONT_CANDIDATES['serif']
        m.FONT_CANDIDATES['serif'] = ['No Such Font Monical']
        try:
            requested, rendered = m.resolve_font('serif')
        finally:
            m.FONT_CANDIDATES['serif'] = saved
        self.assertEqual(requested, 'No Such Font Monical')
        self.assertNotEqual(rendered, requested)
        s = m.default_state(m.STIM_TEXT)
        s.update(font_family='serif', font_requested=requested,
                 font_rendered=rendered)
        self.assertIn('FALLBACK', m.font_label(s))
        self.assertTrue(m.stimulus_specific(s)['font_fallback'])
        a = visual.TextStim(WIN, text='AHO', font=requested, height=0.2,
                            autoLog=False)
        b = visual.TextStim(WIN, text='AHO', font=rendered, height=0.2,
                            autoLog=False)
        self.assertEqual(differing(grab(a), grab(b)), 0)


# =============================================================================
# Multi-stimulus ring: off-screen flags and the selection marker (PRD 6.3)
# =============================================================================

class RingTests(RenderCase):

    def test_offscreen_flags_match_clipping(self):
        # Copies within 1.5 px of an edge are left out: a half-pixel
        # overhang is flagged (correctly) but barely changes a pixel count.
        layouts = [(0.66, 3, 0.225), (0.2, 8, 0.05), (0.66, 16, 0.1),
                   (-0.66, 5, 0.225), (0.45, 4, 0.3), (0.3, 6, 0.3)]
        half_w, compared = W / (2.0 * H), 0
        for x, n, size in layouts:
            s = state(m.STIM_UNIFORM, r=1.0, g=1.0, b=1.0, multi=True,
                      multi_count=n, x_pos=x, size=size)
            m.sync_stim_frames(s)
            patch = m.make_patch(WIN, s, 'rect')
            patch.pos = (0.0, 0.0)
            full = lit(grab(patch), 128).sum()
            flags = m.offscreen_copies(s)
            for pos, flag in zip(m.ring_positions(s), flags):
                over = max(abs(pos[0]) + size / 2 - half_w,
                           abs(pos[1]) + size / 2 - 0.5) * H
                if abs(over) < 1.5:
                    continue
                patch.pos = pos
                clipped = lit(grab(patch), 128).sum() < 0.995 * full
                self.assertEqual(flag, bool(clipped), (x, n, size, pos))
                compared += 1
        self.assertGreater(compared, 35)

    def test_text_ring_offscreen_flags_match_clipping(self):
        s = text_state('ABCDEF', 'monospace', 0.225, pos=(0.66, 0.0),
                       multi=True, multi_count=2)
        g = glyph_string(s)
        s['text_extent'] = g.extent()
        g.pos = (0.0, 0.0)
        full = lit(grab(g), 128).sum()
        clipped = []
        for pos in m.ring_positions(s):
            g.pos = pos
            clipped.append(bool(lit(grab(g), 128).sum() < 0.995 * full))
        self.assertEqual(m.offscreen_copies(s), clipped)
        self.assertEqual(clipped, [True, True])

    def test_marker_never_touches_a_copy(self):
        scene = m.build_scene(WIN, state(m.STIM_UNIFORM), None, verbose=False)
        # One patch, resized per layout as the session loop resizes its own.
        patch = m.make_patch(WIN, state(m.STIM_UNIFORM, r=1.0, g=1.0, b=1.0),
                             'rect')
        layouts = 0
        for n in (2, 3, 4, 6, 8, 12, 16):
            for size in (0.05, 0.1, 0.225):
                for x in (0.4, -0.4):
                    for sel in sorted({0, n // 2}):
                        s = state(m.STIM_UNIFORM, r=1.0, g=1.0, b=1.0,
                                  multi=True, multi_count=n, x_pos=x,
                                  size=size, selected_index=sel)
                        m.sync_stim_frames(s)
                        segment = m.marker_segment(s, m.footprint_radius(s))
                        if segment is None:
                            continue
                        m.size_patch(patch, size)
                        copies = lit(grab(*[CopyAt(patch, pos) for pos in
                                            m.ring_positions(s)], bg=-1.0), 0)
                        scene.marker.vertices = list(segment)
                        marker = lit(grab(scene.marker, bg=-1.0), 0)
                        self.assertTrue(marker.any())
                        self.assertFalse((copies & marker).any(),
                                         (n, size, x, sel))
                        layouts += 1
        self.assertGreater(layouts, 70)

    def test_marker_hidden_with_readout(self):
        s = state(m.STIM_UNIFORM, multi=True, multi_count=4)
        m.sync_stim_frames(s)
        scene = m.build_scene(WIN, s, None, verbose=False)
        calls = []
        scene.marker.draw = lambda *a, **k: calls.append(1)
        timer = m.FrameTimer(60.0)
        for hud, want in ((True, 1), (False, 0)):
            del calls[:]
            s['hud_visible'] = hud
            m.render_frame(WIN, scene, s, 60.0, (W, H), 33.0, timer)
            self.assertEqual(len(calls), want, hud)
        WIN.clearBuffer()


# =============================================================================
# Readout and intro layout (PRD 8, 9)
# =============================================================================

class LayoutTests(RenderCase):

    def hud_states(self):
        long_text = 'THE QUICK BROWN FOX JUMPS OVER'
        yield 'gabor', state(m.STIM_GABOR)
        yield 'text, wrapped line 5', state(m.STIM_TEXT, text_string=long_text)
        ring = state(m.STIM_GRATING, multi=True, multi_count=16,
                     mode=m.MODE_FLICKER_CUSTOM)
        m.sync_stim_frames(ring)
        yield '16-copy ring', ring
        yield 'gamma', state(m.STIM_UNIFORM, mode=m.MODE_GAMMA)
        yield 'uniformity', state(m.STIM_UNIFORM, mode=m.MODE_UNIFORMITY)
        yield 'png, long name', state(
            m.STIM_CUSTOM_PNG, image_path='a_rather_long_texture_name_' * 2 +
            '.png')

    def test_per_line_readout_matches_single_block(self):
        from psychopy import visual
        for label, s in self.hud_states():
            lines = m.build_hud(s, (W, H), 60.0, 59.94, 33.0, sd_ms=0.12,
                                drops=0, out_name='monical_x.json').split('\n')
            y = m.HUD_POS_Y + max(0, len(lines) - 5) * m.HUD_LINE_PITCH / 2.0
            per_line = m.HudLines(WIN)
            per_line.show(lines, y)
            block = visual.TextStim(
                WIN, text='\n'.join(lines), font=m.READOUT_FONT,
                height=m.HUD_HEIGHT, color='white', pos=(0, y),
                wrapWidth=m.HUD_WRAP_W, alignText='center',
                anchorHoriz='center', autoLog=False)
            self.assertEqual(differing(grab(per_line, bg=-1.0),
                                       grab(block, bg=-1.0)), 0, label)

    def test_intro_fits_4_3_and_16_9(self):
        out, preset = 'monical_x.json', 'preset_2026-10-11_120000.json'
        fail = 'FAILED to load not_an_image_long_name.txt, using test pattern'
        for size in ((1024, 768), (1600, 900)):
            win = make_window(size, color=-1.0)
            for warning in (m.monitor_warning_text(12.56), ''):
                # PNG + preset + image line, and radial with the plugin
                # missing, are the longest screens; Gabor is a typical one.
                for sel, radial_ok in ((4, True), (0, False), (1, True)):
                    saved = m.HAS_RADIAL
                    m.HAS_RADIAL = radial_ok
                    try:
                        content = m.build_intro_text(
                            size, 59.94, sel, 'texture.png', out, preset,
                            fail)
                    finally:
                        m.HAS_RADIAL = saved
                    win._setCurrent()
                    text, warn = m.intro_stims(win, size, warning)
                    m.set_intro_text(win, text, warn, content)
                    ink = lit(grab(text, win=win), 0)
                    rows = np.nonzero(ink.any(1))[0]
                    cols = np.nonzero(ink.any(0))[0]
                    case = (size, bool(warning), sel)
                    self.assertGreater(rows.min(), 0, case)
                    self.assertLess(rows.max(), size[1] - 1, case)
                    self.assertGreater(cols.min(), 0, case)
                    self.assertLess(cols.max(), size[0] - 1, case)
                    if warn is not None:
                        wrows = np.nonzero(lit(grab(warn, win=win),
                                               0).any(1))[0]
                        self.assertLess(rows.max(), wrows.min() - 1, case)


# =============================================================================
# One frame of every stimulus type, at defaults and range extremes
# =============================================================================

def extremes(stim, low):
    """A state with every knob of `stim` at its low or high limit."""
    s = state(stim, multi=not low, multi_count=m.MULTI_MAX if not low else 2)
    for key, (field, delta, lo, hi, kind) in m.knob_table(stim, 60.0).items():
        if kind == 'choice':
            options = m.CHOICES[field]
            s[field] = options[0] if low else options[-1]
        elif field == 'flicker_frames':
            s['stim_frames'] = [lo if low else hi] * m.MULTI_MAX
        elif kind == 'wrap':
            s[field] = lo if low else hi - abs(delta)
        else:
            s[field] = lo if low else hi
    m.sync_stim_frames(s)
    return s


class FrameSmokeTests(RenderCase):

    def test_every_type_draws_at_defaults_and_extremes(self):
        image = m.make_test_pattern()
        timer = m.FrameTimer(60.0)
        frames = 0
        for stim in m.STIMULUS_TYPES:
            if stim == m.STIM_RADIAL and not m.HAS_RADIAL:
                continue
            configs = [state(stim, mode=mode) for mode in m.MODE_KEYS.values()]
            configs += [extremes(stim, True), extremes(stim, False)]
            for s in configs:
                scene = m.build_scene(WIN, s, image, verbose=False)
                for frame in range(2):
                    s['frame_idx'] = frame
                    m.render_frame(WIN, scene, s, 60.0, (W, H), 33.0, timer,
                                   out_name='monical_x.json',
                                   flash_text='Snapshot #1 saved')
                    frames += 1
                s['menu_visible'] = True
                m.render_frame(WIN, scene, s, 60.0, (W, H), 33.0, timer)
                frames += 1
        WIN.clearBuffer()
        self.assertGreater(frames, 100)


if __name__ == '__main__':
    unittest.main()
