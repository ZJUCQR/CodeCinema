"""
mix.py -- entry point of the audio lane:  python src/audio/mix.py

Reads out/notes.json and out/events.json at render time, renders
    music     score.py  (pipa, jiegu, paiban, dizi x3, bili, sheng, guqin, bell + wooden-hall reverb)
    foley     sfx.py    (cups, paws, sleeves, water, fan, seal ...)
    cats      cats.py   (meows, purrs, chirps, yawn, giggles, licks)
    ambience  ambience.py (room tone, candles, crickets, dawn birds)
mixes them (music ducks gently under the key comedic sounds), masters to -14 LUFS integrated with a true-peak
ceiling of -1 dBTP, and writes
    out/audio/final_mix.wav   48 kHz stereo 24-bit, exactly 3072 frames at 24 fps (128.0 s)
    out/audio/mix_report.json loudness, peaks, per-section levels, sync checks
    out/audio/final_mix.png   spectrogram + level curve for QC
Deterministic (every random process is seeded).
"""
import json
import os
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import dsp  # noqa: E402
import config  # noqa: E402  (src/common, put on sys.path by dsp)
import score  # noqa: E402
import ambience  # noqa: E402
import sfx  # noqa: E402
import cats  # noqa: E402
from dsp import SR, n_of  # noqa: E402

TARGET_LUFS = -14.0
CEILING_DBTP = -1.0
END_FADE_S = 2.0

# loudest-moment level of each sound (max 50 ms RMS, dBFS, before mastering); music p90 sits around -17
LEVEL = dict(
    # cats
    meow_offended=-15.0, meow_sheepish=-18.0, chirp=-19.0, sigh=-22.0, purr=-27.0, yawn=-19.5, giggle=-18.5,
    lick=-25.0,
    # foley
    tiptoe=-27.0, cup_nudge=-21.5, cup_slide=-25.0, cup_clink=-14.0, moth_flutter=-29.0, pounce=-19.0,
    sleeve_whoosh=-21.0, land_soft=-19.0, applause=-18.5, water_dip=-18.5, paw_shake=-21.0, fan=-32.0, boop=-20.0,
    paw_tap=-21.0, basket_creak=-20.0, blow=-21.0, tea_set=-19.0, seal_thump=-13.0,
)
LEVEL_WHO = {("purr", "kitten"): -25.0, ("sigh", "monk"): -21.0}
# music ducking under key comedic sounds: dB, max hold (s)
DUCK = dict(cup_clink=(-3.5, 0.6), meow_offended=(-6.0, 0.5), water_dip=(-3.0, 0.4), meow_sheepish=(-4.0, 0.6),
            yawn=(-3.0, 1.5), boop=(-3.0, 0.4), chirp=(-3.0, 0.8), seal_thump=(-2.0, 0.4))
FX_SEND = 0.2          # foley + cats into the same wooden hall
KEY_ONSETS = [("note", "sour"), ("note", "squeak"), ("event", "cup_clink"), ("event", "seal_thump")]


def _f2t(frame, fps):
    return (float(frame) - 1.0) / fps


def _st_peak_db(x, win=0.05):
    m = dsp.mono(x)
    w = n_of(win)
    if len(m) < w:
        return float(dsp.lin2db(dsp.rms(m)))
    c = np.cumsum(np.concatenate([[0.0], m * m]))
    e = (c[w:] - c[:-w]) / w
    return float(10.0 * np.log10(max(e.max(), 1e-20)))


def _section_of(doc, frame):
    for s in doc["sections"]:
        if s["f0"] <= frame <= s["f1"]:
            return s
    return doc["sections"][-1]


def _pan_for(doc, ev):
    """gentle stereo placement: event x relative to the centre of its section (story reads right -> left)"""
    if "x" not in ev:
        return 0.0
    s = _section_of(doc, ev["frame"])
    xc = 0.5 * (s["x0"] + s["x1"])
    half_view = 0.5 * config.W / config.Z_SCROLL
    return float(np.clip((float(ev["x"]) - xc) / half_view, -1.0, 1.0) * 0.45)


