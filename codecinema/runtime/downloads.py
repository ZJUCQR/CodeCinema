"""Verified downloads into a per-user cache (standard library only).

    cached(name, url, sha256, size=None) -> Path

The cache root is $CODECINEMA_CACHE, else the platform's per-user cache folder:
Windows %LOCALAPPDATA%/codecinema/Cache, macOS ~/Library/Caches/codecinema,
Linux $XDG_CACHE_HOME/codecinema or ~/.cache/codecinema.
A file is downloaded once to a temporary file next to its target, checked against its SHA-256 and
then renamed atomically, so an interrupted or concurrent download never leaves a broken file behind.
"""
import hashlib
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

CHUNK = 1 << 20
TIMEOUT_S = 30


class DownloadError(RuntimeError):
    """A cached file could not be downloaded or failed verification."""


def cache_root():
    """$CODECINEMA_CACHE, else the platform's per-user cache folder (not created)."""
    explicit = os.environ.get("CODECINEMA_CACHE")
    if explicit:
        return Path(explicit).expanduser()
    home = Path.home()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        return Path(base) / "codecinema" / "Cache"
    if sys.platform == "darwin":
        return home / "Library" / "Caches" / "codecinema"
    return Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache") / "codecinema"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _stamp(target):
    return target.with_name(target.name + ".sha256")


def _valid(target, sha256, size):
    """True when target exists with the expected size and digest; a stamp file avoids re-hashing."""
    if not target.is_file() or (size is not None and target.stat().st_size != size):
        return False
    stamp = _stamp(target)
    try:
        if stamp.read_text(encoding="ascii").strip() == sha256 and stamp.stat().st_mtime >= target.stat().st_mtime:
            return True
    except OSError:
        pass
    if sha256_file(target) != sha256:
        return False
    try:
        stamp.write_text(sha256 + "\n", encoding="ascii")
    except OSError:
        pass
    return True


def _megabytes(n):
    return f"{n / 1e6:.1f} MB"


def cached(name, url, sha256, size=None):
    """Path of `name` in the cache, downloading `url` on first use. The file's SHA-256 must match `sha256`
    (and its length `size` when given). Raises DownloadError with a readable message on failure."""
    sha256 = sha256.lower()
    target = cache_root() / name
    if _valid(target, sha256, size):
        return target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DownloadError(f"Cannot create the cache folder {target.parent}: {exc}") from None
    request = urllib.request.Request(url, headers={"User-Agent": "codecinema"})
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=target.parent)
    tty = sys.stderr.isatty()
    try:
        digest = hashlib.sha256()
        received = 0
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            total = int(response.headers.get("Content-Length") or size or 0)
            label = f"Downloading {target.name}" + (f" ({_megabytes(total)})" if total else "")
            print(label + " ...", file=sys.stderr, flush=True)
            shown = time.monotonic()
            for block in iter(lambda: response.read(CHUNK), b""):
                out.write(block)
                digest.update(block)
                received += len(block)
                if tty and total and time.monotonic() - shown > 0.25:
                    shown = time.monotonic()
                    print(f"\r{label} {100 * received // total:3d}%", end="", file=sys.stderr, flush=True)
        if tty and total:
            print(f"\r{label} 100%", file=sys.stderr, flush=True)
        if size is not None and received != size:
            raise DownloadError(f"{target.name}: expected {size} bytes from {url}, received {received}")
        if digest.hexdigest() != sha256:
            raise DownloadError(f"{target.name}: the download from {url} failed its SHA-256 check")
        os.replace(temporary, target)
        try:
            _stamp(target).write_text(sha256 + "\n", encoding="ascii")
        except OSError:
            pass
        print(f"Saved {target}", file=sys.stderr, flush=True)
        return target
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"Could not download {target.name}: {url} answered HTTP {exc.code} {exc.reason}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise DownloadError(f"Could not download {target.name} from {url} ({reason}). Check the internet "
                            f"connection, or place the file at {target}.") from None
    except OSError as exc:
        raise DownloadError(f"Could not save {target.name} to {target.parent}: {exc}") from None
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass
