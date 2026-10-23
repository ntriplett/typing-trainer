"""The first, deliberately trivial activity module.

Its only job is to prove the module contract (PLAN.md Section 7) end to
end: the scheduler/API can ask an activity to generate content without
knowing anything about its internals. Once the skill model and real
scheduler exist, this gets replaced by actual teach/practice/eval/game
modules, but the shape stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HelloWorldActivity:
    id: str = "hello_world"
    kind: str = "practice"

    def generate(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "message": "Hello, typer! The engine is alive.",
        }
