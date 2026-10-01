"""
cast.py - breeds, costumes and the characters of the film (one Character per costume variant).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common"))

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paint"))
from cat import Breed  # noqa: E402
from character import Character  # noqa: E402

BREEDS = dict(
    maine_coon=Breed("maine_coon", "#8a7a66", light="#efe6d6", dark="#4a3d31", pattern="tabby", eye="#c9a23a",
                     tufts=True, ruff=True, fluff=1.3, seed=1),
    ginger=Breed("ginger", "#e39a4f", light="#f7e2c4", dark="#b0612a", pattern="tabby", eye="#b8c24a", seed=2),
    persian=Breed("persian", "#f4efe6", light="#ffffff", dark="#cfc6b8", face="flat", eye="#6fa3d6", cheek=1.15,
                  fluff=1.4, seed=3),
    siamese=Breed("siamese", "#efe3cc", light="#fbf5ea", dark="#5a4034", mask="#5b4136", face="wedge", ear_size=1.25,
                  eye="#5f9fd9", seed=4),
    sphynx=Breed("sphynx", "#e8bfae", light="#f2d6ca", dark="#b98c7c", hairless=True, ear_size=1.35, eye="#9bc46a",
                 seed=5),
    fold=Breed("fold", "#b9b6b3", light="#e9e6e2", dark="#7d7a78", ears="fold", eye="#d9a441", seed=6),
    tuxedo=Breed("tuxedo", "#2c2a2c", light="#f4f1ea", dark="#141214", pattern="tuxedo", eye="#d7c14a", seed=7),
    calico=Breed("calico", "#f6f1e7", light="#ffffff", dark="#c9c0b0",
                 patches=[("#e0923f", 30, -24, 24), ("#2d2a2a", -44, -30, 18)], eye="#d8b24a", seed=8),
    russian_blue=Breed("russian_blue", "#8d98a6", light="#c9d0d8", dark="#5d6773", eye="#6fbf73", seed=9),
    cream_bsh=Breed("cream_bsh", "#e6cfa2", light="#f6ead2", dark="#b89a66", face="flat", cheek=1.1, eye="#d98a3a",
                    seed=10),
    munchkin=Breed("munchkin", "#a8825e", light="#f1e4d0", dark="#6c4c30", pattern="tabby", eye="#c8b04a", seed=11),
    abyssinian=Breed("abyssinian", "#b8743f", light="#e9c9a4", dark="#7a4520", ear_size=1.15, face="wedge",
                     eye="#9ab04a", seed=12),
    kitten=Breed("kitten", "#9c7a58", light="#efe0c8", dark="#5a3f28", pattern="tabby", eye="#8fb84a", seed=13),
)
B = BREEDS

ROBE_HAN = dict(kind="robe", color="#3b3a3f", trim="#26252a", hat="tall", tail_len=170, tail_fluff=1.2)


def make_cast():
    C = _make()
    import config
    for ch in C.values():
        ch.scale *= config.SS
    return C


def _make():
    C = {}
    C["han"] = Character("han", B["maine_coon"], dict(ROBE_HAN), "cross", scale=1.12)
    C["han_stand"] = Character("han", B["maine_coon"], dict(ROBE_HAN), "stand", scale=1.12)
    C["han_open"] = Character("han", B["maine_coon"], dict(ROBE_HAN, color="#e9e2d2", trim="#8a8474", open=1.0),
                              "cross", scale=1.12)
    C["han_yellow"] = Character("han", B["maine_coon"], dict(ROBE_HAN, color="#c9a458", trim="#7d6230"), "stand",
                                scale=1.12)
    C["lang"] = Character("lang", B["ginger"], dict(kind="robe", color="#b8322a", trim="#7c1f1a", hat="futou"), "cross",
                          scale=1.0)
    C["lang_stand"] = Character("lang", B["ginger"], dict(kind="robe", color="#b8322a", trim="#7c1f1a", hat="futou"),
                                "stand", scale=1.0)
    C["li"] = Character("li", B["persian"], dict(kind="dress", color="#8fb3c9", jacket="#e9e2d0", trim="#c65a4a",
                                                  shawl="#d9c27a", hat="bun", flower="#e07a8a"), "stool", scale=0.98)
    C["jiaming"] = Character("jiaming", B["tuxedo"], dict(kind="robe", color="#9aa77d", trim="#5e6a45", hat="futou"),
                             "stool", scale=1.0)
    C["jiaming_stand"] = Character("jiaming", B["tuxedo"], dict(kind="robe", color="#9aa77d", trim="#5e6a45",
                                                                 hat="futou"), "stand", scale=1.0)
    C["guest_green"] = Character("zhu", B["cream_bsh"], dict(kind="robe", color="#4f7a5a", trim="#2f4a36",
                                                             hat="futou"), "stool", scale=1.0)
    C["guest_blue"] = Character("chen", B["russian_blue"], dict(kind="robe", color="#5b6f8f", trim="#394760",
                                                                hat="futou"), "stool", scale=1.0)
    C["wang"] = Character("wang", B["siamese"], dict(kind="dress", color="#4f7fb3", jacket="#cfe0ea", trim="#e0a040",
                                                      shawl="#e8b7c2", sleeve=1.2, water=170, hat="bun",
                                                      flower="#f0f0e0"), "stand", scale=1.0)
    C["monk"] = Character("monk", B["sphynx"], dict(kind="kasaya", color="#b5863f", trim="#7a5424", tail_len=130),
                          "stand", scale=1.0)
    C["flute_calico"] = Character("calico", B["calico"], dict(kind="dress", color="#6c9a6e", jacket="#f0e6d2",
                                                               trim="#c65a4a", shawl="#e8b7c2", hat="bun",
                                                               flower="#e05a5a"), "stand", scale=0.95)
    C["flute_blue"] = Character("rblue", B["russian_blue"], dict(kind="dress", color="#c0473a", jacket="#efe4cc",
                                                                  trim="#3f6f8f", shawl="#d9c27a", hat="bun",
                                                                  flower="#f0d060"), "stand", scale=0.95)
    C["flute_fold"] = Character("fold", B["fold"], dict(kind="dress", color="#d8b25a", jacket="#f3ead6",
                                                         trim="#8a3a2a", shawl="#9fc3d0", hat="bun",
                                                         flower="#f08aa0"), "stand", scale=0.95)
    C["bili"] = Character("abyssinian", B["abyssinian"], dict(kind="dress", color="#7a5a9a", jacket="#efe4cc",
                                                              trim="#d0a040", shawl="#f0d8a0", hat="bun",
                                                              flower="#ffffff"), "stand", scale=0.95)
    C["attendant"] = Character("munchkin", B["munchkin"], dict(kind="dress", color="#b56a5a", jacket="#f1e6d0",
                                                                trim="#445f7a", hat="bun", flower="#f0c040"),
                               "stand", scale=0.8)
    C["attendant2"] = Character("abyss", B["abyssinian"], dict(kind="dress", color="#5f8a86", jacket="#efe4cc",
                                                                trim="#a0402a", hat="bun", flower="#f0f0f0"),
                                "stand", scale=0.88)
    C["kitten"] = Character("gu", B["kitten"], dict(kind="robe", color="#8c8a80", trim="#5a584e", hat="futou",
                                                     tail_len=110), "stand", scale=0.62)
    C["lady_cross"] = Character("li", B["persian"], dict(kind="dress", color="#c98a9a", jacket="#f3ead6",
                                                          trim="#5a7a9a", hat="bun", flower="#f0f0f0"), "cross",
                                scale=0.95)
    C["guest_green_stand"] = Character("zhu", B["cream_bsh"], dict(kind="robe", color="#4f7a5a", trim="#2f4a36",
                                                                   hat="futou"), "stand", scale=1.0)
    C["guest_blue_stand"] = Character("chen", B["russian_blue"], dict(kind="robe", color="#5b6f8f", trim="#394760",
                                                                      hat="futou"), "stand", scale=1.0)
    return C
