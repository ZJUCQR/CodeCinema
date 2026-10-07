# Contributing to CodeCinema

CodeCinema welcomes improvements to templates, Studio, renderer integrations, shared production tools and documentation.

## Set up

Follow the [getting-started guide](README.md#quick-start) for Python 3.12+, FFmpeg and the system libraries required on your platform. Install an editable checkout:

```bash
python -m pip install -e .
codecinema studio
```

The shared framework and starter templates do not require Blender. Renderer-specific dependencies belong in the corresponding film's guide.

## Make a change

- For a starter look, update the preset data in `codecinema/starters.py` and the rendering palette in `codecinema/template/src/run.py`. Include an actual rendered thumbnail for Studio.
- For an editor improvement, update `codecinema/studio.py` or `codecinema/studio_assets/`. Check both languages and a narrow mobile viewport.
- For a renderer, create a film folder with an entry script and register it under `[tool.codecinema.films.<id>]` in the root `pyproject.toml`. Use the [film contract](README.md#framework) and document its steps, requirements and output paths.
- For documentation, keep English and Chinese setup instructions consistent. Describe the current behavior and provide commands a newcomer can copy.

Generated videos, render caches, recordings and local settings stay outside Git. A release contains finished MP4s; development reports stay local.

## Check your work

```bash
python -m compileall -q codecinema
codecinema list
codecinema new checkfilm --preset aurora --duration 3 --quality preview --render
```

For media changes, inspect the sample's picture, sound and duration. Use a temporary workspace to check behavior such as preserving an existing master or handling an invalid project. CI checks project creation and imports on macOS, Linux and Windows, and renders a short sample on Linux.

Open a focused pull request explaining the problem, the resulting behavior and the checks you ran. Include a screenshot or short preview when the visual result changes. Report bugs in [GitHub Issues](https://github.com/ZJUCQR/CodeCinema/issues) with your OS, Python and FFmpeg versions, the command or Studio action, and the relevant error message. Remove private paths and credentials from logs.
