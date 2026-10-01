#!/usr/bin/env python3
"""
src/post/selftest.py — synthetic test media + verification for the post pipeline.

  python src/post/selftest.py media            # (re)build out/post_test/frames (640x272, every 4th frame) + test WAV
  python src/post/selftest.py run              # everything below -> out/post_test/results.json
  python src/post/selftest.py edge             # edge / refusal cases only
  python src/post/selftest.py legibility       # title contrast over plates + worst-case solid skies
  python src/post/selftest.py contact          # review sheets (contact sheet + one filmstrip per card)
  python src/post/selftest.py verify FILE.mp4  # ffprobe + A/V sync of any output

The synthetic plates mimic the four lighting states (dusk_gold / crimson_fire / storm_night / moon_clear);
like real renders (src/blender/render_frames.py) the fixtures contain no frames inside config.RENDER_SKIP and
do not fade themselves (post owns the S29 fade). Each test frame carries its frame number and, every 24th frame,
a white sync flash in the top-left corner; the test WAV carries a 1 kHz sync beep at exactly the same instants over
a bed mastered to -14 LUFS whose beeps peak near -0.7 dBTP, so the final's AAC true-peak conditioning engages.
The fixtures are stamped with a hash of config.SHOTS/ACTS/RENDER_SKIP and regenerate when the director edits them.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (os.path.join(ROOT, "src", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import procutil  # noqa: E402

TEST_DIR = os.path.join(config.OUT, "post_test")
FRAMES = os.path.join(TEST_DIR, "frames")
WAV = os.path.join(TEST_DIR, "test_audio.wav")
QC_DIR = os.path.join(TEST_DIR, "qc")
FFMPEG, FFPROBE = config.FFMPEG, config.FFPROBE      # the same binaries as assemble.py
SR = config.AUDIO_SR
SYNC_EVERY = config.FPS  # frames between sync flashes/beeps (1 s)
PIC_H, PIC_Y0 = config.letterbox()                    # scope picture inside the delivery frame (816, 132)
FILM_FRAMES = config.FRAME_END - config.FRAME_START + 1
FLASH_BOX = (0.0, 0.0, 0.06, 0.09)   # fractional x0,y0,x1,y1 of the sync flash in the picture
MEDIA_VERSION = 3


def in_skip(f):
    return any(a <= f <= b for a, b in config.RENDER_SKIP)


# ============================================================================ synthetic plates
def env_for(frame):
    if frame <= config.SHOTS[0]["end"]:          # S01: designed black
        return "black"
    for a in config.ACTS:
        if a["start"] <= frame <= a["end"]:
            return a["env"]
    return "moon_clear"


def shot_for(frame):
    for s in config.SHOTS:
        if s["start"] <= frame <= s["end"]:
            return s
    return config.SHOTS[-1]


def _grad(y, stops):
    ys = np.array([s[0] for s in stops], np.float32)
    cols = np.array([s[1] for s in stops], np.float32) / 255.0
    return np.stack([np.interp(y, ys, cols[:, c]) for c in range(3)], -1)


_noise_cache = {}


def _grass_tex(w, h, seed=3):
    key = (w, h, seed)
    if key not in _noise_cache:
        rng = np.random.default_rng(seed)
        g = rng.standard_normal((h // 2 + 2, w // 8 + 2)).astype(np.float32)
        a = np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC), np.float32)
        b = rng.standard_normal((h, w)).astype(np.float32)
        _noise_cache[key] = 0.6 * a / (a.std() + 1e-6) + 0.4 * b
    return _noise_cache[key]


def plate(frame, w=1920, h=816):
    """Synthetic background (float RGB 0..1, h x w) for a film frame."""
    env = env_for(frame)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    xx = np.ones((h, 1), np.float32) * np.linspace(0, 1, w, dtype=np.float32)[None, :]
    sh = shot_for(frame)
    k = int(sh["id"][1:3])
    horizon = 0.58 + 0.08 * math.sin(k * 1.7)
    if env == "black":
        return np.zeros((h, w, 3), np.float32)
    if env == "dusk_gold":
        sky = _grad(yy / horizon, [(0.0, (62, 50, 92)), (0.35, (178, 96, 78)), (0.7, (242, 162, 84)),
                                   (0.93, (255, 214, 140)), (1.0, (255, 236, 186))])
        r = np.sqrt(((xx - 0.52) * w / h) ** 2 + (yy - horizon + 0.035) ** 2)
        disk = np.clip((0.05 - r) / 0.004, 0, 1)
        halo = np.exp(-r / 0.06) * 0.55
        sun = np.clip(disk + halo, 0, 1)[..., None] * np.array([1.0, 0.93, 0.78])
        sky = 1.0 - (1.0 - sky) * (1.0 - sun)                     # screen
        ground = _grad((yy - horizon) / (1 - horizon), [(0.0, (196, 140, 74)), (0.25, (126, 86, 44)),
                                                         (1.0, (30, 20, 12))])
    elif env == "crimson_fire":
        sky = _grad(yy / horizon, [(0.0, (40, 10, 14)), (0.5, (120, 24, 18)), (0.85, (210, 70, 26)),
                                   (1.0, (255, 150, 60))])
        ground = _grad((yy - horizon) / (1 - horizon), [(0.0, (255, 120, 40)), (0.12, (170, 50, 16)),
                                                         (1.0, (24, 8, 6))])
    elif env == "storm_night":
        sky = _grad(yy / horizon, [(0.0, (22, 26, 36)), (0.6, (52, 60, 78)), (1.0, (84, 92, 108))])
        ground = _grad((yy - horizon) / (1 - horizon), [(0.0, (60, 66, 72)), (1.0, (10, 12, 16))])
    else:  # moon_clear
        sky = _grad(yy / horizon, [(0.0, (8, 14, 34)), (0.7, (30, 44, 80)), (1.0, (64, 80, 116))])
        moon = np.exp(-(((xx - 0.7) * w / h) ** 2 + (yy - 0.22) ** 2) / 0.0012)
        sky = np.clip(sky + moon[..., None] * np.array([0.85, 0.88, 0.9]), 0, 1)
        ground = _grad((yy - horizon) / (1 - horizon), [(0.0, (130, 146, 170)), (0.3, (70, 84, 104)),
                                                         (1.0, (10, 14, 22))])
    img = np.where((yy < horizon)[..., None], sky, ground)
    gt = _grass_tex(w, h)
    img = np.clip(img * (1.0 + 0.10 * gt[..., None] * (yy > horizon)[..., None]), 0, 1)
    if env == "storm_night":        # rain streaks
        rng = np.random.default_rng(frame)
        r = rng.random((h // 6 + 1, w // 3 + 1)).astype(np.float32)
        r = np.asarray(Image.fromarray(r).resize((w, h), Image.NEAREST), np.float32)
        img = np.clip(img + (r > 0.985)[..., None] * 0.25, 0, 1)
    # two small figure silhouettes standing on the horizon (backlit)
    asp = w / h
    for fx, fh in ((0.40, 0.13), (0.63, 0.145)):
        foot = horizon + 0.03
        body = (((xx - fx) * asp / 0.022) ** 2 + ((yy - (foot - fh * 0.45)) / (fh * 0.42)) ** 2) < 1.0
        head = (((xx - fx) * asp / 0.011) ** 2 + ((yy - (foot - fh * 0.93)) / (fh * 0.075)) ** 2) < 1.0
        sil = body | head
        img[sil] = img[sil] * 0.12
    return img                      # (no S29 fade: post owns it, like with real renders)


def _label_font(size):
    try:
        return ImageFont.truetype(config.FONT_SONG, size, index=6)     # Songti SC Regular in the macOS Songti.ttc
    except OSError:                                                     # another song font file: its first face
        try:
            return ImageFont.truetype(config.FONT_SONG, size)
        except OSError:
            return ImageFont.load_default(size)


def test_frame(frame, w=640, h=272):
    """Low-res test render: plate + big frame number + sync flash every SYNC_EVERY frames."""
    img = (plate(frame, w, h) * 255).astype(np.uint8)
    im = Image.fromarray(img, "RGB")
    d = ImageDraw.Draw(im)
    f = _label_font(max(12, h // 10))
    sh = shot_for(frame)
    txt = f"{frame:04d}  {sh['id']}"
    d.text((w * 0.03 + 1, h * 0.84 + 1), txt, font=f, fill=(0, 0, 0))
    d.text((w * 0.03, h * 0.84), txt, font=f, fill=(255, 255, 255))
    if (frame - config.FRAME_START) % SYNC_EVERY == 0:
        x0, y0, x1, y1 = FLASH_BOX
        d.rectangle([int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)], fill=(255, 255, 255))
    return im


def media_stamp():
    key = json.dumps([MEDIA_VERSION, config.SHOTS, config.ACTS, config.RENDER_SKIP, config.FRAME_START,
                      config.FRAME_END, config.FPS, SYNC_EVERY], sort_keys=True, ensure_ascii=False)
    with open(os.path.abspath(__file__), "rb") as fh:
        src = fh.read()
    # only the plate / frame generator code matters, not the whole file
    # the plate / frame / audio generator code matters (not the rest of this file)
    a, b = src.find(b"synthetic plates\n"), src.find(b"def ensure_media")
    return hashlib.sha1(key.encode() + src[max(0, a):b]).hexdigest()[:16]


def make_test_frames(out_dir=None, step=4, w=640, h=272, start=config.FRAME_START, end=config.FRAME_END):
    out_dir = out_dir or FRAMES
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    n = 0
    for f in range(start, end + 1, step):
        if in_skip(f):                 # real renders skip the designed black too
            continue
        test_frame(f, w, h).save(os.path.join(out_dir, f"{f:05d}.png"), compress_level=1)
        n += 1
    return out_dir, n


def write_wav(path, x, sr=SR):
    q = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(x.shape[1] if x.ndim == 2 else 1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(q.tobytes())
    return path


def make_test_audio(path=None, seconds=None, target_lufs=-14.0):
    """Bed (low tones + low-passed noise, so the 1 kHz band stays clean) mastered to -14 LUFS, plus 1 kHz 20 ms
    sync beeps at every SYNC_EVERY-th frame boundary peaking near -0.7 dBTP; 48 kHz stereo 16-bit."""
    from scipy.signal import butter, sosfilt
    import assemble as A
    path = path or WAV
    seconds = seconds or (config.FRAME_END - config.FRAME_START + 1) / config.FPS
    n = int(round(seconds * SR))
    t = np.arange(n) / SR
    rng = np.random.default_rng(7)
    noise = sosfilt(butter(4, 300, "low", fs=SR, output="sos"), rng.standard_normal(n))
    bed = 0.30 * np.sin(2 * np.pi * 73.4 * t) + 0.22 * np.sin(2 * np.pi * 110.0 * t) + 0.9 * noise / noise.std() * 0.1
    x = np.stack([bed, bed * 0.92], -1)
    tmp = path + ".bed.wav"
    write_wav(tmp, x / (np.abs(x).max() * 1.05))
    li, _ = A.r128(tmp)
    os.remove(tmp)
    bed = x / (np.abs(x).max() * 1.05) * 10 ** ((target_lufs - li) / 20.0)
    beep_len = int(0.020 * SR)
    tb = np.arange(beep_len) / SR
    # hard onset (sample-accurate reference edge), short linear release to avoid a click at the end
    beep = 0.92 * np.sin(2 * np.pi * 1000.0 * tb) * np.minimum(1.0, np.linspace(1, 0, beep_len) * 4)
    duck = np.ones(n)
    beeps = np.zeros((n, 2))
    for f in range(config.FRAME_START, config.FRAME_END + 1, SYNC_EVERY):
        s0 = (f - config.FRAME_START) * SR // config.FPS
        e = min(n, s0 + beep_len)
        duck[s0:e] = 0.05
        beeps[s0:e, :] = beep[:e - s0, None]
    # the beeps add loudness: trim the bed (secant steps on its gain in dB) until the whole mix is on target
    g, gp, lp = 0.0, None, None
    for _ in range(5):
        x = np.clip(bed * 10 ** (g / 20.0) * duck[:, None] + beeps, -1, 1)
        write_wav(tmp, x)
        li, _ = A.r128(tmp)
        if abs(li - target_lufs) <= 0.05:
            break
        slope = 1.0 if gp is None or li == lp else (li - lp) / (g - gp)
        gp, lp = g, li
        g = g + (target_lufs - li) / max(slope, 0.2)
    os.replace(tmp, path)
    return path


def ensure_media(force=False):
    """(Re)build the fixtures when missing or stale (config SHOTS/ACTS/RENDER_SKIP or the generator changed)."""
    stamp_p = os.path.join(TEST_DIR, "media_stamp.json")
    want = media_stamp()
    have = None
    try:
        with open(stamp_p) as fh:
            have = json.load(fh).get("stamp")
    except (OSError, ValueError):
        pass
    if force or have != want or not os.path.isdir(FRAMES) or not os.path.exists(WAV):
        t0 = time.time()
        d, n = make_test_frames()
        make_test_audio()
        with open(stamp_p, "w") as fh:
            json.dump(dict(stamp=want, frames=n, made=time.strftime("%Y-%m-%d %H:%M:%S")), fh)
        print(f"[selftest] fixtures rebuilt ({n} frames + WAV) in {time.time() - t0:.1f}s (stamp {want})")
        return True
    return False


def make_qc_fixtures():
    """A stand-in 'real events' file + a mix report describing the test WAV, so a full --final can exercise the
    provenance gate exactly like the real run (report.output == WAV, events_source == events, WAV newer)."""
    os.makedirs(QC_DIR, exist_ok=True)
    ev = os.path.join(QC_DIR, "events.json")
    with open(ev, "w") as fh:
        json.dump(dict(fps=config.FPS, frame_start=config.FRAME_START, frame_end=config.FRAME_END, draft=False,
                       events=[dict(frame=v, type="music_cue", cue=k) for k, v in config.MUSIC_CUES.items()]), fh)
    now = time.time()
    os.utime(ev, (now - 10, now - 10))
    os.utime(WAV, (now, now))
    rep = os.path.join(QC_DIR, "mix_report.json")
    n = wave.open(WAV).getnframes()
    with open(rep, "w") as fh:
        json.dump(dict(output=os.path.abspath(WAV), events_source=os.path.abspath(ev), events_draft=False,
                       length_samples=n, length_s=n / SR, expected_length_s=(config.FRAME_END - config.FRAME_START + 1)
                       / config.FPS), fh)
    return ev, rep


# ============================================================================ title review sheets
def composite_title(tid, local_frame, bg=None):
    """Composite title frame (1-based local) over the synthetic plate of its absolute frame at 1920x1080."""
    import titles
    spec = titles.effective_spec(tid)
    fr_abs = spec["start"] + local_frame - 1
    if bg is None:
        pic = plate(fr_abs, config.DELIVERY_X, titles.PIC_H)
        bg = np.zeros((config.DELIVERY_Y, config.DELIVERY_X, 3), np.float32)
        bg[titles.PIC_Y0:titles.PIC_Y1] = pic
    p = os.path.join(titles.title_dir(tid), f"{local_frame:05d}.png")
    if os.path.exists(p) and titles.is_current(spec):
        fr = np.asarray(Image.open(p), np.float32) / 255.0
    else:
        fr = titles.build(spec).frame(local_frame - 1).astype(np.float32) / 255.0
    a = fr[..., 3:4]
    out = fr[..., :3] * a + bg * (1 - a)
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def filmstrip(tid, frames, out=None, cols=4, scale=0.5):
    """Grid of title frames (1-based local) composited over plates, cropped to the title's canvas."""
    import titles
    spec = titles.effective_spec(tid)
    t = titles.build(spec)
    x0, y0, w, h = t.cv
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(config.DELIVERY_X, x0 + w), min(config.DELIVERY_Y, y0 + h)
    tiles = []
    for k in frames:
        fr_abs = spec["start"] + k - 1
        bg = np.zeros((config.DELIVERY_Y, config.DELIVERY_X, 3), np.float32)
        bg[titles.PIC_Y0:titles.PIC_Y1] = plate(fr_abs, config.DELIVERY_X, titles.PIC_H)
        fr = t.frame(k - 1).astype(np.float32) / 255.0
        a = fr[..., 3:4]
        img = (np.clip(fr[..., :3] * a + bg * (1 - a), 0, 1) * 255 + 0.5).astype(np.uint8)[y0:y1, x0:x1]
        im = Image.fromarray(img)
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
        ImageDraw.Draw(im).text((6, 4), f"{tid} #{k} (f{fr_abs})", font=_label_font(16), fill=(0, 255, 120))
        tiles.append(im)
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet_im = Image.new("RGB", (cols * tw + (cols - 1) * 4, rows * th + (rows - 1) * 4), (40, 40, 40))
    for i, im in enumerate(tiles):
        sheet_im.paste(im, ((i % cols) * (tw + 4), (i // cols) * (th + 4)))
    out = out or os.path.join(TEST_DIR, "sheets", f"strip_{tid}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet_im.save(out)
    print(out)
    return out


def contact_sheet(out=None):
    """All titles at their mid-legible frame over matching synthetic plates, cropped to each card (review aid)."""
    import titles as T
    tiles = []
    for t in config.TITLES:
        tt = T.build(T.effective_spec(t))
        x0, y0, w, h = tt.cv
        a, b = tt._local_moments()
        k = int((a + b) / 2) + 1
        im = Image.fromarray(composite_title(t["id"], k))
        cx, cy = x0 + w / 2, y0 + h / 2
        W2, H2 = max(900, min(1900, w)), max(360, min(1060, h))
        bx = int(max(0, min(config.DELIVERY_X - W2, cx - W2 / 2)))
        by = int(max(0, min(config.DELIVERY_Y - H2, cy - H2 / 2)))
        crop = im.crop((bx, by, bx + int(W2), by + int(H2)))
        crop.thumbnail((960, 400))
        ImageDraw.Draw(crop).text((6, 4), f"{t['id']} #{k}", font=_label_font(15), fill=(0, 255, 120))
        tiles.append(crop)
    tw, th = max(x.width for x in tiles), max(x.height for x in tiles)
    rows = (len(tiles) + 1) // 2
    sheet_im = Image.new("RGB", (2 * tw + 6, rows * th + 6 * (rows - 1)), (30, 30, 30))
    for i, x in enumerate(tiles):
        sheet_im.paste(x, ((i % 2) * (tw + 6), (i // 2) * (th + 6)))
    out = out or os.path.join(TEST_DIR, "sheets", "contact.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet_im.save(out)
    print(out)
    return out


# ============================================================================ legibility
WORST_SKIES = {"cream": (255, 236, 186), "orange": (242, 162, 84), "crimson": (120, 24, 18),
               "storm": (84, 92, 108), "black": (0, 0, 0)}


def _lum8(rgb8):
    import flash_qc
    lut = flash_qc.srgb_lut()
    lin = lut[rgb8]
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def glyph_contrasts(fr, bg8):
    """Per text blob: WCAG contrast of the text interior against a 2-7 px ring around it after compositing the
    title frame over bg8. Text = opaque, light pixels of the title (ivory / subtitle colours)."""
    from scipy import ndimage
    f = fr.astype(np.float32) / 255.0
    a = f[..., 3:4]
    out = (np.clip(f[..., :3] * a + bg8.astype(np.float32) / 255.0 * (1 - a), 0, 1) * 255 + 0.5).astype(np.uint8)
    col = (f[..., :3] * 255 + 0.5).astype(np.uint8)
    text = (f[..., 3] > 0.9) & (_lum8(col) > 0.45)
    if not text.any():
        return []
    grp, n = ndimage.label(ndimage.binary_dilation(text, iterations=6))
    Lo = _lum8(out)
    res = []
    for k in range(1, n + 1):
        g = (grp == k) & text
        if g.sum() < 30:
            continue
        ring = ndimage.binary_dilation(g, iterations=7) & ~ndimage.binary_dilation(g, iterations=2) & ~text
        lt, lr = float(Lo[g].mean()), float(Lo[ring].mean())
        ys, xs = np.nonzero(g)
        res.append(dict(contrast=round((max(lt, lr) + 0.05) / (min(lt, lr) + 0.05), 2), px=int(g.sum()),
                        box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]))
    return res


def legibility_report():
    """Contrast of every card at its mid-legible frame over its own synthetic plate and over worst-case solid skies."""
    import titles as T
    rows = {}
    for t in config.TITLES:
        spec = T.effective_spec(t)
        tt = T.build(spec)
        a, b = tt._local_moments()
        k = int((a + b) / 2)
        fr = tt.frame(k)
        r = {}
        bgs = dict(WORST_SKIES)
        for name, c in list(bgs.items()) + [("plate", None)]:
            bg = np.zeros((config.DELIVERY_Y, config.DELIVERY_X, 3), np.uint8)
            if c is None:
                bg[T.PIC_Y0:T.PIC_Y1] = (plate(spec["start"] + k, config.DELIVERY_X, T.PIC_H) * 255 + 0.5).astype(np.uint8)
            else:
                bg[T.PIC_Y0:T.PIC_Y1] = c
            g = glyph_contrasts(fr, bg)
            if not g:
                continue
            big = [x["contrast"] for x in g if x["px"] >= 1500]
            small = [x["contrast"] for x in g if x["px"] < 1500]
            r[name] = dict(large_min=min(big) if big else None, small_min=min(small) if small else None,
                           small_median=float(np.median(small)) if small else None)
        rows[t["id"]] = dict(frame=spec["start"] + k, **r)
        print(f"[legibility] {t['id']:13s} " + "  ".join(
            f"{n}: L{v['large_min']} s{v['small_min']}" for n, v in r.items()))
    return rows


# ============================================================================ verification helpers
def ffprobe_json(path):
    cmd = [FFPROBE, "-v", "error", "-count_frames", "-show_entries",
           "stream=index,codec_type,codec_name,profile,level,width,height,pix_fmt,r_frame_rate,avg_frame_rate,"
           "nb_read_frames,duration,sample_rate,channels,bit_rate,color_space,color_transfer,color_primaries,"
           "color_range:format=duration,bit_rate,size", "-of", "json", path]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def decode_video_gray(path, w=160, h=90):
    """Decode every frame downscaled to w x h gray (for flash detection)."""
    cmd = [FFMPEG, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w)


def decode_audio(path):
    cmd = [FFMPEG, "-v", "error", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def beep_onsets(a, freq=1000.0, sr=SR):
    """Sample-accurate onsets (s) of the 1 kHz sync beeps: zero-phase band-pass, Hilbert envelope,
    first sample of each burst whose envelope crosses 50 % of that burst's peak."""
    from scipy.signal import butter, hilbert, sosfiltfilt
    sos = butter(4, [freq * 0.8, freq * 1.25], btype="bandpass", fs=sr, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, a.astype(np.float64))))
    thr = 0.25 * env.max()
    above = env > thr
    starts = np.flatnonzero(above & ~np.concatenate([[False], above[:-1]]))
    out = []
    for s0 in starts:
        seg = env[s0:s0 + int(0.03 * sr)]
        pk = seg.max()
        j = s0
        while j > 0 and env[j - 1] > 0.5 * pk:
            j -= 1
        while env[j] < 0.5 * pk:
            j += 1
        out.append(j / sr)
    merged = []
    end_guard = len(a) / sr - 0.02            # filtfilt edge transient at the very end of the file
    for t in out:
        if t < end_guard and (not merged or t - merged[-1] > 0.2):
            merged.append(t)
    return merged


def sync_check(path, start=config.FRAME_START, out_h=1080):
    """Detect sync flashes (video) and 1 kHz beeps (audio); report per-event offsets in ms."""
    g = decode_video_gray(path)
    fh, fw = g.shape[1:]
    pic_y0 = PIC_Y0 / float(config.DELIVERY_Y)
    pic_h = PIC_H / float(config.DELIVERY_Y)
    x0, y0, x1, y1 = FLASH_BOX
    ys = int((pic_y0 + (y0 + 0.2 * (y1 - y0)) * pic_h) * fh)
    ye = max(ys + 1, int((pic_y0 + (y0 + 0.8 * (y1 - y0)) * pic_h) * fh))
    xs, xe = int(0.2 * x1 * fw), max(1, int(0.8 * x1 * fw))
    lum = g[:, ys:ye, xs:xe].mean(axis=(1, 2))
    on = lum > 200
    v_onsets = [i for i in range(len(on)) if on[i] and (i == 0 or not on[i - 1])]
    a = decode_audio(path)
    a_onsets = beep_onsets(a)
    v_t = [i / config.FPS for i in v_onsets]
    pairs = []
    for vt in v_t:
        if a_onsets:
            at = min(a_onsets, key=lambda x: abs(x - vt))
            pairs.append((vt, at, (at - vt) * 1000.0))
    # which beeps SHOULD have a visible flash: sync frames that are rendered (not RENDER_SKIP) and not faded
    import assemble as A
    exp_v = [f for f in range(start, start + len(g)) if (f - config.FRAME_START) % SYNC_EVERY == 0
             and not in_skip(f) and A.fade_factor(f) > 0.9]
    return dict(video_onsets=v_onsets, n_video=len(v_onsets), n_audio=len(a_onsets), n_video_expected=len(exp_v),
                offsets_ms=[round(p[2], 3) for p in pairs],
                max_abs_ms=max((abs(p[2]) for p in pairs), default=None))


def decode_rgb_frames(path, indices, w=config.DELIVERY_X, h=config.DELIVERY_Y):
    """Decode 0-based output frames to RGB float (explicit BT.709 limited-range matrix)."""
    expr = "+".join(f"eq(n\\,{i})" for i in indices)
    cmd = [FFMPEG, "-v", "error", "-i", path, "-vf",
           f"select='{expr}',scale={w}:{h}:flags=bicubic+accurate_rnd+full_chroma_int:in_color_matrix=bt709:"
           f"in_range=tv,format=rgb24", "-fps_mode", "passthrough", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32) / 255.0
    return {i: arr[k] for k, i in enumerate(sorted(indices))}


def reference_picture(frame, frames_dir, start, end, mode="final", allow_holds=True, fade=True):
    """What the assembler's picture should be for an absolute film frame (RGB float 1920x1080), following its
    frame plan (RENDER_SKIP black, holds) and S29 fade; majority-size normalisation mimicked with PIL."""
    import assemble as A
    import titles as T
    found = A.scan_frames(frames_dir)
    plan, _ = A.plan_frames(found, start, end, mode, allow_holds=allow_holds)
    kind, val = plan[frame - start]
    out = np.zeros((config.DELIVERY_Y, config.DELIVERY_X, 3), np.float32)
    if kind == "src":
        used = sorted({v for k, v in plan if k == "src"})
        from collections import Counter
        size = Counter(Image.open(found[f]).size for f in used).most_common(1)[0][0]
        im = Image.open(found[val]).convert("RGB")
        if im.size != size:
            im = im.resize(size, Image.LANCZOS)
        im = im.resize((config.DELIVERY_X, T.PIC_H), Image.LANCZOS)
        pic = np.asarray(im, np.float32) / 255.0
        if fade:
            pic = np.floor(pic * 255.0 * A.fade_factor(frame) + 0.5) / 255.0 if A.fade_factor(frame) < 0.9999 else pic
        out[T.PIC_Y0:T.PIC_Y1] = pic
    return out


def over(title_png, pic):
    t = np.asarray(Image.open(title_png).convert("RGBA"), np.float32) / 255.0
    a = t[..., 3:4]
    return t[..., :3] * a + pic * (1 - a)


def psnr(a, b):
    mse = float(np.mean((a - b) ** 2))
    return 99.0 if mse <= 1e-12 else 10 * math.log10(1.0 / mse)


def moving_probes(tid, per_card=3, min_change=2e-4):
    """Local frames (1-based) where the card differs from BOTH neighbours (no static holds): in each third of the
    card, the frame that changes most. Change is measured inside the card's canvas (a whole-frame mean would drown
    a small card). Frames without any visible alpha are skipped."""
    import titles as T
    d = T.title_dir(tid)
    spec = T.spec_by_id(tid)
    n = spec["end"] - spec["start"] + 1
    x0, y0, w, h = T.build(T.effective_spec(tid)).cv
    x0, y0 = max(0, x0), max(0, y0)
    box = (x0, y0, min(config.DELIVERY_X, x0 + w), min(config.DELIVERY_Y, y0 + h))
    ch, opaque, prev = [0.0], [], None
    for k in range(1, n + 1):
        with Image.open(os.path.join(d, f"{k:05d}.png")) as im:
            a = np.asarray(im.crop(box), np.float32) / 255.0
        opaque.append(int((a[..., 3] > 0.3).sum()))
        if prev is not None:
            ch.append(float(np.abs(a - prev).mean()))
        prev = a
    score = [min(ch[k], ch[k + 1]) if (0 < k < n - 1 and opaque[k] > 50) else 0.0 for k in range(n)]
    out = []
    for p in range(per_card):
        lo, hi = p * n // per_card, (p + 1) * n // per_card
        k = max(range(lo, hi), key=lambda j: score[j])
        if score[k] >= min_change:
            out.append(k + 1)
    return out


def title_exactness(path, start, end, frames_dir, probes):
    """For each (title_id, local_k) probe: the decoded output frame vs references built from title frames k-1, k,
    k+1 inside the card's canvas — the best match must be k. Also the mean colour error inside the text and,
    separately, inside saturated-red pixels (the seals: 4:2:0 chroma error shows most there)."""
    import titles as T
    idx = [T.spec_by_id(tid)["start"] + k - 1 - start for tid, k in probes]
    dec = decode_rgb_frames(path, idx)
    rows = []
    for (tid, k), i in zip(probes, idx):
        spec = T.spec_by_id(tid)
        n = spec["end"] - spec["start"] + 1
        t = T.build(T.effective_spec(tid))
        x0, y0, w, h = t.cv
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(config.DELIVERY_X, x0 + w), min(config.DELIVERY_Y, y0 + h)
        fabs = spec["start"] + k - 1
        pic = reference_picture(fabs, frames_dir, start, end)
        got = dec[i][y0:y1, x0:x1]
        res = {}
        for kk in (k - 1, k, k + 1):
            if 1 <= kk <= n:
                ref = over(os.path.join(T.title_dir(tid), f"{kk:05d}.png"), pic)[y0:y1, x0:x1]
                res[kk] = psnr(got, ref)
        png = os.path.join(T.title_dir(tid), f"{k:05d}.png")
        ref = over(png, pic)
        ta = np.asarray(Image.open(png), np.float32) / 255.0
        text = ta[..., 3] > 0.9
        red = text & (ta[..., 0] > 0.45) & (ta[..., 1] < 0.3) & (ta[..., 2] < 0.3)
        text_only = text & ~red
        err = np.abs(dec[i] - ref) * 255.0
        others = [v for kk, v in res.items() if kk != k]
        rows.append(dict(title=tid, local=k, frame=fabs, psnr={str(kk): round(v, 2) for kk, v in res.items()},
                         exact=bool(all(res[k] > v for v in others)),
                         margin_db=round(res[k] - max(others), 2) if others else None,
                         text_err_rgb=[round(float(x), 2) for x in err[text_only].mean(axis=0)] if text_only.any() else None,
                         text_err_max_channel=round(float(err[text_only].mean(axis=0).max()), 2) if text_only.any() else None,
                         seal_red_err_rgb=[round(float(x), 2) for x in err[red].mean(axis=0)] if red.sum() > 20 else None))
    return rows


def extract_frames(path, indices, out_dir, prefix="still"):
    """Extract 0-based output frame indices as PNG (one pass with select)."""
    os.makedirs(out_dir, exist_ok=True)
    expr = "+".join(f"eq(n\\,{i})" for i in indices)
    tmp = os.path.join(out_dir, f"_{prefix}_%03d.png")
    cmd = [FFMPEG, "-v", "error", "-y", "-i", path, "-vf", f"select='{expr}'", "-fps_mode", "passthrough", tmp]
    subprocess.run(cmd, check=True)
    outs = []
    for k, i in enumerate(sorted(indices)):
        src = os.path.join(out_dir, f"_{prefix}_{k + 1:03d}.png")
        dst = os.path.join(out_dir, f"{prefix}_{i:05d}.png")
        os.replace(src, dst)
        outs.append(dst)
    return outs


def _pic_luma(path, indices, w=192, h=108):
    """Mean luma (0..255, tv-range decoded) of the picture area for given output frame indices."""
    g = decode_video_gray(path, w, h)
    y0, y1 = int(h * PIC_Y0 / config.DELIVERY_Y) + 1, int(h * (PIC_Y0 + PIC_H) / config.DELIVERY_Y) - 1
    return {i: float(g[i, y0:y1].mean()) for i in indices}, g


# ============================================================================ edge-case suite
def _mk_dir(path, frames, src_dir=None, modify=None):
    """Populate a frames dir with links to fixture frames (symlink, else hard link, else copy); `modify` =
    {frame: fn(PIL image) -> image} writes a real file instead (never through a link, so the shared fixtures are
    never touched)."""
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)
    src_dir = src_dir or FRAMES
    modify = modify or {}
    for f in frames:
        src = os.path.join(src_dir, f"{f:05d}.png")
        dst = os.path.join(path, f"{f:05d}.png")
        if f in modify:
            im = modify[f](Image.open(src) if os.path.exists(src) else Image.fromarray(
                (plate(f, 640, 272) * 255).astype(np.uint8)))
            if os.path.lexists(dst):
                os.remove(dst)
            im.save(dst)
        elif os.path.exists(src):
            procutil.link_or_copy(src, dst)
    return path


def _fixture_hash():
    h = hashlib.sha1()
    for name in sorted(os.listdir(FRAMES)):
        p = os.path.join(FRAMES, name)
        h.update(name.encode())
        h.update(str(os.path.getsize(p)).encode())
    return h.hexdigest()[:12]


def edge_suite():
    import assemble as A
    import cues as CUES
    import flash_qc as Q
    import titles as T
    E = os.path.join(TEST_DIR, "edge")
    os.makedirs(E, exist_ok=True)
    res = []
    fx_before = _fixture_hash()

    def run(name, check, expect_refusal=None, **kw):
        out = os.path.join(E, f"{name}.mp4")
        try:
            rep = A.assemble(out=out, **kw)
            if expect_refusal:
                ok, note = False, f"expected a refusal containing {expect_refusal!r}, but it encoded"
            else:
                ok, note = check(out, rep)
        except SystemExit as e:
            msg = str(e)
            if expect_refusal and expect_refusal in msg:
                ok, note = True, f"refused as expected: {msg.splitlines()[0][:150]}"
            else:
                ok, note = False, f"SystemExit {msg[:300]}"
        res.append((name, bool(ok), note))
        print(f"[edge] {name:22s} {'PASS' if ok else 'FAIL'}  {note}", flush=True)

    def check_fn(name, fn):
        try:
            ok, note = fn()
        except Exception as e:  # a test crash is a failure, with its reason
            ok, note = False, f"exception {e!r}"
        res.append((name, bool(ok), note))
        print(f"[edge] {name:22s} {'PASS' if ok else 'FAIL'}  {note}", flush=True)

    grid = lambda a, b: [f for f in range(a, b + 1, 4) if not in_skip(f)]   # noqa: E731
    std = FRAMES

    # A. unrendered head of a shot + hold cap: frames only from 161 in S02 (97-240); range 97-300, preview
    dA = _mk_dir(os.path.join(E, "fr_head"), grid(161, 229))

    def chkA(out, rep):
        L, _ = _pic_luma(out, [3, 51, 52, 63, 103, 143, 150, 190])
        # 97..148: before S02's first rendered frame and > cap (12) away -> slate (dark grey + text, not black);
        # 149..160 borrow frame 161 of the same shot; 161..229 rendered; 230..240 held (<= cap);
        # 241..300 (S03, nothing rendered; S02's frames never cross the cut) -> slate
        slate = lambda v: 5 < v < 40                                          # noqa: E731
        ok = rep["ok"] and slate(L[3]) and slate(L[51]) and L[52] > 60 and L[63] > 60 and L[103] > 60 \
            and L[143] > 60 and slate(L[150]) and slate(L[190])
        return ok, (f"luma f100={L[3]:.1f} f148={L[51]:.1f} (slate) f149={L[52]:.1f} f160={L[63]:.1f} (borrowed f161) "
                    f"f200={L[103]:.1f} f240={L[143]:.1f} (held f229) f247={L[150]:.1f} f287={L[190]:.1f} (slate) "
                    f"slates={rep['picture']['slates']}")
    run("preview_slates_cap", chkA, frames_dir=dA, start=97, end=300, mode="preview", titles=False)

    # A2. same with --missing black
    def chkA2(out, rep):
        L, _ = _pic_luma(out, [3, 64, 190])
        return rep["ok"] and L[3] < 3 and L[64] > 60 and L[190] < 3, f"luma f100={L[3]:.1f} f161={L[64]:.1f} f287={L[190]:.1f}"
    run("preview_missing_black", chkA2, frames_dir=dA, start=97, end=300, mode="preview", titles=False, missing="black")

    # B. incomplete tail inside one shot: frames 97..141 -> 142..153 held (cap 12), beyond -> slate
    dB = _mk_dir(os.path.join(E, "fr_tail"), grid(97, 141))

    def chkB(out, rep):
        d = decode_rgb_frames(out, [44, 50, 56, 90], 960, 540)
        p1, p2 = psnr(d[44], d[50]), psnr(d[44], d[56])
        L, _ = _pic_luma(out, [90])
        return rep["ok"] and p1 > 50 and p2 > 50 and L[90] < 40, (
            f"PSNR(f141,f147)={p1:.1f} PSNR(f141,f153)={p2:.1f} dB (held, encoder-noise limited) f187 luma={L[90]:.1f} (slate)")
    run("tail_holds", chkB, frames_dir=dB, start=97, end=200, mode="preview", titles=False)

    # C. mixed resolutions in a draft final (majority 640x272; 105 is 1920x816, 109 is 1280x544)
    big = lambda im: im.convert("RGB").resize((1920, 816), Image.LANCZOS)         # noqa: E731
    mid = lambda im: im.convert("RGB").resize((1280, 544), Image.LANCZOS)         # noqa: E731
    dC = _mk_dir(os.path.join(E, "fr_mixed"), grid(97, 180), modify={105: big, 109: mid})

    def chkC(out, rep):
        d = decode_rgb_frames(out, [105 - 97, 109 - 97])
        notes, ok = [], rep["ok"]
        lab = (slice(800, 940), slice(40, 800))          # the burnt-in frame number: tells neighbours apart
        for f in (105, 109):
            got = d[f - 97]
            ref = reference_picture(f, dC, 97, 180)
            ref_prev = reference_picture(f - 4, dC, 97, 180)
            p = psnr(got[PIC_Y0:PIC_Y0 + PIC_H], ref[PIC_Y0:PIC_Y0 + PIC_H])
            pl, pp = psnr(got[lab], ref[lab]), psnr(got[lab], ref_prev[lab])
            ok = ok and p > 34 and pl > pp + 3
            notes.append(f"f{f}: picture PSNR {p:.1f} dB; label PSNR {pl:.1f} vs {pp:.1f} (f{f - 4})")
        return ok, "; ".join(notes) + f" (normalised {rep['picture']['normalised']})"
    run("mixed_res_draft_final", chkC, frames_dir=dC, start=97, end=180, mode="final", titles=True,
        allow_holds=True, audio=None, allow_silent=True)

    # C2. the strict final refuses the same (off-size + missing frames)
    run("final_refuses_holds", None, expect_refusal="final refused", frames_dir=dC, start=97, end=180,
        mode="final", audio=None, allow_silent=True)

    # D. RGBA frames: transparent left quarter must come out black
    def rgba(im):
        im = im.convert("RGBA")
        a = np.full((im.height, im.width), 255, np.uint8)
        a[:, : im.width // 4] = 0
        im.putalpha(Image.fromarray(a))
        return im
    fr_d = grid(601, 700)
    dD = _mk_dir(os.path.join(E, "fr_rgba"), fr_d, modify={f: rgba for f in fr_d})

    def chkD(out, rep):
        d = decode_rgb_frames(out, [20], 960, 540)[20]
        left = d[100:400, 20:200].mean() * 255
        right = d[100:250, 500:900].mean() * 255
        return rep["ok"] and left < 3 and right > 40, f"left(transparent) mean={left:.1f} right mean={right:.1f}"
    run("rgba_input", chkD, frames_dir=dD, start=601, end=700, mode="preview", titles=False)

    # E. no frames at all -> slates / black (S01 designed black) + titles still there
    def chkE(out, rep):
        L, _ = _pic_luma(out, [3, 119])
        return rep["ok"] and L[3] < 3 and 5 < L[119] < 40, f"luma f4={L[3]:.1f} (S01 black) f120={L[119]:.1f} (slate)"
    run("no_frames", chkE, frames_dir=os.path.join(E, "does_not_exist"), start=1, end=240, mode="preview")

    # F. short 44.1 kHz mono audio in a PREVIEW -> resampled, upmixed, padded with silence to the exact length
    wav = os.path.join(E, "short_mono_44k.wav")
    t = np.arange(int(3.0 * 44100)) / 44100
    x = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(x.tobytes())

    def chkF(out, rep):
        a = decode_audio(out)
        n_exp = 120 * SR // config.FPS
        tail = float(np.sqrt(np.mean(a[int(3.1 * SR):] ** 2)))
        head = float(np.sqrt(np.mean(a[int(0.5 * SR):int(2.5 * SR)] ** 2)))
        ok = rep["ok"] and abs(len(a) - n_exp) <= 1024 and tail < 1e-3 and head > 0.05
        return ok, f"samples={len(a)} (exp {n_exp}) rms[0.5-2.5s]={head:.3f} rms[>3.1s]={tail:.5f} audio={rep['audio']}"
    run("preview_audio_short", chkF, frames_dir=std, audio=wav, start=1, end=120, mode="preview", titles=False)

    # F2. the same WAV in a final is refused (never pad more than 1 frame)
    run("final_refuses_short_audio", None, expect_refusal="refusing to pad/trim", frames_dir=std, audio=wav,
        start=97, end=216, mode="final", allow_holds=True)

    # F3. a final without audio is refused unless --allow-silent; with it, the master has no audio stream
    run("final_refuses_no_audio", None, expect_refusal="final master without audio", frames_dir=std, audio=None,
        start=97, end=144, mode="final", allow_holds=True)

    def chkF4(out, rep):
        return rep["ok"] and "audio" not in rep, f"ok={rep['ok']} streams: video only={'audio' not in rep}"
    run("final_allow_silent", chkF4, frames_dir=std, audio=None, allow_silent=True, start=97, end=144,
        mode="final", allow_holds=True, titles=False)

    # F5. --audio auto: final refuses when final_mix.wav is absent; previews fall back to the demo mix
    def auto_rules():
        tmpd = os.path.join(E, "audio_dir_demo_only")
        os.makedirs(tmpd, exist_ok=True)
        shutil.copy(wav, os.path.join(tmpd, "demo_mix.wav"))
        notes = []
        try:
            A.resolve_audio("auto", "final", audio_dir=tmpd)
            return False, "final auto did not refuse"
        except SystemExit as e:
            notes.append(f"final: refused ({str(e)[:60]}...)")
        p = A.resolve_audio("auto", "preview", audio_dir=tmpd)
        notes.append(f"preview -> {os.path.basename(p or 'None')}")
        s = A.resolve_audio("auto", "final", allow_silent=True, audio_dir=tmpd)
        notes.append(f"final+allow_silent -> {s}")
        return p.endswith("demo_mix.wav") and s is None, "; ".join(notes)
    check_fn("audio_auto_rules", auto_rules)

    # G. provenance gate of a FULL final (checked before any encoding)
    def prov_rules():
        ev, rep = make_qc_fixtures()
        good, _ = A.audio_provenance(WAV, rep, ev)
        notes = [f"good fixture problems={good}"]
        cases = {}
        with open(rep) as fh:
            base = json.load(fh)
        variants = {
            "events_source": dict(base, events_source=os.path.join(config.AUDIO_DIR, "draft_events.json")),
            "draft": dict(base, events_draft=True),
            "length": dict(base, length_s=base["length_s"] - 0.01),
            "other_output": dict(base, output=os.path.join(config.AUDIO_DIR, "demo_mix.wav")),
        }
        for k, v in variants.items():
            p = os.path.join(QC_DIR, f"mix_report_{k}.json")
            with open(p, "w") as fh:
                json.dump(v, fh)
            probs, _ = A.audio_provenance(WAV, p, ev)
            cases[k] = len(probs) > 0
        now = time.time()                           # stale: events newer than the WAV
        os.utime(ev, (now + 5, now + 5))
        probs, _ = A.audio_provenance(WAV, rep, ev)
        cases["stale"] = any("older" in x for x in probs)
        make_qc_fixtures()
        cases["missing_report"] = len(A.audio_provenance(WAV, os.path.join(QC_DIR, "nope.json"), ev)[0]) > 0
        # end to end: a full final with a bad report is refused before encoding
        try:
            A.assemble(frames_dir=std, audio=WAV, mode="final", allow_holds=True, dry_run=True,
                       mix_report=os.path.join(QC_DIR, "mix_report_events_source.json"), events_json=ev,
                       out=os.path.join(E, "never.mp4"))
            cases["full_final_refused"] = False
        except SystemExit as e:
            cases["full_final_refused"] = "not the real mix" in str(e)
        notes.append(str(cases))
        return (not good) and all(cases.values()), "; ".join(notes)
    check_fn("audio_provenance", prov_rules)

    # H. --no-titles: main title mid-frame must equal the plain picture
    def chkH(out, rep):
        d = decode_rgb_frames(out, [180 - 97])[180 - 97]
        ref = reference_picture(180, std, 97, 240)
        p = psnr(d, ref)
        return rep["ok"] and p > 38, f"PSNR(out, plain picture)={p:.1f} dB"
    run("no_titles", chkH, frames_dir=std, start=97, end=240, mode="final", titles=False, allow_holds=True,
        audio=None, allow_silent=True)

    # I. grain: visible in mid-tones, blacks untouched (vs the no-grain run on the same range)
    def chkI(out, rep):
        g1 = decode_video_gray(out, 960, 540).astype(np.float32)
        g0 = decode_video_gray(os.path.join(E, "no_titles.mp4"), 960, 540).astype(np.float32)
        diff = g1 - g0
        mid = (g0 > 90) & (g0 < 170)
        blk = g0 < 18
        s_mid = float(diff[mid].std())
        s_blk = float(diff[blk].std()) if blk.any() else 0.0
        return rep["ok"] and s_mid > 0.8 and s_blk < s_mid * 0.5, f"grain std mid-tones={s_mid:.2f} blacks={s_blk:.2f}"
    run("grain", chkI, frames_dir=std, start=97, end=240, mode="final", titles=False, grain=6, allow_holds=True,
        audio=None, allow_silent=True)

    # J. RENDER_SKIP frames are black even if a stray render exists there; the S29 fade runs 3770 -> 3811
    fr_j = list(range(3761, 3841))
    dJ = _mk_dir(os.path.join(E, "fr_skip"), fr_j, modify={f: (lambda im, f=f: test_frame(f)) for f in fr_j})

    def chkJ(out, rep):
        L, _ = _pic_luma(out, [0, 9, 20, 30, 40, 49, 50, 60, 79])
        f = lambda i: 3761 + i                                               # noqa: E731
        fade_ok = L[0] > 20 and L[9] > 20 and L[9] > L[20] > L[30] > L[40] >= L[49] and L[49] < 3
        black_ok = all(L[i] < 1.5 for i in (50, 60, 79))
        return rep["ok"] and fade_ok and black_ok, (
            "luma " + " ".join(f"f{f(i)}={L[i]:.1f}" for i in (0, 9, 20, 30, 40, 49, 50, 60, 79))
            + f" | {rep['picture']['fade']} | skip-black {rep['picture']['skip_black']}")
    run("skip_black_and_fade", chkJ, frames_dir=dJ, start=3761, end=3840, mode="preview", titles=False)

    # J2. renders that already fade -> post does not fade again
    fr_j2 = list(range(3741, 3811))

    def selffade(im, f):
        a = np.asarray(test_frame(f), np.float32) * A.fade_factor(f)
        return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    dJ2 = _mk_dir(os.path.join(E, "fr_selffade"), fr_j2, modify={f: (lambda im, f=f: selffade(im, f)) for f in fr_j2})

    def chkJ2(out, rep):
        L, _ = _pic_luma(out, [3790 - 3741])
        exp = float(np.asarray(Image.open(os.path.join(dJ2, "03790.png")).convert("L")).mean())
        return rep["ok"] and "skipped" in rep["picture"]["fade"] and abs(L[49] - exp) < 4, (
            f"{rep['picture']['fade']} | f3790 luma out {L[49]:.1f} vs source {exp:.1f} (no double fade)")
    run("fade_auto_skip", chkJ2, frames_dir=dJ2, start=3741, end=3840, mode="preview", titles=False)

    # K. the 'End' card stays crisp over the post fade (title applied after the picture fade)
    def chkK(out, rep):
        tid, spec = "end", T.spec_by_id("end")
        rows = title_exactness(out, 3741, 3840, std, [(tid, 20), (tid, 72)])
        L, _ = _pic_luma(out, [3805 - 3741])
        ok = rep["ok"] and all(r["exact"] and r["psnr"][str(r["local"])] > 38 for r in rows)
        return ok, "; ".join(f"#{r['local']} PSNR {r['psnr'][str(r['local'])]} margin {r['margin_db']} dB" for r in rows)
    run("end_card_over_fade", chkK, frames_dir=std, start=3741, end=3840, mode="final", allow_holds=True,
        audio=None, allow_silent=True)

    # L. mid-film odd-offset range final with audio: sync must hold after the sample-exact slice + conditioning
    def chkL(out, rep):
        r = sync_check(out, start=2003)
        m = r["max_abs_ms"]
        ae = rep.get("audio_encode") or {}
        return rep["ok"] and m is not None and m < 2.0 and r["n_video"] == r["n_audio"], \
            f"flashes={r['n_video']} beeps={r['n_audio']} max|offset|={m:.3f} ms limiter={ae.get('limiter_ceiling')} " \
            f"AAC TP={ae.get('tp')}"
    make_qc_fixtures()
    run("range_sync_odd", chkL, frames_dir=std, audio=WAV, start=2003, end=2150, mode="final", titles=True,
        allow_holds=True)

    # M. black frames mid-film are caught by the final QC (blackdetect)
    fr_m = grid(1001, 1100)
    blk = lambda im: Image.new("RGB", im.size, (0, 0, 0))                        # noqa: E731
    dM = _mk_dir(os.path.join(E, "fr_black_mid"), fr_m, modify={f: blk for f in fr_m if 1033 <= f <= 1060})

    def chkM(out, rep):
        q = rep.get("qc") or {}
        outside = (q.get("black") or {}).get("outside")
        return (not rep["ok"]) and bool(outside), f"ok={rep['ok']} black outside allowed windows: {outside}"
    run("qc_catches_black", chkM, frames_dir=dM, start=1001, end=1100, mode="final", titles=False,
        allow_holds=True, audio=None, allow_silent=True)

    # N. flash QC: 4 flashes/s fails, 2/s passes, the FULL_WHITE window is exempt (synthetic video)
    def flash_rules():
        notes, ok = [], True
        for name, period, f0, expect in (("4_per_s", 6, 2001, "FAIL"), ("2_per_s", 12, 2001, "PASS"),
                                         ("full_white", None, 3240, "PASS")):
            L = np.full(72, 0.08)
            if period:
                for s in range(6, 66, period):
                    L[s:s + 2] = 0.6
            else:
                L[3265 - f0:3269 - f0] = 1.0
            vid = os.path.join(E, f"flash_{name}.mp4")
            frames = [np.full((68, 160, 3), int(round(255 * ((v ** (1 / 2.4)) if v > 0.0031 else v * 12.92))), np.uint8)
                      for v in L]
            p = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "160x68",
                                  "-r", "24", "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                                  "-c:v", "libx264", "-crf", "10", vid], stdin=subprocess.PIPE)
            p.communicate(b"".join(f.tobytes() for f in frames))
            r = Q.analyze_video(vid, frame0=f0)
            ok = ok and r["status"] == expect
            notes.append(f"{name}: {r['status']} (max {r['max_flashes_per_24f']:.1f}/24f, expect {expect})")
        return ok, "; ".join(notes)
    check_fn("flash_qc_rules", flash_rules)

    # O. the main-title seal follows the 'title' cue from events.json (audio-lane resolution), and the stamp notices
    def cue_follow():
        ev = os.path.join(E, "events_cue185.json")
        with open(ev, "w") as fh:
            json.dump(dict(fps=24, frame_start=1, frame_end=3840, events=[dict(frame=185, type="music_cue", cue="title")]),
                      fh)
        saved = config.EVENTS_JSON
        try:
            base = T.effective_spec("main_title")
            config.EVENTS_JSON = ev
            moved = T.effective_spec("main_title")
            f, src = CUES.resolve("title", ev)
            b = T.build(moved)
            notes = [f"resolved {f} ({src})", f"seal impact {moved['start'] + b.seal_impact:.0f}",
                     f"stamp changes: {T.stamp_for(base) != T.stamp_for(moved)}"]
            ok = f == 185 and round(moved["start"] + b.seal_impact) == 185 and T.stamp_for(base) != T.stamp_for(moved)
            with open(ev, "w") as fh:            # a cue outside the card -> warning + design timing
                json.dump(dict(fps=24, frame_start=1, frame_end=3840,
                               events=[dict(frame=300, type="music_cue", cue="title")]), fh)
            os.utime(ev, (time.time() + 2, time.time() + 2))
            b2 = T.build(T.effective_spec("main_title"))
            ok = ok and bool(b2.warnings)
            notes.append(f"cue 300 -> warning: {b2.warnings[:1]}")
        finally:
            config.EVENTS_JSON = saved
        return ok, "; ".join(notes)
    check_fn("seal_follows_cue", cue_follow)

    # P. titles lock: a second process waits while the lock is held; the snapshot is a private copy
    def lock_rules():
        code = ("import sys,time; sys.path.insert(0,%r); sys.path.insert(0,%r); import titles as T\n"
                "with T.titles_lock():\n    print('locked', flush=True); time.sleep(2.0)\n") % (
            os.path.join(ROOT, "src", "common"), HERE)
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        p.stdout.readline()
        t0 = time.time()
        snap = os.path.join(E, "snap")
        shutil.rmtree(snap, ignore_errors=True)
        T.snapshot_titles(["act2"], snap, verbose=False)
        waited = time.time() - t0
        p.wait()
        a = os.path.join(snap, "act2", "00030.png")
        b = os.path.join(T.title_dir("act2"), "00030.png")
        same = os.path.exists(a) and open(a, "rb").read() == open(b, "rb").read()
        stale = [x for x in os.listdir(config.TITLES_DIR) if x.endswith(".tmp") or ".old" in x]
        return waited > 1.2 and same and not stale, f"waited {waited:.2f}s for the lock; snapshot identical={same}; " \
                                                    f"stale tmp dirs={stale}"
    check_fn("titles_lock_snapshot", lock_rules)

    fx_after = _fixture_hash()
    res.append(("fixtures_untouched", fx_before == fx_after, f"fixture hash {fx_before} -> {fx_after}"))
    print(f"[edge] {'fixtures_untouched':22s} {'PASS' if fx_before == fx_after else 'FAIL'}", flush=True)
    n_ok = sum(1 for _, ok, _ in res if ok)
    print(f"[edge] {n_ok}/{len(res)} passed")
    return res


# ============================================================================ the full self-test
def run_all():
    """Fixtures -> titles -> full preview -> FULL FINAL (with provenance gate, AAC conditioning, flash/black/loudness
    QC) -> title exactness on moving frames of all 8 cards -> stills -> range final -> edge suite -> legibility.
    Writes machine-readable results to out/post_test/results.json."""
    import assemble as A
    import titles as T
    t0 = time.time()
    results = dict(started=time.strftime("%Y-%m-%d %H:%M:%S"))
    results["fixtures_rebuilt"] = bool(ensure_media())
    T.ensure_titles()
    results["title_letterbox_leaks"] = T.check_bounds()
    n_title_frames = sum(t["end"] - t["start"] + 1 for t in config.TITLES)
    results["title_frames_checked"] = n_title_frames
    with open(os.path.join(config.TITLES_DIR, "timeline.json")) as fh:
        results["title_timeline"] = json.load(fh)

    # ---- full preview (demo-style: sparse frames, test WAV)
    rp = A.assemble(frames_dir=FRAMES, audio=WAV, mode="preview", out=os.path.join(TEST_DIR, "preview_full.mp4"),
                    qc=True)
    results["preview_full"] = {k: rp.get(k) for k in ("ok", "video", "audio", "format_duration", "size_mb", "picture")}
    results["preview_full"]["sync"] = sync_check(rp["out"])
    results["preview_full"]["flash_qc"] = (rp.get("qc") or {}).get("flash")

    # ---- FULL FINAL, exactly like the delivery run (only --allow-holds for the sparse 640x272 fixtures)
    ev, mixrep = make_qc_fixtures()
    rf = A.assemble(frames_dir=FRAMES, audio=WAV, mode="final", out=os.path.join(TEST_DIR, "final_full.mp4"),
                    allow_holds=True, mix_report=mixrep, events_json=ev)
    ff = {k: rf.get(k) for k in ("ok", "video", "audio", "format_duration", "size_mb", "picture", "qc",
                                 "audio_encode", "audio_provenance", "problems")}
    ff["ffprobe_count"] = ffprobe_json(rf["out"])
    ff["sync"] = sync_check(rf["out"])
    probes = [(t["id"], k) for t in config.TITLES for k in moving_probes(t["id"])]
    rows = title_exactness(rf["out"], config.FRAME_START, config.FRAME_END, FRAMES, probes)
    ff["title_exactness"] = rows
    ff["title_exactness_summary"] = dict(
        probes=len(rows), cards=len({r["title"] for r in rows}), all_exact=all(r["exact"] for r in rows),
        min_margin_db=min(r["margin_db"] for r in rows),
        min_psnr_db=min(r["psnr"][str(r["local"])] for r in rows),
        text_err_max_channel=max(r["text_err_max_channel"] for r in rows if r["text_err_max_channel"] is not None),
        seal_red_err_max=max((max(r["seal_red_err_rgb"]) for r in rows if r["seal_red_err_rgb"]), default=None))
    mids = []
    for t in config.TITLES:
        m = results["title_timeline"]["cards"][t["id"]]
        mids.append((m["legible_from"] + m["legible_to"]) // 2 - config.FRAME_START)
    ff["stills"] = extract_frames(rf["out"], mids, os.path.join(TEST_DIR, "stills"), "final")
    results["final_full"] = ff

    # ---- a range final (odd offset) with audio: provenance problems are warnings there, sync must hold
    rr = A.assemble(frames_dir=FRAMES, audio=WAV, mode="final", start=2003, end=2150, allow_holds=True,
                    out=os.path.join(TEST_DIR, "final_2003-2150.mp4"), mix_report=mixrep, events_json=ev)
    results["final_range"] = {k: rr.get(k) for k in ("ok", "video", "audio", "format_duration", "size_mb")}
    results["final_range"]["sync"] = sync_check(rr["out"], start=2003)

    results["edge"] = [dict(name=n, ok=bool(ok), note=note) for n, ok, note in edge_suite()]
    results["legibility"] = legibility_report()
    fs = results["final_full"]
    checks = dict(
        letterbox=not results["title_letterbox_leaks"],
        preview_ok=bool(results["preview_full"]["ok"]),
        preview_sync=bool(results["preview_full"]["sync"]["max_abs_ms"] is not None
                          and results["preview_full"]["sync"]["max_abs_ms"] < 2),
        final_ok=bool(fs["ok"]),
        final_frames=fs["video"]["frames"] == FILM_FRAMES,
        final_duration=abs(fs["format_duration"] - FILM_FRAMES / config.FPS) < 1e-3,
        final_audio=bool(fs.get("audio")) and fs["audio"]["codec"] == "aac" and fs["audio"]["sr"] == SR,
        final_sync=bool(fs["sync"]["max_abs_ms"] is not None and fs["sync"]["max_abs_ms"] < 2
                        and fs["sync"]["n_video"] >= fs["sync"]["n_video_expected"]),
        final_qc=bool((fs.get("qc") or {}).get("ok")),
        titles_exact=fs["title_exactness_summary"]["all_exact"],
        range_ok=bool(results["final_range"]["ok"]) and bool(results["final_range"]["sync"]["max_abs_ms"] < 2),
        edge=all(e["ok"] for e in results["edge"]))
    results["checks"] = checks
    results["ALL_OK"] = bool(all(checks.values()))
    results["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(TEST_DIR, "results.json"), "w") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"[selftest] ALL_OK={results['ALL_OK']} {checks} in {results['seconds']} s -> "
          f"{os.path.join(TEST_DIR, 'results.json')}")
    return results


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "run"
    if cmd == "media":
        ensure_media(force=True)
    elif cmd == "strip":
        filmstrip(argv[1], [int(x) for x in argv[2].split(",")], cols=int(argv[3]) if len(argv) > 3 else 4,
                  scale=float(argv[4]) if len(argv) > 4 else 0.5)
    elif cmd == "contact":
        contact_sheet()
        for t in config.TITLES:
            n = t["end"] - t["start"] + 1
            filmstrip(t["id"], sorted({max(1, round(n * q)) for q in
                                       (0.04, 0.12, 0.2, 0.28, 0.36, 0.45, 0.6, 0.8, 0.86, 0.91, 0.95, 1.0)}))
    elif cmd == "legibility":
        legibility_report()
    elif cmd == "run":
        run_all()
    elif cmd == "edge":
        ensure_media()
        edge_suite()
    elif cmd == "verify":
        path = argv[1]
        print(json.dumps(ffprobe_json(path), indent=1))
        print(json.dumps(sync_check(path), indent=1))
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
