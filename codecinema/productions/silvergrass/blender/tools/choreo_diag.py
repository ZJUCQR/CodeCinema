"""
choreo_diag.py - choreography diagnostics without renders.

Samples, over a frame range: both rigs' roots + facing, blade base / tip (the evaluated in-hand weapon: katana, or the
saint's spear), the sword-controller paths, every registered clash (moves.clash_report: current blade gap) and the
active camera's frustum (marker cameras), then writes
    <png>  top-down plot (XY) of roots / blade tips / controller paths / clash points / camera frusta, a side view
           (Y-Z) of the blade tips, and a timeline of the blade-to-blade distance with the clash frames marked;
    <csv>  one row per registered clash: frame, kind, attacker, defender, weapons, gap (m) now / at resolve, pos, ok;
           comment rows list unregistered blade contacts (blades < 1.5 cm apart with no clash within 3 f) and body
           overlaps (roots < 0.7 m).

    Blender -b out/scene.blend --python codecinema/productions/silvergrass/blender/tools/choreo_diag.py -- --start 1177 --end 1344 \
            [--png out/dev/moves/choreo_S12.png] [--csv out/dev/moves/choreo_S12.csv] [--step 1] [--gate 0.03]
    inside Blender:  import choreo_diag; choreo_diag.run(f0, f1, png, csv)

Sampling runs inside bl_util.muted_modifiers (grass GN off); plotting runs in the project Python (config.PYTHON, matplotlib).
"""

from codecinema.productions import film_root, source_root
import csv
import json
import math
import os
import subprocess
import sys

ROOT = str(film_root("silvergrass"))
if os.path.join(str(source_root("silvergrass")), "common") not in sys.path:
    sys.path.insert(0, os.path.join(str(source_root("silvergrass")), "common"))
import config  # noqa: E402

PLOT_PY = config.PYTHON if os.path.exists(config.PYTHON) else sys.executable   # matplotlib (project .venv) interpreter
RIGS = ("SHINOBI_rig", "SAINT_rig")
COLORS = {"SHINOBI_rig": "#c0392b", "SAINT_rig": "#b7950b"}
OVERLAP = 0.70          # m: roots closer than this = the bodies interpenetrate (flagged in the plot and the CSV)
STRAY_GAP = 0.015       # m: blades this close away from any registered clash (+-3 f) = an unregistered contact


# =============================================================================================
# sampling (inside Blender)
# =============================================================================================
def _paths():
    for p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
        if p not in sys.path:
            sys.path.insert(0, p)


def _blade(rig, M, C, f):
    try:
        w = M.weapon_at(rig, f)
        vis_name = "SAINT_spear_hand" if w == "spear" else f"{rig.name.split('_')[0]}_katana_hand"
        import bpy
        ob = bpy.data.objects.get(vis_name)
        if ob is None or ob.hide_render:
            return None
        b, t = M.actual_segment(rig, f, w, "full" if w == "spear" else "blade")
        return [list(b), list(t)]
    except Exception:           # noqa: BLE001 - diagnostics never fail a build
        return None


