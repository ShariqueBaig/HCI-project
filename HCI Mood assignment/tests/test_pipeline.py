"""Automated verification suite for AURA CV pipeline, affective hysteresis, Generative UI, and API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
from fastapi.testclient import TestClient
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.affective_engine import AffectiveEngine, HCI_STATES  # noqa: E402
from backend.emotional_agent import compare_prompt_across_emotions  # noqa: E402
from backend.generative_ui_engine import generate_ui_schema  # noqa: E402
from backend.main import app  # noqa: E402
from backend.model_manager import ModelBundle  # noqa: E402
from backend.research_logger import ResearchLogger, compute_cv_sam_alignment, compute_sus  # noqa: E402
from backend.vision_engine import VisionEngine  # noqa: E402
from backend.workspace_store import WorkspaceStore  # noqa: E402


def test_models_and_vision_inference() -> None:
    bundle = ModelBundle().load()
    status = bundle.status_dict()
    assert status["ready"] is True, f"Models failed to load: {status}"
    assert status["yunet_available"] is True
    assert status["emotion_model"] in ("hsemotion", "ferplus")

    vision = VisionEngine(bundle)
    # Create a synthetic test frame (640x480) and also test direct emotion predictor on 224x224 crop
    blank = np.full((480, 640, 3), 180, dtype=np.uint8)
    obs = vision.analyze_frame(blank, include_jpeg=True)
    assert "emotions" in obs and len(obs["emotions"]) == 8
    assert obs["annotated_frame_b64"] is not None

    # Direct ONNX emotion probability sanity check
    crop = np.random.randint(60, 200, (160, 160, 3), dtype=np.uint8)
    probs = vision._predict_emotions(crop)
    assert len(probs) == 8
    assert abs(sum(probs.values()) - 1.0) < 1e-3, f"Probabilities did not sum to 1: {probs}"
    print("[PASS] ONNX ModelBundle & VisionEngine inference")


def test_affective_hysteresis_and_circumplex() -> None:
    engine = AffectiveEngine(dwell_seconds=3.0, cooldown_seconds=5.0, ema_alpha=0.5)
    engine.configure(agency_mode="autonomous")

    spike_obs = {
        "camera_active": True,
        "face_detected": True,
        "confidence": 0.9,
        "attention_score": 0.65,
        "head_pitch_proxy": 0.2,
        "emotions": {
            "anger": 0.55, "fear": 0.30, "disgust": 0.05, "sadness": 0.03,
            "neutral": 0.04, "happiness": 0.01, "surprise": 0.01, "contempt": 0.01,
        },
    }
    calm_obs = {
        "camera_active": True,
        "face_detected": True,
        "confidence": 0.9,
        "attention_score": 0.95,
        "head_pitch_proxy": 0.1,
        "emotions": {
            "neutral": 0.85, "happiness": 0.08, "sadness": 0.02, "anger": 0.01,
            "fear": 0.01, "disgust": 0.01, "surprise": 0.01, "contempt": 0.01,
        },
    }

    # Transient spike at t=10..11 must NOT switch active_state
    t1 = engine.update(spike_obs, now=10.0)
    t2 = engine.update(spike_obs, now=11.0)
    assert t2["active_state"] == "focused", "Should resist transient 1s spike"

    # Return to calm at t=11.5 -> flicker prevented counter increments
    t3 = engine.update(calm_obs, now=11.5)
    assert t3["active_state"] == "focused"
    assert t3["metrics"]["flickers_prevented"] >= 1

    # Sustained overwhelm for >3s (t=20..24) SHOULD trigger transition
    engine.update(spike_obs, now=20.0)
    engine.update(spike_obs, now=21.5)
    t_switch = engine.update(spike_obs, now=23.5)
    assert t_switch["active_state"] == "overwhelmed", f"Expected overwhelmed, got {t_switch['active_state']}"
    assert t_switch["valence"] < 0 and t_switch["arousal"] > 0
    print("[PASS] AffectiveEngine Circumplex & anti-thrashing dwell hysteresis")


def test_generative_ui_all_topologies() -> None:
    store = WorkspaceStore(Path(__file__).resolve().parent / "_tmp_workspace.json")
    try:
        ws = store.snapshot()
        expected_topologies = {
            "focused": ("tri-pane-studio", 1.0),
            "overwhelmed": ("single-focus-tunnel", 1.26),
            "fatigued": ("low-friction-deck", 1.16),
            "energized": ("divergent-board", 1.04),
            "disoriented": ("orientation-split", 1.1),
        }
        seen_topologies = set()
        for st, (topo, scale) in expected_topologies.items():
            schema = generate_ui_schema(
                st,
                {"valence": 0.0, "arousal": 0.0, "cognitive_load": 0.4, "attention_score": 0.8},
                ws,
            )
            assert schema["layout"]["topology"] == topo
            assert abs(schema["interaction"]["targetScale"] - scale) < 1e-6
            assert len(schema["components"]) >= 3
            assert len(schema["hciRationale"]) >= 1
            seen_topologies.add(topo)
        assert len(seen_topologies) == 5
    finally:
        tmp = Path(__file__).resolve().parent / "_tmp_workspace.json"
        if tmp.exists():
            tmp.unlink()
    print("[PASS] GenerativeUIEngine produces 5 distinct structural topologies")


def test_fastapi_rest_and_websocket() -> None:
    with TestClient(app) as client:
        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "ok"

        r_ws = client.get("/api/workspace")
        assert r_ws.status_code == 200
        assert len(r_ws.json()["workspace"]["tasks"]) >= 1

        # Simulate overwhelmed in Co-Pilot mode -> should create pending proposal
        client.post("/api/agency", json={"mode": "copilot"})
        r_sim = client.post("/api/simulate", json={"state": "overwhelmed"})
        assert r_sim.status_code == 200
        assert r_sim.json()["telemetry"]["pending_proposal"]["target_state"] == "overwhelmed"

        # Accept proposal -> switches active state + topology
        r_acc = client.post("/api/proposal/respond", json={"action": "accept"})
        assert r_acc.status_code == 200
        assert r_acc.json()["schema"]["layout"]["topology"] == "single-focus-tunnel"

        # Undo -> reverts back to focused
        r_undo = client.post("/api/proposal/respond", json={"action": "undo"})
        assert r_undo.status_code == 200
        assert r_undo.json()["schema"]["layout"]["topology"] == "tri-pane-studio"

        # Clear simulation
        client.post("/api/simulate", json={"state": None})

        # Test analytics export
        r_csv = client.get("/api/analytics/export?format=csv")
        assert r_csv.status_code == 200
        assert "timestamp,from_state,to_state,source" in r_csv.text

        # Test WebSocket stream
        with client.websocket_connect("/ws/affective") as ws:
            msg = json.loads(ws.receive_text())
            assert "telemetry" in msg and "schema" in msg

        # Ensure all 5 states work smoothly in autonomous simulation
        client.post("/api/agency", json={"mode": "autonomous"})
        for st in HCI_STATES:
            res = client.post("/api/simulate", json={"state": st})
            assert res.status_code == 200
            assert res.json()["schema"]["targetState"] == st
        client.post("/api/simulate", json={"state": None})
        client.post("/api/agency", json={"mode": "copilot"})

        # Test Emotional AI Agent prompt & cross-emotion divergence endpoints
        r_agent = client.post(
            "/api/agent/prompt",
            json={
                "prompt": "Find the best university smartphone under 60,000 PKR with long battery",
                "scenario": "commerce",
                "condition": "emotional_agent",
            },
        )
        assert r_agent.status_code == 200
        assert r_agent.json()["result"]["visualType"] == "Focused & Spotlight"

        r_cmp = client.post(
            "/api/agent/compare",
            json={"prompt": "Compare noise-canceling headphones for quiet studying", "scenario": "commerce"},
        )
        assert r_cmp.status_code == 200
        assert len(r_cmp.json()["comparisons"]) == 6

        # Test empirical HCI session start -> event -> complete -> whiteboard -> export
        r_start = client.post(
            "/api/research/session/start",
            json={
                "participant_id": "P-TEST",
                "scenario": "commerce",
                "condition": "emotional_agent",
                "task_prompt": "Test task",
            },
        )
        assert r_start.status_code == 200
        sid = r_start.json()["session"]["id"]

        r_ev = client.post(
            "/api/research/event",
            json={"session_id": sid, "event_type": "task_complete", "target_id": "p-phone-1"},
        )
        assert r_ev.status_code == 200

        r_comp = client.post(
            "/api/research/session/complete",
            json={
                "session_id": sid,
                "completed": True,
                "task_accuracy": 100.0,
                "error_count": 0,
                "backtrack_count": 0,
                "click_count": 6,
                "rage_click_count": 0,
                "hesitation_count": 0,
                "sus_answers": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
                "sam_valence": 7,
                "sam_arousal": 4,
                "sam_dominance": 7,
                "nasa_tlx_mental": 2,
                "nasa_tlx_frustration": 1,
                "nasa_tlx_effort": 2,
                "visual_type": "Focused & Spotlight",
                "nav_type": "Bento Box",
            },
        )
        assert r_comp.status_code == 200
        assert r_comp.json()["session"]["satisfaction_sus"] == 100.0

        r_wb = client.get("/api/research/whiteboard-table")
        assert r_wb.status_code == 200
        assert any(r["id"] == sid for r in r_wb.json()["rows"])

        r_exp = client.get("/api/research/export?dataset=sessions&format=csv")
        assert r_exp.status_code == 200
        assert "efficiency_score,effectiveness_score,satisfaction_sus" in r_exp.text

        # Clean up test session from production DB
        client.delete("/api/research/sessions")
    print("[PASS] FastAPI REST + WebSocket + Co-Pilot + Research Logger lifecycle")


def test_emotional_agent_and_research_math() -> None:
    # Exact SUS verification
    assert compute_sus([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0
    assert compute_sus([3] * 10) == 50.0
    assert compute_cv_sam_alignment(0.5, 7) == 100.0

    # Same prompt across emotions must diverge structurally
    store = WorkspaceStore(Path(__file__).resolve().parent / "_tmp_ws2.json")
    db_path = Path(__file__).resolve().parent / "_tmp_study.db"
    try:
        rows = compare_prompt_across_emotions(
            "Find the best university smartphone under 60,000 PKR with long battery",
            "commerce",
            store.snapshot(),
        )
        assert len(rows) == 6
        nav_types = {r["navType"] for r in rows}
        vis_types = {r["visualType"] for r in rows}
        counts = {r["label"]: r["visibleCount"] for r in rows}
        assert len(nav_types) == 6, f"Expected 6 distinct nav types, got {nav_types}"
        assert len(vis_types) >= 4
        assert counts["Overwhelmed"] == 1
        assert counts["Control (Prompt-Only)"] == 12

        logger = ResearchLogger(db_path)
        ses = logger.start_session("P-99", "commerce", "emotional_agent", "Test prompt")
        logger.record_affective_sample(
            ses["id"],
            {"timestamp": 100.0, "source": "webcam", "dominant_emotion": "happiness", "raw_confidence": 0.9, "emotions": {"happiness": 0.9}, "valence": 0.5, "arousal": 0.4, "attention_score": 0.9, "head_pitch_proxy": 0.1, "cognitive_load": 0.2, "active_state": "energized"},
            "Visual Bento & Card Grid",
            "Bento Box + Visual Facets",
        )
        done = logger.complete_session(
            session_id=ses["id"],
            completed=True,
            task_accuracy=100.0,
            error_count=0,
            backtrack_count=0,
            click_count=7,
            rage_click_count=0,
            hesitation_count=0,
            sus_answers=[5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
            sam_valence=7,
            sam_arousal=5,
            sam_dominance=7,
            nasa_tlx_mental=2,
            nasa_tlx_frustration=1,
            nasa_tlx_effort=2,
            visual_type="Visual Bento & Card Grid",
            nav_type="Bento Box + Visual Facets",
        )
        assert done is not None
        assert done["satisfaction_sus"] == 100.0
        assert done["effectiveness_score"] == 100.0
        assert done["cv_sam_alignment"] == 100.0
        csv_text, _ = logger.export_dataset("sessions", "csv")
        assert "P-99" in csv_text
        logger._conn.close()
    finally:
        for p in (Path(__file__).resolve().parent / "_tmp_ws2.json", db_path):
            if p.exists():
                p.unlink()
    print("[PASS] EmotionalAgent Same-Prompt Divergence & ResearchLogger SUS/ISO/SAM math")


if __name__ == "__main__":
    test_models_and_vision_inference()
    test_affective_hysteresis_and_circumplex()
    test_generative_ui_all_topologies()
    test_emotional_agent_and_research_math()
    test_fastapi_rest_and_websocket()
    print("\nALL AURA VERIFICATION CHECKS PASSED.")