def render_events(doc, n_total):
    handlers = {}
    handlers.update(sfx.EVENTS)
    handlers.update(cats.EVENTS)
    fps = float(doc.get("fps", 24))
    bus = np.zeros((2, n_total))
    placed = []
    for i, ev in enumerate(doc["events"]):
        typ = ev["type"]
        fn = handlers.get(typ)
        if fn is None:
            print(f"mix: WARNING unknown event type {typ!r} at frame {ev['frame']} -- skipped")
            continue
        r = dsp.rng("event", typ, round(float(ev["frame"]), 3), i)
        clip, anchor = fn(ev, r)
        clip = np.asarray(clip, dtype=np.float64)
        who = str(ev.get("who", "")).rstrip("0123456789")
        lvl = LEVEL_WHO.get((typ, who), LEVEL.get(typ, -24.0))
        clip = clip * dsp.db2lin(lvl - _st_peak_db(clip))
        pan = _pan_for(doc, ev)
        st = dsp.pan_mono(clip, pan) if clip.ndim == 1 else dsp.pan_stereo(clip, pan)
        t = _f2t(ev["frame"], fps)
        s = int(round(t * SR)) - int(anchor)
        dsp.place(bus, st, s)
        placed.append(dict(type=typ, frame=ev["frame"], t=t, start=s, n=st.shape[-1], anchor=int(anchor), pan=pan))
    return bus, placed


def duck_envelope(placed, n_total):
    g_db = np.zeros(n_total)
    for p in placed:
        if p["type"] not in DUCK:
            continue
        depth, hold_max = DUCK[p["type"]]
        a = n_of(0.03)
        hold = min(n_of(hold_max), max(0, p["n"] - p["anchor"]))
        rel = n_of(0.45)
        c = p["start"] + p["anchor"]
        seg = np.concatenate([np.linspace(0.0, 1.0, a), np.ones(hold), 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, rel))])
        s0 = c - a
        i0, i1 = max(0, s0), min(n_total, s0 + len(seg))
        if i1 > i0:
            g_db[i0:i1] = np.minimum(g_db[i0:i1], depth * seg[i0 - s0: i1 - s0])
    return dsp.db2lin(g_db)


