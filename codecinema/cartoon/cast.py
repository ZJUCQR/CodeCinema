"""The character library: archetypes, how a screenplay customizes them, and body proportions.

A character is plain data, so screenplays can reuse a library archetype and
override only what they need, for example::

    "cast": {"mei": {"from": "girl", "name": "Mei", "hair": {"style": "twintails", "color": "#3b2433"}}}

Proportions come from `metrics()`, shared by the Blender rig and the motion
planner, so footsteps in the sound match the feet in the picture.
"""
from __future__ import annotations

import copy

PLANS = ("biped", "penguin", "bird")

HAIR_STYLES = ("none", "short", "spiky", "bob", "buns", "twintails", "ponytail", "braids", "elder_bun", "bald")

ARCHETYPES = {
    "girl": {
        "description": "A lively child of about seven, big anime eyes, buns or tails.",
        "plan": "biped", "height": 1.08, "head": 0.225, "build": 1.0,
        "skin": "#f9dfcf",
        "face": {"iris": "#6b3f2a", "iris_light": "#e3a768", "lashes": True},
        "hair": {"style": "buns", "color": "#2c1d24"},
        "outfit": {"top": "#d8473d", "top_style": "padded", "trim": "#f3c75f", "bottom": "#39334a",
                   "bottom_style": "pants", "shoes": "#3d2b2b"},
        "accessories": [],
        "voice": {"profile": "girl", "speaker": "Vivian", "pitch": 3.0,
                  "design": "A bright, curious seven-year-old girl with a clear, slightly high voice."},
    },
    "boy": {
        "description": "A cheeky child with spiky hair and a cap-ready head.",
        "plan": "biped", "height": 1.1, "head": 0.225, "build": 1.0,
        "skin": "#f5d6c0",
        "face": {"iris": "#3d4f8a", "iris_light": "#9ec2ff"},
        "hair": {"style": "spiky", "color": "#3a2a1f"},
        "outfit": {"top": "#3c86c9", "top_style": "shirt", "trim": "#ffffff", "bottom": "#e2b45c",
                   "bottom_style": "shorts", "shoes": "#c84a3a"},
        "accessories": [],
        "voice": {"profile": "boy", "speaker": "Aiden", "pitch": 4.0,
                  "design": "An energetic eight-year-old boy, cheeky and warm."},
    },
    "woman": {
        "description": "A young adult with a ponytail.",
        "plan": "biped", "height": 1.42, "head": 0.205, "build": 1.0,
        "skin": "#f7d9c4",
        "face": {"iris": "#4a6b3a", "iris_light": "#b8e08a", "lashes": True, "eye_h": 0.40},
        "hair": {"style": "ponytail", "color": "#5a3324"},
        "outfit": {"top": "#7a9fd1", "top_style": "coat", "trim": "#f0e6d2", "bottom": "#3b3b4f",
                   "bottom_style": "skirt", "shoes": "#5a3a2a"},
        "accessories": [],
        "voice": {"profile": "woman", "speaker": "Serena", "pitch": 0.0,
                  "design": "A gentle young woman with a warm, calm voice."},
    },
    "man": {
        "description": "A sturdy adult villager.",
        "plan": "biped", "height": 1.5, "head": 0.2, "build": 1.15,
        "skin": "#efc8a8",
        "face": {"iris": "#3a2a22", "iris_light": "#8a6a52", "eye_h": 0.36, "eye_w": 0.32, "brow_thick": 0.06},
        "hair": {"style": "short", "color": "#2a2220"},
        "outfit": {"top": "#4f5d7a", "top_style": "coat", "trim": "#d9c9a8", "bottom": "#33303a",
                   "bottom_style": "pants", "shoes": "#2d2424"},
        "accessories": [],
        "voice": {"profile": "man", "speaker": "Ryan", "pitch": 0.0,
                  "design": "A friendly middle-aged man with a deep, warm voice."},
    },
    "grandma": {
        "description": "A small, kind grandmother with a white bun and round glasses.",
        "plan": "biped", "height": 1.2, "head": 0.21, "build": 1.05, "hunch": 0.18,
        "skin": "#f2d2bd",
        "face": {"iris": "#4a3a30", "iris_light": "#9a7a62", "eye_h": 0.34, "eye_w": 0.32, "lashes": False,
                 "brow": "#b9b2ab", "line": "#3a2a26"},
        "hair": {"style": "elder_bun", "color": "#e9e4de"},
        "outfit": {"top": "#3c4f78", "top_style": "padded", "trim": "#cdb27a", "bottom": "#2f2a35",
                   "bottom_style": "pants", "shoes": "#2b2222"},
        "accessories": [{"kind": "glasses", "color": "#6b4a2a"}],
        "voice": {"profile": "grandma", "speaker": "Vivian", "pitch": -1.0,
                  "design": "A kind grandmother in her seventies, slow, soft and smiling."},
    },
    "grandpa": {
        "description": "A slow, warm grandfather with bushy brows.",
        "plan": "biped", "height": 1.3, "head": 0.21, "build": 1.1, "hunch": 0.15,
        "skin": "#efcdb4",
        "face": {"iris": "#3a2e28", "iris_light": "#8a7262", "eye_h": 0.30, "eye_w": 0.32,
                 "brow": "#d9d4cc", "brow_thick": 0.08},
        "hair": {"style": "bald", "color": "#ded8cf"},
        "outfit": {"top": "#7b5a3a", "top_style": "coat", "trim": "#e3d3b0", "bottom": "#3a3530",
                   "bottom_style": "pants", "shoes": "#2b2222"},
        "accessories": [],
        "voice": {"profile": "grandpa", "speaker": "Uncle_Fu", "pitch": 0.0,
                  "design": "A gentle old man with a low, unhurried voice."},
    },
    "cat": {
        "description": "A small cat-person with pointed ears and a curling tail.",
        "plan": "biped", "height": 0.95, "head": 0.24, "build": 0.95,
        "skin": "#f2c48a",
        "face": {"style": "creature", "iris": "#5a8a2a", "iris_light": "#d8f080", "nose": True,
                 "skin_line": "#a0603a"},
        "hair": {"style": "none", "color": "#f2c48a"},
        "animal": {"ears": "cat", "tail": "cat", "fur": "#f2c48a", "belly": "#fff1dc"},
        "outfit": {"top": "#6fa8a0", "top_style": "shirt", "trim": "#ffffff", "bottom": "#f2c48a",
                   "bottom_style": "none", "shoes": "#f2c48a"},
        "accessories": [],
        "voice": {"profile": "cat", "speaker": "Serena", "pitch": 5.0,
                  "design": "A playful small cat character with a sly, purring voice."},
    },
    "fox": {
        "description": "A quick fox-person with a white-tipped tail.",
        "plan": "biped", "height": 1.0, "head": 0.24, "build": 0.95,
        "skin": "#e8833a",
        "face": {"style": "creature", "iris": "#7a4a1a", "iris_light": "#ffc870", "skin_line": "#8a3a1a"},
        "hair": {"style": "none", "color": "#e8833a"},
        "animal": {"ears": "fox", "tail": "fox", "snout": "fox", "fur": "#e8833a", "belly": "#fff4e8"},
        "outfit": {"top": "#3a6f4a", "top_style": "shirt", "trim": "#f0e0b0", "bottom": "#e8833a",
                   "bottom_style": "none", "shoes": "#3a2a22"},
        "accessories": [],
        "voice": {"profile": "fox", "speaker": "Aiden", "pitch": 4.0,
                  "design": "A quick-witted young fox with a bright, playful voice."},
    },
    "rabbit": {
        "description": "A gentle rabbit-person with long ears and a puff tail.",
        "plan": "biped", "height": 0.95, "head": 0.24, "build": 0.95,
        "skin": "#f4efe9",
        "face": {"style": "creature", "iris": "#9a3a5a", "iris_light": "#ff9ac0", "skin_line": "#c08a8a"},
        "hair": {"style": "none", "color": "#f4efe9"},
        "animal": {"ears": "rabbit", "tail": "puff", "fur": "#f4efe9", "belly": "#ffffff"},
        "outfit": {"top": "#f2a7b8", "top_style": "dress", "trim": "#ffffff", "bottom": "#f4efe9",
                   "bottom_style": "none", "shoes": "#f4efe9"},
        "accessories": [],
        "voice": {"profile": "girl", "speaker": "Serena", "pitch": 5.0,
                  "design": "A shy, soft-spoken little rabbit."},
    },
    "nian": {
        "description": "Nian, the New Year beast: huge, round, fluffy and gentle, with small horns and big ears.",
        "plan": "biped", "height": 2.15, "head": 0.52, "build": 2.1, "legs": 0.32,
        "skin": "#3f5f8a",
        "face": {"style": "creature", "iris": "#c27a24", "iris_light": "#ffe08a", "eye_w": 0.30, "eye_h": 0.34,
                 "eye_x": 0.36, "eye_y": 0.02, "brow": "#22324a", "brow_y": 0.36, "brow_thick": 0.06,
                 "mouth_y": -0.42, "mouth_w": 0.2, "nose": False, "line": "#1d2433", "skin_line": "#22324a",
                 "blush": "#ff9b8a", "blush_y": -0.24, "blush_x": 0.56,
                 "markings": [{"kind": "ellipse", "color": "#f3e6cf", "x": 0.0, "y": -0.38, "w": 0.52, "h": 0.34}]},
        "hair": {"style": "none", "color": "#3f5f8a"},
        "animal": {"ears": "nian", "tail": "nian", "horns": "nian", "fur": "#3f5f8a", "belly": "#f3e6cf"},
        "outfit": {"top": "#3f5f8a", "top_style": "fur", "trim": "#f3e6cf", "bottom": "#3f5f8a",
                   "bottom_style": "none", "shoes": "#2b4466"},
        "accessories": [{"kind": "scarf", "color": "#b8423a", "faded": 0.35}],
        "voice": {"profile": "creature_big", "speaker": None, "pitch": 0.0, "design": None},
    },
    "nian_cub": {
        "description": "Nian as a small cub, sixty winters ago.",
        "plan": "biped", "height": 0.8, "head": 0.25, "build": 1.25, "legs": 0.34,
        "skin": "#4a6d99",
        "face": {"style": "creature", "iris": "#c27a24", "iris_light": "#ffe08a", "eye_w": 0.34, "eye_h": 0.40,
                 "eye_x": 0.38, "brow": "#22324a", "mouth_w": 0.2, "nose": False, "line": "#1d2433",
                 "markings": [{"kind": "ellipse", "color": "#f3e6cf", "x": 0.0, "y": -0.42, "w": 0.5, "h": 0.32}]},
        "hair": {"style": "none", "color": "#4a6d99"},
        "animal": {"ears": "nian", "tail": "nian", "horns": "nub", "fur": "#4a6d99", "belly": "#f3e6cf"},
        "outfit": {"top": "#4a6d99", "top_style": "fur", "trim": "#f3e6cf", "bottom": "#4a6d99",
                   "bottom_style": "none", "shoes": "#2f4a70"},
        "accessories": [],
        "voice": {"profile": "creature_big", "speaker": None, "pitch": 9.0, "design": None},
    },
    "penguin": {
        "description": "A small round penguin with a head tuft and glossy bead eyes.",
        "plan": "penguin", "height": 0.72, "head": 0.2, "build": 1.0,
        "skin": "#232838",
        "face": {"style": "dot", "line": "#101218", "eye_w": 0.22, "eye_h": 0.28, "eye_x": 0.34, "eye_y": 0.0,
                 "brow": "#101218", "brow_y": 0.3, "brow_w": 0.24, "mouth": False, "nose": False,
                 "blush": "#ff9aa0", "blush_y": -0.26, "blush_x": 0.52,
                 "markings": [{"kind": "heart", "color": "#fbfbf7", "x": 0.0, "y": -0.05, "w": 0.86, "h": 0.8}]},
        "body": {"back": "#232838", "belly": "#fbfbf7", "beak": "#f29a2e", "feet": "#f29a2e", "tuft": 3},
        "accessories": [],
        "voice": {"profile": "penguin_kid", "speaker": "Aiden", "pitch": 5.0,
                  "design": "A small, eager penguin chick with a high, hopeful boy's voice."},
    },
    "penguin_elder": {
        "description": "An old penguin with drooping white brows and spectacles.",
        "plan": "penguin", "height": 0.98, "head": 0.22, "build": 1.2,
        "skin": "#2a2f40",
        "face": {"style": "dot", "line": "#101218", "eye_w": 0.18, "eye_h": 0.2, "eye_x": 0.32, "eye_y": 0.02,
                 "brow": "#f2f2ee", "brow_y": 0.27, "brow_w": 0.34, "brow_thick": 0.09, "mouth": False,
                 "nose": False, "blush": "#f0a0a0",
                 "markings": [{"kind": "heart", "color": "#f6f4ee", "x": 0.0, "y": -0.05, "w": 0.86, "h": 0.8}]},
        "body": {"back": "#2a2f40", "belly": "#f6f4ee", "beak": "#e08a2a", "feet": "#e08a2a", "tuft": 0},
        "accessories": [{"kind": "glasses", "color": "#8a6a3a"}],
        "voice": {"profile": "grandpa", "speaker": "Ryan", "pitch": -2.0,
                  "design": "A wise old penguin, gravelly, slow and kind, with a smile in his voice."},
    },
    "seagull": {
        "description": "A plump white gull with grey wings, black wingtips and a yellow beak.",
        "plan": "bird", "height": 0.52, "head": 0.135, "build": 1.0,
        "skin": "#fbfbf7",
        "face": {"style": "dot", "line": "#15161c", "eye_w": 0.24, "eye_h": 0.3, "eye_x": 0.36, "eye_y": 0.14,
                 "brow": "#6d7684", "brow_y": 0.46, "brow_w": 0.24, "brow_thick": 0.05, "mouth": False,
                 "nose": False, "blush": "#ffb0a8", "blush_y": -0.12, "blush_x": 0.5},
        "body": {"back": "#9aa6b6", "belly": "#f7f7f2", "beak": "#f2c230", "feet": "#f0b040", "wingtip": "#3a3f4a"},
        "accessories": [],
        "voice": {"profile": "seagull", "speaker": "Serena", "pitch": 2.0,
                  "design": "A confident, quick-talking young seagull with a bright, slightly raspy voice."},
    },
}


