"""The set, lighting and prop libraries.

A set is a reusable location: a ground shape shared with the motion planner
(so feet stay on the terrain), named marks for blocking, a surface for
footsteps, an ambience bed and a default time of day. Times of day are lighting
recipes. Props are small objects characters can carry or that move on their own.
All of it is data, so screenplays override any part:

    "sets": {"village": {"from": "snow_village", "time": "night", "marks": {"well": [3, -2]}}}
"""
from __future__ import annotations

import copy
import math

SETS = {
    "stage": {
        "description": "A soft studio backdrop: quick tests, character sheets and title cards.",
        "ground": ("flat", {}), "surface": "wood", "ambience": None, "space": "room", "time": "studio",
        "marks": {"center": [0, 0], "left": [-1.5, 0], "right": [1.5, 0], "back": [0, 2], "front": [0, -1.5]},
        "params": {"floor": "#e9e2d6", "backdrop": "#cfe0ea"},
    },
    "meadow": {
        "description": "Rolling spring hills with flowers, round trees and big summer clouds.",
        "ground": ("hills", {"amp": 0.6, "scale": 0.06}), "surface": "grass", "ambience": "meadow_day",
        "space": "outdoor", "time": "morning",
        "marks": {"center": [0, 0], "hilltop": [6, 8], "tree": [-5, 5], "path": [2, -4], "far": [0, 25]},
        "params": {"grass": "#8cc26a", "flowers": 260, "trees": 14},
    },
    "beach": {
        "description": "A sunny rocky beach: sand, boulders, a turquoise sea and a cliff to the east.",
        "ground": ("beach", {}), "surface": "sand", "ambience": "beach_day", "space": "outdoor", "time": "morning",
        "marks": {"center": [0, -1], "rock": [-3.2, -1.2], "rock_top": [-3.2, -1.2, 0.95], "shore": [0, 1.6],
                  "tide": [2, 2.6], "dune": [-6, -5], "colony": [-8, -2.5], "cliff_path": [9, -1],
                  "cliff_top": [14.5, 0.5], "cliff_edge": [14.5, 2.2], "sea": [6, 14], "horizon": [0, 60],
                  "sky": [0, 20, 9], "sand_drawing": [1.2, -2.2]},
        "params": {"sand": "#f3dfae", "sea": "#33b8c9", "deep": "#1f7fa8", "rock": "#a99f98", "cliff": "#c8a27a"},
        "water": 0.0, "weather": None,
    },
    "underwater": {
        "description": "A sunlit cove under the waves: sand ripples, kelp, rocks, fish and light shafts.",
        "ground": ("seabed", {}), "surface": "none", "ambience": "underwater", "space": "underwater",
        "time": "underwater",
        "marks": {"surface": [0, 0, -0.4], "middle": [0, 6, -3], "kelp": [-4, 9, -4.5], "net": [3, 7, -3.6],
                  "bottom": [0, 8, -5.6], "rise": [1, 4, -0.6], "far": [0, 30, -4]},
        "params": {"sand": "#d9c99a", "water": "#1d8fb0", "deep": "#0b3d63", "kelp": "#3d8f5a"},
        "water": 0.0,
    },
    "snow_village": {
        "description": "A mountain village on New Year's Eve: tiled roofs, red lanterns, couplets and deep snow.",
        "ground": ("snowfield", {"amp": 0.08}), "surface": "snow", "ambience": "snow_night_village",
        "space": "outdoor", "time": "night",
        "marks": {"home_door": [0, 1.7], "yard": [0, -0.4], "lane": [5, -2.5], "lane_west": [-6, -2.5],
                  "gate": [-12, -2.2], "edge": [-17, -2.0], "square": [7, -6], "well": [3.5, -4.5]},
        "params": {"snow": "#eef3fb", "wall": "#d9cdbb", "roof": "#3b4150", "wood": "#7a3b2a", "lantern": "#e0302a"},
        "weather": "snow",
    },
    "snow_forest": {
        "description": "A hushed pine forest in deep snow, with a small clearing and a fallen log.",
        "ground": ("snowfield", {"amp": 0.25}), "surface": "snow", "ambience": "snow_forest_night",
        "space": "forest", "time": "moonlight",
        "marks": {"clearing": [0, 0], "trees": [-3, 5], "path_in": [-9, -3], "path_out": [9, -2], "rock": [2.8, 2.2],
                  "log": [-2.2, 2.6], "back": [0, 7]},
        "params": {"snow": "#eef3fb", "pine": "#2f5a4f", "bark": "#5a4034"},
        "weather": "snow",
    },
    "room": {
        "description": "A warm village kitchen: paper-cut window, a square table, stools, a stove and a lamp.",
        "ground": ("flat", {}), "surface": "wood", "ambience": "interior_warm", "space": "room",
        "time": "interior_night",
        "marks": {"table": [0, 0.6], "stool_l": [-0.75, 0.35], "stool_r": [0.75, 0.35], "window": [0, 2.3],
                  "door": [-2.6, 0.2], "stove": [2.3, 1.7], "center": [0, -0.6]},
        "params": {"floor": "#8a5a3c", "wall": "#e8d6b8", "wood": "#6b3a26", "paper": "#f6ead2"},
    },
}