def sample(f0, f1, step=1):
    """Sample the scene (see module doc).  Returns a JSON-able dict."""
    _paths()
    import bpy
    import bl_util as U
    import characters as C
    import moves as M
    sc = bpy.context.scene
    rigs = [bpy.data.objects[n] for n in RIGS if n in bpy.data.objects]
    out = dict(f0=f0, f1=f1, step=step, rigs={r.name: [] for r in rigs}, cams=[], blade_gap=[])
    frames = []
    f = float(f0)
    while f <= f1 + 1e-6:
        frames.append(round(f, 3))
        f += step
    with U.muted_modifiers():
        for f in frames:
            U.frame_set(f)
            segs = {}
            for r in rigs:
                mw = r.matrix_world
                fwd = mw.to_3x3() @ __import__("mathutils").Vector((0.0, -1.0, 0.0))
                c = r.name.split("_")[0]
                ctrl = bpy.data.objects.get(f"{c}_sword_ctrl")
                cp = list(U.world_pos_of(ctrl)) if ctrl is not None else None
                seg = _blade(r, M, C, f)
                segs[r.name] = seg
                out["rigs"][r.name].append(dict(f=f, root=list(mw.translation), fwd=[fwd.x, fwd.y],
                                                ctrl=cp, blade=seg))
            if len(rigs) == 2:
                p0, p1 = rigs[0].matrix_world.translation, rigs[1].matrix_world.translation
                out.setdefault("root_dist", []).append([f, math.hypot(p0.x - p1.x, p0.y - p1.y)])
            if len(segs) == 2 and all(segs.values()):
                from mathutils import Vector
                a, b = segs[rigs[0].name], segs[rigs[1].name]
                d = M.seg_seg(Vector(a[0]), Vector(a[1]), Vector(b[0]), Vector(b[1]))[0]
                out["blade_gap"].append([f, d])
            cam = sc.camera
            if cam is not None and cam.type == 'CAMERA':
                M3 = cam.matrix_world
                look = M3.to_3x3() @ __import__("mathutils").Vector((0.0, 0.0, -1.0))
                hfov = 2 * math.atan(cam.data.sensor_width / (2 * cam.data.lens))
                out["cams"].append(dict(f=f, name=cam.name, pos=list(M3.translation), look=[look.x, look.y, look.z],
                                        hfov=hfov))
        rep = M.clash_report(measure=True) if hasattr(M, "clash_report") else []
    out["clashes"] = [dict(r) for r in rep if f0 - 6 <= r["frame"] <= f1 + 6]
    cf = [c["frame"] for c in out["clashes"]]
    spans = [tuple(c["span"]) for c in out["clashes"] if c.get("span")]
    out["stray_contacts"] = [bg[0] for bg in out["blade_gap"]
                             if bg[1] < STRAY_GAP and not any(abs(bg[0] - c) <= 3 for c in cf)
                             and not any(a - 3 <= bg[0] <= b + 3 for a, b in spans)]
    near = [rd for rd in out.get("root_dist", []) if rd[1] < OVERLAP]
    out["overlap_frames"] = [rd[0] for rd in near]
    out["markers"] = sorted([(m.frame, m.name) for m in sc.timeline_markers if f0 <= m.frame <= f1])
    return out


def write_csv(data, path, gate=0.03):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "kind", "attacker", "defender", "weapons", "gap_m", "gap_at_resolve_m", "pos_x", "pos_y",
                    "pos_z", "ok"])
        st = data.get("stray_contacts", [])
        if st:
            w.writerow([f"# unregistered blade contact (< {STRAY_GAP * 100:.1f} cm, no clash within 3 f) at "
                        + ",".join(f"{x:.0f}" for x in st[:60])])
        ov = data.get("overlap_frames", [])
        if ov:
            w.writerow([f"# body overlap (roots < {OVERLAP} m) at {len(ov)} sampled frames: "
                        + ",".join(f"{x:.0f}" for x in ov[:60])])
        for c in data["clashes"]:
            pos = c.get("pos") or (None, None, None)
            g = c.get("gap")
            w.writerow([c["frame"], c["kind"], c["attacker"], c["defender"], c.get("weapons", ""),
                        "" if g is None else f"{g:.4f}", "" if c.get("gap_resolved") is None else f"{c['gap_resolved']:.4f}",
                        *("" if v is None else f"{v:.3f}" for v in pos), "" if g is None else int(g <= gate)])


def run(f0, f1, png, csv_path=None, step=1, gate=0.03, title=None):
    """Sample [f0, f1] and write the PNG plot (+ CSV).  Returns the sample dict."""
    data = sample(f0, f1, step)
    data["title"] = title or f"choreography {f0}-{f1}"
    data["gate"] = gate
    if csv_path:
        write_csv(data, csv_path, gate)
    js = os.path.splitext(png)[0] + "_samples.json"
    with open(js, "w") as fh:
        json.dump(data, fh)
    r = subprocess.run([PLOT_PY, os.path.abspath(__file__), "--plot", js, png], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-1500:] if r.returncode else "")
    return data


