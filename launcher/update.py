"""Apply an update the app asked for (app/desktop.py writes data/update.json).

The install folder (windows/install.ps1):

    TypingTrainer/
      bin/uv.exe          fetches Python and the packages
      python/ venv/       uv's Python and the app's packages
      versions/v0.2.0/    one folder per version of the code
      current.txt         which of those to run
      launch.pyw          what the shortcut runs
      data/               typing.db, backups/, the app window's profile

Code and data never share a folder, so an update can't touch progress;
the database is still copied to data/backups/ first in case a new version's
schema change goes wrong. A new version goes into its own folder and only
becomes current once its packages installed, so a failed update leaves the
old version running. The previous version is kept to roll back by hand
(edit current.txt).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

KEEP_BACKUPS = 10
KEEP_VERSIONS = 2
PYTHON = "3.12"


def log(root: Path, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(root / "data" / "update.log", "a", encoding="utf-8") as f:
        f.write(f"{stamp} {message}\n")


def backup_db(root: Path, tag: str) -> Path | None:
    """A consistent copy via SQLite's backup API (safe even mid-write)."""
    db = root / "data" / "typing.db"
    if not db.exists():
        return None
    backups = root / "data" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    dest = backups / f"typing-{datetime.now():%Y%m%d-%H%M%S}-before-{tag}.db"
    src, out = sqlite3.connect(db), sqlite3.connect(dest)
    try:
        src.backup(out)
    finally:
        src.close()
        out.close()
    for old in sorted(backups.glob("typing-*.db"))[:-KEEP_BACKUPS]:
        old.unlink()
    return dest


def unpack(zip_path: Path, dest: Path) -> None:
    """Extract a release zip into dest. Release zips hold one top folder
    (typing-trainer/); its contents become dest."""
    tmp = Path(tempfile.mkdtemp(dir=dest.parent, prefix=dest.name + ".tmp-"))
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        entries = list(tmp.iterdir())
        top = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp
        if not (top / "pyproject.toml").exists():
            raise ValueError("not a Typing Trainer release zip")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(top), str(dest))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def uv_env(root: Path) -> dict:
    """Keep everything uv makes inside the install folder."""
    env = dict(os.environ)
    env.update({
        "UV_PYTHON_INSTALL_DIR": str(root / "python"),
        "UV_PROJECT_ENVIRONMENT": str(root / "venv"),
        "UV_CACHE_DIR": str(root / "cache"),
        "UV_MANAGED_PYTHON": "1",
    })
    return env


def sync_packages(root: Path, version_dir: Path) -> None:
    """Install exactly the packages in that version's uv.lock. The code
    itself isn't installed into the venv: the launcher runs it in place."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(
        [str(root / "bin" / "uv.exe"), "sync", "--frozen", "--no-install-project",
         "--python", PYTHON, "--project", str(version_dir)],
        env=uv_env(root), capture_output=True, text=True, creationflags=flags,
    )
    if result.returncode != 0:
        raise RuntimeError(f"uv sync failed:\n{result.stderr[-2000:]}")


def prune_versions(root: Path, current: str) -> None:
    versions = root / "versions"
    others = sorted((d for d in versions.iterdir() if d.is_dir() and d.name != current),
                    key=lambda d: d.stat().st_mtime)
    for old in others[: max(0, len(others) - (KEEP_VERSIONS - 1))]:
        shutil.rmtree(old, ignore_errors=True)


def install(root: Path, tag: str, zip_url: str) -> None:
    downloads = root / "data" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    zip_path = downloads / f"typing-trainer-{tag}.zip"
    urllib.request.urlretrieve(zip_url, zip_path)
    version_dir = root / "versions" / tag
    version_dir.parent.mkdir(parents=True, exist_ok=True)
    unpack(zip_path, version_dir)
    sync_packages(root, version_dir)
    # The stable bits outside versions/ come from the new version too.
    for name in ("launch.pyw", "TypingTrainer.ico"):
        src = version_dir / "windows" / name
        if src.exists():
            shutil.copy2(src, root / name)
    (root / "current.txt").write_text(tag)
    zip_path.unlink(missing_ok=True)
    prune_versions(root, tag)


def apply(root: Path, request: dict) -> bool:
    """Back up, install, switch. Always clears the request, so a broken
    update can't retry forever; the old version keeps running on failure."""
    tag, zip_url = request.get("tag", ""), request.get("zip_url", "")
    ok = False

    def work():
        nonlocal ok
        try:
            backup = backup_db(root, tag)
            log(root, f"updating to {tag} (backup: {backup})")
            install(root, tag, zip_url)
            log(root, f"now on {tag}")
            ok = True
        except Exception as exc:  # noqa: BLE001 - log anything, keep the old version
            log(root, f"update to {tag} failed: {exc!r}")
        finally:
            (root / "data" / "update.json").unlink(missing_ok=True)

    with_progress_window(work, f"Updating Typing Trainer to {tag}...")
    return ok


def with_progress_window(work, message: str) -> None:
    """Run work with a small "Updating..." window, so the minute uv takes
    doesn't look like the app just vanished. No Tk, no window."""
    try:
        import tkinter as tk
        from tkinter import ttk
        window = tk.Tk()
    except Exception:  # noqa: BLE001 - tkinter missing or no display
        work()
        return
    window.title("Typing Trainer")
    window.resizable(False, False)
    tk.Label(window, text=message, font=("Segoe UI", 14), padx=30, pady=16).pack()
    bar = ttk.Progressbar(window, mode="indeterminate", length=320)
    bar.pack(padx=30, pady=(0, 24))
    bar.start(12)
    worker = threading.Thread(target=work, daemon=True)
    worker.start()

    def check():
        if worker.is_alive():
            window.after(200, check)
        else:
            window.destroy()

    check()
    window.mainloop()
    worker.join()


def relaunch(root: Path) -> None:
    """Start the (possibly new) version fresh, the way the shortcut does."""
    flags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
    pythonw = root / "venv" / "Scripts" / "pythonw.exe"
    subprocess.Popen([str(pythonw), str(root / "launch.pyw")], cwd=root, creationflags=flags)
