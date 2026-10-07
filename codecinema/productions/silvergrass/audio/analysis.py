"""
analysis.py -- measurement tools used for self-verification (we cannot listen, so we measure).

    loudness_integrated / short_term / momentary / lra  : ITU-R BS.1770-4 / EBU R128 (K-weighted, gated)
    true_peak_dbtp                                       : 4x oversampled true peak (dsp.true_peak_envelope)
    onset_times / guided_onset                           : HF energy-rise onset detector (0.5 ms hop)
    spectral_centroid / decay_t60 / f0_estimate          : per-instrument sanity stats
    plot_spectrogram                                     : log-frequency spectrogram + loudness panel (PNG)
"""

import numpy as np
from scipy import signal

import dsp
from dsp import SR

# ------------------------------------------------------------------ BS.1770 K-weighting (48 kHz)
_KB1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
_KA1 = [1.0, -1.69065929318241, 0.73248077421585]
_KB2 = [1.0, -2.0, 1.0]
_KA2 = [1.0, -1.99004745483398, 0.99007225036621]


def k_weight(x):
    y = signal.lfilter(_KB1, _KA1, dsp.as_stereo(x), axis=-1)
    return signal.lfilter(_KB2, _KA2, y, axis=-1)


def _block_ms(y, win, hop):
    """mean-square per block (sum over channels, G=1 for L/R)"""
    n = y.shape[-1]
    wn, hn = int(round(win * SR)), int(round(hop * SR))
    if n < wn:
        return np.array([])
    c = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y * y, axis=-1)], axis=-1)
    starts = np.arange(0, n - wn + 1, hn)
    ms = (c[:, starts + wn] - c[:, starts]) / wn
    return ms.sum(axis=0)


def _to_lufs(z):
    return -0.691 + 10.0 * np.log10(np.maximum(z, 1e-20))


def loudness_integrated(x):
    """integrated loudness in LUFS (absolute gate -70, relative gate -10 LU)"""
    y = k_weight(x)
    z = _block_ms(y, 0.4, 0.1)
    if z.size == 0:
        return -np.inf
    l = _to_lufs(z)
    zg = z[l > -70.0]
    if zg.size == 0:
        return -np.inf
    rel = _to_lufs(np.mean(zg)) - 10.0
    zg2 = z[(l > -70.0) & (l > rel)]
    if zg2.size == 0:
        return -np.inf
    return float(_to_lufs(np.mean(zg2)))


def loudness_curve(x, win=3.0, hop=0.1):
    """short-term (win=3) or momentary (win=0.4) loudness curve -> (times_centre, lufs)"""
    y = k_weight(x)
    z = _block_ms(y, win, hop)
    t = np.arange(len(z)) * hop + win / 2
    return t, _to_lufs(z)


def lra(x):
    """EBU Tech 3342 loudness range (LU)"""
    t, st = loudness_curve(x, 3.0, 0.1)
    st = st[st > -70]
    if st.size < 2:
        return 0.0
    z = 10 ** ((st + 0.691) / 10)
    rel = _to_lufs(np.mean(z)) - 20.0
    st = st[st > rel]
    if st.size < 2:
        return 0.0
    return float(np.percentile(st, 95) - np.percentile(st, 10))


def true_peak_dbtp(x, oversample=8):
    """BS.1770 true peak (dBTP).  8x oversampling (the standard asks for >= 4x; 8x reads ~0.1 dB closer to a
    16x reference on this material)."""
    return dsp.true_peak_dbtp(x, oversample)


def basic_stats(x):
    xs = dsp.as_stereo(x)
    finite = bool(np.all(np.isfinite(xs)))
    return dict(
        finite=finite,
        sample_peak_dbfs=float(dsp.lin2db(np.max(np.abs(xs)))) if finite else None,
        dc_offset=[float(np.mean(xs[0])), float(np.mean(xs[1]))] if finite else None,
        clip_count=int(np.sum(np.abs(xs) >= 0.99999)) if finite else None,
        rms_dbfs=float(dsp.lin2db(np.sqrt(np.mean(xs * xs)))) if finite else None,
    )


# ------------------------------------------------------------------ onsets
def _energy_db(xm, hp=1000.0, win=0.002, hop=0.0005):
    y = dsp.highpass(xm, hp, 4)
    wn, hn = int(round(win * SR)), int(round(hop * SR))
    c = np.concatenate([[0.0], np.cumsum(y * y)])
    starts = np.arange(0, len(y) - wn, hn)
    e = (c[starts + wn] - c[starts]) / wn
    t = (starts + wn / 2) / SR
    return t, 10 * np.log10(e + 1e-14)