TIMES = {
    "studio": {"sun": (45, 55, "#fff6ea", 3.0), "ambient": ("#d9e6f2", 0.08), "sky": ("#cfe0ea", "#eef2f4", "#e9e2d6"),
               "shadow": (0.62, 0.58, 0.80), "fog": None, "bloom": 0.15, "stars": 0, "clouds": 0},
    "morning": {"sun": (55, 40, "#fff1d6", 3.2), "ambient": ("#bcd8f0", 0.08),
                "sky": ("#5eaee8", "#cfe9f7", "#f4f0de"), "shadow": (0.58, 0.58, 0.82), "fog": ("#cfe5f2", 0.004),
                "bloom": 0.18, "stars": 0, "clouds": 0.9},
    "noon": {"sun": (40, 62, "#ffffff", 3.4), "ambient": ("#c7dcf0", 0.08), "sky": ("#4aa2e6", "#bfe2f6", "#eef3ea"),
             "shadow": (0.58, 0.60, 0.84), "fog": ("#d6eaf5", 0.003), "bloom": 0.15, "stars": 0, "clouds": 1.0},
    "golden": {"sun": (130, 18, "#ffd59a", 3.0), "ambient": ("#f2c9a6", 0.07), "sky": ("#6f9fd6", "#ffd9a8", "#ffe8c4"),
               "shadow": (0.62, 0.50, 0.78), "fog": ("#ffe1bd", 0.005), "bloom": 0.3, "stars": 0, "clouds": 0.7},
    "sunset": {"sun": (160, 7, "#ffb070", 2.6), "ambient": ("#e8a8a0", 0.07), "sky": ("#5a5fa8", "#ff9f6e", "#ffc98a"),
               "shadow": (0.58, 0.44, 0.74), "fog": ("#f6b48c", 0.006), "bloom": 0.4, "stars": 0.1, "clouds": 0.6},
    "dusk": {"sun": (-80, 10, "#c9a0ff", 1.2), "ambient": ("#7a74b8", 0.08), "sky": ("#2a2f6b", "#8a6aa8", "#d89a9a"),
             "shadow": (0.45, 0.42, 0.72), "fog": ("#6a5f98", 0.008), "bloom": 0.45, "stars": 0.4, "clouds": 0.4},
    "night": {"sun": (-40, 38, "#9fb8ff", 0.9), "ambient": ("#3a4a80", 0.12), "sky": ("#0b1233", "#24305e", "#3a3f66"),
              "shadow": (0.38, 0.42, 0.70), "fog": ("#1e2850", 0.012), "bloom": 0.6, "stars": 1.0, "clouds": 0.15},
    "moonlight": {"sun": (-30, 42, "#b8ccff", 1.1), "ambient": ("#3f5590", 0.14),
                  "sky": ("#0e1a40", "#2c3d72", "#46507a"), "shadow": (0.40, 0.46, 0.74),
                  "fog": ("#22305c", 0.03), "bloom": 0.55, "stars": 1.0, "clouds": 0.1},
    "storm": {"sun": (20, 45, "#c8d2e0", 1.4), "ambient": ("#5a6478", 0.1), "sky": ("#3a4252", "#6c7686", "#7c8494"),
              "shadow": (0.5, 0.52, 0.62), "fog": ("#5c6676", 0.02), "bloom": 0.2, "stars": 0, "clouds": 1.0},
    "underwater": {"sun": (20, 70, "#c8fff4", 2.6), "ambient": ("#2a8fb0", 0.25),
                   "sky": ("#7fe3ea", "#1f87ad", "#1f87ad"), "shadow": (0.42, 0.62, 0.78),
                   "fog": ("#1f87ad", 0.045), "bloom": 0.35, "stars": 0, "clouds": 0},
    "memory": {"sun": (60, 30, "#ffe0b0", 3.0), "ambient": ("#f0d0a8", 0.1), "sky": ("#c9b48a", "#f2dcb0", "#f6e8c8"),
               "shadow": (0.66, 0.56, 0.62), "fog": ("#f0dcb8", 0.02), "bloom": 0.35, "stars": 0, "clouds": 0.4},
    "interior_night": {"sun": (35, 50, "#ffcf8a", 1.2), "ambient": ("#7a5a48", 0.12),
                       "sky": ("#1a1f3a", "#2a3050", "#3a3a58"), "shadow": (0.55, 0.42, 0.52), "fog": None,
                       "bloom": 0.5, "stars": 0.3, "clouds": 0},
    "interior_day": {"sun": (40, 45, "#fff2dc", 2.2), "ambient": ("#e8d8c0", 0.12),
                     "sky": ("#9fd0f0", "#e0f0fa", "#f0ebe0"), "shadow": (0.62, 0.55, 0.66), "fog": None,
                     "bloom": 0.2, "stars": 0, "clouds": 0.5},
}

