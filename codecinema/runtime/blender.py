"""Launch a film's Blender script with the same settings as its Python steps.

This module is safe to import without Blender. Scene scripts run in Blender's
Python and import bpy there, rather than adding bpy to the framework's dependencies.
"""
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from codecinema.workspace import settings


def command(script, *args, blend=None, root=None, executable=None):
    """A headless command; script arguments follow Blender's ``--`` separator."""
    root = Path(root or settings.ROOT)
    script = root / script
    cmd = [executable or settings.tool("blender"), "-b", "--factory-startup", "--python-use-system-env"]
    if blend:
        cmd += [str((root / blend).resolve())]
    cmd += ["--python-exit-code", "1", "--python", str(script.resolve()), "--", *map(str, args)]
    return cmd


def run(script, *args, blend=None):
    """Run a scene builder/renderer, preserving the film and tool overrides."""
    env = dict(os.environ, CODECINEMA_FILM_DIR=settings.ROOT)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        return subprocess.run(command(script, *args, blend=blend), cwd=settings.ROOT,
                              env=env, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Blender was not found. Install Blender or set BLENDER_BIN.") from exc


def channelbag_of(id_or_obj):
    """Read the assigned action slot using Blender 5.x's animation API."""
    from bpy_extras import anim_utils
    animation = getattr(id_or_obj, "animation_data", None)
    if animation is None or animation.action is None or animation.action_slot is None:
        return None
    return anim_utils.animdata_get_channelbag_for_assigned_slot(animation)


def fcurves_of(id_or_obj, prefix=None):
    """F-curves for an object's assigned slot, optionally by data-path prefix."""
    bag = channelbag_of(id_or_obj)
    if bag is None:
        return []
    return [curve for curve in bag.fcurves
            if prefix is None or curve.data_path.startswith(prefix)]


@contextmanager
def muted_modifiers(objects=None, types=('NODES',)):
    """Defer expensive geometry evaluation while baking motion, then restore it.

    Extracted from SilverGrass's Blender utility. Render visibility is unchanged.
    Import bpy only when running this context inside Blender.
    """
    import bpy
    saved = []
    for ob in objects if objects is not None else bpy.data.objects:
        for modifier in ob.modifiers:
            if modifier.type in types and modifier.show_viewport:
                saved.append(modifier)
                modifier.show_viewport = False
    try:
        yield saved
    finally:
        for modifier in saved:
            modifier.show_viewport = True
