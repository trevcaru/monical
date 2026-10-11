"""Headless tests of monical's pure logic: no window, runs anywhere PsychoPy
imports.

    python -m unittest tests.test_logic
"""
import contextlib
import io
import json
import math
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import monical as m  # noqa: E402

REFRESH_RATES = (60.0, 144.0, 240.0)


def quiet(func, *args, **kwargs):
    """Call func with stdout captured. Returns (result, console text)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = func(*args, **kwargs)
    return result, out.getvalue()


def multi_state(n, x=0.66, y=0.0, offset=0.0, stim=m.STIM_UNIFORM,
                refresh=60.0, **kwargs):
    state = m.default_state(stim, refresh)
    state.update(multi=True, multi_count=n, x_pos=x, y_pos=y,
                 ring_offset_deg=offset, **kwargs)
    m.sync_stim_frames(state)
    return state


# =============================================================================
# Flicker (PRD 6.1)
# =============================================================================

class FlickerTests(unittest.TestCase):

    def test_stim_is_on_known_sequences(self):
        self.assertEqual([m.stim_is_on(i, 2) for i in range(4)],
                         [True, False, True, False])
        self.assertEqual([m.stim_is_on(i, 4) for i in range(4)],
                         [True, True, False, False])
        self.assertEqual([m.stim_is_on(i, 5) for i in range(5)],
                         [True, True, False, False, False])

    def test_stim_is_on_formula_all_counts(self):
        for frames in range(2, 241):
            cycle = [m.stim_is_on(i, frames) for i in range(frames)]
            self.assertEqual(cycle, [i < frames // 2 for i in range(frames)])
            # Stateless: the next cycle repeats exactly.
            self.assertEqual(cycle, [m.stim_is_on(frames + i, frames)
                                     for i in range(frames)])

    def test_on_off_split(self):
        for frames in range(2, 241):
            on, off = m.flicker_split(frames)
            self.assertEqual(on + off, frames)
            self.assertEqual(on, sum(m.stim_is_on(i, frames)
                                     for i in range(frames)))
            self.assertLessEqual(on, off)       # odd counts: ON is shorter

    def test_custom_frames_step_without_dead_presses(self):
        for refresh in REFRESH_RATES:
            table = m.knob_table(m.STIM_GABOR, refresh)
            state = m.default_state(m.STIM_GABOR, refresh)
            state['stim_frames'][0] = 2
            seen, rates = [2], [m.frames_to_hz(2, refresh)]
            while True:                         # [J]: one frame slower
                m.apply_knob(state, 'j', table)
                frames = state['stim_frames'][0]
                if frames == seen[-1]:
                    break                       # clamped at the top
                seen.append(frames)
                rates.append(m.frames_to_hz(frames, refresh))
            top = m.max_flicker_frames(refresh)
            self.assertEqual(seen, list(range(2, top + 1)), refresh)
            # Every press moved the realised rate (no dead presses).
            self.assertTrue(all(a > b for a, b in zip(rates, rates[1:])))
            for expected in range(top - 1, 1, -1):  # [F]: one frame faster
                m.apply_knob(state, 'f', table)
                self.assertEqual(state['stim_frames'][0], expected)
            m.apply_knob(state, 'f', table)
            self.assertEqual(state['stim_frames'][0], 2)    # clamped

    def test_default_custom_frames_nearest_15hz(self):
        for refresh, frames in ((60.0, 4), (144.0, 10), (240.0, 16)):
            state = m.default_state(m.STIM_RADIAL, refresh)
            self.assertEqual(state['stim_frames'], [frames, frames])

    def test_modes_3_and_4_frame_counts(self):
        for refresh, f15, f20 in ((60.0, 4, 3), (144.0, 10, 7),
                                  (240.0, 16, 12)):
            self.assertEqual(m.hz_to_frames(15, refresh), f15)
            self.assertEqual(m.hz_to_frames(20, refresh), f20)

    def test_asym_marking(self):
        for frames in range(2, 41):
            text = m.flicker_text(frames, 240.0)
            self.assertEqual('ASYM' in text, frames % 2 == 1, text)
        self.assertEqual(m.flicker_text(5, 240.0),
                         '48.00 Hz (5 fr, 2 on/3 off) ASYM')
        labels = {}
        for refresh in (60.0, 144.0, 240.0):
            for mode in (m.MODE_FLICKER_15, m.MODE_FLICKER_20):
                labels[refresh, mode] = m.mode_label({'mode': mode}, refresh)
        self.assertEqual(labels[60.0, m.MODE_FLICKER_20],
                         'Flicker 20 (20.00 Hz ASYM)')
        self.assertEqual(labels[144.0, m.MODE_FLICKER_15],
                         'Flicker 15 (14.40 Hz)')
        self.assertEqual(labels[144.0, m.MODE_FLICKER_20],
                         'Flicker 20 (20.57 Hz ASYM)')
        self.assertEqual(labels[240.0, m.MODE_FLICKER_20],
                         'Flicker 20 (20.00 Hz)')


# =============================================================================
# Multi-stimulus ring (PRD 6.3)
# =============================================================================

class MultiTests(unittest.TestCase):

    def test_ring_geometry(self):
        for n in range(2, 17):
            for x, y, offset in ((0.66, 0.0, 0.0), (-0.4, 0.1, 35.0),
                                 (0.25, -0.2, 355.0)):
                state = multi_state(n, x, y, offset)
                base = 0.0 if x >= 0 else 180.0
                for i, (px, py) in enumerate(m.ring_positions(state)):
                    self.assertAlmostEqual(math.hypot(px, py - y), abs(x),
                                           places=9)
                    angle = math.degrees(math.atan2(py - y, px)) % 360.0
                    want = (base + offset + i * 360.0 / n) % 360.0
                    diff = (angle - want + 180.0) % 360.0 - 180.0
                    self.assertAlmostEqual(diff, 0.0, places=6)

    def test_n2_offset0_is_legacy_dual_exactly(self):
        # Every X the knob can reach, as the knob stores it.
        xs = [round(-1.0 + k * m.STEP_POS, m.STORE_DP) for k in range(401)]
        for x in xs:
            for y in (-0.5, -0.2, 0.0, 0.1, 0.3, 0.5):
                state = multi_state(2, x, y)
                self.assertEqual(m.ring_positions(state), [(x, y), (-x, y)])

    def test_multi_off_draws_once_at_xy(self):
        state = m.default_state(m.STIM_GABOR)
        self.assertEqual(m.ring_positions(state), [(0.66, 0.0)])

    def test_n16_spacing(self):
        state = multi_state(16, 0.4, 0.05)
        pos = m.ring_positions(state)
        chords = [math.hypot(a[0] - b[0], a[1] - b[1])
                  for a, b in zip(pos, pos[1:] + pos[:1])]
        want = 2 * 0.4 * math.sin(math.pi / 16)
        for chord in chords:
            self.assertAlmostEqual(chord, want, places=9)

    def test_offset_wraps(self):
        table = m.knob_table(m.STIM_UNIFORM)
        state = multi_state(4, offset=355.0)
        m.apply_knob(state, 'comma', table)
        self.assertEqual(state['ring_offset_deg'], 0.0)
        m.apply_knob(state, 'period', table)
        self.assertEqual(state['ring_offset_deg'], 355.0)
        state['ring_offset_deg'] = 0.0
        for _ in range(72):
            m.apply_knob(state, 'comma', table)
        self.assertEqual(state['ring_offset_deg'], 0.0)

    def test_count_clamped_2_to_16(self):
        table = m.knob_table(m.STIM_UNIFORM)
        state = multi_state(2)
        m.apply_knob(state, 'bracketleft', table)
        self.assertEqual(state['multi_count'], 2)
        for _ in range(20):
            m.apply_knob(state, 'bracketright', table)
        self.assertEqual(state['multi_count'], 16)
        self.assertEqual(len(state['stim_frames']), 16)

    def test_overlap_threshold(self):
        chord = 2 * 0.3 * math.sin(math.pi / 4)
        self.assertTrue(m.ring_overlap(multi_state(4, 0.3, size=chord + 1e-4)))
        self.assertFalse(m.ring_overlap(multi_state(4, 0.3,
                                                    size=chord - 1e-4)))
        off = multi_state(4, 0.3, size=1.0)
        off['multi'] = False
        self.assertFalse(m.ring_overlap(off))

    def test_offscreen_detection(self):
        self.assertEqual(m.offscreen_copies(multi_state(3, 0.66)),
                         [False, True, True])
        self.assertEqual(m.offscreen_copies(multi_state(8, 0.2, size=0.05)),
                         [False] * 8)
        self.assertEqual(m.offscreen_copies(m.default_state(m.STIM_GABOR)),
                         [False])
        # Text uses its string extent, not the size square.
        text = multi_state(2, 0.66, stim=m.STIM_TEXT, text_extent=(0.8, 0.225))
        self.assertEqual(m.offscreen_copies(text), [True, True])
        # Orientation turns the box: a 45 deg square reaches further out.
        edge = 16 / 9.0 / 2 - 0.1125 - 0.01
        grating = m.default_state(m.STIM_GRATING)
        grating['x_pos'] = edge
        self.assertEqual(m.offscreen_copies(grating), [False])
        grating['ori'] = 45.0
        self.assertEqual(m.offscreen_copies(grating), [True])

    def test_per_copy_eccentricity(self):
        state = multi_state(4, 0.5, 0.1, selected_index=1)
        stimuli = m.stimuli_record(state, 33.0, 60.0)
        for entry, (x, y) in zip(stimuli, m.ring_positions(state)):
            want = math.degrees(math.atan(math.hypot(x, y) * 33.0 / 40.0))
            self.assertEqual(entry['ecc_deg'], round(want, 2))
        hud = m.build_hud(state, (1920, 1080), 60.0, 60.0, 33.0)
        self.assertIn('Ecc(#2): {:.2f} deg'.format(stimuli[1]['ecc_deg']),
                      hud)

    def test_eccentricity_vs_extent_formulas(self):
        # PRD 7's worked numbers: a displacement has no factor of 2.
        self.assertEqual(round(m.eccentricity_deg(0.66, 33.0, 40.0), 2),
                         28.57)
        self.assertEqual(round(m.visual_angle_deg(0.66, 33.0, 40.0), 2),
                         30.46)
        self.assertEqual(round(m.eccentricity_deg(1.0, 33.0, 40.0), 2),
                         39.52)
        self.assertEqual(round(m.visual_angle_deg(1.0, 33.0, 40.0), 2),
                         44.83)
        self.assertIsNone(m.eccentricity_deg(0.66, None, 40.0))


# =============================================================================
# Per-copy flicker / steady / off (PRD 6.3)
# =============================================================================

class CopyStateTests(unittest.TestCase):

    STATES = ['flicker', 'steady', 'off', 'flicker']

    def drawn_over(self, state, frames):
        positions = m.ring_positions(state)
        seq = []
        for frame in range(frames):
            state['frame_idx'] = frame
            drawn = m.drawn_positions(state, 60.0)
            seq.append([positions.index(p) for p in drawn])
        return seq

    def test_mode5_two_lcm_cycles(self):
        state = multi_state(4, 0.5, mode=m.MODE_FLICKER_CUSTOM,
                            stim_frames=[3, 4, 5, 6],
                            stim_states=list(self.STATES))
        seq = self.drawn_over(state, 120)       # LCM(3, 4, 5, 6) = 60
        for frame, drawn in enumerate(seq):
            want = [i for i, n in ((0, 3), (3, 6))
                    if m.stim_is_on(frame, n)] + [1]
            self.assertEqual(sorted(drawn), sorted(want), frame)
        self.assertEqual(sum(1 in d for d in seq), 120)     # steady
        self.assertEqual(sum(2 in d for d in seq), 0)       # off

    def test_modes_3_and_4_shared_rate(self):
        for mode, hz in ((m.MODE_FLICKER_15, 15), (m.MODE_FLICKER_20, 20)):
            n = m.hz_to_frames(hz, 60.0)
            state = multi_state(4, 0.5, mode=mode, stim_frames=[3, 4, 5, 6],
                                stim_states=list(self.STATES))
            for frame, drawn in enumerate(self.drawn_over(state, 2 * n * 6)):
                on = m.stim_is_on(frame, n)
                self.assertEqual(sorted(drawn),
                                 sorted([0, 3] * on + [1]), (mode, frame))

    def test_static_modes(self):
        state = multi_state(4, 0.5, stim_states=list(self.STATES))
        self.assertEqual(self.drawn_over(state, 3), [[0, 1, 3]] * 3)
        state['mode'] = m.MODE_STATIC_OFF
        self.assertEqual(self.drawn_over(state, 3), [[]] * 3)

    def test_multi_off_ignores_copy_state(self):
        state = m.default_state(m.STIM_UNIFORM, 60.0)
        state.update(mode=m.MODE_FLICKER_CUSTOM, stim_states=['off', 'off'])
        n = state['stim_frames'][0]
        seq = self.drawn_over(state, 2 * n)
        self.assertEqual([bool(d) for d in seq],
                         [m.stim_is_on(f, n) for f in range(2 * n)])


# =============================================================================
# Input: dispatch precedence, hold-to-repeat, press dropping (PRD 5.1)
# =============================================================================

class InputTests(unittest.TestCase):

    def hold(self, state, key, seconds, rate=60.0, sweeping=False,
             times=None):
        """Hold `key` from t=0 to t=seconds through repeat_tick."""
        table = m.knob_table(state['stimulus_type'])
        names = m.repeat_key_names(state['stimulus_type'])
        held, counts = {}, {}
        if times is None:
            times = [i / rate for i in range(int(round(seconds * rate)) + 1)]
        for t in times:
            m.repeat_tick(state, table, names, {key}, held, counts, t,
                          sweeping=sweeping)
        return counts.get(key, 0)

    def test_key_claim_precedence(self):
        s = m.default_state(m.STIM_UNIFORM)
        claim = m.key_claim
        for key in ('1', '2', '3', '4', '5', 'g', '8'):
            self.assertEqual(claim(s, key), 'mode')
        self.assertEqual(claim(s, '7'), 'dual')
        self.assertEqual(claim(s, '9'), 'select')
        self.assertEqual(claim(s, '0'), 'select')
        self.assertEqual(claim(s, 'slash'), 'copy_state')
        self.assertEqual(claim(s, 'm'), 'menu')
        self.assertEqual(claim(s, 'h'), 'hud')
        self.assertEqual(claim(s, 'p'), 'preset')
        self.assertEqual(claim(s, 'f12'), 'screenshot')
        self.assertIsNone(claim(s, 'a'))            # blue knob here
        self.assertIsNone(claim(s, 'b'))            # shape knob, not text
        self.assertIsNone(claim(s, 'escape'))       # falls through: quit
        s['menu_visible'] = True
        self.assertEqual(claim(s, 'escape'), 'menu_close')
        self.assertEqual(claim(s, 'escape', sweeping=True), 'sweep_cancel')
        s['mode'] = m.MODE_GAMMA
        self.assertEqual(claim(s, 'a'), 'sweep_toggle')
        self.assertEqual(claim(s, 'left'), 'mode_arrow')
        self.assertIsNone(claim(s, 'up'))
        self.assertIsNone(claim(s, 'pageup'))       # never claimed
        s['mode'] = m.MODE_UNIFORMITY
        for key in ('left', 'right', 'up', 'down'):
            self.assertEqual(claim(s, key), 'mode_arrow')
        text = m.default_state(m.STIM_TEXT)
        self.assertEqual(claim(text, 'b'), 'text_cycle')
        self.assertEqual(claim(text, 'n'), 'text_cycle')

    def test_repeat_60_per_second_after_1s_delay(self):
        for rate in REFRESH_RATES:
            state = m.default_state(m.STIM_GABOR)
            state['x_pos'] = 0.0
            self.assertEqual(self.hold(state, 'right', 0.99, rate), 0)
            state['x_pos'] = 0.0
            steps = self.hold(state, 'right', 3.0, rate)
            self.assertEqual(steps, 120, rate)      # 2 s x 60/s
            self.assertEqual(state['x_pos'], round(120 * m.STEP_POS, 4))

    def test_repeat_rate_survives_uneven_frames(self):
        # Alternating 10 ms and 24 ms frames: the count keys off the hold
        # start, so slow frames are made up rather than lost.
        times, t = [], 0.0
        while t < 3.0:
            times.append(t)
            t += 0.010 if len(times) % 2 else 0.024
        times.append(3.0)
        state = m.default_state(m.STIM_GABOR)
        state['x_pos'] = -0.6
        self.assertEqual(self.hold(state, 'right', 3.0, times=times), 120)

    def test_single_press_knobs_never_repeat(self):
        state = m.default_state(m.STIM_GABOR)
        self.assertEqual(self.hold(state, 'equal', 3.0), 0)
        self.assertEqual(state['size'], 0.225)

    def test_held_press_dropped(self):
        held, counts = {}, {}
        state = m.default_state(m.STIM_GABOR)
        table = m.knob_table(m.STIM_GABOR)
        names = m.repeat_key_names(m.STIM_GABOR)
        presses = []
        for frame in range(30):
            # The OS delivers a press event every frame while 's' is down.
            presses += m.new_presses(['s'], held)
            m.repeat_tick(state, table, names, {'s'}, held, counts,
                          frame / 60.0)
        self.assertEqual(presses, ['s'])
        m.repeat_tick(state, table, names, set(), held, counts, 0.6)
        self.assertEqual(m.new_presses(['s'], held), ['s'])  # released

    def test_gamma_mode_a_never_touches_blue(self):
        state = m.default_state(m.STIM_UNIFORM)
        state['mode'] = m.MODE_GAMMA
        self.assertEqual(self.hold(state, 'a', 3.0), 0)
        self.assertEqual(state['b'], 0.0)
        state['mode'] = m.MODE_STATIC_ON          # outside gamma it is blue
        self.assertEqual(self.hold(state, 'a', 3.0), 120)
        self.assertEqual(state['b'], -0.12)

    def test_uniformity_arrows_walk_grid_not_stimulus(self):
        state = m.default_state(m.STIM_UNIFORM)
        state['mode'] = m.MODE_UNIFORMITY
        self.assertEqual(self.hold(state, 'right', 3.0), 0)
        self.assertEqual(state['x_pos'], 0.66)
        for key in ('up', 'left', 'left'):
            m.move_uniformity(state, key)
        name = m.UNIFORMITY_GRID[state['uniformity_grid_index']]
        self.assertEqual(name, 'top_left')
        self.assertIn('Cell: top_left (-0.78, 0.39)', m.mode_line(state))

    def test_gamma_level_readout(self):
        state = m.default_state(m.STIM_UNIFORM)
        state.update(mode=m.MODE_GAMMA, gamma_step_index=8)
        self.assertIn('Level 9/11: +0.6 rgb (204 8-bit)', m.mode_line(state))
        eight_bit = [int(round(255 * (lv + 1.0) / 2.0))
                     for lv in m.GAMMA_LEVELS]
        self.assertEqual(eight_bit,
                         [0, 25, 51, 76, 102, 128, 153, 178, 204, 230, 255])


class FrameTimerTests(unittest.TestCase):

    class Clock(object):
        def __init__(self):
            self.t = 0.0

        def getTime(self):
            return self.t

        def reset(self):
            self.t = 0.0

    def run_timer(self, intervals, refresh=60.0):
        timer = m.FrameTimer(refresh)
        timer.clock = self.Clock()
        timer.tick()                    # first flip: discarded
        for interval in intervals:
            timer.clock.t = interval
            quiet(timer.tick)
        return timer

    def test_drops_counted_against_rolling_median(self):
        frame = 1 / 60.0
        timer = self.run_timer([frame] * 60 + [0.1] + [frame] * 30 + [0.1])
        self.assertEqual(timer.dropped, 2)
        timer = self.run_timer([frame] * 60 + [1.4 * frame, 1.6 * frame])
        self.assertEqual(timer.dropped, 1)          # 1.5x median threshold
        timer = self.run_timer([frame] * 150)
        self.assertEqual(timer.dropped, 0)
        self.assertAlmostEqual(timer.rolling_hz, 60.0, places=6)


# =============================================================================
# Presets (PRD 10)
# =============================================================================

class PresetTests(unittest.TestCase):

    def load(self, loaded, stim=m.STIM_RADIAL, refresh=60.0,
             text_presets=None):
        state = m.default_state(stim, refresh)
        _, console = quiet(m.apply_preset, state, dict(loaded), text_presets)
        return state, console

    def test_round_trip(self):
        state = m.default_state(m.STIM_GRATING, 60.0)
        state.update(sf=7.5, ori=35.0, waveform='sqr', mask='circle',
                     multi=True, multi_count=3, size=0.3)
        m.sync_stim_frames(state)
        saved = json.loads(json.dumps(m.preset_from_state(state)))
        for key in m.PRESET_EXCLUDE:
            self.assertNotIn(key, saved)
        restored, _ = self.load(saved, m.STIM_GRATING)
        for key in ('sf', 'ori', 'waveform', 'mask', 'multi', 'multi_count',
                    'size', 'stim_frames'):
            self.assertEqual(restored[key], state[key], key)

    def test_clamps(self):
        state, console = self.load({'size': 5, 'contrast': -1, 'x_pos': 3,
                                    'viewing_distance_cm': 0.4, 'rings': 50})
        self.assertEqual((state['size'], state['contrast'], state['x_pos'],
                          state['viewing_distance_cm'], state['rings']),
                         (2.0, 0.0, 1.0, 1, 20))
        self.assertEqual(console.count('Preset: '), 5)

    def test_wedges_round_to_even_ties_up(self):
        for value, want in ((7, 8), (9, 10), (1, 2), (3, 4), (31, 32),
                            (33, 32), (16, 16)):
            state, _ = self.load({'wedges': value})
            self.assertEqual(state['wedges'], want, value)

    def test_junk_and_nan_fall_back_to_default(self):
        cases = {'size': 'x', 'contrast': True, 'bg_gray': float('nan'),
                 'sf': None, 'phase': [0.5], 'waveform': 'triangle'}
        state, console = self.load(cases, m.STIM_GRATING)
        default = m.default_state(m.STIM_GRATING)
        for key in cases:
            self.assertEqual(state[key], default[key], key)
        nan = json.loads('{"size": NaN}')           # json accepts NaN
        self.assertEqual(self.load(nan)[0]['size'], 0.225)

    def test_orientation_wraps(self):
        self.assertEqual(self.load({'ori': 370}, m.STIM_GABOR)[0]['ori'],
                         10.0)
        self.assertEqual(self.load({'ori': -5}, m.STIM_GABOR)[0]['ori'],
                         355.0)

    def test_old_custom_freq_hz(self):
        for refresh, frames in ((60.0, 4), (144.0, 10), (240.0, 16)):
            state, console = self.load({'custom_freq_hz': 15},
                                       refresh=refresh)
            self.assertEqual(state['stim_frames'], [frames, frames])
            self.assertIn('old format', console)

    def test_dual_migration(self):
        state, console = self.load({'dual': True})
        self.assertEqual((state['multi'], state['multi_count'],
                          state['ring_offset_deg']), (True, 2, 0.0))
        self.assertIn('dual -> multi-stimulus ring', console)
        self.assertFalse(self.load({'dual': False})[0]['multi'])
        self.assertFalse(self.load({'dual': True, 'multi': False})[0]['multi'])

    def test_missing_fields_keep_defaults(self):
        state, _ = self.load({})
        default = m.default_state(m.STIM_RADIAL)
        self.assertEqual(state, default)
        state, _ = self.load({'size': 0.3})
        self.assertEqual(state['size'], 0.3)
        self.assertEqual(state['rings'], default['rings'])

    def test_refresh_mismatch_conversion(self):
        saved = {'flicker_frames': 16, 'refresh_hz': 240.0}
        self.assertEqual(self.load(saved, refresh=60.0)[0]['stim_frames'],
                         [4, 4])
        self.assertEqual(self.load(saved, refresh=239.97)[0]['stim_frames'],
                         [16, 16])                  # within 1%
        self.assertEqual(self.load(saved, refresh=144.0)[0]['stim_frames'],
                         [10, 10])
        lists = {'stim_frames': [16, 8], 'refresh_hz': 240.0}
        self.assertEqual(self.load(lists, refresh=60.0)[0]['stim_frames'],
                         [4, 2])

    def test_length_mismatches(self):
        state, console = self.load({'stim_frames': [3, 5], 'refresh_hz': 60.0,
                                    'multi': True, 'multi_count': 4})
        self.assertEqual(state['stim_frames'], [3, 5, 5, 5])
        self.assertIn('padded with the last', console)
        state, console = self.load({'stim_frames': [3, 4, 5, 6, 7],
                                    'refresh_hz': 60.0, 'multi_count': 2})
        self.assertEqual(state['stim_frames'], [3, 4])
        self.assertIn('extra dropped', console)
        state, console = self.load({'stim_states': ['steady', 'bogus'],
                                    'multi_count': 3})
        self.assertEqual(state['stim_states'],
                         ['steady', 'flicker', 'flicker'])
        state, _ = self.load({'stim_states': ['off'] * 5, 'multi_count': 2})
        self.assertEqual(state['stim_states'], ['off', 'off'])

    def test_selected_index_and_mode(self):
        state, _ = self.load({'selected_index': 7, 'multi_count': 4})
        self.assertEqual(state['selected_index'], 3)
        self.assertEqual(self.load({'selected_index': 'x'})[0]
                         ['selected_index'], 0)
        state, console = self.load({'mode': 'bogus'})
        self.assertEqual(state['mode'], m.MODE_STATIC_ON)
        self.assertIn('unknown mode', console)

    def test_text_restored_by_string(self):
        cycle = m.text_cycle('HELLO')[0]   # HELLO H E L L O A..Z
        state, _ = self.load({'text_string': 'E', 'text_index': 5},
                             m.STIM_TEXT, text_presets=cycle)
        self.assertEqual((state['text_index'], state['text_string']),
                         (2, 'E'))
        state, _ = self.load({'text_string': 'L', 'text_index': 4},
                             m.STIM_TEXT, text_presets=cycle)
        self.assertEqual(state['text_index'], 4)     # duplicate kept
        state, _ = self.load({'text_string': 'L', 'text_index': 0},
                             m.STIM_TEXT, text_presets=cycle)
        self.assertEqual(state['text_index'], 3)

    def test_text_index_wraps_when_string_missing(self):
        state, console = self.load({'text_string': 'ZZZ', 'text_index': 7},
                                   m.STIM_TEXT,
                                   text_presets=list(m.TEXT_PRESETS))
        self.assertEqual((state['text_index'], state['text_string']),
                         (2, '123456'))
        self.assertIn('wrapped', console)
        self.assertIn("'ZZZ' is not in this session's cycle", console)

    def test_unknown_and_excluded_keys_ignored(self):
        state, console = self.load({'bogus_key': 1, 'aspect': 1.0,
                                    'image_path': 'x.png'})
        self.assertEqual(state['aspect'], 16.0 / 9.0)
        self.assertEqual(state['image_path'], m.GENERATED_LABEL)
        self.assertIn('ignored 3 unknown key(s)', console)

    def test_load_preset_rejects_non_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = os.path.join(tmp, 'code.json')
            with open(code, 'w') as handle:
                handle.write('__import__("os").system("echo PWNED")')
            arr = os.path.join(tmp, 'arr.json')
            with open(arr, 'w') as handle:
                handle.write('[1, 2]')
            self.assertEqual(quiet(m.load_preset, code)[0], {})
            self.assertEqual(quiet(m.load_preset, arr)[0], {})
            self.assertEqual(quiet(m.load_preset,
                                   os.path.join(tmp, 'none.json'))[0], {})


# =============================================================================
# Text cycle (PRD 4.6)
# =============================================================================

class TextCycleTests(unittest.TestCase):

    def test_no_text_five_strings(self):
        self.assertEqual(m.text_cycle(None),
                         (['ABCDEF', 'abcdef', '123456', 'XXXXXX', 'oOoOoO'],
                          0))
        self.assertEqual(m.default_state(m.STIM_TEXT)['text_string'],
                         'ABCDEF')

    def test_single_character(self):
        self.assertEqual(m.text_cycle('c'),
                         (list('abcdefghijklmnopqrstuvwxyz'), 2))
        self.assertEqual(m.text_cycle('Q'), (list(m.ALPHABET), 16))
        self.assertEqual(m.text_cycle('5'), (['5'] + list(m.ALPHABET), 0))

    def test_multi_character(self):
        self.assertEqual(m.text_cycle('AHO'),
                         (['AHO', 'A', 'H', 'O', m.ALPHABET], 0))


# =============================================================================
# Output files, --image and screen text (PRD 3.2, 4.5, 8.3, 9)
# =============================================================================

class OutputTests(unittest.TestCase):

    def test_output_path_label(self):
        inside = os.path.join(m.OUT_DIR, 'presets', 'preset_x.json')
        self.assertEqual(m.output_path_label(inside), 'presets/preset_x.json')
        with tempfile.TemporaryDirectory() as tmp:
            outside = os.path.join(tmp, 'sub', 'mine.json')
            self.assertEqual(m.output_path_label(outside), 'mine.json')
        self.assertIsNone(m.output_path_label(None))

    def test_session_header_has_no_absolute_paths(self):
        win = types.SimpleNamespace(waitBlanking=True, winHandle=None,
                                    fullscr=True)
        mon = types.SimpleNamespace(getWidth=lambda: 59.8)
        with tempfile.TemporaryDirectory() as tmp:
            header = m.session_header(
                win, mon, (1920, 1080), 33.6, 239.97,
                os.path.join(tmp, 'deep', 'texture.png'),
                out_path=os.path.join(m.OUT_DIR, 'monical_x.json'),
                preset_arg=os.path.join(tmp, 'p.json'), text_arg='AHO',
                image_failed=True)
        self.assertEqual(header['image_path'], 'texture.png')
        self.assertEqual(header['preset_path'], 'p.json')
        self.assertEqual(header['output_file'], 'monical_x.json')
        self.assertTrue(header['image_load_failed'])
        text = json.dumps(header)
        for marker in (':\\\\', '/Users/', '/home/', tmp):
            self.assertNotIn(marker, text)

    def test_resolve_image(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, 'good.png')
            Image.new('RGB', (8, 8), (255, 0, 0)).save(png)
            fake = os.path.join(tmp, 'notes.png')
            with open(fake, 'w') as handle:
                handle.write('not an image\n')
            image, label, failure = m.resolve_image(png)
            self.assertEqual((image, label, failure), (png, 'good.png', ''))
            (image, label, failure), console = quiet(m.resolve_image, fake)
            self.assertEqual(label, m.GENERATED_LABEL)
            self.assertEqual(failure,
                             'FAILED to load notes.png, using test pattern')
            self.assertEqual(image.shape, (m.TEST_PATTERN_RES,) * 2)
            self.assertIn('WARNING', console)
            (image, label, failure), _ = quiet(
                m.resolve_image, os.path.join(tmp, 'missing.png'))
            self.assertTrue(failure.startswith('NOT FOUND missing.png'))
            long_name = os.path.join(tmp, 'x' * 60 + '.txt')
            (_, _, failure), _ = quiet(m.resolve_image, long_name)
            self.assertIn('...', failure)
        self.assertEqual(m.resolve_image(None)[1:], (m.GENERATED_LABEL, ''))

    def test_intro_text(self):
        plain = m.build_intro_text((1920, 1080), 60.0, 4, 'texture.png',
                                   'monical_x.json')
        self.assertNotIn('Image:', plain)
        failed = m.build_intro_text(
            (1920, 1080), 60.0, 0, m.GENERATED_LABEL, 'monical_x.json',
            image_failure='FAILED to load notes.png, using test pattern')
        self.assertIn('Image:      FAILED to load notes.png, using test '
                      'pattern', failed)
        for key in ('[H]', '[M]', "[;/']", '[ESC]', '[Q]'):
            self.assertIn(key, plain)
        self.assertLessEqual(max(len(line) for line in failed.split('\n')),
                             80)

    def test_menu_wording(self):
        menu = m.build_menu_text(m.default_state(m.STIM_GABOR))
        self.assertIn('F/J = Custom flicker faster/slower (one frame per '
                      'step)', menu)
        self.assertNotIn('+/-1 frame', menu)
        self.assertIn("DISTANCE:  ;/' = Viewing distance", menu)

    def test_snapshot_record_is_json_and_complete(self):
        state = m.default_state(m.STIM_RADIAL, 239.97)
        record = m.state_record(state, 33.0, 239.97, rolling_hz=239.94,
                                drops=0, snapshot_number=1)
        json.dumps(record)
        self.assertEqual((record['eccentricity_deg'],
                          record['visual_angle_deg']), (28.57, 10.61))
        self.assertEqual(record['flicker_frames'], 16)
        self.assertEqual(record['stimulus_specific'],
                         {'rings': 4, 'wedges': 16, 'radialCycles': 2.0,
                          'angularCycles': 8.0, 'radialPhase': 0.25})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'out.json')
            m.write_json(state, {'x': 1}, path)
            self.assertEqual(os.listdir(tmp), ['out.json'])
            with open(path) as handle:
                self.assertTrue(json.load(handle)['note'].startswith(
                    'REFERENCE ONLY'))

    def test_cli_flags(self):
        args = m.parse_args(['--image', 'x.png', '--text', 'AB',
                             '--preset', 'p.json', '--bench'])
        self.assertEqual((args.image, args.text, args.preset, args.bench),
                         ('x.png', 'AB', 'p.json', True))
        args = m.parse_args([])
        self.assertEqual((args.image, args.text, args.preset, args.bench),
                         (None, None, None, False))


if __name__ == '__main__':
    unittest.main()