PROPS = {
    "lantern": {"description": "A round red paper lantern with gold tassels; glows when lit.",
                "color": "#e0302a", "trim": "#f2c14e", "size": 0.38, "glow": 1.0},
    "hand_lantern": {"description": "A small red lantern on a short stick, carried at night.",
                     "color": "#e64a32", "trim": "#f2c14e", "size": 0.16, "glow": 1.0},
    "bowl": {"description": "A blue-and-white bowl of steaming dumplings.", "color": "#f4f1ea", "trim": "#3a6ab0",
             "size": 0.14, "dumplings": 5},
    "dumpling": {"description": "A single plump dumpling.", "color": "#f8f2e4", "size": 0.05},
    "scarf": {"description": "A knitted red scarf with fringes.", "color": "#c8322b", "size": 0.9},
    "earmuffs": {"description": "Pink fluffy earmuffs.", "color": "#f2c4d4", "band": "#c94a6a", "size": 0.16},
    "firecrackers": {"description": "A string of red firecrackers hanging from a bamboo pole.", "color": "#d22a22",
                     "size": 1.4},
    "table": {"description": "A square wooden table.", "color": "#6b3a26", "size": 0.8},
    "stool": {"description": "A small wooden stool.", "color": "#7a4a2e", "size": 0.32},
    "leaf_wings": {"description": "Two big palm leaves tied on as wings.", "color": "#5aa04a", "size": 0.55},
    "fish": {"description": "A small silver fish.", "color": "#b8c8d8", "size": 0.12},
    "net": {"description": "A tangle of old fishing net with a float.", "color": "#7f8a7a", "size": 0.6},
    "shell": {"description": "A pink scallop shell.", "color": "#f4b8a8", "size": 0.08},
    "crab": {"description": "A little red crab.", "color": "#e0503a", "size": 0.12},
    "kite": {"description": "A diamond kite with a ribboned tail.", "color": "#e0503a", "size": 0.6},
    "rock": {"description": "A rounded boulder.", "color": "#a99f98", "size": 0.8},
    "star": {"description": "A small glowing star.", "color": "#ffe27a", "size": 0.15, "glow": 3.0},
}

FX = ("splash", "big_splash", "bubbles", "sparkles", "dust", "snow_puff", "fireworks", "firecracker_burst",
      "smoke", "steam", "hearts", "tears", "ripples", "light_burst", "sweat")


def ground_height(kind, params, x, y):
    """Terrain height (meters) at (x, y): the one definition the rig, the planner and the set builder share."""
    if kind == "flat":
        return 0.0
    if kind == "hills":
        a, s = params.get("amp", 0.6), params.get("scale", 0.06)
        h = a * (math.sin(x * s * 1.3) * math.cos(y * s) + 0.5 * math.sin((x + y) * s * 2.1))
        return h * min(1.0, math.hypot(x, y) / 6.0)
    if kind == "beach":
        # Sand slopes gently under the water (the shoreline is near y = 2.5); a cliff rises east of x = 10
        # and ends in a sheer drop into deep water at y ~ 3.
        sand = 0.12 - 0.05 * y + 0.12 * math.sin(x * 0.35) * math.cos(y * 0.4)
        sand += 0.35 * math.exp(-((x + 7) ** 2 + (y + 6) ** 2) / 12.0)
        cliff = 3.6 / (1 + math.exp(-(x - 10.5) * 1.6)) / (1 + math.exp((y - 3.0) * 2.5))
        return sand if cliff < 0.05 else max(sand, cliff)
    if kind == "seabed":
        return -6.0 + 0.25 * math.sin(x * 0.7) * math.cos(y * 0.5) + 0.6 * math.exp(-((x + 5) ** 2) / 10.0)
    if kind == "snowfield":
        a = params.get("amp", 0.1)
        return a * (math.sin(x * 0.4) * math.cos(y * 0.33) + 0.5 * math.sin((x - y) * 0.71))
    raise ValueError(f"Unknown ground: {kind}")


def resolve(entry, sid):
    entry = dict(entry or {})
    base = entry.pop("from", sid)
    if base not in SETS:
        raise ValueError(f"set '{sid}': unknown base '{base}'. Library: {', '.join(SETS)}")
    spec = copy.deepcopy(SETS[base])
    marks = entry.pop("marks", {})
    params = entry.pop("params", {})
    spec.update(entry)
    spec["marks"].update(marks)
    spec["params"].update(params)
    spec["kind"] = base
    if spec["time"] not in TIMES:
        raise ValueError(f"set '{sid}': unknown time '{spec['time']}'")
    return spec


def resolve_prop(entry, pid):
    entry = dict(entry or {})
    base = entry.pop("from", pid)
    if base not in PROPS:
        raise ValueError(f"prop '{pid}': unknown base '{base}'. Library: {', '.join(PROPS)}")
    spec = copy.deepcopy(PROPS[base])
    spec.update(entry)
    spec["kind"] = base
    return spec


def ground_function(spec):
    kind, params = spec["ground"]
    return lambda x, y: ground_height(kind, params, x, y)


def catalog():
    return {"sets": [(k, v["description"]) for k, v in SETS.items()], "times": list(TIMES),
            "props": [(k, v["description"]) for k, v in PROPS.items()], "fx": list(FX)}