# ======================================================================================  analysis
def onset_near(x, t, win=0.25):
    """time of the steepest rise of the 2 ms energy envelope (1 ms hop) within +-win of t"""
    m = dsp.highpass(dsp.mono(x), 150, 2)
    a, b = max(0, n_of(t - win)), min(len(m), n_of(t + win))
    seg = m[a:b]
    hop = SR // 1000
    w = 2 * hop
    c = np.cumsum(np.concatenate([[0.0], seg * seg]))
    idx = np.arange(0, len(seg) - w, hop)
    e = (c[idx + w] - c[idx]) / w
    ldb = 10 * np.log10(e + 1e-14)
    ldb = np.convolve(np.pad(ldb, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    flux = np.diff(ldb)
    # weight by level so a rise from silence into a loud event beats noise-floor wiggles
    lvl = ldb[1:] - ldb.max()
    score_ = flux * (lvl > -25.0)
    k = int(np.argmax(score_))
    return (a + idx[k] + hop) / SR


def write_wav24(path, x, r):
    y = x.T + (r.uniform(-0.5, 0.5, x.T.shape) + r.uniform(-0.5, 0.5, x.T.shape)) / 8388607.0   # TPDF dither
    q = np.round(np.clip(y, -1.0, 1.0 - 2 ** -23) * 8388607.0).astype("<i4")
    b = np.ascontiguousarray(q).view(np.uint8).reshape(-1, 4)[:, :3]
    tmp = path + ".part"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b.tobytes())
    os.replace(tmp, path)


def plot_qc(path, x, doc, fps, marks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy import signal as sg
    m = dsp.mono(x)
    f, tt, S = sg.spectrogram(m, fs=SR, nperseg=2048, noverlap=1024, window="hann", mode="magnitude")
    keep = f <= 14000
    Sdb = 20 * np.log10(S[keep] + 1e-9)
    fig, ax = plt.subplots(2, 1, figsize=(20, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
    vmax = np.percentile(Sdb, 99.7)
    ax[0].pcolormesh(tt, f[keep], Sdb, vmin=vmax - 80, vmax=vmax, cmap="magma", shading="auto", rasterized=True)
    ax[0].set_yscale("symlog", linthresh=500)
    ax[0].set_ylim(40, 14000)
    ax[0].set_ylabel("Hz")
    ax[0].set_title("final_mix.wav -- spectrogram (sections and key sync points marked)")
    hop = SR // 10
    nb = len(m) // hop
    lv = 10 * np.log10(np.mean(m[: nb * hop].reshape(nb, hop) ** 2, axis=1) + 1e-12)
    ax[1].plot(np.arange(nb) * hop / SR, lv, lw=0.7, color="k")
    ax[1].set_ylim(-80, 0)
    ax[1].set_ylabel("RMS dBFS (100 ms)")
    ax[1].set_xlabel("seconds")
    for s in doc["sections"]:
        t0 = _f2t(s["f0"], fps)
        for a in ax:
            a.axvline(t0, color="c", lw=0.8, alpha=0.8)
        ax[1].text(t0 + 0.3, -8, s["id"], fontsize=9)
    for name, t in marks:
        for a in ax:
            a.axvline(t, color="lime", lw=0.6, ls="--", alpha=0.8)
        ax[0].text(t, 9000, name, fontsize=7, color="lime", rotation=90, va="top")
    ax[1].set_xlim(0, len(m) / SR)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)


# ======================================================================================  main
def main():
    t_start = time.time()
    with open(config.NOTES_JSON, encoding="utf-8") as fh:
        notes_doc = json.load(fh)
    with open(config.EVENTS_JSON, encoding="utf-8") as fh:
        ev_doc = json.load(fh)
    fps = float(ev_doc.get("fps", config.FPS))
    f_end = int(ev_doc.get("frame_end", config.FRAME_END))
    f_start = int(ev_doc.get("frame_start", config.FRAME_START))
    n_frames = f_end - f_start + 1
    n_total = int(round(n_frames / fps * SR))
    os.makedirs(config.AUDIO_DIR, exist_ok=True)

    t0 = time.time()
    mus = score.render(notes_doc, ev_doc.get("cue", {}), n_total)
    music_dry = sum(mus["stems"].values())
    print(f"music     {time.time() - t0:5.1f} s   ({len(notes_doc['notes'])} notes)")

    t0 = time.time()
    fx, placed = render_events(ev_doc, n_total)
    fx_wet = dsp.convolve_reverb(fx, "woodhall", seed=11)
    fx_wet = dsp.eq_chain(fx_wet, [("highshelf", 5500, -4.0, 0.7), ("hp", 80, 0.0, 0.7)])
    print(f"events    {time.time() - t0:5.1f} s   ({len(placed)} placed)")

    t0 = time.time()
    amb = ambience.render(ev_doc, n_total)
    print(f"ambience  {time.time() - t0:5.1f} s")

    duck = duck_envelope(placed, n_total)
    music = (music_dry + mus["wet"]) * duck
    mix = music + fx + FX_SEND * fx_wet + amb
    mix = dsp.highpass(mix, 25.0, 2)

    # ---------------------------------------------------------------- master
    t0 = time.time()
    import pyloudnorm as pyln
    meter = pyln.Meter(SR)

    def lufs(x):
        return float(meter.integrated_loudness(x.T))

    mix = mix * dsp.db2lin(-18.0 - lufs(mix))
    mix, _ = dsp.compressor(mix, threshold_db=-17.0, ratio=1.6, attack_ms=12.0, release_ms=220.0, knee_db=8.0)
    t_fade = END_FADE_S
    mix = dsp.fade(mix, 0.005, t_fade)
    gain_db = TARGET_LUFS - lufs(mix)
    out = mix
    for it in range(4):
        out, _ = dsp.limiter(mix * dsp.db2lin(gain_db), ceiling_db=CEILING_DBTP - 0.1, lookahead_ms=5.0,
                             release_ms=150.0)
        L = lufs(out)
        if abs(L - TARGET_LUFS) < 0.05:
            break
        gain_db += TARGET_LUFS - L
    out = dsp.pad_to(out, n_total)
    tp = dsp.true_peak_dbtp(out)
    L = lufs(out)
    print(f"master    {time.time() - t0:5.1f} s   {L:.2f} LUFS  {tp:.2f} dBTP")

    wav_path = os.path.join(config.AUDIO_DIR, "final_mix.wav")
    write_wav24(wav_path, out, dsp.rng("dither"))

    # ---------------------------------------------------------------- report
    g_master = dsp.db2lin(gain_db)
    sections = []
    for s in ev_doc["sections"]:
        a, b = n_of(_f2t(s["f0"], fps)), min(n_total, n_of(_f2t(s["f1"] + 1, fps)))
        seg = out[:, a:b]
        sl = float(meter.integrated_loudness(seg.T)) if b - a > SR else None
        sections.append(dict(id=s["id"], f0=s["f0"], f1=s["f1"], rms_dbfs=round(float(dsp.lin2db(dsp.rms(seg))), 2),
                             lufs=round(sl, 2) if sl is not None and np.isfinite(sl) else None,
                             peak_dbfs=round(float(dsp.lin2db(dsp.peak(seg))), 2),
                             music_rms_dbfs=round(float(dsp.lin2db(dsp.rms(music[:, a:b] * g_master))), 2),
                             fx_rms_dbfs=round(float(dsp.lin2db(dsp.rms(fx[:, a:b] * g_master))), 2)))
    checks = []
    marks = []
    for kind, name in KEY_ONSETS:
        if kind == "note":
            tgt = [n for n in notes_doc["notes"] if n["tech"] == name]
            stem = mus["stems"]["pipa" if name == "sour" else "winds"]
        else:
            tgt = [e for e in ev_doc["events"] if e["type"] == name]
            stem = fx
        for n_ in tgt:
            t = _f2t(n_["frame"], fps)
            t_stem = onset_near(stem, t)
            t_mix = onset_near(out, t)
            ok = abs(t_stem - t) <= 1.0 / fps and abs(t_mix - t) <= 1.0 / fps
            checks.append(dict(what=name, frame=n_["frame"], t=round(t, 4), onset_stem=round(t_stem, 4),
                               onset_mix=round(t_mix, 4), err_frames_stem=round((t_stem - t) * fps, 3),
                               err_frames_mix=round((t_mix - t) * fps, 3), ok=bool(ok)))
            marks.append((name, t))
    marks.append(("music_stop", mus["stop"][0]))
    rep = dict(file=os.path.relpath(wav_path, config.ROOT), sample_rate=SR, channels=2, bit_depth=24,
               samples=int(out.shape[-1]), seconds=out.shape[-1] / SR, frames=n_frames, fps=fps,
               integrated_lufs=round(L, 2), true_peak_dbtp=round(tp, 2),
               sample_peak_dbfs=round(float(dsp.lin2db(dsp.peak(out))), 2), clipped_samples=int(np.sum(np.abs(out) >= 1.0)),
               master_gain_db=round(gain_db, 2), sections=sections, sync_checks=checks,
               events_placed=len(placed), notes=len(notes_doc["notes"]),
               render_seconds=round(time.time() - t_start, 1))
    with open(os.path.join(config.AUDIO_DIR, "mix_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    plot_qc(os.path.join(config.AUDIO_DIR, "final_mix.png"), out, ev_doc, fps, marks)

    print(f"wrote {wav_path}  ({out.shape[-1]} samples = {out.shape[-1] / SR:.3f} s)")
    print(f"integrated {L:.2f} LUFS | true peak {tp:.2f} dBTP | sample peak {rep['sample_peak_dbfs']:.2f} dBFS | "
          f"clipped {rep['clipped_samples']}")
    for s in sections:
        print(f"  {s['id']:9s} rms {s['rms_dbfs']:7.2f} dBFS  lufs {s['lufs']}  music {s['music_rms_dbfs']:7.2f}  "
              f"fx {s['fx_rms_dbfs']:7.2f}")
    for c in checks:
        print(f"  sync {c['what']:10s} frame {c['frame']:7.1f}  stem {c['err_frames_stem']:+.2f} f  "
              f"mix {c['err_frames_mix']:+.2f} f  {'OK' if c['ok'] else 'FAIL'}")
    print(f"total {time.time() - t_start:.1f} s")
    return 0 if all(c["ok"] for c in checks) and tp <= CEILING_DBTP + 1e-6 else 1


if __name__ == "__main__":
    sys.exit(main())
