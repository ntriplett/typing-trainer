"""pet_render.js is loaded beside almost every other script, and plain <script>
files share one global scope: a function of the same name in another file
silently replaces its own (the Observatory's drawStars once hid starry pets'
stars). Its top-level names must be its own."""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[2] / "web" / "static" / "js"
TOP_LEVEL = re.compile(r"^(?:async )?function (\w+)\(|^(?:const|let|var|class) (\w+)", re.M)


def top_level_names(path: Path) -> set[str]:
    return {a or b for a, b in TOP_LEVEL.findall(path.read_text())}


def test_pet_render_names_are_its_own():
    mine = top_level_names(JS / "pet_render.js")
    clashes = {p.name: sorted(mine & top_level_names(p)) for p in JS.glob("*.js") if p.name != "pet_render.js"}
    assert {k: v for k, v in clashes.items() if v} == {}
