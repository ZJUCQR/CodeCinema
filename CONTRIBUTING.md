# Contributing to CodeCinema

CodeCinema welcomes improvements to templates, Studio, renderer integrations, shared production tools and documentation.

## Set up

Follow the [getting-started guide](README.md#quick-start) for Python 3.12+, FFmpeg and the system libraries required on your platform. Run the following commands from the repository root. On Windows, use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`:

```bash
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

Skia projects do not require Blender. Blender projects require Blender 5.2 or later.

## Make a change

- For a starter look, update the preset data in `codecinema/workspace/story.py` and the rendering palette in `codecinema/renderers/palettes.py`. Include an actual rendered thumbnail for Studio.
- For an editor improvement, update `codecinema/studio/server.py`, `codecinema/studio/jobs.py` or `assets/_shared/studio/`. Check both languages and a narrow mobile viewport.
- For a renderer, implement the plugin interface below. Keep backend code in the framework or an installed package and keep film folders free of production scripts.
- For documentation, keep English and Chinese setup instructions consistent. Describe the current behavior and provide commands a newcomer can copy.

Generated videos, render caches, recordings and local settings stay outside Git. A release contains finished MP4s. Development reports stay local.

## Check your work

```bash
.venv/bin/python -m compileall -q codecinema
.venv/bin/python -m codecinema list
.venv/bin/python -m codecinema new checkfilm --preset aurora --duration 3 --quality preview --render
```

For media changes, inspect the sample's picture, sound and duration. Use a temporary workspace to check behavior such as preserving an existing master or handling an invalid project. CI checks project creation and imports on macOS, Linux and Windows, and renders a short sample on Linux.

Open a focused pull request explaining the problem, the resulting behavior and the checks you ran. Include a screenshot or short preview when the visual result changes. Report bugs in [GitHub Issues](https://github.com/ZJUCQR/CodeCinema/issues) with your OS, Python and FFmpeg versions, the command or Studio action, and the relevant error message. Remove private paths and credentials from logs.

## Package boundaries

- `cli/` translates terminal input into workspace or production operations.
- `workspace/` owns film discovery, configuration, scene data and reversible edits.
- `engine/` coordinates the shared timeline and production stages in isolated workers.
- `runtime/` wraps external programs, file locks and dependency checks.
- `studio/` separates HTTP handling in `server.py` from background jobs in `jobs.py`. Frontend resources live in the root `assets/_shared/studio/`.
- `renderers/` supplies picture backends, `audio/` supplies sound, and `productions/` holds the authored example packs.

Keep package initializers lightweight. In particular, importing `codecinema` must not load film settings, graphics or audio libraries. The worker sets the active film before importing its pipeline. Settings reads and Blender helpers must work in Blender's Python without the Studio or optional speech dependencies.

New extensions should use the grouped module paths, for example `codecinema.workspace.settings`, `codecinema.engine.context` and `codecinema.runtime.media`. The older `from codecinema import settings, media` convenience imports remain lazy aliases of the same module objects. Direct imports of the former flat modules should move to the new paths. The CLI commands and `codecinema.renderers` plugin entry-point group are unchanged.

Keep UI files under `assets/_shared/studio/` and starting film files under `assets/_shared/scaffold/`. The build hook in `codecinema/runtime/build.py` bundles only these two resource folders into wheels. `MANIFEST.in` includes them in source distributions. Check their inclusion in a built wheel and run from a separate workspace, since repository imports can conceal missing packaged files.

## Renderer plugins

A renderer supplies pictures. CodeCinema handles the timeline, soundtrack, speech, encoding, assembly and verification. Keep plugin code in an installable Python package, outside film folders.

Register its class in your package's `pyproject.toml`:

```toml
[project.entry-points."codecinema.renderers"]
myrenderer = "myrenderer:Renderer"
```

The class has no required constructor arguments, a `version` string and `render(context, frames)`. It yields one packed RGBA byte buffer per requested zero-based frame, in order. Each buffer is exactly `width * height * 4` bytes. Bump `version` when dependencies or rendering behavior change. An optional `validate(context)` method can reject unsupported scene fields before production.

`RenderContext` in `codecinema.engine.context` exposes the film path, the central asset directory as `context.assets`, story, quantized `(scene, start, end)` intervals, dimensions, frame rate, duration and working paths. Intervals are half-open. Use `frame / context.fps` for time so picture and sound stay aligned. Do not mutate the context or scene dictionaries. Backend-specific data may be stored under an additional scene key, which Studio preserves when editing.

For example, a minimal animated renderer can use Pillow:

```python
from PIL import Image

class Renderer:
    version = "1"

    def render(self, context, frames):
        for frame in frames:
            blue = round(255 * frame / max(1, context.frames - 1))
            image = Image.new("RGBA", (context.width, context.height), (20, 30, blue, 255))
            yield image.tobytes()
```

Install the package into the same environment as CodeCinema, then run `.venv/bin/python -m codecinema new demo --renderer myrenderer --render`. Restart Studio to discover new plugins. Plugin frames include their own captions if desired. The built-in Skia and Blender backends share a caption compositor.

For `.blend` input, a scene can contain a `blender` object with `file`, optional `scene`, optional `camera` and `frame_start` (default 1). The file path is relative to `assets/<film-id>/`, for example `scenes/world.blend`. Pack textures and linked resources inside Blender. The framework samples the source animation at its native frame rate and uses the film's selected output dimensions.

## Authored production packs

The original examples live in `codecinema/productions/`. Their shot data lives in `films/<id>/story.json`, and their settings remain in the workspace `pyproject.toml`. They retain dedicated choreography and mastering steps. Each pack executes in an isolated worker, including when it launches Blender, so its imports and audio settings do not leak into another film. These packages demonstrate advanced production work, while new editable projects use the common story pipeline.

Use the film context for data and output paths, and the production source path for Python scripts. Never infer a film folder from a module's `__file__`. If you change an authored shot boundary, review its camera, performance and audio cues together. Previously created projects with `entry` scripts remain supported and are never automatically overwritten. Import their `scenes.json` into a new film with `--story` to adopt the shared pipeline.
