"""
codecinema.audio.soundfont -- a pure-numpy SoundFont 2 (SF2) reader and sampler.

    bank = load(path)                              # parse once (cached per path)
    bank.presets()                                 # [(bank, program, name), ...]
    bank.render_note(bank_no, program, key, velocity, duration_s, release_s=None) -> (2, n) float64 at dsp.SR
    default()                                      # the configured bank (setting audio.soundbank) or None
    render_note(bank_no, program, key, velocity, duration_s, release_s=None)    # with default()

The reader parses RIFF/INFO, sdta (smpl + optional sm24) and every pdta list (phdr pbag pmod pgen inst ibag
imod igen shdr), including global preset and instrument zones; preset generators add to instrument generators.
The voice model covers key/velocity ranges, root-key override, coarse/fine/scale tuning, sample modes (loops,
loop-until-release), address offsets, pan, initial attenuation (0.4 cB per unit, the convention FluidSynth and the
original players use), the DAHDSR volume envelope with keynum-to-hold/decay, the modulation envelope and LFO
(pitch and filter), the vibrato LFO, a resonant low-pass at initialFilterFc/Q, and modulators with note-on sources
(velocity, key number, default controller values) on top of the default ones: velocity-to-attenuation (concave,
96 dB: amplitude (v/127)^2) and velocity-to-cutoff.  Stereo-linked samples share one playback-rate curve so the
image never drifts.  Samples are read with loop-aware cubic interpolation.  Rendered notes are cached (LRU).

The default bank is GeneralUser GS v2.0.3 by S. Christian Collins, downloaded once into the per-user cache.
"""
import hashlib
import struct
import sys
from collections import OrderedDict
from pathlib import Path

import numpy as np

from codecinema.audio import dsp
from codecinema.audio.dsp import SR

BANK_NAME = "soundbanks/GeneralUser-GS.sf2"
BANK_URL = "https://github.com/ZJUCQR/CodeCinema/releases/download/soundbank/GeneralUser-GS.sf2"
BANK_SHA256 = "9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe"
BANK_SIZE = 32319396
BANK_CREDIT = "GeneralUser GS v2.0.3 by S. Christian Collins"

# ------------------------------------------------------------------------------------------------ generators
START_OFS, END_OFS, LOOP_START_OFS, LOOP_END_OFS, START_COARSE = 0, 1, 2, 3, 4
MOD_LFO_TO_PITCH, VIB_LFO_TO_PITCH, MOD_ENV_TO_PITCH = 5, 6, 7
FILTER_FC, FILTER_Q, MOD_LFO_TO_FC, MOD_ENV_TO_FC, END_COARSE, MOD_LFO_TO_VOL = 8, 9, 10, 11, 12, 13
PAN = 17
DELAY_MOD_LFO, FREQ_MOD_LFO, DELAY_VIB_LFO, FREQ_VIB_LFO = 21, 22, 23, 24
DELAY_MOD_ENV, ATTACK_MOD_ENV, HOLD_MOD_ENV, DECAY_MOD_ENV, SUSTAIN_MOD_ENV, RELEASE_MOD_ENV = 25, 26, 27, 28, 29, 30
KEY_TO_MOD_HOLD, KEY_TO_MOD_DECAY = 31, 32
DELAY_VOL, ATTACK_VOL, HOLD_VOL, DECAY_VOL, SUSTAIN_VOL, RELEASE_VOL = 33, 34, 35, 36, 37, 38
KEY_TO_VOL_HOLD, KEY_TO_VOL_DECAY = 39, 40
INSTRUMENT, KEY_RANGE, VEL_RANGE, LOOP_START_COARSE, KEYNUM, VELOCITY, ATTENUATION = 41, 43, 44, 45, 46, 47, 48
LOOP_END_COARSE, COARSE_TUNE, FINE_TUNE, SAMPLE_ID, SAMPLE_MODES, SCALE_TUNING = 50, 51, 52, 53, 54, 56
EXCLUSIVE_CLASS, ROOT_KEY = 57, 58

DEFAULT_GENS = {FILTER_FC: 13500, DELAY_MOD_LFO: -12000, DELAY_VIB_LFO: -12000, DELAY_MOD_ENV: -12000,
                ATTACK_MOD_ENV: -12000, HOLD_MOD_ENV: -12000, DECAY_MOD_ENV: -12000, RELEASE_MOD_ENV: -12000,
                DELAY_VOL: -12000, ATTACK_VOL: -12000, HOLD_VOL: -12000, DECAY_VOL: -12000, RELEASE_VOL: -12000,
                KEYNUM: -1, VELOCITY: -1, SCALE_TUNING: 100, ROOT_KEY: -1}
