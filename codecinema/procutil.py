"""
procutil.py - small cross-platform OS helpers (pure standard library; macOS, Linux, Windows).

    lock_file(fh, blocking=False) -> bool     exclusive advisory lock on an open file (fcntl / msvcrt)
    unlock_file(fh)
    pid_alive(pid) -> bool                    is a process still running
    process_command(pid) -> str | None        its command line, when the OS can tell
    free_memory_gb() -> float | None          reclaimable memory (vm_stat / /proc/meminfo / GlobalMemoryStatusEx)
    popen_group_kwargs() -> dict              Popen kwargs that put a child in its own process group
    terminate_tree(proc, grace=10.0)          stop a child and everything it started
    link_or_copy(src, dst)                    symlink, falling back to a hard link, then a copy
"""
import os
import shutil
import signal
import subprocess
import sys
import time

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt   # noqa: F401
else:
    import fcntl


def lock_file(fh, blocking=False):
    """Exclusive lock on an open file object. Returns False if it is held elsewhere (non-blocking)."""
    try:
        if IS_WINDOWS:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return True
    except OSError:
        return False


def unlock_file(fh):
    try:
        if IS_WINDOWS:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if IS_WINDOWS:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION, STILL_ACTIVE = 0x1000, 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def process_command(pid):
    """Command line of a process, or None when unavailable (used to recognise our own stale lock holders)."""
    try:
        if IS_WINDOWS:
            out = subprocess.run(["wmic", "process", "where", f"ProcessId={int(pid)}", "get", "CommandLine"],
                                 capture_output=True, text=True, timeout=10).stdout
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            return lines[1] if len(lines) > 1 else None
        if os.path.exists(f"/proc/{int(pid)}/cmdline"):
            with open(f"/proc/{int(pid)}/cmdline", "rb") as fh:
                return fh.read().replace(b"\0", b" ").decode(errors="replace").strip() or None
        out = subprocess.run(["ps", "-o", "command=", "-p", str(int(pid))], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:           # noqa: BLE001 - purely informational
        return None


def free_memory_gb():
    """Free + reclaimable memory in GB, or None if it cannot be determined."""
    try:
        if sys.platform == "darwin":
            txt = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=10).stdout
            page = 4096
            first = txt.splitlines()[0] if txt else ""
            if "page size of" in first:
                page = int(first.split("page size of")[1].split()[0])
            pages = {}
            for line in txt.splitlines()[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    pages[k.strip()] = int(v.strip().rstrip(".") or 0)
            free = sum(pages.get(k, 0) for k in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"))
            return free * page / 1024 ** 3
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo") as fh:
                info = {l.split(":")[0]: int(l.split()[1]) for l in fh if ":" in l}
            return info.get("MemAvailable", info.get("MemFree", 0)) / 1024 ** 2
        if IS_WINDOWS:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return st.ullAvailPhys / 1024 ** 3
    except Exception:           # noqa: BLE001
        return None
    return None


def popen_group_kwargs():
    """Start a child in its own process group / session so terminate_tree() can stop all of it."""
    if IS_WINDOWS:
        return dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return dict(start_new_session=True)


def terminate_tree(proc, grace=10.0):
    """Terminate a Popen child and its descendants; kill after `grace` seconds."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            deadline = time.time() + grace
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.2)
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def link_or_copy(src, dst):
    """Symlink dst -> src; falls back to a hard link, then to a copy (Windows without symlink rights)."""
    src = os.path.abspath(src)
    for fn in (os.symlink, os.link):
        try:
            fn(src, dst)
            return
        except (OSError, NotImplementedError):
            continue
    shutil.copy2(src, dst)
