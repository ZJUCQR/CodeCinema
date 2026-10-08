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

HAIR_STYLES = ("none", "short", "spiky", "bob", "buns", "twintails", "ponytail", "braids", "elder_bun", "bald", "long",
               "curly", "afro")
# Torso silhouettes: how the width changes from the hem (0) to the neck (1), and shoulder and hip widths.
SHAPES = {
    "egg": {"profile": ((0.0, 1.0), (1.0, 1.0)), "chest": 1.0, "hips": 1.0},
    "pear": {"profile": ((0.0, 1.16), (0.45, 1.04), (0.8, 0.9), (1.0, 0.88)), "chest": 0.92, "hips": 1.12},
    "barrel": {"profile": ((0.0, 0.98), (0.3, 1.2), (0.55, 1.16), (0.85, 0.96), (1.0, 0.9)), "chest": 1.02, "hips": 1.0},
    "slim": {"profile": ((0.0, 0.86), (1.0, 0.84)), "chest": 0.9, "hips": 0.9},
    "broad": {"profile": ((0.0, 0.9), (0.4, 0.95), (0.75, 1.16), (1.0, 1.08)), "chest": 1.15, "hips": 0.95},
    "round": {"profile": ((0.0, 1.05), (0.35, 1.14), (0.7, 1.08), (1.0, 0.95)), "chest": 1.0, "hips": 1.05},
}
HATS = ("cap", "beanie", "straw", "chef", "top", "beret", "party")
ACCESSORIES = ("glasses", "scarf", "earmuffs", "ribbon", "hat", "mustache", "bowtie", "backpack")

