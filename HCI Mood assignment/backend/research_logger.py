"""SQLite-backed empirical HCI data logger for ISO 9241-11, SAM, SUS, and multimodal telemetry."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "hci_study.db"


def compute_sus(answers: list[int]) -> float:
    """Compute standard 10-item System Usability Scale (0..100)."""
    if len(answers) != 10:
        raise ValueError("SUS requires exactly 10 item scores (1..5).")
    total = 0
    for idx, raw in enumerate(answers):
        val = max(1, min(5, int(raw)))
        if idx % 2 == 0:  # Odd items (1,3,5,7,9 -> idx 0,2,4,6,8)
            total += val - 1
        else:  # Even items (2,4,6,8,10 -> idx 1,3,5,7,9)
            total += 5 - val
    return round(total * 2.5, 1)


def compute_iso_metrics(
    completed: bool,
    task_accuracy: float,
    error_count: int,
    time_sec: float,
    clicks: int,
    rage_clicks: int,
) -> tuple[float, float]:
    """Compute ISO 9241-11 Efficiency (0..100) and Effectiveness (0..100)."""
    acc = max(0.0, min(100.0, float(task_accuracy)))
    effectiveness = round(
        max(0.0, min(100.0, (acc if completed else acc * 0.4) - max(0, error_count) * 5.0)),
        1,
    )
    t_norm = 45.0 / max(45.0, float(time_sec))
    c_norm = 8.0 / max(8.0, float(clicks))
    efficiency = round(
        max(0.0, min(100.0, t_norm * 75.0 + c_norm * 25.0 - max(0, rage_clicks) * 4.0)),
        1,
    )
    return efficiency, effectiveness


def compute_cv_sam_alignment(mean_valence: float, sam_valence: int) -> float:
    """Compare CV mean_valence (-1..+1) against normalized SAM Valence (1..9 -> -1..+1)."""
    sam_norm = (max(1, min(9, int(sam_valence))) - 5.0) / 4.0
    return round(max(0.0, (1.0 - abs(float(mean_valence) - sam_norm) / 2.0) * 100.0), 1)


class ResearchLogger:
    """Thread-safe SQLite logger for controlled affective HCI studies."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    participant_id TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    task_prompt TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    completed INTEGER DEFAULT 0,
                    task_accuracy REAL DEFAULT 100.0,
                    error_count INTEGER DEFAULT 0,
                    backtrack_count INTEGER DEFAULT 0,
                    click_count INTEGER DEFAULT 0,
                    rage_click_count INTEGER DEFAULT 0,
                    hesitation_count INTEGER DEFAULT 0,
                    time_on_task_sec REAL DEFAULT 0.0,
                    dominant_emotion TEXT DEFAULT 'neutral',
                    visual_type TEXT DEFAULT 'Focused & Spotlight',
                    nav_type TEXT DEFAULT 'Bento Box',
                    mean_valence REAL DEFAULT 0.0,
                    mean_arousal REAL DEFAULT 0.0,
                    mean_cognitive_load REAL DEFAULT 0.0,
                    delta_valence REAL DEFAULT 0.0,
                    efficiency_score REAL DEFAULT 0.0,
                    effectiveness_score REAL DEFAULT 0.0,
                    satisfaction_sus REAL DEFAULT 0.0,
                    sam_valence INTEGER DEFAULT 5,
                    sam_arousal INTEGER DEFAULT 5,
                    sam_dominance INTEGER DEFAULT 5,
                    cv_sam_alignment REAL DEFAULT 0.0,
                    nasa_tlx_mental INTEGER DEFAULT 3,
                    nasa_tlx_frustration INTEGER DEFAULT 3,
                    nasa_tlx_effort INTEGER DEFAULT 3,
                    notes TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS affective_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    dominant_emotion TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    emotions_json TEXT NOT NULL,
                    valence REAL NOT NULL,
                    arousal REAL NOT NULL,
                    attention_score REAL NOT NULL,
                    head_pitch REAL NOT NULL,
                    cognitive_load REAL NOT NULL,
                    active_state TEXT NOT NULL,
                    visual_type TEXT NOT NULL,
                    nav_type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS interaction_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    target_id TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS agent_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT DEFAULT '',
                    timestamp REAL NOT NULL,
                    prompt TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    emotion_state TEXT NOT NULL,
                    dominant_emotion TEXT NOT NULL,
                    visual_type TEXT NOT NULL,
                    nav_type TEXT NOT NULL,
                    agent_tone TEXT NOT NULL,
                    used_llm INTEGER DEFAULT 0,
                    response_summary TEXT NOT NULL,
                    schema_json TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def start_session(
        self,
        participant_id: str,
        scenario: str,
        condition: str,
        task_prompt: str,
        dominant_emotion: str = "neutral",
        visual_type: str = "Focused & Spotlight",
        nav_type: str = "Bento Box",
    ) -> dict[str, Any]:
        now = time.time()
        sid = f"ses-{int(now * 1000)}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions (
                    id, participant_id, scenario, condition, task_prompt, started_at,
                    dominant_emotion, visual_type, nav_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    participant_id.strip() or "P-01",
                    scenario,
                    condition,
                    task_prompt.strip(),
                    now,
                    dominant_emotion,
                    visual_type,
                    nav_type,
                ),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
            return dict(row)

    def record_affective_sample(
        self,
        session_id: str,
        telemetry: dict[str, Any],
        visual_type: str,
        nav_type: str,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO affective_samples (
                    session_id, timestamp, source, dominant_emotion, confidence,
                    emotions_json, valence, arousal, attention_score, head_pitch,
                    cognitive_load, active_state, visual_type, nav_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    float(telemetry.get("timestamp", time.time())),
                    str(telemetry.get("source", "idle")),
                    str(telemetry.get("dominant_emotion", "neutral")),
                    float(telemetry.get("raw_confidence", 0.0)),
                    json.dumps(telemetry.get("emotions", {})),
                    float(telemetry.get("valence", 0.0)),
                    float(telemetry.get("arousal", 0.0)),
                    float(telemetry.get("attention_score", 1.0)),
                    float(telemetry.get("head_pitch_proxy", 0.0)),
                    float(telemetry.get("cognitive_load", 0.0)),
                    str(telemetry.get("active_state", "focused")),
                    visual_type,
                    nav_type,
                ),
            )
            self._conn.commit()

    def record_interaction_event(
        self,
        session_id: str,
        event_type: str,
        target_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO interaction_events (session_id, timestamp, event_type, target_id, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, time.time(), event_type, target_id, json.dumps(metadata or {})),
            )
            self._conn.commit()

    def record_agent_generation(
        self,
        session_id: str | None,
        agent_result: dict[str, Any],
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agent_generations (
                    session_id, timestamp, prompt, condition, scenario, emotion_state,
                    dominant_emotion, visual_type, nav_type, agent_tone, used_llm,
                    response_summary, schema_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id or "",
                    time.time(),
                    str(agent_result.get("prompt", "")),
                    str(agent_result.get("condition", "emotional_agent")),
                    str(agent_result.get("scenario", "commerce")),
                    str(agent_result.get("emotionState", "focused")),
                    str(agent_result.get("dominantEmotion", "neutral")),
                    str(agent_result.get("visualType", "")),
                    str(agent_result.get("navType", "")),
                    str(agent_result.get("agentTone", "")),
                    1 if agent_result.get("usedLlm") else 0,
                    str(agent_result.get("message", ""))[:300],
                    json.dumps(agent_result.get("uiOverrides", {})),
                ),
            )
            self._conn.commit()

    def complete_session(
        self,
        session_id: str,
        completed: bool,
        task_accuracy: float,
        error_count: int,
        backtrack_count: int,
        click_count: int,
        rage_click_count: int,
        hesitation_count: int,
        sus_answers: list[int],
        sam_valence: int,
        sam_arousal: int,
        sam_dominance: int,
        nasa_tlx_mental: int,
        nasa_tlx_frustration: int,
        nasa_tlx_effort: int,
        visual_type: str,
        nav_type: str,
        fallback_emotion: str = "neutral",
        fallback_valence: float = 0.0,
        fallback_arousal: float = 0.0,
        fallback_load: float = 0.2,
        notes: str = "",
    ) -> dict[str, Any] | None:
        now = time.time()
        with self._lock:
            ses = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not ses:
                return None

            samples = self._conn.execute(
                "SELECT * FROM affective_samples WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()

            time_sec = max(1.0, round(now - float(ses["started_at"]), 2))
            if samples:
                vals = [float(s["valence"]) for s in samples]
                aros = [float(s["arousal"]) for s in samples]
                loads = [float(s["cognitive_load"]) for s in samples]
                mean_val = round(sum(vals) / len(vals), 4)
                mean_aro = round(sum(aros) / len(aros), 4)
                mean_load = round(sum(loads) / len(loads), 4)
                delta_val = round(vals[-1] - vals[0], 4)
                # Mode of dominant_emotion across samples
                counts: dict[str, int] = {}
                for s in samples:
                    em = str(s["dominant_emotion"])
                    counts[em] = counts.get(em, 0) + 1
                dom_emotion = max(counts, key=lambda k: counts[k])
            else:
                mean_val = round(fallback_valence, 4)
                mean_aro = round(fallback_arousal, 4)
                mean_load = round(fallback_load, 4)
                delta_val = 0.0
                dom_emotion = fallback_emotion

            sus_score = compute_sus(sus_answers)
            efficiency, effectiveness = compute_iso_metrics(
                completed=completed,
                task_accuracy=task_accuracy,
                error_count=error_count,
                time_sec=time_sec,
                clicks=click_count,
                rage_clicks=rage_click_count,
            )
            alignment = compute_cv_sam_alignment(mean_val, sam_valence)

            self._conn.execute(
                """
                UPDATE sessions SET
                    ended_at = ?, completed = ?, task_accuracy = ?, error_count = ?,
                    backtrack_count = ?, click_count = ?, rage_click_count = ?,
                    hesitation_count = ?, time_on_task_sec = ?, dominant_emotion = ?,
                    visual_type = ?, nav_type = ?, mean_valence = ?, mean_arousal = ?,
                    mean_cognitive_load = ?, delta_valence = ?, efficiency_score = ?,
                    effectiveness_score = ?, satisfaction_sus = ?, sam_valence = ?,
                    sam_arousal = ?, sam_dominance = ?, cv_sam_alignment = ?,
                    nasa_tlx_mental = ?, nasa_tlx_frustration = ?, nasa_tlx_effort = ?,
                    notes = ?
                WHERE id = ?
                """,
                (
                    now,
                    1 if completed else 0,
                    float(task_accuracy),
                    int(error_count),
                    int(backtrack_count),
                    int(click_count),
                    int(rage_click_count),
                    int(hesitation_count),
                    time_sec,
                    dom_emotion,
                    visual_type,
                    nav_type,
                    mean_val,
                    mean_aro,
                    mean_load,
                    delta_val,
                    efficiency,
                    effectiveness,
                    sus_score,
                    int(sam_valence),
                    int(sam_arousal),
                    int(sam_dominance),
                    alignment,
                    int(nasa_tlx_mental),
                    int(nasa_tlx_frustration),
                    int(nasa_tlx_effort),
                    notes,
                    session_id,
                ),
            )
            self._conn.commit()
            updated = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(updated)

    def whiteboard_summary(self) -> dict[str, Any]:
        with self._lock:
            rows = [
                dict(r)
                for r in self._conn.execute(
                    "SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC"
                ).fetchall()
            ]
            samples_count = self._conn.execute("SELECT COUNT(*) FROM affective_samples").fetchone()[0]
            events_count = self._conn.execute("SELECT COUNT(*) FROM interaction_events").fetchone()[0]
            gens_count = self._conn.execute("SELECT COUNT(*) FROM agent_generations").fetchone()[0]

            def _agg(cond: str) -> dict[str, Any]:
                subset = [r for r in rows if r["condition"] == cond]
                n = len(subset)
                if n == 0:
                    return {
                        "count": 0,
                        "avg_efficiency": 0.0,
                        "avg_effectiveness": 0.0,
                        "avg_satisfaction_sus": 0.0,
                        "avg_delta_valence": 0.0,
                        "avg_cv_sam_alignment": 0.0,
                        "avg_time_sec": 0.0,
                    }
                return {
                    "count": n,
                    "avg_efficiency": round(sum(r["efficiency_score"] for r in subset) / n, 1),
                    "avg_effectiveness": round(sum(r["effectiveness_score"] for r in subset) / n, 1),
                    "avg_satisfaction_sus": round(sum(r["satisfaction_sus"] for r in subset) / n, 1),
                    "avg_delta_valence": round(sum(r["delta_valence"] for r in subset) / n, 3),
                    "avg_cv_sam_alignment": round(sum(r["cv_sam_alignment"] for r in subset) / n, 1),
                    "avg_time_sec": round(sum(r["time_on_task_sec"] for r in subset) / n, 1),
                }

            return {
                "rows": rows,
                "aggregates": {
                    "emotional_agent": _agg("emotional_agent"),
                    "prompt_only_control": _agg("prompt_only_control"),
                },
                "counts": {
                    "completed_sessions": len(rows),
                    "affective_samples": samples_count,
                    "interaction_events": events_count,
                    "agent_generations": gens_count,
                },
            }

    def seed_demo_pilot(self) -> int:
        """Populate 4 illustrative pilot evaluation rows comparing Control vs Emotional Agent."""
        now = time.time()
        pilots = [
            {
                "id": f"pilot-ctrl-1-{int(now)}",
                "participant_id": "P-01 (Pilot)",
                "scenario": "commerce",
                "condition": "prompt_only_control",
                "task_prompt": "Find the best university smartphone under 60,000 PKR with long battery",
                "started_at": now - 600,
                "ended_at": now - 518,
                "completed": 1,
                "task_accuracy": 100.0,
                "error_count": 2,
                "backtrack_count": 4,
                "click_count": 19,
                "rage_click_count": 2,
                "hesitation_count": 3,
                "time_on_task_sec": 82.0,
                "dominant_emotion": "fear",
                "visual_type": "Standard Z-Pattern Grid (Control)",
                "nav_type": "Horizontal Top-Down (Control)",
                "mean_valence": -0.38,
                "mean_arousal": 0.44,
                "mean_cognitive_load": 0.74,
                "delta_valence": -0.14,
                "efficiency_score": 43.7,
                "effectiveness_score": 90.0,
                "satisfaction_sus": 52.5,
                "sam_valence": 3,
                "sam_arousal": 7,
                "sam_dominance": 4,
                "cv_sam_alignment": 94.0,
                "nasa_tlx_mental": 6,
                "nasa_tlx_frustration": 6,
                "nasa_tlx_effort": 5,
                "notes": "Mirrors Daraz baseline on class whiteboard: high task completion, low satisfaction due to dense clutter under stress.",
            },
            {
                "id": f"pilot-emo-1-{int(now)}",
                "participant_id": "P-01 (Pilot)",
                "scenario": "commerce",
                "condition": "emotional_agent",
                "task_prompt": "Find the best university smartphone under 60,000 PKR with long battery",
                "started_at": now - 480,
                "ended_at": now - 437,
                "completed": 1,
                "task_accuracy": 100.0,
                "error_count": 0,
                "backtrack_count": 0,
                "click_count": 7,
                "rage_click_count": 0,
                "hesitation_count": 0,
                "time_on_task_sec": 43.0,
                "dominant_emotion": "neutral",
                "visual_type": "Focused & Spotlight",
                "nav_type": "Single-Path Guided Stepper",
                "mean_valence": 0.18,
                "mean_arousal": -0.05,
                "mean_cognitive_load": 0.28,
                "delta_valence": 0.42,
                "efficiency_score": 100.0,
                "effectiveness_score": 100.0,
                "satisfaction_sus": 87.5,
                "sam_valence": 7,
                "sam_arousal": 4,
                "sam_dominance": 7,
                "cv_sam_alignment": 84.0,
                "nasa_tlx_mental": 2,
                "nasa_tlx_frustration": 1,
                "nasa_tlx_effort": 2,
                "notes": "Emotional AI Agent switched to Spotlight + Stepper when overwhelmed; reduced clicks 19->7 and lifted SUS to 87.5.",
            },
            {
                "id": f"pilot-ctrl-2-{int(now)}",
                "participant_id": "P-02 (Pilot)",
                "scenario": "commerce",
                "condition": "prompt_only_control",
                "task_prompt": "Compare noise-canceling headphones for quiet studying",
                "started_at": now - 380,
                "ended_at": now - 315,
                "completed": 1,
                "task_accuracy": 85.0,
                "error_count": 1,
                "backtrack_count": 3,
                "click_count": 15,
                "rage_click_count": 1,
                "hesitation_count": 2,
                "time_on_task_sec": 65.0,
                "dominant_emotion": "sadness",
                "visual_type": "Standard Z-Pattern Grid (Control)",
                "nav_type": "Horizontal Top-Down (Control)",
                "mean_valence": -0.32,
                "mean_arousal": -0.35,
                "mean_cognitive_load": 0.48,
                "delta_valence": -0.08,
                "efficiency_score": 61.3,
                "effectiveness_score": 80.0,
                "satisfaction_sus": 57.5,
                "sam_valence": 3,
                "sam_arousal": 3,
                "sam_dominance": 4,
                "cv_sam_alignment": 91.0,
                "nasa_tlx_mental": 5,
                "nasa_tlx_frustration": 4,
                "nasa_tlx_effort": 6,
                "notes": "Fatigued participant struggled with small dense spec text in standard grid.",
            },
            {
                "id": f"pilot-emo-2-{int(now)}",
                "participant_id": "P-02 (Pilot)",
                "scenario": "commerce",
                "condition": "emotional_agent",
                "task_prompt": "Compare noise-canceling headphones for quiet studying",
                "started_at": now - 260,
                "ended_at": now - 219,
                "completed": 1,
                "task_accuracy": 100.0,
                "error_count": 0,
                "backtrack_count": 0,
                "click_count": 6,
                "rage_click_count": 0,
                "hesitation_count": 0,
                "time_on_task_sec": 41.0,
                "dominant_emotion": "happiness",
                "visual_type": "Minimalist Calm List",
                "nav_type": "Low-Friction Linear Stack",
                "mean_valence": 0.34,
                "mean_arousal": 0.12,
                "mean_cognitive_load": 0.22,
                "delta_valence": 0.36,
                "efficiency_score": 100.0,
                "effectiveness_score": 100.0,
                "satisfaction_sus": 90.0,
                "sam_valence": 7,
                "sam_arousal": 5,
                "sam_dominance": 8,
                "cv_sam_alignment": 92.0,
                "nasa_tlx_mental": 2,
                "nasa_tlx_frustration": 1,
                "nasa_tlx_effort": 2,
                "notes": "Minimalist Calm List + 1.14x readable typography + Voice Read-Aloud resolved visual fatigue.",
            },
        ]
        with self._lock:
            for p in pilots:
                cols = ", ".join(p.keys())
                placeholders = ", ".join(["?"] * len(p))
                self._conn.execute(
                    f"INSERT OR REPLACE INTO sessions ({cols}) VALUES ({placeholders})",
                    list(p.values()),
                )
            self._conn.commit()
        return len(pilots)

    def clear_all(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                DELETE FROM sessions;
                DELETE FROM affective_samples;
                DELETE FROM interaction_events;
                DELETE FROM agent_generations;
                """
            )
            self._conn.commit()

    def export_dataset(self, dataset: str, fmt: str = "csv") -> tuple[str, str]:
        table_map = {
            "sessions": "sessions",
            "samples": "affective_samples",
            "events": "interaction_events",
            "generations": "agent_generations",
        }
        table = table_map.get(dataset, "sessions")
        with self._lock:
            rows = [dict(r) for r in self._conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC").fetchall()]

        if fmt == "json":
            return json.dumps(rows, indent=2), "application/json"

        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        else:
            # Emit schema headers even when empty
            cols = [r[1] for r in self._conn.execute(f"PRAGMA table_info({table})").fetchall()]
            writer = csv.writer(buf)
            writer.writerow(cols)
        return buf.getvalue(), "text/csv"
