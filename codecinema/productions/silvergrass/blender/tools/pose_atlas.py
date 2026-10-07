"""
pose_atlas.py - render a grid of named poses on both rigs from 3 views (Workbench) into ONE labelled PNG.

Usage (headless Blender renders the cells, then calls the project Python (config.PYTHON, PIL) to tile + label them):
    Blender -b --factory-startup --python codecinema/productions/silvergrass/blender/tools/pose_atlas.py -- \
        [--poses <file.py|module>[:VARIABLE]] [--only a,b] [--out out/dev/moves/atlas.png] [--cell 300] \
        [--chars SHINOBI,SAINT] [--views front,right,q34] [--meshes auto|placeholder] \
        [--hide SAINT_haori,...] [--lr-tint] [--auto-elbow]
    --hide: objects hidden in every cell (e.g. the haori, to judge the saint's legs); --lr-tint: warm LEFT / cool RIGHT
    limbs (QA only; the costume is symmetric); --auto-elbow: characters.auto_elbow on every IK arm of every pose.
    Every render takes a machine-wide lane_tools.render_lock slot.
    --poses defaults to the built-in DEMO_POSES (rig verification set). A module is imported from codecinema/productions/silvergrass/blender
    (e.g. --poses poses:POSES); a .py path is executed and VARIABLE (default POSES) read from it.

Pose format (dict name -> spec), see characters.apply_pose:
    {"body": {bone: (rx, ry, rz) deg, ...}, "hips_offset": (x, y, z),
     "legs": {"R": {"ankle": (x, y, z), "foot_yaw": 0, "foot_pitch": 0, "toe": (rx, ry, rz)}},
     "ctrl": None | {"loc": (x,y,z), "rot": (rx,ry,rz)} | {"grip": (x,y,z), "dir": (x,y,z), "edge": (x,y,z)}
             (RIG space, SHINOBI metres, scaled by height for the SAINT; or {"SHINOBI": {...}, "SAINT": {...}}),
     "ctrl": "sheathed" (right fist on the sheathed hilt), "left": "free"|"grip"|"saya", "saya": (pull, roll),
     "elbow": {"R"|"L": "auto" | (x, y, z)}, "hat_tilt": (pitch, roll), "hide": [names],
     "two_hand": bool, "weapon": "katana"|"spear", "spear_grip": (grip_R, grip_L), "chars": ["SAINT"]}
    A plain {bone: (rx,ry,rz)} dict (poses.py POSES style, optional "hips_offset") is accepted as a body-only pose.

Programmatic use (inside Blender):  import pose_atlas; pose_atlas.render_atlas(poses, "/path/atlas.png")
Each row is annotated per character with the IK reach residuals (right arm / left hand, mm), the wrist check
(characters.wrist_issues: swing > 75 / |twist| > 100 deg) and, for the SAINT with the hat on, the hat clearance
(characters.hat_clearance < 1 cm); problems are printed in red ('!').
"""

from codecinema.productions import film_root, source_root
import json
import os
import subprocess
import sys

ROOT = str(film_root("silvergrass"))
if os.path.join(str(source_root("silvergrass")), "common") not in sys.path:
    sys.path.insert(0, os.path.join(str(source_root("silvergrass")), "common"))
import config  # noqa: E402

TILE_PY = config.PYTHON if os.path.exists(config.PYTHON) else sys.executable   # PIL (project .venv) interpreter

VIEWS = {   # name -> (camera direction from the subject (rig space), elevation offset)
    "front": ((0.0, -1.0, 0.0), 0.10),
    "right": ((-1.0, 0.0, 0.0), 0.10),
    "q34": ((0.72, -0.70, 0.0), 0.55),
}