# =============================================================================================
# plotting (.venv Python, matplotlib)
# =============================================================================================
def plot(js, png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    data = json.load(open(js))
    gate = data.get("gate", 0.03)
    fig = plt.figure(figsize=(16, 11), dpi=110)
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 1.1], width_ratios=[1.35, 1])
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, :])
    f0, f1 = data["f0"], data["f1"]
    for name, samples in data["rigs"].items():
        col = COLORS.get(name, "k")
        xs = [s["root"][0] for s in samples]
        ys = [s["root"][1] for s in samples]
        ax.plot(xs, ys, "-", color=col, lw=2.2, label=name.replace("_rig", "") + " root")
        for s in samples[:: max(1, int(12 / data["step"]))]:
            x, y = s["root"][:2]
            ax.arrow(x, y, s["fwd"][0] * 0.25, s["fwd"][1] * 0.25, head_width=0.06, color=col, alpha=0.7, lw=0.8)
            ax.text(x + 0.05, y + 0.05, f"{s['f']:.0f}", fontsize=6, color=col, alpha=0.8)
        tips = [(s["f"], s["blade"][1]) for s in samples if s.get("blade")]
        if tips:
            segs = []
            for (fa, ta), (fb, tb) in zip(tips, tips[1:]):
                if fb - fa <= data["step"] * 1.5:
                    segs.append([(ta[0], ta[1]), (tb[0], tb[1])])
            ax.add_collection(LineCollection(segs, colors=col, linewidths=0.7, alpha=0.55))
            for s in samples:
                if s.get("blade"):
                    b, t = s["blade"]
                    ax2.plot([b[1], t[1]], [b[2], t[2]], "-", color=col, lw=0.4, alpha=0.25)
            ty = [t[1] for _, t in tips]
            tz = [t[2] for _, t in tips]
            ax2.plot(ty, tz, ".", color=col, ms=1.5, alpha=0.8, label=name.replace("_rig", "") + " tip")
        cps = [s["ctrl"] for s in samples if s.get("ctrl")]
        if cps:
            ax.plot([c[0] for c in cps], [c[1] for c in cps], ":", color=col, lw=0.9, alpha=0.8)
    for c in data["clashes"]:
        pos = c.get("pos")
        if not pos:
            continue
        ok = c.get("gap") is not None and c["gap"] <= gate
        mk = "*" if ok else "X"
        ax.plot(pos[0], pos[1], mk, color="#1e8449" if ok else "#e74c3c", ms=13, mec="k", mew=0.6)
        ax.text(pos[0] + 0.06, pos[1] - 0.12, f"{c['frame']:.0f} {c['kind']}\n{(c.get('gap') or 0) * 100:.1f} cm",
                fontsize=7, color="#145a32" if ok else "#922b21")
        ax2.plot(pos[1], pos[2], mk, color="#1e8449" if ok else "#e74c3c", ms=11, mec="k", mew=0.6)
    seen = set()
    for cam in data["cams"]:
        key = (cam["name"])
        if key in seen and int(cam["f"]) % 48:
            continue
        seen.add(key)
        x, y = cam["pos"][:2]
        lx, ly = cam["look"][:2]
        n = math.hypot(lx, ly) or 1.0
        lx, ly = lx / n, ly / n
        h = cam["hfov"] / 2
        L = 7.0
        for s in (-1, 1):
            ca, sa = math.cos(s * h), math.sin(s * h)
            ax.plot([x, x + L * (lx * ca - ly * sa)], [y, y + L * (lx * sa + ly * ca)], "-", color="#2e86c1", lw=0.6,
                    alpha=0.5)
        ax.plot(x, y, "s", color="#2e86c1", ms=5)
        ax.text(x, y + 0.15, f"{cam['name']} @{cam['f']:.0f}", fontsize=6, color="#2e86c1")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"{data['title']}: top view (roots, facing every 12 f, blade tips, controller paths ..., clashes, "
                 f"cameras)", fontsize=9)
    allx = [s["root"][0] for v in data["rigs"].values() for s in v]
    ally = [s["root"][1] for v in data["rigs"].values() for s in v]
    if allx:
        cx, cy = (min(allx) + max(allx)) / 2, (min(ally) + max(ally)) / 2
        r = max(max(allx) - min(allx), max(ally) - min(ally)) / 2 + 1.6
        ax.set_xlim(cx - r, cx + r)
        ax.set_ylim(cy - r, cy + r)
    ax.legend(fontsize=7, loc="upper left")
    ax2.set_title("side view (y-z): blades (faint) and tips, clash points", fontsize=9)
    ax2.set_xlabel("y (m)")
    ax2.set_ylabel("z (m)")
    ax2.grid(True, alpha=0.3)
    ax2.set_aspect("equal")
    ax2.axhline(0.0, color="k", lw=0.8)
    ax2.axhspan(0.0, 1.05, color="#abebc6", alpha=0.25, label="grass line ~1.05 m")
    ax2.legend(fontsize=7)
    if data["blade_gap"]:
        fs = [g[0] for g in data["blade_gap"]]
        ds = [min(2.0, g[1]) for g in data["blade_gap"]]
        ax3.plot(fs, ds, "-", color="#34495e", lw=0.9, label="blade-blade")
    if data.get("root_dist"):
        ax3.plot([g[0] for g in data["root_dist"]], [min(2.0, g[1]) for g in data["root_dist"]], "-", color="#8e44ad",
                 lw=0.9, alpha=0.8, label="root-root")
        ax3.axhline(OVERLAP, color="#8e44ad", lw=0.6, ls=":")
        for fo in data.get("overlap_frames", []):
            ax3.axvspan(fo - 0.5, fo + 0.5, color="#e74c3c", alpha=0.15)
    for fs_ in data.get("stray_contacts", []):
        ax3.plot(fs_, 0.02, "v", color="#d35400", ms=5)
        ax3.legend(fontsize=7, loc="upper right")
    for c in data["clashes"]:
        g = c.get("gap")
        ok = g is not None and g <= gate
        ax3.axvline(c["frame"], color="#1e8449" if ok else "#e74c3c", lw=1.0, alpha=0.7)
        ax3.text(c["frame"], 1.9, f"{c['frame']:.0f}", fontsize=6, rotation=90, va="top")
    for fr, nm in data.get("markers", []):
        ax3.axvline(fr, color="#2e86c1", lw=0.6, ls="--", alpha=0.6)
        ax3.text(fr, 0.05, nm, fontsize=6, color="#2e86c1", rotation=90)
    ax3.axhline(gate, color="#e74c3c", lw=0.6, ls=":")
    ax3.set_xlim(f0, f1)
    ax3.set_ylim(0, 2.0)
    ax3.set_xlabel("film frame")
    ax3.set_ylabel("blade-blade dist (m)")
    ax3.set_title(f"blade-to-blade and root-to-root distance (clash frames green = within {gate * 100:.0f} cm; red bands "
                  f"= bodies overlapping, roots < {OVERLAP} m; orange marks = blades touching with no clash)", fontsize=9)
    ax3.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(png)
    print("choreo_diag written:", png)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--png", default=os.path.join(config.DEV_DIR, "moves", "choreo.png"))
    ap.add_argument("--csv", default=None)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--gate", type=float, default=0.03)
    a = ap.parse_args(argv)
    run(a.start, a.end, a.png, a.csv or os.path.splitext(a.png)[0] + ".csv", a.step, a.gate)


if __name__ == "__main__":
    if "--plot" in sys.argv:
        i = sys.argv.index("--plot")
        plot(sys.argv[i + 1], sys.argv[i + 2])
    else:
        main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
