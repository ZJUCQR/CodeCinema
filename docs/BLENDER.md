# Blender in CodeCinema

CodeCinema includes a complete Blender production: [Duel in the Silver Grass](../films/silvergrass/README.md). Blender is one of the framework's supported renderers. The starter and the opening trilogy use Skia. Each film declares its own renderer and production steps.

Install [Blender 5.2 or later](https://www.blender.org/download/) and follow the [framework installation guide](GETTING_STARTED.md). Standard installation locations and `PATH` are detected. Set `BLENDER_BIN` if Blender is elsewhere.

## Follow the existing production

From the repository root:

```bash
codecinema run silvergrass check
codecinema run silvergrass build
```

The first command checks the toolchain. The second builds the rigged, animated scene without rendering the whole film. See the film's [guide](../films/silvergrass/README.md) for rendering and assembly.

| Existing source | Responsibility |
| --- | --- |
| [characters.py](../films/silvergrass/src/blender/characters.py) | Two-duelist rigs, IK/FK and anatomical dimensions |
| [character_meshes.py](../films/silvergrass/src/blender/character_meshes.py) | Procedural character meshes and materials |
| [poses.py](../films/silvergrass/src/blender/poses.py) / [moves.py](../films/silvergrass/src/blender/moves.py) | Pose macros, world-space foot planting, gait and fight choreography |
| [secondary.py](../films/silvergrass/src/blender/secondary.py) | Cloth, hair and beard response to motion, wind and rain |
| [cameras.py](../films/silvergrass/src/blender/cameras.py) | Shot markers, lenses, focus and camera movement |
| [render_setup.py](../films/silvergrass/src/blender/render_setup.py) / [render_frames.py](../films/silvergrass/src/blender/render_frames.py) | EEVEE settings, color management, motion blur and resumable frame rendering |
| [audio/score.py](../films/silvergrass/src/audio/score.py) | Music arranged against the film's action events |

These modules share SilverGrass's two-character configuration, bone conventions, time warps and choreography lanes. Importing its walking or secondary-motion modules directly into an unrelated cast does not create a compatible rig. Its scene design remains inside that film.

## Reuse the shared Blender tools

The renderer-neutral launcher and selected Blender utilities extracted from SilverGrass live in [`codecinema.blender`](../codecinema/blender.py). Importing this module in ordinary Python does not import `bpy`.

```python
# In films/<id>/src/run.py, with CODECINEMA_FILM_DIR set by the CLI:
from codecinema import blender

blender.run("src/build_scene.py", "--quality", "preview")
```

`run()` uses the active film directory, tool overrides and Blender's background mode. Script arguments follow Blender's `--` separator. Blender script failures return a nonzero exit code. `command()` returns the same argument list for supervisors that manage their own processes; it also accepts `blend=`, `root=` and `executable=`.

Inside a Blender script:

```python
from codecinema.blender import fcurves_of, muted_modifiers

with muted_modifiers(types=("SUBSURF", "ARMATURE", "SOLIDIFY")):
    bake_motion()

for curve in fcurves_of(camera, "location"):
    for key in curve.keyframe_points:
        key.interpolation = "LINEAR"
```

`muted_modifiers()` restores viewport flags even when baking raises an exception; render visibility is unchanged. `channelbag_of()` and `fcurves_of()` use Blender 5.x's assigned action slots, rather than the removed legacy action API. SilverGrass calls these same shared helpers.

[`codecinema.audio.performance`](../codecinema/audio/performance.py) is also usable inside Blender. Its `Performance.mouth(time, character)` returns speech activity and syllable shapes from the final recorded take. Use the shot's own time in seconds and the same audio start offset when muxing. Narration and thoughts must not drive a visible character's mouth. See the [speech guide](SPEECH.md).