# generators that are not allowed at preset level (sample addressing, modes, overrides)
_NOT_PRESET = {START_OFS, END_OFS, LOOP_START_OFS, LOOP_END_OFS, START_COARSE, END_COARSE, LOOP_START_COARSE,
               LOOP_END_COARSE, KEYNUM, VELOCITY, SAMPLE_MODES, EXCLUSIVE_CLASS, ROOT_KEY, SAMPLE_ID, INSTRUMENT,
               KEY_RANGE, VEL_RANGE}
_RANGES = (KEY_RANGE, VEL_RANGE)

_PHDR = np.dtype([("name", "S20"), ("program", "<u2"), ("bank", "<u2"), ("bag", "<u2"), ("library", "<u4"),
                  ("genre", "<u4"), ("morphology", "<u4")])
_BAG = np.dtype([("gen", "<u2"), ("mod", "<u2")])
_MOD = np.dtype([("src", "<u2"), ("dest", "<u2"), ("amount", "<i2"), ("amount_src", "<u2"), ("transform", "<u2")])
_GEN = np.dtype([("oper", "<u2"), ("amount", "<i2")])
_INST = np.dtype([("name", "S20"), ("bag", "<u2")])
_SHDR = np.dtype([("name", "S20"), ("start", "<u4"), ("end", "<u4"), ("loop_start", "<u4"), ("loop_end", "<u4"),
                  ("rate", "<u4"), ("pitch", "u1"), ("correction", "i1"), ("link", "<u2"), ("type", "<u2")])

ATTENUATION_SCALE = 0.4        # initialAttenuation counts 0.04 dB per unit, as FluidSynth and the original players apply it
MAX_TAIL_S = 8.0               # longest release tail rendered after the gate
CACHE_SAMPLES = 48_000_000     # note cache budget (float32 samples, ~190 MB)


class SoundFontError(ValueError):
    """The file is not a readable SoundFont 2 bank."""


def tc2s(tc):
    """absolute timecents -> seconds"""
    return float(2.0 ** (float(tc) / 1200.0))


def abs_cents_hz(c):
    """absolute cents -> Hz (8.176 Hz = 0 cents)"""
    return float(8.176 * 2.0 ** (float(c) / 1200.0))


# ------------------------------------------------------------------------------------------------ modulators
# identity (src, dest, amount_src, transform) -> amount.  Velocity -> attenuation: concave, negative, 960 cB, i.e.
# amplitude (v/127)^2.  Velocity -> cutoff: the SF2 2.01 default as FluidSynth implements it.
DEFAULT_MODS = {(0x0502, ATTENUATION, 0, 0): 960, (0x0102, FILTER_FC, 0x0D02, 0): -2400}
# controller values a fresh MIDI channel starts with (volume 100, pan centre, expression full, GS reverb send 40)
CC_DEFAULTS = {7: 100, 10: 64, 11: 127, 91: 40}


def _curve(kind, x):
    """SF2 source curves on x in [0, 1]: 0 linear, 1 concave, 2 convex, 3 switch"""
    if kind == 1:
        return 1.0 if x >= 1.0 else min(1.0, max(0.0, -(5.0 / 12.0) * np.log10(1.0 - x)))
    if kind == 2:
        return 0.0 if x <= 0.0 else min(1.0, max(0.0, 1.0 + (5.0 / 12.0) * np.log10(x)))
    if kind == 3:
        return 1.0 if x >= 0.5 else 0.0
    return x


def _source(src, key, vel):
    """value of a modulator source for a note-on with static controllers"""
    index, is_cc = src & 0x7F, src & 0x80
    if is_cc:
        raw = CC_DEFAULTS.get(index, 0) / 127.0
    elif index == 0:
        return 1.0                       # 'no controller' reads as 1
    elif index == 2:
        raw = vel / 127.0
    elif index == 3:
        raw = key / 127.0
    elif index == 14:
        raw = 0.5                        # pitch wheel centred
    elif index == 16:
        raw = 2.0 / 127.0                # pitch-wheel sensitivity: 2 semitones
    else:
        raw = 0.0                        # pressure, links
    x = 1.0 - raw if (src >> 8) & 1 else raw
    kind = (src >> 10) & 0x3F
    if (src >> 9) & 1:                   # bipolar
        s = 2.0 * x - 1.0
        return np.sign(s) * _curve(kind, abs(s)) if kind else s
    return _curve(kind, x)


