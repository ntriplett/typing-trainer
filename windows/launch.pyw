"""What the Typing Trainer shortcut runs (under the venv's pythonw.exe, so
no console window). Runs whichever version current.txt names; see
launcher/update.py for the install folder. Copied out of the newest
version on every install or update, so keep it this small.
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    version_dir = ROOT / "versions" / (ROOT / "current.txt").read_text().strip()
    sys.path.insert(0, str(version_dir))
    from launcher import start

    start.run_installed(ROOT)
except Exception:
    (ROOT / "data").mkdir(exist_ok=True)
    with open(ROOT / "data" / "launcher.log", "a", encoding="utf-8") as f:
        traceback.print_exc(file=f)