S = 1.0
DEMO_POSES = {
    "rest": {},
    "chudan": {
        "body": {"spine": (4, 0, 0), "chest": (2, -4, 0), "neck": (-4, 4, 0), "head": (-2, 0, 0),
                 "shoulder.R": (8, 0, 0), "shoulder.L": (10, 0, 0)},
        "hips_offset": (0.0, -0.04, 0.0),
        "legs": {"R": {"ankle": (-0.10, -0.24, 0.077)}, "L": {"ankle": (0.11, 0.24, 0.077), "foot_yaw": 12}},
        "ctrl": {"grip": (-0.035, -0.36, 1.03), "dir": (0.0, -0.87, 0.50)},
        "two_hand": True,
    },
    "jodan": {
        "body": {"spine": (-2, 0, 0), "chest": (-6, -6, 0), "neck": (4, 4, 0), "head": (4, 0, 0),
                 "shoulder.R": (0, 0, 14), "shoulder.L": (0, 0, -14)},
        "hips_offset": (0.0, -0.03, 0.0),
        "legs": {"R": {"ankle": (-0.10, -0.26, 0.077)}, "L": {"ankle": (0.11, 0.22, 0.077), "foot_yaw": 12}},
        "ctrl": {"grip": (-0.02, -0.12, 1.86), "dir": (0.0, 0.62, 0.78), "edge": (0.0, -0.78, 0.62)},
        "two_hand": True,
    },
    "lunge_thrust": {
        "body": {"hips": (0, 10, 0), "spine": (16, 5, 0), "chest": (12, 8, 0), "neck": (-18, -6, 0), "head": (-12, -5, 0),
                 "shoulder.R": (26, 0, 0), "upper_arm.L": (-40, 0, 24), "forearm.L": (25, 0, 0)},
        "hips_offset": (0.0, -0.20, -0.06),
        "legs": {"R": {"ankle": (-0.13, -0.72, 0.077), "foot_yaw": 5},
                 "L": {"ankle": (0.16, 0.62, 0.077), "foot_yaw": 30, "foot_pitch": 35, "toe": (-35, 0, 0)}},
        "ctrl": {"grip": (-0.12, -0.80, 1.06), "dir": (0.02, -1.0, 0.06)},
        "two_hand": False,
    },
    "cut_horizontal_R": {       # one-handed R->L horizontal cut as the blade passes the front: arm extended, palm up
        "body": {"hips": (0, 12, 0), "spine": (6, 12, 0), "chest": (4, 18, 0), "neck": (0, -14, 0), "head": (0, -12, 0),
                 "shoulder.R": (18, 0, 0), "upper_arm.L": (-15, 0, 18), "forearm.L": (30, 0, 0)},
        "hips_offset": (0.0, -0.08, 0.0),
        "legs": {"R": {"ankle": (-0.22, -0.30, 0.077), "foot_yaw": -10}, "L": {"ankle": (0.20, 0.22, 0.077), "foot_yaw": 25}},
        "ctrl": {"grip": (0.10, -0.70, 1.14), "dir": (0.147, -0.985, 0.0), "edge": (0.985, 0.147, 0.0)},
        "elbow": {"R": "auto"},
        "two_hand": False,
    },
    "kesa_impact": {            # two-handed kesa (right shoulder -> left hip) at impact: tip trails right, edge down-left
        "body": {"hips": (0, -8, 0), "spine": (8, -6, 0), "chest": (6, -8, 0), "neck": (-6, 8, 0), "head": (-4, 6, 0),
                 "shoulder.R": (10, 0, 0), "shoulder.L": (10, 0, 0)},
        "hips_offset": (0.0, -0.06, 0.0),
        "legs": {"R": {"ankle": (-0.12, -0.30, 0.077)}, "L": {"ankle": (0.12, 0.24, 0.077), "foot_yaw": 15}},
        "ctrl": {"grip": (-0.04, -0.50, 1.00), "dir": (-0.330, -0.908, -0.259), "edge": (0.393, -0.382, -0.837)},
        "elbow": {"R": "auto", "L": "auto"},
        "two_hand": True,
    },
    "iai_grab": {               # iai stance: right fist on the sheathed hilt, left hand on the saya (rolled edge-out 60)
        "body": {"hips": (0, 12, 0), "spine": (14, 8, 0), "chest": (8, 10, 0), "neck": (-12, -10, 0), "head": (-8, -8, 0),
                 "shoulder.R": (20, 0, 0)},
        "hips_offset": (0.0, -0.12, 0.0),
        "legs": {"R": {"ankle": (-0.14, -0.30, 0.077)}, "L": {"ankle": (0.14, 0.26, 0.077), "foot_yaw": 20}},
        "ctrl": "sheathed", "left": "saya", "saya": (0.0, 60.0),
        "elbow": {"R": "auto", "L": "auto"},
    },
    "kneel_sword_planted": {    # HANDOFF[3072] (shinobi, S23) / S27 (elder): right knee down, blade planted, head bowed
        "body": {"spine": (12, 0, 0), "chest": (8, 0, 0), "neck": (22, 0, 0), "head": (18, 0, 0)},
        "hips_offset": (0.0, -0.44, 0.0),
        "legs": {"L": {"ankle": (0.12, -0.42, 0.077)},
                 "R": {"ankle": (-0.11, 0.36, 0.11), "foot_pitch": 20, "toe": (-60, 0, 0)}},
        "ctrl": {"grip": (-0.03, -0.45, 0.66), "dir": (0.0, -0.15, -1.0), "edge": (0.0, -1.0, 0.0)},
        "elbow": {"R": "auto", "L": "auto"},
        "two_hand": True,
    },
    "spear_guard": {
        "chars": ["SAINT"],
        "weapon": "spear",
        "body": {"hips": (0, -20, 0), "spine": (6, -12, 0), "chest": (4, -14, 0), "neck": (-4, 22, 0), "head": (-2, 18, 0),
                 "shoulder.L": (12, 0, 0)},
        "hips_offset": (0.0, -0.06, 0.0),
        "legs": {"L": {"ankle": (0.08, -0.30, 0.077), "foot_yaw": -10}, "R": {"ankle": (-0.14, 0.26, 0.077), "foot_yaw": -35}},
        "ctrl": {"SAINT": {"grip": (-0.20, 0.00, 1.02), "dir": (0.10, -1.0, 0.17)}},
        "two_hand": True,
    },
}