def _modulate(mods, key, vel):
    """{dest: summed amount} of a merged modulator set"""
    out = {}
    for (src, dest, amt_src, transform), amount in mods.items():
        v = _source(src, key, vel) * (_source(amt_src, key, vel) if amt_src else 1.0) * amount
        if transform == 2:
            v = abs(v)
        out[dest] = out.get(dest, 0.0) + float(v)
    return out


def _riff(data, offset, end):
    while offset + 8 <= end:
        cid = data[offset:offset + 4]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        yield cid, offset + 8, size
        offset += 8 + size + (size & 1)


def _cstr(raw):
    return raw.split(b"\0", 1)[0].decode("latin-1", "replace").strip()


class Zone:
    __slots__ = ("gens", "keys", "mods", "vels")

    def __init__(self, gens, mods):
        self.gens = gens
        self.mods = mods
        lo_hi = gens.get(KEY_RANGE)
        self.keys = lo_hi if lo_hi is not None else (0, 127)
        lo_hi = gens.get(VEL_RANGE)
        self.vels = lo_hi if lo_hi is not None else (0, 127)

    def matches(self, key, vel):
        return self.keys[0] <= key <= self.keys[1] and self.vels[0] <= vel <= self.vels[1]


def _zones(bags, gens, mods, first, last, terminal):
    """[global Zone or None, [Zone, ...]] for bags first..last-1; a zone without `terminal` (sampleID / instrument)
    is the global zone only when it comes first, otherwise it is ignored (SF2 2.04 sections 7.3 / 7.7)."""
    glob, local = None, []
    for b in range(first, last):
        g0, g1 = int(bags[b]["gen"]), int(bags[b + 1]["gen"])
        m0, m1 = int(bags[b]["mod"]), int(bags[b + 1]["mod"])
        zm = {}
        for m in mods[m0:m1]:
            ident = (int(m["src"]), int(m["dest"]), int(m["amount_src"]), int(m["transform"]))
            if ident[0] or ident[2]:
                zm[ident] = int(m["amount"])
        d = {}
        for oper, amount in zip(gens["oper"][g0:g1].tolist(), gens["amount"][g0:g1].tolist()):
            if oper in _RANGES:
                u = amount & 0xFFFF
                d[oper] = (u & 0xFF, u >> 8)
            elif oper in (SAMPLE_ID, INSTRUMENT, SAMPLE_MODES):
                d[oper] = amount & 0xFFFF
            else:
                d[oper] = amount
        if terminal in d:
            local.append(Zone(d, zm))
        elif b == first and glob is None:
            glob = Zone(d, zm)
    return glob, local


