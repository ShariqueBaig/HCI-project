"""JSON-persisted workspace store for tasks, notes, brainstorm ideas, and user settings."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
WORKSPACE_FILE = DATA_DIR / "workspace.json"


def _default_workspace() -> dict[str, Any]:
    now = time.time()
    return {
        "tasks": [
            {
                "id": "t-1",
                "title": "Synthesize HCI literature review on adaptive affective interfaces",
                "priority": "high",
                "estimatedMinutes": 45,
                "completed": False,
                "category": "Research",
                "microSteps": [
                    {"id": "ms-1", "text": "Open the Affective Computing notes and highlight 2 key citations", "done": True},
                    {"id": "ms-2", "text": "Draft a 3-sentence comparison of hysteresis vs raw frame switching", "done": False},
                    {"id": "ms-3", "text": "Add Russell Circumplex diagram reference to Section 2", "done": False},
                ],
                "createdAt": now - 7200,
            },
            {
                "id": "t-2",
                "title": "Reply to advisor email confirming usability study schedule",
                "priority": "high",
                "estimatedMinutes": 6,
                "completed": False,
                "category": "Admin",
                "microSteps": [
                    {"id": "ms-4", "text": "Confirm Thursday 2:00 PM slot in two sentences", "done": False},
                ],
                "createdAt": now - 5400,
            },
            {
                "id": "t-3",
                "title": "Verify ONNX model latency under CPU load",
                "priority": "medium",
                "estimatedMinutes": 25,
                "completed": False,
                "category": "Engineering",
                "microSteps": [
                    {"id": "ms-5", "text": "Run test_pipeline.py benchmark on 320x240 and 640x480 frames", "done": False},
                    {"id": "ms-6", "text": "Record mean inference ms in experiment table", "done": False},
                ],
                "createdAt": now - 3600,
            },
            {
                "id": "t-4",
                "title": "Clean up bibliography tags for Week 7 seminar",
                "priority": "low",
                "estimatedMinutes": 8,
                "completed": False,
                "category": "Research",
                "microSteps": [
                    {"id": "ms-7", "text": "Tag 4 PDFs with #affective-ui and #fitts-law", "done": False},
                ],
                "createdAt": now - 2400,
            },
            {
                "id": "t-5",
                "title": "Sketch low-friction recovery card micro-copy",
                "priority": "low",
                "estimatedMinutes": 10,
                "completed": False,
                "category": "Design",
                "microSteps": [
                    {"id": "ms-8", "text": "Write calm 1-line prompt for 4-7-8 breathing card", "done": False},
                ],
                "createdAt": now - 1800,
            },
            {
                "id": "t-6",
                "title": "Configure YuNet 5-point facial landmark detector",
                "priority": "medium",
                "estimatedMinutes": 20,
                "completed": True,
                "category": "Engineering",
                "microSteps": [
                    {"id": "ms-9", "text": "Verify landmark coordinates on webcam test", "done": True},
                ],
                "createdAt": now - 9600,
            },
        ],
        "notes": [
            {
                "id": "n-1",
                "title": "HCI Assignment: Affective Generative UI Architecture",
                "content": (
                    "Core Thesis: Emotion-driven interfaces fail when they only re-skin background colors. "
                    "True affective HCI adapts information architecture, choice density (Hick's Law), target "
                    "acquisition size (Fitts's Law), and mixed-initiative agency.\n\n"
                    "Next Checkpoint:\n"
                    "- Compare Co-Pilot proposal acceptance vs autonomous switching.\n"
                    "- Validate 3-second dwell hysteresis prevents single-frame blink thrashing.\n"
                    "- Document Russell's Circumplex mapping (Valence x Arousal) across 5 operational modes."
                ),
                "updatedAt": now - 300,
            },
            {
                "id": "n-2",
                "title": "Usability Protocol & Privacy Guardrails",
                "content": (
                    "1. Hardware Privacy Shutter: Camera frames stay strictly in local RAM; toggling off releases VideoCapture immediately.\n"
                    "2. Explainability: Users can inspect exact OpenCV bounding boxes, 8 emotion probabilities, and the generated UISchema JSON.\n"
                    "3. Graceful Overrides: Never trap a user in an unwanted layout; 1-click Undo and Agency Mode selector always visible."
                ),
                "updatedAt": now - 1800,
            },
        ],
        "ideas": [
            {
                "id": "i-1",
                "text": "Add speech synthesis read-aloud for fatigued reading comprehension",
                "tag": "Accessibility",
                "createdAt": now - 4000,
            },
            {
                "id": "i-2",
                "text": "Auto-extract 2-minute micro-step when cognitive load exceeds 70%",
                "tag": "Hick's Law",
                "createdAt": now - 3000,
            },
            {
                "id": "i-3",
                "text": "Export affective session timeline as CSV for HCI evaluation report",
                "tag": "Evaluation",
                "createdAt": now - 1200,
            },
        ],
        "settings": {
            "agency_mode": "copilot",
            "dwell_seconds": 3.0,
            "reduced_motion": False,
        },
    }


class WorkspaceStore:
    """Thread-safe JSON persistence for the user's productive workspace."""

    def __init__(self, path: Path = WORKSPACE_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load_or_init()

    def _load_or_init(self) -> dict[str, Any]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if all(k in loaded for k in ("tasks", "notes", "ideas", "settings")):
                    return loaded
            except Exception:
                pass
        seed = _default_workspace()
        self.path.write_text(json.dumps(seed, indent=2), encoding="utf-8")
        return seed

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data))

    def task_pressure(self) -> float:
        with self._lock:
            incomplete = [t for t in self._data["tasks"] if not t.get("completed")]
            high = sum(1 for t in incomplete if t.get("priority") == "high")
            return min(1.0, (len(incomplete) * 0.08) + (high * 0.15))

    def add_task(self, title: str, priority: str = "medium", estimated_minutes: int = 15, category: str = "General") -> dict[str, Any]:
        with self._lock:
            now = time.time()
            tid = f"t-{int(now * 1000)}"
            task = {
                "id": tid,
                "title": title.strip(),
                "priority": priority if priority in ("high", "medium", "low") else "medium",
                "estimatedMinutes": max(2, min(180, int(estimated_minutes))),
                "completed": False,
                "category": category.strip() or "General",
                "microSteps": [
                    {"id": f"ms-{int(now * 1000)}", "text": f"Spend 2 minutes outlining: {title.strip()[:48]}", "done": False}
                ],
                "createdAt": now,
            }
            self._data["tasks"].insert(0, task)
            self._save()
            return task

    def update_task(self, task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for t in self._data["tasks"]:
                if t["id"] == task_id:
                    for key in ("title", "priority", "estimatedMinutes", "completed", "category"):
                        if key in updates and updates[key] is not None:
                            t[key] = updates[key]
                    self._save()
                    return dict(t)
            return None

    def toggle_microstep(self, task_id: str, step_id: str) -> dict[str, Any] | None:
        with self._lock:
            for t in self._data["tasks"]:
                if t["id"] == task_id:
                    for step in t.get("microSteps", []):
                        if step["id"] == step_id:
                            step["done"] = not step["done"]
                            self._save()
                            return dict(t)
            return None

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            before = len(self._data["tasks"])
            self._data["tasks"] = [t for t in self._data["tasks"] if t["id"] != task_id]
            if len(self._data["tasks"]) != before:
                self._save()
                return True
            return False

    def add_note(self, title: str, content: str = "") -> dict[str, Any]:
        with self._lock:
            now = time.time()
            note = {
                "id": f"n-{int(now * 1000)}",
                "title": title.strip() or "Untitled Note",
                "content": content,
                "updatedAt": now,
            }
            self._data["notes"].insert(0, note)
            self._save()
            return note

    def update_note(self, note_id: str, title: str | None = None, content: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            for n in self._data["notes"]:
                if n["id"] == note_id:
                    if title is not None:
                        n["title"] = title
                    if content is not None:
                        n["content"] = content
                    n["updatedAt"] = time.time()
                    self._save()
                    return dict(n)
            return None

    def delete_note(self, note_id: str) -> bool:
        with self._lock:
            before = len(self._data["notes"])
            self._data["notes"] = [n for n in self._data["notes"] if n["id"] != note_id]
            if len(self._data["notes"]) != before:
                self._save()
                return True
            return False

    def add_idea(self, text: str, tag: str = "Spark") -> dict[str, Any]:
        with self._lock:
            now = time.time()
            idea = {
                "id": f"i-{int(now * 1000)}",
                "text": text.strip(),
                "tag": tag.strip() or "Spark",
                "createdAt": now,
            }
            self._data["ideas"].insert(0, idea)
            self._save()
            return idea

    def delete_idea(self, idea_id: str) -> bool:
        with self._lock:
            before = len(self._data["ideas"])
            self._data["ideas"] = [i for i in self._data["ideas"] if i["id"] != idea_id]
            if len(self._data["ideas"]) != before:
                self._save()
                return True
            return False

    def promote_idea(self, idea_id: str) -> dict[str, Any] | None:
        with self._lock:
            target = next((i for i in self._data["ideas"] if i["id"] == idea_id), None)
            if not target:
                return None
            now = time.time()
            task = {
                "id": f"t-{int(now * 1000)}",
                "title": target["text"],
                "priority": "medium",
                "estimatedMinutes": 15,
                "completed": False,
                "category": target.get("tag", "Idea"),
                "microSteps": [
                    {"id": f"ms-{int(now * 1000)}", "text": f"Outline first step for: {target['text'][:42]}", "done": False}
                ],
                "createdAt": now,
            }
            self._data["tasks"].insert(0, task)
            self._data["ideas"] = [i for i in self._data["ideas"] if i["id"] != idea_id]
            self._save()
            return task

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for k in ("agency_mode", "dwell_seconds", "reduced_motion"):
                if k in updates and updates[k] is not None:
                    self._data["settings"][k] = updates[k]
            self._save()
            return dict(self._data["settings"])
