"""
silk.py - the aged silk ground of the scroll and a screen-space fibre grain.

make_silk(length, height) -> uint8 RGBA array (1 px per scroll unit), cached to disk by the renderer.
"""

import numpy as np
from scipy.ndimage import gaussian_filter

SILK = np.array([0.82, 0.72, 0.54])


def _noise(shape, sigma, rng):
    n = gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma)
    return n / (n.std() + 1e-6)


def make_silk(length, height, seed=7):
    rng = np.random.default_rng(seed)
    H, W = int(height), int(length)
    lum = np.zeros((H, W), np.float32)
    # large mottling and stains (computed small, upsampled)
    small = _noise((H // 8 + 1, W // 8 + 1), 14, rng) * 0.014 + _noise((H // 8 + 1, W // 8 + 1), 3, rng) * 0.008
    lum += np.kron(small, np.ones((8, 8), np.float32))[:H, :W]
    # weave: horizontal and vertical threads
    rows = gaussian_filter(rng.standard_normal((H, W // 16 + 1)).astype(np.float32), (0.6, 3))
    lum += np.repeat(rows, 16, axis=1)[:, :W] * 0.012
    cols = gaussian_filter(rng.standard_normal((H // 16 + 1, W)).astype(np.float32), (3, 0.6))
    lum += np.repeat(cols, 16, axis=0)[:H, :] * 0.010
    lum += rng.standard_normal((H, W)).astype(np.float32) * 0.010
    # ageing toward the top / bottom edges and the two ends
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    lum -= 0.10 * (np.exp(-y / 0.05) + np.exp(-(1 - y) / 0.05))
    lum -= 0.05 * (np.exp(-x / 0.02) + np.exp(-(1 - x) / 0.02))
    # roll creases every ~1100 units
    for cx in np.arange(900, W, 1100) + rng.integers(-120, 120, len(np.arange(900, W, 1100))):
        lum -= 0.025 * np.exp(-((np.arange(W) - cx) ** 2) / (2 * 3.0 ** 2))[None, :].astype(np.float32)
    rgb = SILK[None, None, :] * (1.0 + lum[..., None])
    # warm the darker areas slightly (browner stains)
    rgb[..., 2] -= np.clip(-lum, 0, 1) * 0.10
    # foxing spots
    for _ in range(int(W / 180)):
        cx, cy, r = rng.integers(0, W), rng.integers(0, H), rng.uniform(2, 9)
        x0, x1, y0, y1 = max(0, int(cx - 3 * r)), min(W, int(cx + 3 * r)), max(0, int(cy - 3 * r)), min(H, int(cy + 3 * r))
        yy, xx = np.mgrid[y0:y1, x0:x1]
        m = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)) * rng.uniform(0.04, 0.12)
        rgb[y0:y1, x0:x1] *= (1 - m[..., None] * np.array([0.6, 0.9, 1.3]))
    rgba = np.concatenate([np.clip(rgb, 0, 1), np.ones((H, W, 1), np.float32)], axis=2)
    return (rgba * 255).astype(np.uint8)


def make_grain(w, h, seed=11):
    """Screen-space fibre grain, centred on 128 (used as a soft overlay)."""
    rng = np.random.default_rng(seed)
    g = gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), (0.5, 1.4)) * 10
    g += gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), (1.4, 0.5)) * 8
    a = np.clip(128 + g, 0, 255).astype(np.uint8)
    return np.dstack([a, a, a, np.full_like(a, 255)])