class SoundFont:
    """A parsed SF2 bank. Sample data stays in one float32 array; presets are looked up by (bank, program)."""

    def __init__(self, path):
        self.path = Path(path)
        data = self.path.read_bytes()
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"sfbk":
            raise SoundFontError(f"{self.path} is not a SoundFont 2 file")
        lists = {}
        for cid, start, size in _riff(data, 12, len(data)):
            if cid == b"LIST":
                lists[data[start:start + 4]] = (start + 4, start + size)
        for need in (b"sdta", b"pdta"):
            if need not in lists:
                raise SoundFontError(f"{self.path}: missing the {need.decode()} list")
        self.info = {}
        if b"INFO" in lists:
            for cid, start, size in _riff(data, *lists[b"INFO"]):
                if cid == b"ifil" and size >= 4:
                    major, minor = struct.unpack_from("<HH", data, start)
                    self.info["ifil"] = f"{major}.{minor:02d}"
                else:
                    self.info[cid.decode("latin-1")] = _cstr(data[start:start + size])
        smpl = sm24 = None
        for cid, start, size in _riff(data, *lists[b"sdta"]):
            if cid == b"smpl":
                smpl = np.frombuffer(data, dtype="<i2", count=size // 2, offset=start)
            elif cid == b"sm24":
                sm24 = np.frombuffer(data, dtype=np.uint8, count=size, offset=start)
        if smpl is None:
            raise SoundFontError(f"{self.path}: no sample data")
        if sm24 is not None and len(sm24) >= len(smpl):
            pcm = (smpl.astype(np.int32) << 8) | sm24[:len(smpl)].astype(np.int32)
            self.samples = (pcm.astype(np.float32) / np.float32(8388608.0))
        else:
            self.samples = smpl.astype(np.float32) / np.float32(32768.0)
        self.bits = 24 if sm24 is not None else 16
        pd = {}
        for cid, start, size in _riff(data, *lists[b"pdta"]):
            pd[cid] = (start, size)
        dtypes = {b"phdr": _PHDR, b"pbag": _BAG, b"pmod": _MOD, b"pgen": _GEN, b"inst": _INST, b"ibag": _BAG,
                  b"imod": _MOD, b"igen": _GEN, b"shdr": _SHDR}
        tab = {}
        for cid, dt in dtypes.items():
            if cid not in pd:
                raise SoundFontError(f"{self.path}: missing the {cid.decode()} table")
            start, size = pd[cid]
            if size % dt.itemsize:
                raise SoundFontError(f"{self.path}: the {cid.decode()} table has a bad size")
            tab[cid] = np.frombuffer(data, dtype=dt, count=size // dt.itemsize, offset=start).copy()
        self.pmod, self.imod = tab[b"pmod"], tab[b"imod"]
        self.sample_headers = tab[b"shdr"][:-1]
        self.sample_names = [_cstr(s) for s in self.sample_headers["name"]]
        insts = tab[b"inst"]
        self.instruments = []
        for i in range(len(insts) - 1):
            g, z = _zones(tab[b"ibag"], tab[b"igen"], tab[b"imod"], int(insts[i]["bag"]), int(insts[i + 1]["bag"]),
                          SAMPLE_ID)
            self.instruments.append((_cstr(insts[i]["name"]), g, z))
        ph = tab[b"phdr"]
        self._presets = {}
        for p in range(len(ph) - 1):
            g, z = _zones(tab[b"pbag"], tab[b"pgen"], tab[b"pmod"], int(ph[p]["bag"]), int(ph[p + 1]["bag"]),
                          INSTRUMENT)
            key = (int(ph[p]["bank"]), int(ph[p]["program"]))
            self._presets.setdefault(key, (_cstr(ph[p]["name"]), g, z))
        self._cache = OrderedDict()
        self._cached = 0
        self._loudness = {}

    # -------------------------------------------------------------------------------------- lookup
    def presets(self):
        return sorted((b, p, v[0]) for (b, p), v in self._presets.items())

    def preset_name(self, bank, program):
        key = self._resolve(bank, program)
        return self._presets[key][0] if key else None

    def has_preset(self, bank, program):
        return (int(bank), int(program)) in self._presets

    def _resolve(self, bank, program):
        bank, program = int(bank), int(program)
        for key in ((bank, program), (128, 0) if bank == 128 else (0, program)):
            if key in self._presets:
                return key
        return None

    def voices(self, bank, program, key, vel):
        """[(sample_index, gens)] for every sounding (preset zone, instrument zone) pair of a note.
        gens holds the merged generator values plus the evaluated modulators (velocity, key, default controllers);
        gens['att_cB'] is the final attenuation in centibels."""
        found = self._resolve(bank, program)
        if found is None:
            raise KeyError(f"no preset {bank}:{program} in {self.path.name}")
        _, pglob, pzones = self._presets[found]
        out = []
        for pz in pzones:
            pg = dict(pglob.gens) if pglob else {}
            pg.update(pz.gens)
            keys = pz.gens.get(KEY_RANGE, pg.get(KEY_RANGE, (0, 127)))
            vels = pz.gens.get(VEL_RANGE, pg.get(VEL_RANGE, (0, 127)))
            if not (keys[0] <= key <= keys[1] and vels[0] <= vel <= vels[1]):
                continue
            inst = pz.gens[INSTRUMENT]
            if inst >= len(self.instruments):
                continue
            pmods = dict(pglob.mods) if pglob else {}
            pmods.update(pz.mods)
            _, iglob, izones = self.instruments[inst]
            for iz in izones:
                ig = dict(iglob.gens) if iglob else {}
                ig.update(iz.gens)
                ik = iz.gens.get(KEY_RANGE, ig.get(KEY_RANGE, (0, 127)))
                iv = iz.gens.get(VEL_RANGE, ig.get(VEL_RANGE, (0, 127)))
                if not (ik[0] <= key <= ik[1] and iv[0] <= vel <= iv[1]):
                    continue
                gens = dict(DEFAULT_GENS)
                gens.update(ig)
                for oper, amount in pg.items():
                    if oper not in _NOT_PRESET:
                        gens[oper] = gens.get(oper, 0) + amount
                sid = gens[SAMPLE_ID]
                if sid >= len(self.sample_headers) or int(self.sample_headers[sid]["type"]) & 0x8000:
                    continue
                # modulators: defaults < instrument global < instrument local (identical ones replace),
                # then preset modulators add their amounts
                mods = dict(DEFAULT_MODS)
                if iglob:
                    mods.update(iglob.mods)
                mods.update(iz.mods)
                for ident, amount in pmods.items():
                    mods[ident] = mods.get(ident, 0) + amount
                kn = gens[KEYNUM] if gens[KEYNUM] >= 0 else key
                vv = gens[VELOCITY] if gens[VELOCITY] > 0 else vel
                mod = _modulate(mods, kn, vv)
                att = ATTENUATION_SCALE * gens.get(ATTENUATION, 0) + mod.pop(ATTENUATION, 0.0)
                for dest, v in mod.items():
                    if dest not in (SAMPLE_ID, INSTRUMENT, KEY_RANGE, VEL_RANGE, SAMPLE_MODES):
                        gens[dest] = gens.get(dest, 0) + v
                gens["att_cB"] = float(np.clip(att, 0.0, 1440.0))
                out.append((sid, gens))
        return out

    # -------------------------------------------------------------------------------------- rendering
    def render_note(self, bank, program, key, velocity, duration_s, release_s=None, bend=None, vibrato=None):
        """Render one note (stereo float64 at dsp.SR, onset at sample 0).
        key       MIDI note (float: fractional part detunes; zones are chosen by the rounded key)
        velocity  MIDI velocity 1..127 (floats 0..1 are read as a fraction of 127)
        duration_s  gate (note-on) time; the clip continues through the release
        release_s   override of the zone release time
        bend      optional pitch deviation in cents: scalar or array at dsp.SR (held at its last value)
        vibrato   optional (depth_cents, rate_hz, delay_s) added on top of the bank's own vibrato"""
        vel = float(velocity)
        vel = vel * 127.0 if vel <= 1.0 else vel
        vel = int(np.clip(round(vel), 1, 127))
        duration_s = max(0.005, float(duration_s))
        bkey = None
        if bend is not None and np.ndim(bend) > 0:
            b = np.ascontiguousarray(bend, dtype=np.float64)
            bkey = hashlib.blake2b(b.tobytes(), digest_size=8).hexdigest()
        elif bend is not None:
            bkey = round(float(bend), 3)
        ckey = (int(bank), int(program), round(float(key), 3), vel, round(duration_s, 3),
                None if release_s is None else round(float(release_s), 3), bkey,
                None if vibrato is None else tuple(round(float(v), 3) for v in vibrato))
        hit = self._cache.get(ckey)
        if hit is not None:
            self._cache.move_to_end(ckey)
            return hit.astype(np.float64)
        out = self._render(int(bank), int(program), float(key), vel, duration_s, release_s, bend, vibrato)
        self._cache[ckey] = out.astype(np.float32)
        self._cached += out.size
        while self._cached > CACHE_SAMPLES and len(self._cache) > 1:
            _, old = self._cache.popitem(last=False)
            self._cached -= old.size
        return out

    def _render(self, bank, program, key, vel, gate, release_s, bend, vibrato):
        ikey = int(np.clip(round(key), 0, 127))
        voices = self.voices(bank, program, ikey, vel)
        if not voices:
            return np.zeros((2, dsp.n_of(gate + 0.05)))
        # stereo-linked pairs share the playback-rate curve of their partner (rendered first)
        order = sorted(range(len(voices)), key=lambda i: int(self.sample_headers[voices[i][0]]["type"]) & 2)
        rates = {}
        parts = []
        for i in order:
            sid, gens = voices[i]
            partner = int(self.sample_headers[sid]["link"])
            shared = rates.get((partner, sid))
            y, pan, rate = self._voice(sid, gens, key, vel, gate, release_s, bend, vibrato, shared)
            rates[(sid, partner)] = rate
            parts.append((y, pan))
        n = max(len(y) for y, _ in parts)
        out = np.zeros((2, n))
        for y, pan in parts:
            gl, gr = dsp.pan_gains(pan)
            out[0, :len(y)] += gl * y
            out[1, :len(y)] += gr * y
        out = _trim_tail(out, dsp.n_of(gate))
        n = out.shape[-1]
        k = min(n, dsp.n_of(0.004))
        if k > 1:
            out[:, n - k:] *= np.linspace(1.0, 0.0, k)
        return out

    def _voice(self, sid, g, key, vel, gate, release_s, bend, vibrato, shared_rate):
        h = self.sample_headers[sid]
        kn = g[KEYNUM] if g[KEYNUM] >= 0 else key
        start = int(h["start"]) + round(g.get(START_OFS, 0) + 32768 * g.get(START_COARSE, 0))
        end = int(h["end"]) + round(g.get(END_OFS, 0) + 32768 * g.get(END_COARSE, 0))
        ls = int(h["loop_start"]) + round(g.get(LOOP_START_OFS, 0) + 32768 * g.get(LOOP_START_COARSE, 0))
        le = int(h["loop_end"]) + round(g.get(LOOP_END_OFS, 0) + 32768 * g.get(LOOP_END_COARSE, 0))
        total = len(self.samples)
        start, end = int(np.clip(start, 0, total - 1)), int(np.clip(end, 1, total))
        mode = g.get(SAMPLE_MODES, 0) & 3
        looped = mode in (1, 3) and start <= ls < le <= end and le - ls >= 4
        # ------------------------------------------------ volume envelope (DAHDSR) and output length
        kfac = 60.0 - float(np.clip(round(kn), 0, 127))
        d = tc2s(g[DELAY_VOL])
        a = max(tc2s(g[ATTACK_VOL]), 0.0015)
        hold = tc2s(g[HOLD_VOL] + g.get(KEY_TO_VOL_HOLD, 0) * kfac)
        dec = max(tc2s(g[DECAY_VOL] + g.get(KEY_TO_VOL_DECAY, 0) * kfac), 0.001)
        sus_db = float(np.clip(g.get(SUSTAIN_VOL, 0), 0, 1440)) / 10.0
        rel = max(float(release_s) if release_s is not None else tc2s(g[RELEASE_VOL]), 0.008)
        tail = min(rel, MAX_TAIL_S)
        n = dsp.n_of(gate + tail)
        t = dsp.t_axis(n)
        env_db = self._env_db(t, d, a, hold, dec, sus_db)
        g_i = min(len(t) - 1, dsp.n_of(gate))
        rel_db = env_db[g_i]
        after = t >= gate
        env_db = np.where(after, rel_db - 100.0 * (t - gate) / rel, env_db)
        amp = np.where(t < d, 0.0, 10.0 ** (np.maximum(env_db, -100.0) / 20.0))
        att_lin = np.clip((t - d) / a, 0.0, 1.0)
        amp = np.where((t >= d) & (t < d + a) & ~after, att_lin, amp)
        if g_i > 0 and gate < d + a:                            # released during the attack: release from there
            lvl = float(np.clip((gate - d) / a, 1e-5, 1.0))
            amp = np.where(after, lvl * 10.0 ** (-5.0 * (t - gate) / rel), amp)
        # ------------------------------------------------ pitch: tuning, LFOs, modulation envelope, bend
        root = g[ROOT_KEY] if g[ROOT_KEY] >= 0 else (int(h["pitch"]) if int(h["pitch"]) <= 127 else 60)
        cents = ((kn - root) * g[SCALE_TUNING] + 100.0 * g.get(COARSE_TUNE, 0) + g.get(FINE_TUNE, 0)
                 + int(h["correction"]))
        cents_t = np.full(n, float(cents))
        mod_env = None
        if g.get(MOD_ENV_TO_PITCH, 0) or g.get(MOD_ENV_TO_FC, 0):
            mod_env = self._mod_env(t, g, kfac, gate)
            if g.get(MOD_ENV_TO_PITCH, 0):
                cents_t += g[MOD_ENV_TO_PITCH] * mod_env
        if g.get(VIB_LFO_TO_PITCH, 0):
            cents_t += g[VIB_LFO_TO_PITCH] * self._lfo(t, tc2s(g[DELAY_VIB_LFO]), abs_cents_hz(g.get(FREQ_VIB_LFO, 0)))
        mod_lfo = None
        if g.get(MOD_LFO_TO_PITCH, 0) or g.get(MOD_LFO_TO_FC, 0) or g.get(MOD_LFO_TO_VOL, 0):
            mod_lfo = self._lfo(t, tc2s(g[DELAY_MOD_LFO]), abs_cents_hz(g.get(FREQ_MOD_LFO, 0)))
            if g.get(MOD_LFO_TO_PITCH, 0):
                cents_t += g[MOD_LFO_TO_PITCH] * mod_lfo
            if g.get(MOD_LFO_TO_VOL, 0):
                amp = amp * 10.0 ** (-g[MOD_LFO_TO_VOL] * mod_lfo / 200.0)
        if vibrato is not None:
            depth, vrate, vdelay = (list(vibrato) + [0.25])[:3]
            ramp = dsp.smoothstep((t - vdelay) / 0.35)
            cents_t += depth * ramp * np.sin(dsp.TWO_PI * vrate * t)
        if bend is not None:
            if np.ndim(bend) == 0:
                cents_t += float(bend)
            else:
                b = np.asarray(bend, dtype=np.float64)
                cents_t += b[:n] if len(b) >= n else np.concatenate([b, np.full(n - len(b), b[-1] if len(b) else 0.0)])
        if shared_rate is not None and len(shared_rate) == n:
            rate = shared_rate
        else:
            rate = 2.0 ** (cents_t / 1200.0) * (float(h["rate"]) / SR)
        # ------------------------------------------------ read positions (loop-aware) and cubic interpolation
        u = np.cumsum(rate) - rate[0]
        p = start + u
        wrap = np.zeros(n, dtype=bool)
        if looped:
            L = le - ls
            pw = np.where(p >= le, ls + np.mod(p - ls, L), p)
            if mode == 1:
                wrap = p >= ls
                p = pw
            else:
                in_hold = t < gate
                wrap = in_hold & (p >= ls)
                if np.any(~in_hold):
                    i_rel = int(np.argmax(~in_hold))
                    p_rel = pw[i_rel] - u[i_rel]
                    p = np.where(in_hold, pw, p_rel + u)
                else:
                    p = pw
        alive = wrap | (p < end - 1)
        if not np.all(alive):
            n = max(int(np.argmin(alive)), 2)
            p, wrap, amp, t = p[:n], wrap[:n], amp[:n], t[:n]
            amp = amp * np.minimum(1.0, (n - np.arange(n)) / max(1.0, dsp.n_of(0.003)))
            if mod_lfo is not None:
                mod_lfo = mod_lfo[:n]
            if mod_env is not None:
                mod_env = mod_env[:n]
            rate = rate[:n]
        p = np.minimum(p, end - 1.000001)
        i0 = np.floor(p).astype(np.int64)
        fr = p - i0
        im1, i1, i2 = i0 - 1, i0 + 1, i0 + 2
        if looped:
            L = le - ls
            i1 = np.where(wrap & (i1 >= le), i1 - L, i1)
            i2 = np.where(wrap & (i2 >= le), i2 - L, i2)
            im1 = np.where(wrap & (im1 < ls) & (u[:len(p)] + start >= le), im1 + L, im1)
        hi = len(self.samples) - 1
        x = self.samples
        xm1 = x[np.clip(im1, 0, hi)].astype(np.float64)
        x0 = x[np.clip(i0, 0, hi)].astype(np.float64)
        x1 = x[np.clip(i1, 0, hi)].astype(np.float64)
        x2 = x[np.clip(i2, 0, hi)].astype(np.float64)
        c1 = 0.5 * (x1 - xm1)
        c2 = xm1 - 2.5 * x0 + 2.0 * x1 - 0.5 * x2
        c3 = 0.5 * (x2 - xm1) + 1.5 * (x0 - x1)
        y = ((c3 * fr + c2) * fr + c1) * fr + x0
        # ------------------------------------------------ filter, gain, pan
        fc = float(g[FILTER_FC])
        fc_t = None
        if mod_env is not None and g.get(MOD_ENV_TO_FC, 0):
            fc_t = fc + g[MOD_ENV_TO_FC] * mod_env
        if mod_lfo is not None and g.get(MOD_LFO_TO_FC, 0):
            fc_t = (fc if fc_t is None else fc_t) + g[MOD_LFO_TO_FC] * mod_lfo
        q_lin = max(0.7071, 10.0 ** (float(np.clip(g.get(FILTER_Q, 0), 0, 960)) / 200.0))
        if fc_t is not None:
            hz = 8.176 * 2.0 ** (np.clip(fc_t, 1500, 13500) / 1200.0)
            if np.min(hz) < 17000.0:
                y = dsp.lp_varying(y, np.minimum(hz, dsp.NYQ * 0.95), q_lin)
        elif fc < 13400:
            hz = abs_cents_hz(np.clip(fc, 1500, 13500))
            if hz < 17000.0:
                y = dsp.biquad(y, "lp", hz, q_lin)
        y = y * amp * 10.0 ** (-g["att_cB"] / 200.0)
        pan = float(np.clip(g.get(PAN, 0), -500, 500)) / 500.0
        return y, pan, rate

    @staticmethod
    def _env_db(t, d, a, hold, dec, sus_db):
        """volume envelope in dB (0 at the peak): flat through attack/hold, then a linear-in-dB decay of
        100 dB per `dec` seconds that stops at the sustain level"""
        t_dec = d + a + hold
        return np.where(t < t_dec, 0.0, np.maximum(-100.0 * (t - t_dec) / dec, -sus_db))

    @staticmethod
    def _lfo(t, delay, hz):
        """triangle LFO in [-1, 1] starting at 0 after `delay`"""
        ph = np.maximum(t - delay, 0.0) * hz
        tri = 4.0 * np.abs(np.mod(ph + 0.25, 1.0) - 0.5) - 1.0
        return np.where(t < delay, 0.0, tri)

    @staticmethod
    def _mod_env(t, g, kfac, gate):
        d = tc2s(g[DELAY_MOD_ENV])
        a = max(tc2s(g[ATTACK_MOD_ENV]), 0.001)
        hold = tc2s(g[HOLD_MOD_ENV] + g.get(KEY_TO_MOD_HOLD, 0) * kfac)
        dec = max(tc2s(g[DECAY_MOD_ENV] + g.get(KEY_TO_MOD_DECAY, 0) * kfac), 0.001)
        sus = 1.0 - float(np.clip(g.get(SUSTAIN_MOD_ENV, 0), 0, 1000)) / 1000.0
        rel = max(tc2s(g[RELEASE_MOD_ENV]), 0.001)
        e = np.where(t < d, 0.0, np.clip((t - d) / a, 0.0, 1.0))
        t_dec = d + a + hold
        e = np.where(t >= t_dec, np.maximum(1.0 - (t - t_dec) / dec, sus), e)
        at_gate = float(np.interp(gate, t, e)) if len(t) else 0.0
        return np.where(t >= gate, np.maximum(at_gate - (t - gate) / rel, 0.0), e)

    def loudness(self, bank, program, key=60, velocity=100, duration_s=1.0):
        """RMS (dBFS) of the first `duration_s` of a reference note -- for level matching across presets"""
        k = (bank, program, key, velocity, duration_s)
        if k not in self._loudness:
            y = self.render_note(bank, program, key, velocity, duration_s, release_s=0.05)
            m = y[:, : dsp.n_of(duration_s)]
            self._loudness[k] = float(dsp.lin2db(np.sqrt(np.mean(m * m)) + 1e-12))
        return self._loudness[k]


def _trim_tail(y, keep, floor_db=-66.0):
    """drop the inaudible end of a clip (after sample `keep`): cut where the 10 ms envelope stays below the
    clip's peak by `floor_db`"""
    n = y.shape[-1]
    w = dsp.n_of(0.01)
    if n <= keep + 4 * w:
        return y
    k = n // w
    e = np.sqrt(np.mean(y[:, :k * w].reshape(2, k, w) ** 2, axis=(0, 2)))
    thr = e.max() * 10.0 ** (floor_db / 20.0)
    loud = np.nonzero(e > thr)[0]
    end = max(keep, (int(loud[-1]) + 2) * w if len(loud) else keep)
    return y[:, :min(n, end)]


# ------------------------------------------------------------------------------------------------ banks
_LOADED = {}
_STATE = {"choice": None, "bank": None, "resolved": False}


def load(path):
    """Parse an SF2 file once per process (cached by resolved path)."""
    p = Path(path).expanduser().resolve()
    if p not in _LOADED:
        _LOADED[p] = SoundFont(p)
    return _LOADED[p]


def use(choice):
    """Override the audio.soundbank setting for this process: 'auto' | 'off' | a path to an .sf2 file."""
    _STATE.update(choice=str(choice), bank=None, resolved=False)


def setting():
    if _STATE["choice"] is not None:
        return _STATE["choice"]
    from codecinema.workspace import settings
    return str(settings.get("audio", "soundbank", "auto") or "auto")


def default():
    """The configured bank, or None for synthesized instruments.
    'auto' downloads GeneralUser GS on first use and quietly falls back to synthesis when that fails;
    'off' always uses synthesis; any other value is a path to an .sf2 file."""
    if _STATE["resolved"]:
        return _STATE["bank"]
    choice = setting().strip()
    bank = None
    if choice.lower() == "off":
        bank = None
    elif choice.lower() == "auto":
        from codecinema.runtime import downloads
        try:
            bank = load(downloads.cached(BANK_NAME, BANK_URL, BANK_SHA256, BANK_SIZE))
        except (downloads.DownloadError, SoundFontError, OSError) as exc:
            print(f"Sound bank unavailable ({exc}); using synthesized instruments.", file=sys.stderr, flush=True)
            bank = None
    else:
        from codecinema.workspace import settings
        from codecinema.workspace.paths import resolve_path
        path = resolve_path(choice, settings.ROOT)
        if not Path(path).is_file():
            raise FileNotFoundError(f"audio.soundbank: no SoundFont file at {path}")
        bank = load(path)
    _STATE.update(bank=bank, resolved=True)
    return bank


def available():
    return default() is not None


def render_note(bank, program, key, velocity, duration_s, release_s=None, **kw):
    """render_note on the default bank; raises RuntimeError when sampling is off or unavailable"""
    sf = default()
    if sf is None:
        raise RuntimeError("No SoundFont bank is available (audio.soundbank is off or the download failed)")
    return sf.render_note(bank, program, key, velocity, duration_s, release_s, **kw)