def _merge(base, extra):
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def resolve(entry, cid="character"):
    """A full character spec from a screenplay cast entry (`from` names an archetype)."""
    entry = dict(entry or {})
    base = entry.pop("from", "girl")
    if base not in ARCHETYPES:
        raise ValueError(f"{cid}: unknown archetype '{base}'. Library: {', '.join(ARCHETYPES)}")
    spec = _merge(ARCHETYPES[base], entry)
    spec["archetype"] = base
    spec.setdefault("name", cid.replace("_", " ").title())
    if spec["plan"] not in PLANS:
        raise ValueError(f"{cid}: unknown body plan '{spec['plan']}'")
    style = spec.get("hair", {}).get("style", "none")
    if style not in HAIR_STYLES:
        raise ValueError(f"{cid}: unknown hair style '{style}'. Styles: {', '.join(HAIR_STYLES)}")
    return spec


def metrics(spec):
    """Joint heights, limb lengths and gait constants in meters for a resolved character."""
    h, r = float(spec["height"]), float(spec["head"])
    build = float(spec.get("build", 1.0))
    plan = spec["plan"]
    if plan == "biped":
        head_z = h - r * 0.97
        neck = head_z - r * 0.80
        leg_ratio = float(spec.get("legs", 0.44 if h < 1.25 else 0.5))
        body = neck
        leg = body * leg_ratio
        hip = leg + r * 0.10
        chest = hip + (neck - hip) * 0.55
        torso_r = r * 0.8 * build
        shoulder = (torso_r * 0.86, chest + (neck - chest) * 0.5)
        arm = (shoulder[1] - hip) * 0.98 + r * 0.05
        return {"plan": plan, "height": h, "head_r": r, "head_z": head_z, "neck": neck, "chest": chest, "hip": hip,
                "leg": leg, "hip_x": torso_r * 0.42, "torso_r": torso_r, "shoulder": shoulder, "arm": arm,
                "limb_r": r * 0.15 * min(build, 1.4) ** 0.5, "hand_r": r * 0.26 * min(build, 1.6) ** 0.7,
                "foot": (r * 0.62 * min(build, 1.8) ** 0.7, r * 0.26),
                "stride": max(0.12, leg * 0.9), "cadence": 1.0, "hunch": float(spec.get("hunch", 0.0)),
                "eye_z": head_z - 0.1 * r}
    if plan == "penguin":
        body_r = h * 0.30 * build
        head_z = h - r * 0.98
        hip = h * 0.10
        return {"plan": plan, "height": h, "head_r": r, "head_z": head_z, "neck": head_z - r * 0.6,
                "chest": h * 0.42, "hip": hip, "leg": hip, "hip_x": body_r * 0.42, "torso_r": body_r,
                "shoulder": (body_r * 0.92, h * 0.52), "arm": h * 0.30, "hand_r": 0.0,
                "foot": (h * 0.13, h * 0.035), "stride": h * 0.11, "cadence": 1.6, "hunch": 0.0,
                "eye_z": head_z}
    if plan == "bird":
        hip = h * 0.3
        head_z = h - r
        return {"plan": plan, "height": h, "head_r": r, "head_z": head_z, "neck": head_z - r * 0.55,
                "chest": h * 0.5, "hip": hip, "leg": hip, "hip_x": h * 0.06, "torso_r": h * 0.2,
                "shoulder": (h * 0.12, h * 0.6), "arm": h * 1.15, "hand_r": 0.0, "foot": (h * 0.12, h * 0.02),
                "stride": h * 0.16, "cadence": 1.8, "hunch": 0.0, "eye_z": head_z}
    raise ValueError(f"Unknown body plan: {plan}")


def catalog():
    return [(name, spec["plan"], spec["description"]) for name, spec in ARCHETYPES.items()]