# =============================================================================================
# tiling (runs under the project Python with PIL)
# =============================================================================================
def tile(manifest_path):
    from PIL import Image, ImageDraw, ImageFont
    man = json.load(open(manifest_path))
    cell = man["cell"]
    rows, cols = man["rows"], man["cols"]
    lab_w, head_h = 170, 34
    W = lab_w + cell * len(cols)
    H = head_h + (cell + 4) * len(rows)
    img = Image.new("RGB", (W, H), (28, 28, 30))
    dr = ImageDraw.Draw(img)
    try:
        if not config.FONT_UI:
            raise OSError("no UI font found (settings fonts.ui)")
        font = ImageFont.truetype(config.FONT_UI, 15)
        small = ImageFont.truetype(config.FONT_UI, 12)
    except OSError:
        font = small = ImageFont.load_default()
    for j, c in enumerate(cols):
        dr.text((lab_w + j * cell + 8, 9), c, fill=(230, 230, 230), font=font)
    for i, r in enumerate(rows):
        y = head_h + i * (cell + 4)
        dr.text((8, y + cell // 2 - 20), r["name"], fill=(250, 220, 150), font=font)
        for k, line in enumerate(r.get("notes", [])):
            dr.text((8, y + cell // 2 + 2 + 15 * k), line, fill=(200, 200, 200), font=small)
        for j, path in enumerate(r["cells"]):
            x = lab_w + j * cell
            if path and os.path.exists(path):
                im = Image.open(path).convert("RGB").resize((cell, cell))
                img.paste(im, (x, y))
            else:
                dr.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(45, 45, 48))
                dr.text((x + cell // 2 - 12, y + cell // 2 - 8), "n/a", fill=(140, 140, 140), font=font)
            tag = r.get("tags", {}).get(str(j))
            if tag:
                col = (255, 120, 120) if tag.startswith("!") else (170, 230, 170)
                dr.text((x + 6, y + cell - 18), tag, fill=col, font=small)
    img.save(man["out"])
    print("atlas written:", man["out"], img.size)


# =============================================================================================
# rendering (inside Blender)
# =============================================================================================
def _setup_scene(meshes="auto", lr_tint=False):
    import bpy
    for p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import bl_util as U
    import characters as C
    U.clear_scene()
    C.PH_LR_TINT = bool(lr_tint)
    res = C.build(meshes=meshes, place=False)
    C.PH_LR_TINT = False
    rigs = {"SHINOBI": res["shinobi"], "SAINT": res["saint"]}
    rigs["SHINOBI"].location = (0.0, 0.0, 0.0)
    rigs["SAINT"].location = (0.0, 0.0, -60.0)     # out of every horizontal ortho frame of the other rig
    for r in rigs.values():
        r.rotation_euler = (0.0, 0.0, 0.0)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
    sh.show_cavity = True
    sh.cavity_type = 'WORLD'
    sh.show_object_outline = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.16, 0.17, 0.19)
    sc.render.film_transparent = False
    U.configure_png(sc)
    mat = U.new_material("atlas_ground", (0.30, 0.29, 0.27))
    line = U.new_material("atlas_grid", (0.22, 0.21, 0.20))
    for z0 in (0.0, -60.0):
        U.mesh_from_data(f"atlas_ground_{int(-z0)}", [(-4, -4, z0), (4, -4, z0), (4, 4, z0), (-4, 4, z0)],
                         faces=[(0, 1, 2, 3)], materials=[mat])
        # 0.5 m grid strips for reading foot contact / stance width
        verts, faces = [], []
        for k in range(-6, 7):
            for (x0, y0, x1, y1) in ((k * 0.5 - 0.006, -3, k * 0.5 + 0.006, 3), (-3, k * 0.5 - 0.006, 3, k * 0.5 + 0.006)):
                n = len(verts)
                verts += [(x0, y0, z0 + 0.002), (x1, y0, z0 + 0.002), (x1, y1, z0 + 0.002), (x0, y1, z0 + 0.002)]
                faces.append((n, n + 1, n + 2, n + 3))
        U.mesh_from_data(f"atlas_grid_{int(-z0)}", verts, faces=faces, materials=[line])
    cam = U.new_camera("ATLAS_cam", (0, -6, 1), (0, 0, 1), lens=50)
    cam.data.type = 'ORTHO'
    sc.camera = cam
    return rigs, cam, C, U


def _normalise(spec):
    if spec is None:
        return {}
    if any(k in spec for k in ("body", "ctrl", "legs", "two_hand", "weapon", "chars", "left", "saya", "elbow",
                               "hat_tilt", "hide")):
        return spec
    body = {k: v for k, v in spec.items() if k != "hips_offset"}
    out = {"body": body}
    if "hips_offset" in spec:
        out["hips_offset"] = spec["hips_offset"]
    return out


def _qa_tags(C, rig, char):
    """Reach / wrist / hat QA text for the current pose of `rig`: (tag, is_problem)."""
    rep = C.reach_report(rig)
    bits, bad = [], False
    for key, lab in (("sword_mm", "R"), ("grip_mm", "L")):
        if rep[key] is not None:
            b = rep[key] > 2
            bad |= b
            bits.append(("!" if b else "") + f"{lab} {rep[key]:.0f}mm")
    iss = C.wrist_issues(rig, update=False)
    w = C.wrist_report(rig, update=False)
    if iss:
        bad = True
        bits.append("!W " + ",".join(i.replace(" wrist ", ":").replace("swing", "sw").replace("twist", "tw").split(">")[0]
                                     for i in iss))
    else:
        bits.append("W ok %.0f/%.0f" % (max(w["L"]["wrist_swing"], w["R"]["wrist_swing"]),
                                          max(abs(w["L"]["wrist_twist"]), abs(w["R"]["wrist_twist"]))))
    if char == "SAINT":
        hc = C.hat_clearance()
        if hc:
            mn = min(hc.values())
            b = mn < 0.01
            bad |= b
            bits.append(("!" if b else "") + f"hat {mn * 100:.0f}cm")
    return " ".join(bits), bad


def render_atlas(poses, out_png, chars=("SHINOBI", "SAINT"), views=("front", "right", "q34"), cell=300,
                 meshes="auto", workdir=None, ortho=3.0, center=(0.0, -0.25, 1.05), hide=(), lr_tint=False,
                 auto_elbow=False):
    """Render every pose on each rig from each view (Workbench) and tile them into `out_png` (PIL, .venv).
    Every still takes a lane_tools.render_lock() slot. Returns the manifest dict (per-pose QA tags included)."""
    import bpy
    from mathutils import Vector
    rigs, cam, C, U = _setup_scene(meshes, lr_tint)
    import lane_tools as LT
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = cell
    cam.data.ortho_scale = ortho
    workdir = workdir or os.path.splitext(out_png)[0] + "_cells"
    os.makedirs(workdir, exist_ok=True)
    cols = [f"{c} {v}" for c in chars for v in views]
    rows = []
    for name, spec in poses.items():
        spec = _normalise(spec)
        row = {"name": name, "cells": [], "notes": [], "tags": {}}
        for ci, char in enumerate(chars):
            rig = rigs[char]
            if spec.get("chars") and char not in spec["chars"]:
                row["cells"] += [None] * len(views)
                continue
            sp = dict(spec)
            if hide:
                sp["hide"] = list(sp.get("hide", ())) + list(hide)
            C.apply_pose(rig, sp)
            if auto_elbow:
                for sd in ("R", "L"):
                    C.auto_elbow(rig, None, sd, key=True)
            C.settle_secondary(rig, wind=float(spec.get("wind", 0.0)))      # tails / beard / sleeves hang
            tag, bad = _qa_tags(C, rig, char)
            row["tags"][str(ci * len(views))] = ("!" if bad else "") + tag.replace("!", "")
            print(f"[atlas] {name:22s} {char:8s} {tag}")
            base = rig.matrix_world.translation
            ctr = base + Vector(center)
            for vi, v in enumerate(views):
                d, el = VIEWS[v]
                d = Vector(d).normalized()
                loc = ctr + d * 8.0 + Vector((0, 0, el))
                cam.location = loc
                cam.rotation_euler = U.look_at_euler(loc, ctr + Vector((0, 0, el * 0.3)))
                path = os.path.join(workdir, f"{name}_{char}_{v}.png")
                with LT.render_lock(label="pose_atlas"):
                    U.render_still(path)
                row["cells"].append(path)
        rows.append(row)
    man = dict(cell=cell, rows=rows, cols=cols, out=os.path.abspath(out_png))
    mpath = os.path.join(workdir, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(man, f, indent=1)
    r = subprocess.run([TILE_PY, os.path.abspath(__file__), "--tile", mpath], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-500:] if r.returncode else "")
    return man


def _load_poses(arg):
    if not arg:
        return DEMO_POSES
    var = "POSES"
    if ":" in arg:
        arg, var = arg.rsplit(":", 1)
    if arg.endswith(".py"):
        ns = {"__name__": "pose_file"}
        exec(compile(open(arg).read(), arg, "exec"), ns)
        return ns[var]
    import importlib
    return getattr(importlib.import_module(arg), var)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--poses", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=os.path.join(config.DEV_DIR, "characters", "rig_atlas.png"))
    ap.add_argument("--cell", type=int, default=300)
    ap.add_argument("--chars", default="SHINOBI,SAINT")
    ap.add_argument("--views", default="front,right,q34")
    ap.add_argument("--meshes", default="auto")
    ap.add_argument("--ortho", type=float, default=3.0, help="ortho frame size (m)")
    ap.add_argument("--center", default="0,-0.25,1.05", help="frame centre x,y,z relative to the rig origin")
    ap.add_argument("--hide", default="", help="objects hidden in every cell, comma separated (e.g. SAINT_haori)")
    ap.add_argument("--lr-tint", action="store_true", help="QA: warm LEFT / cool RIGHT placeholder limbs")
    ap.add_argument("--auto-elbow", action="store_true", help="characters.auto_elbow on every IK arm")
    a = ap.parse_args(argv)
    poses = _load_poses(a.poses)
    if a.only:
        keep = a.only.split(",")
        poses = {k: v for k, v in poses.items() if k in keep}
    render_atlas(poses, a.out, chars=tuple(a.chars.split(",")), views=tuple(a.views.split(",")), cell=a.cell,
                 meshes=a.meshes, ortho=a.ortho, center=tuple(float(x) for x in a.center.split(",")),
                 hide=tuple(x for x in a.hide.split(",") if x), lr_tint=a.lr_tint, auto_elbow=a.auto_elbow)


if __name__ == "__main__":
    if "--tile" in sys.argv:
        tile(sys.argv[sys.argv.index("--tile") + 1])
    else:
        main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
