"""
codecinema.audio.demo -- render audition files for the whole sound library.

    python -m codecinema.audio.demo OUT_DIR [--only instruments|styles|sfx|ambience|voices] [--soundbank auto|off|PATH]

instruments/  a short phrase per instrument (a beat pattern for drums)
styles/       20 s of every composer style (its own generated theme)
sfx/          every sound effect
ambience/     15 s of every ambience bed
voices/       every babble profile speaking a line, and every vocalization
Each folder also gets a spectrogram contact sheet (<category>.png) for visual inspection.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

from codecinema.audio import dsp

CATEGORIES = ("instruments", "styles", "sfx", "ambience", "voices")
LINES = {"en": "Hello there, my little friend! Shall we go and see the sea?", "zh": "奶奶说，年兽其实很温柔，对吧？"}


def _write(path, x):
    from codecinema.audio.mixer import write_wav
    x = dsp.as_stereo(x)
    pk = dsp.peak(x)
    if pk > 0.98:
        x = x * (0.98 / pk)
    write_wav(path, x, bits=16)


def _sheet(items, path, title, fmax=12000, cols=4):
    """spectrogram contact sheet: one panel per (name, audio)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = int(np.ceil(len(items) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 2.0), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for ax, (name, x) in zip(axes.flat, items):
        m = dsp.mono(x)
        if len(m) < 512:
            m = np.pad(m, (0, 512 - len(m)))
        ax.axis("on")
        with np.errstate(divide="ignore"):          # exact digital silence has no level in dB
            ax.specgram(m + 1e-9, NFFT=1024, Fs=dsp.SR, noverlap=768, cmap="magma", vmin=-140, vmax=-25)
        ax.set_ylim(0, fmax)
        ax.set_title(name, fontsize=8)
        ax.tick_params(labelsize=6)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=60)
    plt.close(fig)


def _phrase(name):
    """a short phrase that shows an instrument's range, articulation and decay"""
    from codecinema.audio import instruments
    inst = instruments.get(name)
    if inst.kind == "drum" and name != "timpani":
        out = np.zeros((2, dsp.n_of(2.6)))
        pattern = [(0.0, 0.9), (0.25, 0.5), (0.5, 0.7), (0.75, 0.5), (1.0, 0.95), (1.5, 0.6)]
        for k, (t, v) in enumerate(pattern):
            dsp.place(out, instruments.play(name, 60, 0.25, v, seed=k), dsp.n_of(t))
        return out
    lo, hi = inst.lo, inst.hi
    root = int(np.clip(inst.ref or (lo + hi) // 2 - 5, lo, hi - 12))
    scale = [0, 2, 4, 5, 7, 9, 11, 12] if inst.family != "chinese" else [0, 2, 4, 7, 9, 12, 14, 16]
    notes = [(root + s, 0.28) for s in scale[:6]] + [(root + scale[7], 0.9)]
    out = np.zeros((2, dsp.n_of(5.0)))
    t = 0.0
    for k, (m, d) in enumerate(notes):
        dsp.place(out, instruments.play(name, m, d * 0.95, 0.75, seed=k), dsp.n_of(t))
        t += d
    if inst.kind != "drum":
        chord = [root, root + 4, root + 7] if inst.family not in ("woodwinds", "brass") or name == "brass_section" else []
        for k, m in enumerate(chord):
            dsp.place(out, instruments.play(name, m, 1.2, 0.6, seed=10 + k), dsp.n_of(t + 0.15))
    return out


def instruments_demo(out):
    from codecinema.audio import instruments
    from codecinema.audio.theory import pitch_name
    items = []
    for e in instruments.catalog():
        x = _phrase(e["name"])
        _write(out / f"{e['name']}.wav", x)
        span = f" {pitch_name(e['range'][0])}-{pitch_name(e['range'][1])}" if e["range"] else ""
        items.append((f"{e['name']}{span} ({e['source'][:5]})", x))
    _sheet(items, out / "instruments.png", "instruments")
    return len(items)


def styles_demo(out):
    from codecinema.audio import composer
    items = []
    for name in [row["name"] for row in composer.catalog() if not row["alias_of"]]:
        music = {"cues": [{"start": 0.0, "end": 20.0, "style": name, "intensity": 0.7, "seed": 3}]}
        stems = composer.render_score(music, 21.0, seed=3)
        x = sum(stems.values())
        _write(out / f"{name}.wav", x)
        items.append((name, x))
    _sheet(items, out / "styles.png", "styles (20 s each)", fmax=9000, cols=3)
    return len(items)


def sfx_demo(out):
    from codecinema.audio import sfx
    items = []
    for name in sfx.names():
        x = sfx.render(name, seed=1)
        _write(out / f"{name}.wav", x)
        items.append((name, x))
    _sheet(items, out / "sfx.png", "sound effects", fmax=16000, cols=6)
    return len(items)


def ambience_demo(out):
    from codecinema.audio import ambience
    items = []
    for name in ambience.names():
        x = ambience.bed(name, 15.0, seed=1)
        _write(out / f"{name}.wav", x)
        items.append((name, x))
    _sheet(items, out / "ambience.png", "ambience beds (15 s each)", fmax=12000, cols=3)
    return len(items)


def voices_demo(out):
    from codecinema.audio import babble
    items = []
    for prof in babble.PROFILES:
        for lang, line in LINES.items():
            x = babble.render(line, prof, "happy" if lang == "en" else "tender", seed=2)
            _write(out / f"{prof}_{lang}.wav", x)
            items.append((f"{prof} {lang}", x))
    for kind in babble.VOCALIZATIONS:
        prof = {"squawk": "seagull", "chirp": "small_bird", "yip": "fox", "growl_soft": "creature_big",
                "rumble_happy": "creature_big", "snore": "grandpa", "cough": "man", "sneeze": "woman", "whistle": "boy",
                "hum": "woman", "gulp": "boy"}.get(kind, "robot" if kind.startswith("beep") else "girl")
        x = babble.vocalize(kind, prof, seed=1)
        _write(out / f"vocal_{kind}_{prof}.wav", x)
        items.append((f"{kind} ({prof})", x))
    _sheet(items, out / "voices.png", "voices and vocalizations", fmax=8000, cols=6)
    return len(items)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("--only", choices=CATEGORIES)
    ap.add_argument("--soundbank", help="auto | off | path to an .sf2 (default: the audio.soundbank setting)")
    a = ap.parse_args(argv)
    from codecinema.audio import soundfont
    if a.soundbank:
        soundfont.use(a.soundbank)
    root = Path(a.out_dir)
    jobs = {"instruments": instruments_demo, "styles": styles_demo, "sfx": sfx_demo, "ambience": ambience_demo,
            "voices": voices_demo}
    for cat in ([a.only] if a.only else CATEGORIES):
        out = root / cat
        out.mkdir(parents=True, exist_ok=True)
        t = time.monotonic()
        count = jobs[cat](out)
        print(f"{cat}: {count} files in {out} ({time.monotonic() - t:.1f}s)", flush=True)
    bank = soundfont.default()
    print(f"Instruments: {'sampled from ' + bank.path.name if bank else 'synthesized'}"
          + (f" ({soundfont.BANK_CREDIT})" if bank and bank.path.name == Path(soundfont.BANK_NAME).name else ""),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
