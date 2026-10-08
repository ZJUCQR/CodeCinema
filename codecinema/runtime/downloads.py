"""Verified downloads into a per-user cache (standard library only).

    cached(name, url, sha256, size=None, *, label=None, quiet=False) -> Path
    is_cached(name, sha256, size=None) -> bool
    offline() -> bool

`url` is one address or a sequence of mirrors, tried in order until one delivers the expected bytes.
The cache root is $CODECINEMA_CACHE, else the platform's per-user cache folder:
Windows %LOCALAPPDATA%/codecinema/Cache, macOS ~/Library/Caches/codecinema,
Linux $XDG_CACHE_HOME/codecinema or ~/.cache/codecinema.
A file is downloaded once to a temporary file next to its target, checked against its SHA-256 and
then renamed atomically, so an interrupted or concurrent download never leaves a broken file behind.
Set CODECINEMA_OFFLINE=1 to never use the network; files already in the cache keep working.
"""
import hashlib
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
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


def offline():
    """True when CODECINEMA_OFFLINE asks for no network access."""
    return os.environ.get("CODECINEMA_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


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


def is_cached(name, sha256, size=None):
    """True when `name` is in the cache with the expected digest (and size), without downloading."""
    return _valid(cache_root() / name, sha256.lower(), size)


def _megabytes(n):
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{n / 1e3:.0f} kB"


def host(url):
    """A short name for a download address, for messages."""
    parts = urllib.parse.urlsplit(url)
    return parts.netloc or ("a local folder" if parts.scheme == "file" else url)


def _fetch(url, target, sha256, size, label, quiet):
    """One download attempt from one address; raises DownloadError with the reason."""
    request = urllib.request.Request(url, headers={"User-Agent": "codecinema"})
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=target.parent)
    tty = sys.stderr.isatty() and not quiet
    pending = False             # a progress line without its newline yet (terminals only)
    try:
        digest = hashlib.sha256()
        received = 0
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            total = int(response.headers.get("Content-Length") or size or 0)
            line = f"Downloading {label}" + (f" ({_megabytes(total)})" if total else "") + f" from {host(url)}"
            if not quiet:
                print(line + " ...", end="" if tty else "\n", file=sys.stderr, flush=True)
                pending = tty
            shown = time.monotonic()
            for block in iter(lambda: response.read(CHUNK), b""):
                out.write(block)
                digest.update(block)
                received += len(block)
                if tty and total and time.monotonic() - shown > 0.25:
                    shown = time.monotonic()
                    print(f"\r{line} {100 * received // total:3d}%", end="", file=sys.stderr, flush=True)
        if pending:
            print(f"\r{line} ... done", file=sys.stderr, flush=True)
            pending = False
        if size is not None and received != size:
            raise DownloadError(f"{target.name}: expected {size} bytes from {host(url)}, received {received}")
        if digest.hexdigest() != sha256:
            raise DownloadError(f"{target.name}: the download from {host(url)} failed its SHA-256 check")
        os.replace(temporary, target)
        try:
            _stamp(target).write_text(sha256 + "\n", encoding="ascii")
        except OSError:
            pass
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"Could not download {target.name}: {url} answered HTTP {exc.code} {exc.reason}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise DownloadError(f"Could not download {target.name} from {url} ({reason})") from None
    except OSError as exc:
        raise DownloadError(f"Could not save {target.name} to {target.parent}: {exc}") from None
    finally:
        if pending:
            print(file=sys.stderr, flush=True)
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def cached(name, url, sha256, size=None, *, label=None, quiet=False):
    """Path of `name` in the cache, downloading on first use from `url` (an address or a sequence of mirrors,
    tried in order). The file's SHA-256 must match `sha256` (and its length `size` when given).
    `label` names the file in progress messages; `quiet` hides them. Raises DownloadError with a readable message."""
    sha256 = sha256.lower()
    target = cache_root() / name
    if _valid(target, sha256, size):
        return target
    urls = [url] if isinstance(url, str) else [u for u in url if u]
    if not urls:
        raise DownloadError(f"No download address for {target.name}. Place the file at {target}.")
    if offline():
        raise DownloadError(f"{target.name} is not downloaded yet and CODECINEMA_OFFLINE is set. "
                            f"Download it once online, or place the file at {target}.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DownloadError(f"Cannot create the cache folder {target.parent}: {exc}") from None
    problems = []
    for i, address in enumerate(urls):
        try:
            _fetch(address, target, sha256, size, label or target.name, quiet)
        except DownloadError as exc:
            problems.append(str(exc))
            if i + 1 < len(urls) and not quiet:
                print(f"  {exc}; trying {host(urls[i + 1])}", file=sys.stderr, flush=True)
            continue
        if label is None and not quiet:
            print(f"Saved {target}", file=sys.stderr, flush=True)
        return target
    if len(urls) == 1:
        raise DownloadError(f"{problems[0]}. Check the internet connection, or place the file at {target}.")
    raise DownloadError(f"Could not download {target.name} from any of {len(urls)} addresses:\n  "
                        + "\n  ".join(problems)
                        + f"\nCheck the internet connection or set a mirror, or place the file at {target}.")