def onset_times(x, hp=1000.0, rise_db=9.0, min_gap=0.03, floor_db=-70.0):
    """unguided onset detection: frames where HF energy rises >= rise_db within 2 ms
    above a floor. Returns onset times (s) at the half-rise crossing."""
    xm = dsp.mono(x)
    t, db = _energy_db(xm, hp)
    d = np.zeros_like(db)
    d[4:] = db[4:] - np.minimum.reduce([db[:-4], db[1:-3], db[2:-2], db[3:-1]])
    cand = np.nonzero((d >= rise_db) & (db > floor_db))[0]
    onsets = []
    last = -1e9
    for i in cand:
        if t[i] - last < min_gap:
            continue
        # half-rise crossing between the pre-level and the local max
        lo = db[max(0, i - 6)]
        hi = db[i: i + 8].max()
        mid = 0.5 * (lo + hi)
        j = i - 6
        while j < i + 8 and j < len(db) - 1 and db[j] < mid:
            j += 1
        onsets.append(float(t[max(j, 0)]))
        last = t[i]
    return np.array(onsets)


def guided_onset(x, t_event, search=0.05, hp=1000.0):
    """locate the onset nearest to t_event: candidate onsets are local maxima (>= 6 dB) of the energy-rise
    function in three bands (LF 60-400 Hz with 6 ms frames, MF 400-2500 Hz, HF > 2.5 kHz with 2 ms frames);
    the candidate nearest to the event wins.  Returns (t_onset, rise_db)."""
    xm = dsp.mono(x)
    a = max(0, int((t_event - search - 0.03) * SR))
    b = min(len(xm), int((t_event + search + 0.03) * SR))
    if b - a < 800:
        return None, 0.0
    seg = xm[a:b]
    cands = []
    best = (None, -99.0)
    for (lo, hi, win, lag) in ((60, 400, 0.006, 6), (400, 2500, 0.002, 4), (2500, None, 0.002, 4)):
        y = dsp.bandpass(seg, lo, hi, 2) if hi else dsp.highpass(seg, lo, 4)
        wn, hn = int(round(win * SR)), int(round(0.0005 * SR))
        c = np.concatenate([[0.0], np.cumsum(y * y)])
        st = np.arange(0, len(y) - wn, hn)
        e = (c[st + wn] - c[st]) / wn
        t = (st + wn / 2) / SR + a / SR
        db = 10 * np.log10(e + 1e-14)
        db = np.maximum(db, db.max() - 50.0)
        L = lag * int(round(win / 0.002))
        rise = np.full_like(db, -99.0)
        rise[L:-L] = db[2 * L:] - db[:-2 * L]
        m = (t >= t_event - search) & (t <= t_event + search)
        idx = np.nonzero(m)[0]
        for i in idx:
            if rise[i] >= 6.0 and rise[i] >= rise[max(i - 1, 0)] and rise[i] >= rise[min(i + 1, len(rise) - 1)]:
                lo_, hi_ = db[max(0, i - L)], db[min(len(db) - 1, i + L)]
                mid = 0.5 * (lo_ + hi_)
                j = max(0, i - L)
                while j < min(len(db) - 1, i + L) and db[j] < mid:
                    j += 1
                cands.append((float(t[j]), float(rise[i])))
        if len(idx):
            k = idx[np.argmax(rise[idx])]
            if rise[k] > best[1]:
                best = (float(t[k]), float(rise[k]))
    if cands:
        return min(cands, key=lambda c: abs(c[0] - t_event))
    return best