ARCHETYPES = {
    "girl": {
        "shape": "round", "sheet": {"act": "wave", "at": 0.75, "facing": -35},
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
        "shape": "slim", "sheet": {"act": "point", "at": 0.9, "facing": 30},
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
        "shape": "pear", "head_shape": (0.96, 0.94, 0.99), "sheet": {"act": "hand_on_heart", "at": 0.8, "facing": -15},
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
        "shape": "broad", "head_shape": (1.02, 0.96, 0.97), "sheet": {"act": "clap", "at": 0.45, "facing": 25},
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
        "shape": "pear", "sheet": {"act": "hold", "at": 0.8, "facing": -30},
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
        "shape": "barrel", "head_shape": (1.04, 0.96, 0.92), "sheet": {"act": "think", "at": 0.8, "facing": 35},
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
        "shape": "slim", "sheet": {"act": "tilt", "at": 0.8, "facing": -25},
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
        "shape": "slim", "sheet": {"act": "beckon", "at": 0.6, "facing": 40},
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
        "shape": "round", "sheet": {"act": "hop", "at": 0.12, "facing": -10},
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
        "sheet": {"act": "wave_both", "at": 0.6, "facing": 15},
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
        "sheet": {"act": "sit", "at": 1.0, "facing": -35},
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
        "sheet": {"act": "flap", "at": 0.2, "facing": 30},
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
        "sheet": {"act": "nod", "at": 0.4, "facing": -35},
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
        "sheet": {"act": "tilt", "at": 0.8, "facing": 40},
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
    "toddler": {
        "description": "A two-year-old: a big round head, a round tummy and short legs.",
        "plan": "biped", "height": 0.8, "head": 0.27, "build": 1.08, "legs": 0.36, "shape": "round",
        "head_shape": (1.0, 0.97, 0.97),
        "skin": "#fbe3d3",
        "face": {"iris": "#4a3020", "iris_light": "#c89060", "eye_h": 0.46, "eye_w": 0.36},
        "hair": {"style": "curly", "color": "#c98a4a"},
        "outfit": {"top": "#f2c94c", "top_style": "padded", "trim": "#6fb3d9", "bottom": "#6fb3d9",
                   "bottom_style": "shorts", "shoes": "#e2554a"},
        "accessories": [],
        "voice": {"profile": "girl", "speaker": "Vivian", "pitch": 6.0,
                  "design": "A babbling two-year-old with a very high, giggly voice."},
        "sheet": {"act": "cheer", "at": 0.45, "facing": 15},
    },
    "teen": {
        "description": "A tall, slim teenager with long hair and a knitted beanie.",
        "plan": "biped", "height": 1.5, "head": 0.185, "build": 0.88, "legs": 0.53, "shape": "slim",
        "head_shape": (0.95, 0.93, 1.0),
        "skin": "#f3d2bd",
        "face": {"iris": "#2f4a6a", "iris_light": "#8ab8e8", "lashes": True, "eye_h": 0.36},
        "hair": {"style": "long", "color": "#3a2a2a"},
        "outfit": {"top": "#5b8a72", "top_style": "shirt", "trim": "#f2efe6", "bottom": "#2f3a55",
                   "bottom_style": "pants", "shoes": "#f2efe6"},
        "accessories": [{"kind": "hat", "style": "beanie", "color": "#e0a03a"}],
        "voice": {"profile": "woman", "speaker": "Serena", "pitch": 1.5,
                  "design": "A cheerful teenage girl, quick and bright."},
        "sheet": {"act": "point", "at": 0.8, "facing": -40},
    },
    "chef": {
        "description": "A round, jolly cook with a tall white hat and a twirled moustache.",
        "plan": "biped", "height": 1.42, "head": 0.205, "build": 1.4, "shape": "barrel",
        "skin": "#f0c8a8",
        "face": {"iris": "#3a2a22", "iris_light": "#8a6a52", "eye_h": 0.32, "brow_thick": 0.07},
        "hair": {"style": "short", "color": "#4a3428"},
        "outfit": {"top": "#f6f4ee", "top_style": "coat", "trim": "#c0392b", "bottom": "#3a3a46",
                   "bottom_style": "pants", "shoes": "#2b2222"},
        "accessories": [{"kind": "hat", "style": "chef"}, {"kind": "mustache", "color": "#4a3428"}],
        "voice": {"profile": "man", "speaker": "Uncle_Fu", "pitch": 1.0,
                  "design": "A jolly cook with a booming, warm voice."},
        "sheet": {"act": "offer", "at": 0.8, "facing": 25},
    },
    "dog": {
        "description": "A friendly dog-person with floppy ears and a wagging tail.",
        "plan": "biped", "height": 1.02, "head": 0.25, "build": 1.0, "shape": "egg",
        "skin": "#c98a52",
        "face": {"style": "creature", "iris": "#4a2a1a", "iris_light": "#c88a50", "skin_line": "#7a4a2a",
                 "mouth_y": -0.66},
        "hair": {"style": "none", "color": "#c98a52"},
        "animal": {"ears": "dog", "tail": "dog", "snout": "dog", "fur": "#c98a52", "belly": "#f7e8d4",
                   "inner": "#8a5a3a", "ear_color": "#7a4a2a"},
        "outfit": {"top": "#d9534f", "top_style": "shirt", "trim": "#ffffff", "bottom": "#c98a52",
                   "bottom_style": "none", "shoes": "#c98a52"},
        "accessories": [],
        "voice": {"profile": "fox", "speaker": "Aiden", "pitch": 2.0,
                  "design": "A loyal, excitable young dog with a happy voice."},
        "sheet": {"act": "wave", "at": 0.7, "facing": -30},
    },
    "bear": {
        "description": "A big, gentle bear with round ears, a soft belly and a bow tie.",
        "plan": "biped", "height": 1.45, "head": 0.27, "build": 1.6, "shape": "round", "legs": 0.36,
        "skin": "#8a5a3a",
        "face": {"style": "creature", "iris": "#2a1a12", "iris_light": "#7a5a3a", "eye_w": 0.26, "eye_h": 0.3,
                 "skin_line": "#4a2a1a", "mouth_y": -0.64},
        "hair": {"style": "none", "color": "#8a5a3a"},
        "animal": {"ears": "bear", "tail": "puff", "snout": "bear", "fur": "#8a5a3a", "belly": "#e8c9a0",
                   "inner": "#c99a70"},
        "outfit": {"top": "#8a5a3a", "top_style": "fur", "trim": "#e8c9a0", "bottom": "#8a5a3a",
                   "bottom_style": "none", "shoes": "#6a4228"},
        "accessories": [{"kind": "bowtie", "color": "#3a6fb0"}],
        "voice": {"profile": "man", "speaker": "Uncle_Fu", "pitch": -3.0,
                  "design": "A big, slow, gentle bear with a deep, soft voice."},
        "sheet": {"act": "hug", "at": 0.7, "facing": 20},
    },
    "panda": {
        "description": "A round panda with black ears, eye patches and limbs.",
        "plan": "biped", "height": 1.2, "head": 0.27, "build": 1.5, "shape": "round", "legs": 0.36,
        "skin": "#f6f4ee",
        "face": {"style": "creature", "iris": "#1a1a1a", "iris_light": "#8a8a8a", "eye_w": 0.24, "eye_h": 0.3,
                 "skin_line": "#2a2a2a", "mouth_y": -0.64,
                 "markings": [{"kind": "ellipse", "color": "#2a2a30", "x": -0.36, "y": -0.02, "w": 0.36, "h": 0.44},
                              {"kind": "ellipse", "color": "#2a2a30", "x": 0.36, "y": -0.02, "w": 0.36, "h": 0.44}]},
        "hair": {"style": "none", "color": "#f6f4ee"},
        "animal": {"ears": "bear", "tail": "puff", "snout": "bear", "fur": "#f6f4ee", "belly": "#ffffff",
                   "ear_color": "#2a2a30", "limbs": "#2a2a30", "inner": "#3a3a42"},
        "outfit": {"top": "#f6f4ee", "top_style": "fur", "trim": "#ffffff", "bottom": "#2a2a30",
                   "bottom_style": "none", "shoes": "#2a2a30"},
        "accessories": [],
        "voice": {"profile": "boy", "speaker": "Aiden", "pitch": 1.0,
                  "design": "A sleepy, sweet young panda with a soft, slow voice."},
        "sheet": {"act": "eat", "at": 0.6, "facing": -25},
    },
    "mouse": {
        "description": "A tiny mouse with big round ears and a long thin tail.",
        "plan": "biped", "height": 0.78, "head": 0.24, "build": 0.9, "shape": "pear", "legs": 0.4,
        "skin": "#a9a3a8",
        "face": {"style": "creature", "iris": "#1a1a22", "iris_light": "#8a8aa0", "skin_line": "#5a5458"},
        "hair": {"style": "none", "color": "#a9a3a8"},
        "animal": {"ears": "mouse", "tail": "mouse", "snout": "mouse", "fur": "#a9a3a8", "belly": "#efe7ea",
                   "inner": "#f2b3c0"},
        "outfit": {"top": "#f0d36a", "top_style": "dress", "trim": "#ffffff", "bottom": "#a9a3a8",
                   "bottom_style": "none", "shoes": "#a9a3a8"},
        "accessories": [],
        "voice": {"profile": "small_bird", "speaker": "Vivian", "pitch": 7.0,
                  "design": "A tiny, quick, squeaky mouse."},
        "sheet": {"act": "tilt", "at": 0.8, "facing": 35},
    },
    "pig": {
        "description": "A cheerful round pig with a flat snout and a curly tail.",
        "plan": "biped", "height": 1.0, "head": 0.25, "build": 1.35, "shape": "barrel", "legs": 0.38,
        "skin": "#f5b6b8",
        "face": {"style": "creature", "iris": "#3a2228", "iris_light": "#b07080", "skin_line": "#c07078",
                 "blush": "#ff8a90", "mouth_y": -0.72, "eye_y": 0.08, "eye_h": 0.4, "blush_y": -0.18},
        "hair": {"style": "none", "color": "#f5b6b8"},
        "animal": {"ears": "pig", "tail": "pig", "snout": "pig", "fur": "#f5b6b8", "belly": "#fbd3d4",
                   "inner": "#e8909a"},
        "outfit": {"top": "#7fbf6a", "top_style": "shirt", "trim": "#ffffff", "bottom": "#f5b6b8",
                   "bottom_style": "none", "shoes": "#c97a80"},
        "accessories": [],
        "voice": {"profile": "boy", "speaker": "Aiden", "pitch": 2.0,
                  "design": "A cheerful, chuckling young pig."},
        "sheet": {"act": "laugh", "at": 0.5, "facing": -20},
    },
    "duck": {
        "description": "A white duck with a flat orange bill and a curl on its head.",
        "plan": "penguin", "height": 0.62, "head": 0.2, "build": 0.95,
        "skin": "#fbfbf7",
        "face": {"style": "dot", "line": "#101218", "eye_w": 0.2, "eye_h": 0.26, "eye_x": 0.36, "eye_y": 0.06,
                 "brow": "#9a9a94", "brow_y": 0.34, "brow_w": 0.22, "mouth": False, "nose": False,
                 "blush": "#ffb0b0", "blush_y": -0.2, "blush_x": 0.5},
        "body": {"back": "#fbfbf7", "belly": "#ffffff", "beak": "#f59a2a", "feet": "#f59a2a", "tuft": 1,
                 "bill": "flat"},
        "accessories": [],
        "voice": {"profile": "small_bird", "speaker": "Serena", "pitch": 3.0,
                  "design": "A fussy, quacky little duck."},
        "sheet": {"act": "flap", "at": 0.3, "facing": 30},
    },
    "chick": {
        "description": "A fluffy yellow chick, round as a ball.",
        "plan": "penguin", "height": 0.42, "head": 0.16, "build": 1.2,
        "skin": "#f8d64e",
        "face": {"style": "dot", "line": "#101218", "eye_w": 0.24, "eye_h": 0.3, "eye_x": 0.34, "eye_y": 0.04,
                 "brow": "#c9a020", "brow_y": 0.34, "brow_w": 0.2, "mouth": False, "nose": False,
                 "blush": "#ff9a80", "blush_y": -0.22, "blush_x": 0.5},
        "body": {"back": "#f8d64e", "belly": "#fbe68a", "beak": "#f29a2e", "feet": "#f29a2e", "tuft": 3},
        "accessories": [],
        "voice": {"profile": "small_bird", "speaker": "Vivian", "pitch": 8.0,
                  "design": "A tiny chick with a cheeping, very high voice."},
        "sheet": {"act": "hop", "at": 0.15, "facing": -30},
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
    if spec.get("shape", "egg") not in SHAPES:
        raise ValueError(f"{cid}: unknown body shape '{spec['shape']}'. Shapes: {', '.join(SHAPES)}")
    for item in spec.get("accessories", []):
        if item.get("kind") not in ACCESSORIES:
            raise ValueError(f"{cid}: unknown accessory '{item.get('kind')}'. Accessories: {', '.join(ACCESSORIES)}")
        if item["kind"] == "hat" and item.get("style", "cap") not in HATS:
            raise ValueError(f"{cid}: unknown hat '{item.get('style')}'. Hats: {', '.join(HATS)}")
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
        shape = SHAPES[spec.get("shape", "egg")]
        shoulder = (torso_r * 0.86 * shape["chest"], chest + (neck - chest) * 0.5)
        arm = (shoulder[1] - hip) * 0.98 + r * 0.05
        return {"plan": plan, "height": h, "head_r": r, "head_z": head_z, "neck": neck, "chest": chest, "hip": hip,
                "leg": leg, "hip_x": torso_r * 0.42 * shape["hips"], "torso_r": torso_r, "shoulder": shoulder,
                "arm": arm,
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
                "foot": (h * 0.13, h * 0.035), "stride": h * 0.2, "cadence": 1.6, "hunch": 0.0,
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
