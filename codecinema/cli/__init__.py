"""Command-line entry point, shared by the console script and python -m codecinema."""


def main(argv=None):
    from .app import main as run

    return run(argv)