# ------------------------------------------------------------------ instrument stats
def spectral_centroid(x, nfft=4096, weight="power"):
    """energy centroid (Hz): power-weighted mean frequency over the whole clip ('power', where the energy
    is) or the classic magnitude-weighted per-frame centroid averaged by frame energy ('mag', sensitive to
    broadband noise floors)"""
    xm = dsp.mono(x)
    if len(xm) < nfft:
        xm = np.pad(xm, (0, nfft - len(xm)))
    f, t, Z = signal.stft(xm, SR, nperseg=nfft, noverlap=nfft // 2)
    if weight == "power":
        P = (np.abs(Z) ** 2).sum(axis=1)
        return float(np.sum(f * P) / max(np.sum(P), 1e-20))
    mag = np.abs(Z)
    e = mag.sum(axis=0)
    c = (f[:, None] * mag).sum(axis=0) / np.maximum(e, 1e-12)
    w = (mag ** 2).sum(axis=0)
    return float(np.sum(c * w) / max(np.sum(w), 1e-20))


def band_share(x, lo, hi):
    """fraction (dB) of the clip's energy between lo and hi Hz"""
    xm = dsp.mono(x)
    if len(xm) < 256:
        return None
    f, P = signal.welch(xm, SR, nperseg=min(8192, len(xm)))
    tot = P.sum()
    if tot <= 0:
        return None
    return float(10 * np.log10(max(P[(f >= lo) & (f < hi)].sum(), 1e-20) / tot))


def decay_t60(x, frame=0.01):
    """T60 from a linear fit of the dB envelope between (peak-5 dB) and (peak-35 dB or noise)"""
    xm = dsp.mono(x)
    hn = int(frame * SR)
    nb = len(xm) // hn
    if nb < 4:
        return None
    e = 10 * np.log10(np.mean(xm[: nb * hn].reshape(nb, hn) ** 2, axis=1) + 1e-14)
    ip = int(np.argmax(e))
    pk = e[ip]
    seg = e[ip:]
    try:
        i0 = np.nonzero(seg <= pk - 5)[0][0]
    except IndexError:
        return None
    below = np.nonzero(seg <= pk - 35)[0]
    i1 = below[0] if len(below) else len(seg) - 1
    if i1 - i0 < 3:
        return None
    tt = np.arange(i0, i1) * frame
    slope = np.polyfit(tt, seg[i0:i1], 1)[0]
    if slope >= -1e-3:
        return None
    return float(-60.0 / slope)


def f0_estimate(x, fmin=40.0, fmax=2000.0, t0=0.05, dur=0.5):
    """FFT-peak f0 estimate on a steady portion (harmonic product spectrum, 3 harmonics)"""
    xm = dsp.mono(x)
    a = int(t0 * SR)
    seg = xm[a: a + int(dur * SR)]
    if len(seg) < 2048:
        return None
    seg = seg * np.hanning(len(seg))
    nfft = 1 << int(np.ceil(np.log2(len(seg) * 8)))
    S = np.abs(np.fft.rfft(seg, nfft))
    f = np.fft.rfftfreq(nfft, 1 / SR)
    hps = S.copy()
    for h in (2, 3):
        d = S[::h]
        hps[: len(d)] *= d
    m = (f >= fmin) & (f <= fmax)
    return float(f[m][np.argmax(hps[m])])


# ------------------------------------------------------------------ spectrogram plot
def _log_spec(xm, t0, t1, n_t=2000, n_f=320, fmin=25.0, fmax=20000.0):
    a, b = int(t0 * SR), int(t1 * SR)
    seg = xm[a:b]
    dur = (b - a) / SR
    nfft = 4096 if dur > 20 else 2048
    hop = max(64, int(len(seg) / n_t))
    hop = min(hop, nfft)
    f, t, Z = signal.stft(seg, SR, nperseg=nfft, noverlap=nfft - hop, boundary=None, padded=False)
    P = np.abs(Z) ** 2
    edges = np.geomspace(fmin, fmax, n_f + 1)
    idx = np.searchsorted(f, edges)
    out = np.zeros((n_f, P.shape[1]))
    for i in range(n_f):
        lo, hi = idx[i], max(idx[i + 1], idx[i] + 1)
        out[i] = P[lo:hi].mean(axis=0)
    return t + t0, edges, 10 * np.log10(out + 1e-14)


def plot_spectrogram(x, path, t0=0.0, t1=None, title="", markers=(), spans=(), loud=True, vrange=85.0):
    """markers: [(t, label)] vertical lines; spans: [(ta, tb, label)] shaded act bands"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = dsp.as_stereo(x)
    xm = xs.mean(axis=0)
    t1 = xs.shape[-1] / SR if t1 is None else t1
    tt, edges, S = _log_spec(xm, t0, t1)
    vmax = np.percentile(S, 99.7)
    nrows = 2 if loud else 1
    fig, axes = plt.subplots(nrows, 1, figsize=(18, 7.5 if loud else 5.5), sharex=True,
                             gridspec_kw=dict(height_ratios=[3, 1] if loud else [1]))
    ax = axes[0] if loud else axes
    fc = np.sqrt(edges[:-1] * edges[1:])
    ax.pcolormesh(tt, fc, S, shading="nearest", cmap="magma", vmin=vmax - vrange, vmax=vmax)
    ax.set_yscale("log")
    ax.set_ylim(edges[0], edges[-1])
    ax.set_ylabel("Hz")
    ax.set_title(title)
    for (ta, tb, lab) in spans:
        if tb < t0 or ta > t1:
            continue
        ax.axvline(max(ta, t0), color="cyan", lw=1.2, alpha=0.8)
        ax.text(max(ta, t0) + 0.2, edges[-1] * 0.7, lab, color="cyan", fontsize=9, va="top")
    for (tm, lab) in markers:
        if t0 <= tm <= t1:
            ax.axvline(tm, color="white", lw=0.7, ls="--", alpha=0.7)
            ax.text(tm + 0.05, edges[0] * 1.3, lab, color="white", fontsize=7, rotation=90, va="bottom")
    if loud:
        a2 = axes[1]
        seg = xs[:, int(t0 * SR): int(t1 * SR)]
        if seg.shape[-1] > int(3.2 * SR):
            ts, st = loudness_curve(seg, 3.0, 0.1)
            a2.plot(ts + t0, st, color="tab:orange", lw=1.2, label="short-term (3 s)")
        tm_, mo = loudness_curve(seg, 0.4, 0.05)
        a2.plot(tm_ + t0, mo, color="tab:blue", lw=0.6, alpha=0.7, label="momentary (0.4 s)")
        a2.axhline(-14, color="gray", ls=":", lw=1)
        a2.set_ylim(-60, 0)
        a2.set_ylabel("LUFS")
        a2.set_xlabel("time (s)")
        a2.legend(loc="lower left", fontsize=8)
        a2.grid(alpha=0.25)
        for (tm, lab) in markers:
            if t0 <= tm <= t1:
                a2.axvline(tm, color="k", lw=0.5, ls="--", alpha=0.3)
    ax.set_xlim(t0, t1)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return path


# ------------------------------------------------------------------ loudness-map / balance measurements
def k_block_energy(x, win=0.4, hop=0.05):
    """K-weighted mean-square energy per block (sum over channels) -> (block start times, energy)"""
    y = k_weight(x)
    z = _block_ms(y, win, hop)
    return np.arange(len(z)) * hop, z


def momentary_curve(x, hop=0.05):
    """momentary loudness (400 ms blocks) -> (block centre times, LUFS)"""
    t, z = k_block_energy(x, 0.4, hop)
    return t + 0.2, _to_lufs(z)


def loudness_window(x, t0, t1):
    """ungated K-weighted loudness of the span [t0, t1] (LUFS) -- 'how loud was this stretch' for contexts"""
    a, b = max(0, int(round(t0 * SR))), min(x.shape[-1], int(round(t1 * SR)))
    if b - a < int(0.05 * SR):
        return -np.inf
    y = k_weight(x[:, a:b])
    return float(_to_lufs(np.sum(np.mean(y * y, axis=-1))))


def short_term_stats(x, t0, t1, hop=0.1):
    """median / p10 / p90 of the short-term (3 s) loudness over windows lying inside [t0, t1]; spans shorter than
    3 s fall back to the ungated loudness of the span"""
    a, b = max(0, int(round(t0 * SR))), min(x.shape[-1], int(round(t1 * SR)))
    if b - a < int(3.0 * SR):
        L = loudness_window(x, t0, t1)
        return dict(median=L, p10=L, p90=L, n=0)
    _, st = loudness_curve(x[:, a:b], 3.0, hop)
    st = st[np.isfinite(st)]
    return dict(median=float(np.median(st)), p10=float(np.percentile(st, 10)), p90=float(np.percentile(st, 90)),
                n=int(st.size))


OCTAVES = (31.5, 63.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0)


def octave_bands(x, t0, t1, ref=1000.0):
    """octave-band power levels (dB) relative to the `ref` octave over [t0, t1] (pink noise = flat 0 dB)"""
    a, b = max(0, int(round(t0 * SR))), min(x.shape[-1], int(round(t1 * SR)))
    xm = dsp.mono(x[:, a:b]) if x.ndim == 2 else x[a:b]
    if len(xm) < 8192:
        return None
    f, P = signal.welch(xm, SR, nperseg=8192)
    lv = {}
    for fc in OCTAVES:
        m = (f >= fc / np.sqrt(2)) & (f < fc * np.sqrt(2))
        lv[fc] = 10 * np.log10(max(P[m].sum(), 1e-30))
    r = lv[ref]
    return {(str(int(fc)) if fc >= 63 else "31.5"): round(v - r, 1) for fc, v in lv.items()}


def power_fraction_below(x, t0, t1, f_hi=120.0):
    a, b = max(0, int(round(t0 * SR))), min(x.shape[-1], int(round(t1 * SR)))
    xm = dsp.mono(x[:, a:b]) if x.ndim == 2 else x[a:b]
    if len(xm) < 8192:
        return None
    f, P = signal.welch(xm, SR, nperseg=8192)
    return float(P[f < f_hi].sum() / max(P.sum(), 1e-30))
