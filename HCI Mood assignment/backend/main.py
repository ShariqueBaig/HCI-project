"""FastAPI server exposing AURA's affective telemetry WebSocket, workspace REST APIs, and static UI."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import csv
import io
import json
import logging
from pathlib import Path
import time
from typing import Any

import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import numpy as np
from pydantic import BaseModel

from backend.affective_engine import AffectiveEngine, HCI_STATES
from backend.emotional_agent import (
    PRODUCT_CATALOG,
    compare_prompt_across_emotions,
    run_emotional_agent,
)
from backend.generative_ui_engine import generate_ui_schema
from backend.model_manager import ModelBundle
from backend.research_logger import ResearchLogger
from backend.vision_engine import VisionEngine
from backend.workspace_store import WorkspaceStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("aura.api")

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


class TaskCreate(BaseModel):
    title: str
    priority: str = "medium"
    estimatedMinutes: int = 15
    category: str = "General"


class TaskUpdate(BaseModel):
    title: str | None = None
    priority: str | None = None
    estimatedMinutes: int | None = None
    completed: bool | None = None
    category: str | None = None


class NoteCreate(BaseModel):
    title: str
    content: str = ""


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class IdeaCreate(BaseModel):
    text: str
    tag: str = "Spark"


class CameraToggle(BaseModel):
    enabled: bool


class AgencyUpdate(BaseModel):
    mode: str | None = None
    dwell_seconds: float | None = None
    reduced_motion: bool | None = None


class ProposalResponse(BaseModel):
    action: str  # 'accept' | 'dismiss' | 'undo'


class SimulateRequest(BaseModel):
    state: str | None = None


class LlmConfigBody(BaseModel):
    enabled: bool = False
    provider: str = "gemini"
    api_key: str = ""


class AgentPromptRequest(BaseModel):
    prompt: str
    scenario: str = "commerce"
    condition: str = "emotional_agent"
    session_id: str | None = None
    llm_config: LlmConfigBody | None = None


class AgentCompareRequest(BaseModel):
    prompt: str
    scenario: str = "commerce"


class SessionStartRequest(BaseModel):
    participant_id: str = "P-01"
    scenario: str = "commerce"
    condition: str = "emotional_agent"
    task_prompt: str


class ResearchEventRequest(BaseModel):
    session_id: str
    event_type: str
    target_id: str = ""
    metadata: dict[str, Any] | None = None


class SessionCompleteRequest(BaseModel):
    session_id: str
    completed: bool = True
    task_accuracy: float = 100.0
    error_count: int = 0
    backtrack_count: int = 0
    click_count: int = 0
    rage_click_count: int = 0
    hesitation_count: int = 0
    sus_answers: list[int]
    sam_valence: int = 5
    sam_arousal: int = 5
    sam_dominance: int = 5
    nasa_tlx_mental: int = 3
    nasa_tlx_frustration: int = 3
    nasa_tlx_effort: int = 3
    visual_type: str = "Focused & Spotlight"
    nav_type: str = "Bento Box"
    notes: str = ""


class RuntimeContext:
    def __init__(self) -> None:
        self.models = ModelBundle()
        self.store = WorkspaceStore()
        self.research = ResearchLogger()
        settings = self.store.snapshot()["settings"]
        self.affective = AffectiveEngine(dwell_seconds=float(settings.get("dwell_seconds", 3.0)))
        self.affective.configure(agency_mode=settings.get("agency_mode", "copilot"))
        self.vision: VisionEngine | None = None
        self.active_session_id: str | None = None
        self.active_condition: str = "emotional_agent"
        self.active_visual_type: str = "Focused & Spotlight"
        self.active_nav_type: str = "Bento Box"
        self._last_sample_ts: float = 0.0

    def init_models(self) -> None:
        if self.vision is None:
            self.models.load()
            self.vision = VisionEngine(self.models)

    def current_payload(self, include_frame: bool = True) -> dict[str, Any]:
        assert self.vision is not None
        vision_obs = self.vision.get_latest()
        telemetry = self.affective.update(vision_obs, task_pressure=self.store.task_pressure())
        workspace = self.store.snapshot()
        schema = generate_ui_schema(
            telemetry["active_state"],
            telemetry,
            workspace,
            from_state=telemetry.get("previous_state") or telemetry["active_state"],
        )

        # Log 1 Hz affective samples whenever an empirical trial session is active
        now = time.time()
        if self.active_session_id and (now - self._last_sample_ts) >= 1.0:
            self._last_sample_ts = now
            vtype = (
                "Standard Z-Pattern Grid (Control)"
                if self.active_condition == "prompt_only_control"
                else schema["layout"].get("visualType", self.active_visual_type)
            )
            ntype = (
                "Horizontal Top-Down (Control)"
                if self.active_condition == "prompt_only_control"
                else schema["layout"].get("navType", self.active_nav_type)
            )
            self.research.record_affective_sample(self.active_session_id, telemetry, vtype, ntype)

        proposal = telemetry.get("pending_proposal")
        if proposal is not None:
            proposed_schema = generate_ui_schema(
                proposal["target_state"],
                telemetry,
                workspace,
                from_state=telemetry["active_state"],
            )
            proposal = {
                **proposal,
                "structural_diff": proposed_schema["structuralDiff"],
                "target_mode_name": proposed_schema["modeName"],
            }
            telemetry["pending_proposal"] = proposal

        return {
            "telemetry": telemetry,
            "schema": schema,
            "annotated_frame_b64": vision_obs.get("annotated_frame_b64") if include_frame else None,
            "vision_latency_ms": vision_obs.get("latency_ms", 0.0),
        }


ctx = RuntimeContext()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ctx.init_models()
    yield
    if ctx.vision is not None:
        ctx.vision.stop_camera()


app = FastAPI(title="AURA Affective Generative UI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_ready() -> None:
    if ctx.vision is None:
        ctx.init_models()


@app.get("/api/health")
def health() -> dict[str, Any]:
    _ensure_ready()
    assert ctx.vision is not None
    return {
        "status": "ok",
        "models": ctx.models.status_dict(),
        "camera_active": ctx.vision.camera_active,
        "active_state": ctx.affective.active_state,
    }


@app.get("/api/workspace")
def get_workspace() -> dict[str, Any]:
    _ensure_ready()
    payload = ctx.current_payload(include_frame=False)
    return {
        "workspace": ctx.store.snapshot(),
        "telemetry": payload["telemetry"],
        "schema": payload["schema"],
        "models": ctx.models.status_dict(),
    }


@app.post("/api/tasks")
def create_task(body: TaskCreate) -> dict[str, Any]:
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")
    task = ctx.store.add_task(body.title, body.priority, body.estimatedMinutes, body.category)
    return {"task": task, "workspace": ctx.store.snapshot()}


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate) -> dict[str, Any]:
    task = ctx.store.update_task(task_id, body.model_dump())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task, "workspace": ctx.store.snapshot()}


@app.post("/api/tasks/{task_id}/microstep/{step_id}")
def toggle_microstep(task_id: str, step_id: str) -> dict[str, Any]:
    task = ctx.store.toggle_microstep(task_id, step_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task or microstep not found")
    return {"task": task, "workspace": ctx.store.snapshot()}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str) -> dict[str, Any]:
    if not ctx.store.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "workspace": ctx.store.snapshot()}


@app.post("/api/notes")
def create_note(body: NoteCreate) -> dict[str, Any]:
    note = ctx.store.add_note(body.title, body.content)
    return {"note": note, "workspace": ctx.store.snapshot()}


@app.patch("/api/notes/{note_id}")
def update_note(note_id: str, body: NoteUpdate) -> dict[str, Any]:
    note = ctx.store.update_note(note_id, body.title, body.content)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note, "workspace": ctx.store.snapshot()}


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str) -> dict[str, Any]:
    if not ctx.store.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True, "workspace": ctx.store.snapshot()}


@app.post("/api/ideas")
def create_idea(body: IdeaCreate) -> dict[str, Any]:
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Idea text cannot be empty")
    idea = ctx.store.add_idea(body.text, body.tag)
    return {"idea": idea, "workspace": ctx.store.snapshot()}


@app.delete("/api/ideas/{idea_id}")
def delete_idea(idea_id: str) -> dict[str, Any]:
    if not ctx.store.delete_idea(idea_id):
        raise HTTPException(status_code=404, detail="Idea not found")
    return {"ok": True, "workspace": ctx.store.snapshot()}


@app.post("/api/ideas/{idea_id}/promote")
def promote_idea(idea_id: str) -> dict[str, Any]:
    task = ctx.store.promote_idea(idea_id)
    if not task:
        raise HTTPException(status_code=404, detail="Idea not found")
    return {"task": task, "workspace": ctx.store.snapshot()}


@app.post("/api/camera/toggle")
def toggle_camera(body: CameraToggle) -> dict[str, Any]:
    _ensure_ready()
    assert ctx.vision is not None
    if body.enabled:
        ctx.affective.set_simulation(None)
        return ctx.vision.start_camera()
    return ctx.vision.stop_camera()


@app.post("/api/agency")
def update_agency(body: AgencyUpdate) -> dict[str, Any]:
    settings = ctx.store.update_settings(
        {
            "agency_mode": body.mode,
            "dwell_seconds": body.dwell_seconds,
            "reduced_motion": body.reduced_motion,
        }
    )
    ctx.affective.configure(agency_mode=settings["agency_mode"], dwell_seconds=settings["dwell_seconds"])
    return {"settings": settings, **ctx.current_payload(include_frame=False)}


@app.post("/api/proposal/respond")
def respond_proposal(body: ProposalResponse) -> dict[str, Any]:
    res = ctx.affective.respond_to_proposal(body.action)
    return {**res, **ctx.current_payload(include_frame=False)}


@app.post("/api/simulate")
def simulate_state(body: SimulateRequest) -> dict[str, Any]:
    if body.state is not None and body.state not in HCI_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state. Choose from {HCI_STATES}")
    res = ctx.affective.set_simulation(body.state)
    return {**res, **ctx.current_payload(include_frame=False)}


@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """Run real OpenCV YuNet + ONNX HSEmotion on an uploaded face photo and preview its UI."""
    _ensure_ready()
    assert ctx.vision is not None
    raw = await file.read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode uploaded image")

    obs = ctx.vision.analyze_frame(bgr, include_jpeg=True)
    # Compute instantaneous Circumplex + inferred state without overwriting user's live dwell state
    temp = AffectiveEngine()
    temp.agency_mode = "autonomous"
    temp.dwell_seconds = 0.0
    temp.cooldown_seconds = 0.0
    obs["camera_active"] = True
    snap = temp.update(obs, task_pressure=ctx.store.task_pressure(), now=100.0)
    snap2 = temp.update(obs, task_pressure=ctx.store.task_pressure(), now=101.0)
    preview_schema = generate_ui_schema(snap2["active_state"], snap2, ctx.store.snapshot())
    return {
        "vision": obs,
        "inferred_state": snap2["active_state"],
        "valence": snap2["valence"],
        "arousal": snap2["arousal"],
        "cognitive_load": snap2["cognitive_load"],
        "preview_schema": preview_schema,
    }


@app.get("/api/analytics/export")
def export_analytics(format: str = Query(default="json", pattern="^(json|csv)$")) -> Response:
    _ensure_ready()
    payload = ctx.current_payload(include_frame=False)
    events = ctx.affective.export_events()
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["timestamp", "from_state", "to_state", "source"])
        for ev in events:
            writer.writerow([ev["timestamp"], ev["from_state"], ev["to_state"], ev["source"]])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=aura_hci_session.csv"},
        )
    return JSONResponse(
        content={
            "active_state": payload["telemetry"]["active_state"],
            "metrics": payload["telemetry"]["metrics"],
            "transition_events": events,
            "models": ctx.models.status_dict(),
        }
    )


@app.get("/api/catalog")
def get_catalog() -> dict[str, Any]:
    return {"items": PRODUCT_CATALOG}


@app.post("/api/agent/prompt")
def agent_prompt(body: AgentPromptRequest) -> dict[str, Any]:
    _ensure_ready()
    payload = ctx.current_payload(include_frame=False)
    llm_cfg = body.llm_config.model_dump() if body.llm_config else None
    result = run_emotional_agent(
        prompt=body.prompt,
        scenario=body.scenario,
        condition=body.condition,
        affective=payload["telemetry"],
        workspace=ctx.store.snapshot(),
        llm_config=llm_cfg,
    )
    ctx.active_visual_type = result["visualType"]
    ctx.active_nav_type = result["navType"]
    ctx.research.record_agent_generation(body.session_id or ctx.active_session_id, result)
    return {"result": result, "telemetry": payload["telemetry"]}


@app.post("/api/agent/compare")
def agent_compare(body: AgentCompareRequest) -> dict[str, Any]:
    _ensure_ready()
    rows = compare_prompt_across_emotions(
        prompt=body.prompt,
        scenario=body.scenario,
        workspace=ctx.store.snapshot(),
    )
    return {"prompt": body.prompt, "scenario": body.scenario, "comparisons": rows}


@app.post("/api/research/session/start")
def start_research_session(body: SessionStartRequest) -> dict[str, Any]:
    _ensure_ready()
    payload = ctx.current_payload(include_frame=False)
    tel = payload["telemetry"]
    vtype = (
        "Standard Z-Pattern Grid (Control)"
        if body.condition == "prompt_only_control"
        else payload["schema"]["layout"].get("visualType", "Focused & Spotlight")
    )
    ntype = (
        "Horizontal Top-Down (Control)"
        if body.condition == "prompt_only_control"
        else payload["schema"]["layout"].get("navType", "Bento Box")
    )
    ses = ctx.research.start_session(
        participant_id=body.participant_id,
        scenario=body.scenario,
        condition=body.condition,
        task_prompt=body.task_prompt,
        dominant_emotion=tel["dominant_emotion"],
        visual_type=vtype,
        nav_type=ntype,
    )
    ctx.active_session_id = ses["id"]
    ctx.active_condition = body.condition
    ctx.active_visual_type = vtype
    ctx.active_nav_type = ntype
    ctx._last_sample_ts = 0.0
    return {"session": ses}


@app.post("/api/research/event")
def log_research_event(body: ResearchEventRequest) -> dict[str, Any]:
    ctx.research.record_interaction_event(
        session_id=body.session_id,
        event_type=body.event_type,
        target_id=body.target_id,
        metadata=body.metadata,
    )
    return {"ok": True}


@app.post("/api/research/session/complete")
def complete_research_session(body: SessionCompleteRequest) -> dict[str, Any]:
    _ensure_ready()
    if len(body.sus_answers) != 10:
        raise HTTPException(status_code=400, detail="sus_answers must have exactly 10 items")
    payload = ctx.current_payload(include_frame=False)
    tel = payload["telemetry"]
    ses = ctx.research.complete_session(
        session_id=body.session_id,
        completed=body.completed,
        task_accuracy=body.task_accuracy,
        error_count=body.error_count,
        backtrack_count=body.backtrack_count,
        click_count=body.click_count,
        rage_click_count=body.rage_click_count,
        hesitation_count=body.hesitation_count,
        sus_answers=body.sus_answers,
        sam_valence=body.sam_valence,
        sam_arousal=body.sam_arousal,
        sam_dominance=body.sam_dominance,
        nasa_tlx_mental=body.nasa_tlx_mental,
        nasa_tlx_frustration=body.nasa_tlx_frustration,
        nasa_tlx_effort=body.nasa_tlx_effort,
        visual_type=body.visual_type,
        nav_type=body.nav_type,
        fallback_emotion=tel["dominant_emotion"],
        fallback_valence=tel["valence"],
        fallback_arousal=tel["arousal"],
        fallback_load=tel["cognitive_load"],
        notes=body.notes,
    )
    if not ses:
        raise HTTPException(status_code=404, detail="Session not found")
    if ctx.active_session_id == body.session_id:
        ctx.active_session_id = None
    return {"session": ses, "summary": ctx.research.whiteboard_summary()}


@app.get("/api/research/whiteboard-table")
def get_whiteboard_table() -> dict[str, Any]:
    return ctx.research.whiteboard_summary()


@app.get("/api/research/export")
def export_research_data(
    dataset: str = Query(default="sessions", pattern="^(sessions|samples|events|generations)$"),
    format: str = Query(default="csv", pattern="^(csv|json)$"),
) -> Response:
    content, media_type = ctx.research.export_dataset(dataset, format)
    ext = "json" if format == "json" else "csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=aura_{dataset}.{ext}"},
    )


@app.post("/api/research/seed-demo")
def seed_demo_research() -> dict[str, Any]:
    count = ctx.research.seed_demo_pilot()
    return {"inserted": count, "summary": ctx.research.whiteboard_summary()}


@app.delete("/api/research/sessions")
def clear_research_sessions() -> dict[str, Any]:
    ctx.active_session_id = None
    ctx.research.clear_all()
    return {"ok": True, "summary": ctx.research.whiteboard_summary()}


@app.websocket("/ws/affective")
async def ws_affective(websocket: WebSocket) -> None:
    await websocket.accept()
    _ensure_ready()
    try:
        while True:
            payload = ctx.current_payload(include_frame=True)
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.14)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.debug("WebSocket closed: %s", exc)


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
