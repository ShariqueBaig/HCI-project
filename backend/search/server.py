"""Local FastAPI server for Aura UI (unified shell + Search + Companion API).

Security model: binds to 127.0.0.1 only, and every /api and /ws request must
carry the random per-launch token (header ``X-Aura-Token`` or query ``t``).
Default port: 8765 (automatically falls back to the next free port if busy).
"""
import argparse
import asyncio
import json
import os
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.paths import resource_dirs
from backend.search.live_state import LiveStateStore, SimulatedLiveState

HOST = '127.0.0.1'
DEFAULT_PORT = int(os.environ.get('AURA_SEARCH_PORT', '8765'))
WS_PUSH_S = 0.5

_PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>Aura Search</title>
<body style="font-family:system-ui;background:#0c0b12;color:#eeecf3;padding:32px">
<h2>Aura Search</h2><p>The UI has not been built yet. Run
<code>npm install</code> and <code>npm run build</code> in <code>search_ui/</code>.</p>
</body>"""


def find_ui_dist():
    for folder in resource_dirs():
        path = os.path.join(folder, 'search_ui', 'dist')
        if os.path.isfile(os.path.join(path, 'index.html')):
            return path
    return None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class TypingReport(BaseModel):
    events: list = Field(default_factory=list, max_length=400)
    now: float


class BehaviourEvent(BaseModel):
    type: str = Field(pattern='^(rage_click|hesitation|backtrack|scroll_thrash|hover_abandon)$')


MAX_SEARCHES = 50


class RerenderRequest(BaseModel):
    policy: str = Field(pattern='^(neutral|focused|overwhelmed|fatigued|energized|disoriented)$')


class ViewChoice(BaseModel):
    policy: str = Field(pattern='^(neutral|focused|overwhelmed|fatigued|energized|disoriented)$')


class ProposalAction(BaseModel):
    proposal_id: str = Field(default='', max_length=40)
    action: str = Field(pattern='^(accept|dismiss|undo)$')


class MoodSimulation(BaseModel):
    state: Optional[str] = Field(default=None, pattern='^(focused|overwhelmed|fatigued|energized|disoriented)$')
    duration_s: float = Field(default=45.0, ge=5, le=300)


class CameraToggle(BaseModel):
    enabled: bool


class TaskStart(BaseModel):
    task_id: str = Field(min_length=1, max_length=60)


class SurveyBody(BaseModel):
    kind: str = Field(pattern='^(task|sus)$')
    task_id: str = Field(default='', max_length=60)
    answers: dict = Field(default_factory=dict)
    answer_text: str = Field(default='', max_length=500)


class ComfortUpdate(BaseModel):
    auto_bright: Optional[bool] = None
    focus_mode: Optional[bool] = None
    auto_music: Optional[bool] = None
    theme: Optional[str] = Field(default=None, pattern='^(dark|slate|light|sepia|contrast)$')
    auto_adapt: Optional[bool] = None
    view_mode_override: Optional[str] = Field(default=None, max_length=32)
    onboarding_complete: Optional[bool] = None


class AudioAction(BaseModel):
    action: str = Field(pattern='^(connect|disconnect|play_pause|next|prev)$')


class NudgeAction(BaseModel):
    action: str = Field(pattern='^(dismiss|snooze|breathe|chat)$')
    snooze_minutes: int = Field(default=30, ge=1, le=240)


class ChatSend(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class JournalNote(BaseModel):
    note: str = Field(default='', max_length=2000)
    reflection: str = Field(default='', max_length=2000)


class ConsentGrant(BaseModel):
    participant_code: str = Field(min_length=1, max_length=64)
    store_queries: bool = True


class ConsentWithdraw(BaseModel):
    confirm: bool = False


class CalibrationStart(BaseModel):
    duration_s: float = Field(default=30.0, ge=5.0, le=60.0)


class CalibrationSample(BaseModel):
    keys_per_second: float = 0.0
    error_rate: float = 0.0
    mean_dwell: float = 0.0
    mean_flight: float = 0.0
    std_flight: float = 0.0
    flight_count: int = 0


class RecordingFinalize(BaseModel):
    perceived_stress: Optional[int] = Field(default=None, ge=0, le=10)
    mood: Optional[int] = Field(default=None, ge=0, le=10)
    note: str = Field(default='', max_length=2000)
    reflection: str = Field(default='', max_length=2000)
    skip_ratings: bool = False


class DemoAction(BaseModel):
    action: str = Field(pattern='^(script|manual|stop|notify)$')
    level: Optional[float] = None


class BreathingState(BaseModel):
    active: bool


UNCERTAIN_ERROR_RATE = 0.2


def create_app(store, token, ui_dist=None, chain=None, stage_a=None, hub=None, composer=None,
               research=None, controller=None):
    app = FastAPI(title='Aura v2', docs_url=None, redoc_url=None, openapi_url=None)
    if research is None:
        from backend.search.research_bridge import ResearchBridge
        research = ResearchBridge()
    app.state.research = research
    last_task = {}
    if hub is None:
        from backend.search.hub import StateHub
        hub = StateHub(store)
    app.state.hub = hub
    hub.anticipator.listener = research.record_anticipation
    if chain is None:
        from backend.search.providers import ProviderChain
        chain = ProviderChain()
    if stage_a is None:
        from backend.llm_controller import LLMController
        from backend.search.synthesis import StageA
        stage_a = StageA(LLMController())
    if composer is None:
        from backend.search.composer import Composer
        composer = Composer(getattr(stage_a, 'llm', None))
    if controller is None:
        from backend.daemon_controller import AuraController
        controller = AuraController(standalone=True, persist=False, live_state=store)
    app.state.controller = controller
    searches = OrderedDict()

    from backend.search.composer import state_summary_from
    from backend.search.policy import get_policy
    from backend.search.validator import referenced_claims

    def _compose(rec, policy, state_summary):
        cache = rec['_specs']
        key = policy.get('cache_key', policy['name'])
        if key not in cache:
            spec = composer.compose(rec['query'], rec['stageA'], rec['_sources_full'], policy,
                                    state_summary, trail=rec['_trail'], history=rec['_history'])
            spec['claims_shown'] = sorted(referenced_claims(spec))
            cache[key] = spec
        return cache[key]

    def _with_clarifier(policy):
        p = dict(policy, proactive=dict(policy['proactive'], clarifiers=True),
                 cache_key=policy['name'] + '+clarify')
        if 'ClarifierChips' not in p['allowed_widgets']:
            p['allowed_widgets'] = list(p['allowed_widgets']) + ['ClarifierChips']
        return p

    def _get(search_id):
        rec = searches.get(search_id)
        if rec is None:
            raise HTTPException(status_code=404, detail='unknown or expired search')
        return rec

    def _public(rec, **extra):
        out = {k: v for k, v in rec.items() if not k.startswith('_')}
        out.update(extra)
        return out

    def _check(tok):
        if not tok or not secrets.compare_digest(str(tok), token):
            raise HTTPException(status_code=401, detail='bad or missing token')

    def _resolve_initial_policy(snap):
        """Honor Control A, active mood simulation, manual view override / auto_adapt=False, else fused policy."""
        adaptive = bool((snap or {}).get('adaptive', False))
        if not adaptive:
            return get_policy('neutral'), False
        if (snap or {}).get('simulation'):
            return (snap or {}).get('policy') or get_policy('neutral'), True
        if controller:
            auto_adapt = bool(controller.settings.get('auto_adapt', True))
            override = (controller.settings.get('view_mode_override') or '').strip()
            if override:
                return get_policy(override), True
            if not auto_adapt:
                return get_policy('neutral'), True
        return (snap or {}).get('policy') or get_policy('neutral'), True

    @app.middleware('http')
    async def require_token(request: Request, call_next):
        if request.url.path.startswith('/api/'):
            tok = request.headers.get('x-aura-token') or request.query_params.get('t')
            if not tok or not secrets.compare_digest(str(tok), token):
                return JSONResponse({'detail': 'bad or missing token'}, status_code=401)
        return await call_next(request)

    def _payload():
        live = store.get()
        cur = hub.current() if live is not None else None
        return {
            'live': live,
            'state': cur,
            'app': controller.app_status() if controller else None,
            'server_ts': time.time(),
        }

    @app.get('/api/health')
    def health():
        return {'ok': True, 'has_state': store.get() is not None}

    @app.get('/api/state')
    def state():
        p = _payload()
        if p['live'] is None:
            raise HTTPException(status_code=503, detail='no state yet')
        return p

    @app.get('/api/search/status')
    def search_status():
        return {'providers': chain.status(),
                'llm': bool(getattr(getattr(stage_a, 'llm', None), 'key', ''))}

    @app.get('/api/fixtures')
    def fixtures():
        return {'fixtures': chain.fixtures.list()}

    def _prepare_search_record(query, res, a, live, snap, t0, t1, t2):
        sources = [s.to_dict() for s in res.sources]
        reformulation = hub.behaviour.add_query(query)
        policy, adaptive = _resolve_initial_policy(snap)
        rec = {
            'search_id': uuid.uuid4().hex[:12],
            'query': query,
            'created_at': time.time(),
            'condition': (live or {}).get('condition'),
            'state_at_query': {k: (live or {}).get(k) for k in ('score', 'tier', 'label')},
            'reformulation': reformulation,
            'fused_at_query': (snap or {}).get('fused'),
            'adaptive': adaptive,
            'policy': policy,
            'provider': res.provider,
            'provider_note': res.note,
            'sources': [{k: v for k, v in s.items() if k != 'content'} for s in sources],
            'stageA': a,
        }
        typing_now = (snap or {}).get('typing') or {}
        rec['query_uncertain'] = bool(
            rec['adaptive'] and typing_now.get('fresh')
            and (typing_now.get('features') or {}).get('error_rate', 0) >= UNCERTAIN_ERROR_RATE)
        if rec['query_uncertain']:
            policy = _with_clarifier(policy)
        rec['policy'] = policy
        rec.update(_sources_full=sources, _specs={},
                   _trail=(snap or {}).get('query_trail') or [query],
                   _history=hub.text.lines())
        return rec

    def _finalize_search_record(rec, snap, t0, t1, t2):
        quiet = bool(((snap or {}).get('fused') or {}).get('quiet'))
        summary = state_summary_from((snap or {}).get('fused')) if rec['adaptive'] else None
        spec = _compose(rec, rec['policy'], summary)
        t3 = time.perf_counter()
        rec['timings_ms'] = {
            'retrieval': round((t1 - t0) * 1000),
            'stageA': round((t2 - t1) * 1000),
            'stageB': round((t3 - t2) * 1000),
            'total': round((t3 - t0) * 1000),
        }
        searches[rec['search_id']] = rec
        while len(searches) > MAX_SEARCHES:
            searches.popitem(last=False)
        hub.on_search(rec['search_id'], rec['query'], rec['policy']['name'],
                      [c['type'] for c in spec['components']],
                      ((snap or {}).get('fused') or {}).get('committed_state'), rec['reformulation'])
        research.record_search(rec, spec, snap)
        return _public(rec, spec=spec, quiet=quiet, task_id=research.active_task_id())

    @app.post('/api/search')
    def search(body: SearchRequest):
        query = ' '.join(body.query.split())
        if not query:
            raise HTTPException(status_code=422, detail='empty query')
        live = store.get()
        snap = hub.current() if live is not None else None
        t0 = time.perf_counter()
        try:
            res = chain.search(query, task_id=research.active_task_id())
        except Exception as e:
            raise HTTPException(status_code=502, detail='search failed: {}'.format(str(e)[:200]))
        t1 = time.perf_counter()
        sources = [s.to_dict() for s in res.sources]
        a = stage_a.run(query, sources)
        t2 = time.perf_counter()
        rec = _prepare_search_record(query, res, a, live, snap, t0, t1, t2)
        return _finalize_search_record(rec, snap, t0, t1, t2)

    @app.post('/api/search/stream')
    async def search_stream(body: SearchRequest):
        """Progressive SSE search: streams stage updates + immediate Stage A TL;DR before Stage B."""
        query = ' '.join(body.query.split())
        if not query:
            raise HTTPException(status_code=422, detail='empty query')

        async def gen():
            def emit(obj):
                return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

            live = store.get()
            snap = hub.current() if live is not None else None
            t0 = time.perf_counter()
            yield emit({'event': 'stage', 'stage': 'retrieving', 'message': 'Searching sources…'})
            try:
                res = await asyncio.to_thread(chain.search, query, research.active_task_id())
            except Exception as e:
                yield emit({'event': 'error', 'detail': 'search failed: {}'.format(str(e)[:200])})
                return
            t1 = time.perf_counter()
            sources = [s.to_dict() for s in res.sources]
            yield emit({'event': 'stage', 'stage': 'synthesizing',
                        'message': 'Extracting cited facts…',
                        'source_count': len(sources), 'provider': res.provider})
            a = await asyncio.to_thread(stage_a.run, query, sources)
            t2 = time.perf_counter()
            rec = _prepare_search_record(query, res, a, live, snap, t0, t1, t2)
            yield emit({
                'event': 'stageA',
                'search_id': rec['search_id'],
                'query': query,
                'provider': res.provider,
                'provider_note': res.note,
                'sources': rec['sources'],
                'stageA': a,
                'policy': rec['policy'],
                'adaptive': rec['adaptive'],
                'timings_ms': {'retrieval': round((t1 - t0) * 1000), 'stageA': round((t2 - t1) * 1000)},
            })
            yield emit({'event': 'stage', 'stage': 'composing', 'message': 'Tailoring layout…'})
            result = await asyncio.to_thread(_finalize_search_record, rec, snap, t0, t1, t2)
            yield emit({'event': 'done', 'result': result})

        return StreamingResponse(gen(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache'})

    @app.post('/api/search/{search_id}/rerender')
    def rerender(search_id: str, body: RerenderRequest):
        rec = _get(search_id)
        t0 = time.perf_counter()
        policy = get_policy(body.policy)
        summary = None if body.policy == 'neutral' else {
            'state': body.policy, 'confidence': None, 'why': ['layout selected by user']}
        live_fused = (hub.current() or {}).get('fused') if store.get() else None
        if live_fused and live_fused.get('committed_state') == body.policy:
            summary = state_summary_from(live_fused)
        spec = _compose(rec, policy, summary)
        hub.anticipator.user_choice(search_id, body.policy)
        hub.text.add_event(search_id, 'chose {} view'.format(body.policy))
        research.record_event('standard_view' if body.policy == 'neutral' else 'adapted_view',
                              search_id, target=body.policy)
        return {'search_id': search_id, 'policy': policy, 'spec': spec,
                'ms': round((time.perf_counter() - t0) * 1000)}

    @app.post('/api/search/{search_id}/view')
    def view_choice(search_id: str, body: ViewChoice):
        _get(search_id)
        hub.anticipator.user_choice(search_id, body.policy)
        research.record_event('standard_view' if body.policy == 'neutral' else 'adapted_view',
                              search_id, target=body.policy)
        return {'ok': True}

    @app.post('/api/search/{search_id}/proposal')
    def proposal(search_id: str, body: ProposalAction):
        rec = _get(search_id)
        try:
            target = hub.anticipator.respond(body.proposal_id, body.action)
        except KeyError as e:
            raise HTTPException(status_code=409, detail=str(e).strip("'"))
        hub.text.add_event(search_id, '{} offer'.format(body.action))
        hub.tick()
        if target is None:
            return {'search_id': search_id, 'action': body.action, 'policy': None, 'spec': None}
        policy = get_policy(target)
        fused = (hub.current() or {}).get('fused')
        summary = None if target == 'neutral' else (
            state_summary_from(fused) if fused and fused.get('committed_state') == target
            else {'state': target, 'confidence': None, 'why': ['offered by Aura and accepted']})
        spec = _compose(rec, policy, summary)
        return {'search_id': search_id, 'action': body.action, 'policy': policy, 'spec': spec}

    @app.post('/api/simulate')
    def simulate(body: MoodSimulation):
        if controller and controller.blinded:
            raise HTTPException(status_code=403, detail='Simulation is locked during a blinded study recording.')
        st = hub.simulate(body.state, body.duration_s)
        if controller:
            if body.state == 'overwhelmed':
                controller._sim_ticks = 30
            elif body.state is None:
                controller._sim_ticks = 0
        research.record_event('mood_sim_start' if body.state else 'mood_sim_stop', None,
                              target=body.state)
        return {'simulation': st}

    @app.get('/api/camera')
    def camera_status():
        from backend.vision.sensor import vision_available
        if hub.camera is None:
            ok, why = vision_available()
            return {'available': ok, 'active': False, 'loading': False, 'error': None if ok else why,
                    'latest': None}
        return hub.camera.status()

    @app.get('/api/camera/explain')
    def camera_explain():
        if hub.camera is None or not hub.camera.active:
            return {'active': False, 'detail': None, 'used_by_fusion': False}
        from backend.search.state_fusion import CAMERA_FRESH_S
        lat = hub.camera.latest() or {}
        used = bool(lat.get('face')) and time.time() - lat.get('ts', 0) <= CAMERA_FRESH_S and not (hub.current() or {}).get('simulation')
        return {'active': True, 'detail': hub.camera.explain(), 'used_by_fusion': used}

    @app.post('/api/camera')
    def camera_toggle(body: CameraToggle):
        from backend.vision.sensor import CameraSensor
        if hub.camera is None:
            hub.camera = CameraSensor()
        st = hub.camera.start() if body.enabled else hub.camera.stop()
        research.record_event('camera_on' if st['active'] else 'camera_off')
        return st

    @app.get('/api/study')
    def study_status():
        from backend.study_metrics import SUS_ITEMS
        st = research.status()
        st['tasks'] = [f for f in chain.fixtures.list() if f.get('task')]
        st['sus_items'] = list(SUS_ITEMS)
        return st

    @app.post('/api/study/task/start')
    def task_start(body: TaskStart):
        fx = chain.fixtures.by_id(body.task_id)
        if not fx or not fx.get('task'):
            raise HTTPException(status_code=404, detail='unknown study task')
        return research.start_task(fx['id'], fx['task'])

    @app.post('/api/study/task/end')
    def task_end():
        t = research.end_task()
        if not t:
            raise HTTPException(status_code=409, detail='no task is running')
        last_task.clear()
        last_task.update(t)
        return {'task': t}

    @app.post('/api/study/survey')
    def survey(body: SurveyBody):
        stats = dict(last_task) if (body.kind == 'task' and last_task.get('id') == body.task_id) else None
        try:
            scores = research.record_survey(body.kind, body.answers, body.task_id or None,
                                            body.answer_text, stats)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {'ok': True, 'scores': scores, 'recorded': research.recording}

    @app.get('/api/anticipation/log')
    def anticipation_log():
        return {'log': hub.anticipator.recent_log(200)}

    @app.post('/api/search/{search_id}/compare')
    def compare(search_id: str):
        from concurrent.futures import ThreadPoolExecutor
        rec = _get(search_id)
        names = ('neutral', 'focused', 'overwhelmed', 'fatigued', 'energized', 'disoriented')

        def one(name):
            summary = None if name == 'neutral' else {'state': name, 'confidence': None,
                                                      'why': ['comparison view']}
            return name, _compose(rec, get_policy(name), summary)
        with ThreadPoolExecutor(len(names)) as ex:
            specs = dict(ex.map(one, names))
        claim_sets = {n: set(s['claims_shown']) for n, s in specs.items()}
        stage_a_ids = {c['id'] for c in rec['stageA']['claims']}
        return {'search_id': search_id, 'query': rec['query'],
                'specs': {n: dict(s, policy_label=get_policy(n)['label']) for n, s in specs.items()},
                'all_within_stage_a': all(c <= stage_a_ids for c in claim_sets.values())}

    @app.post('/api/telemetry/typing')
    def telemetry_typing(body: TypingReport):
        snap = hub.typing.ingest(body.events, body.now)
        return {'score': snap['score'], 'fresh': snap['fresh']}

    @app.post('/api/behavior')
    def behaviour_event(body: BehaviourEvent):
        hub.behaviour.add_event(body.type)
        view = hub.anticipator.snapshot()['view']
        research.record_event(body.type, (view or {}).get('search_id'))
        return {'ok': True}

    # ------------------------------------------------- unified companion API --

    @app.get('/api/app/status')
    def app_status():
        return controller.app_status()

    @app.post('/api/app/comfort')
    def app_comfort(body: ComfortUpdate):
        return controller.set_comfort(**body.model_dump())

    @app.post('/api/app/audio')
    def app_audio(body: AudioAction):
        try:
            return controller.audio_action(body.action)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @app.post('/api/app/nudge')
    def app_nudge(body: NudgeAction):
        return controller.nudge_action(body.action, body.snooze_minutes)

    @app.post('/api/app/breathing')
    def app_breathing(body: BreathingState):
        controller.set_breathing_active(body.active)
        return {'ok': True}

    @app.post('/api/app/focus/clear-digest')
    def app_clear_digest():
        controller.clear_focus_digest()
        return {'ok': True}

    @app.get('/api/app/chat')
    def app_chat_get():
        return controller.chat_history()

    @app.post('/api/app/chat/send')
    def app_chat_send(body: ChatSend):
        return controller.chat_send(body.text)

    @app.post('/api/app/chat/reset')
    def app_chat_reset():
        return controller.chat_reset()

    @app.get('/api/app/journal')
    def app_journal_get():
        return controller.journal_list()

    @app.post('/api/app/journal/reflect')
    def app_journal_reflect(body: JournalNote):
        return controller.journal_reflect(body.note)

    @app.post('/api/app/journal/note')
    def app_journal_note(body: JournalNote):
        return controller.save_journal_note(body.note, body.reflection)

    @app.get('/api/app/consent')
    def app_consent_get():
        return controller.consent_info()

    @app.post('/api/app/consent/grant')
    def app_consent_grant(body: ConsentGrant):
        try:
            return controller.grant_consent(body.participant_code, body.store_queries)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @app.post('/api/app/consent/withdraw')
    def app_consent_withdraw(body: ConsentWithdraw):
        try:
            return controller.withdraw_consent(confirm=body.confirm)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post('/api/app/calibration/start')
    def app_calib_start(body: CalibrationStart):
        return controller.start_calibration(body.duration_s)

    @app.post('/api/app/calibration/cancel')
    def app_calib_cancel():
        return controller.cancel_calibration()

    @app.post('/api/app/calibration/sample')
    def app_calib_sample(body: CalibrationSample):
        return controller.ingest_calibration_sample(body.model_dump())

    @app.post('/api/app/recording/start')
    def app_rec_start():
        try:
            return controller.start_recording()
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    @app.post('/api/app/recording/stop')
    def app_rec_stop():
        return controller.stop_recording()

    @app.post('/api/app/recording/resume')
    def app_rec_resume():
        return controller.resume_recording()

    @app.post('/api/app/recording/finalize')
    def app_rec_finalize(body: RecordingFinalize):
        return controller.finalize_recording(**body.model_dump())

    @app.get('/api/app/study/audit')
    def app_study_audit():
        from backend import research as research_mod
        rep = research_mod.audit()
        return {
            'sessions': rep['sessions'],
            'chain_ok': rep['chain_ok'],
            'bad_count': len(rep.get('bad') or []),
            'consent': rep['consent'],
            'retention_days': rep['retention_days'],
            'data_root': rep['data_root'],
        }

    @app.post('/api/app/study/export')
    def app_study_export():
        from backend import paths as paths_mod
        from backend import research as research_mod
        ts = time.strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(paths_mod.base_dir(), 'exports', ts)
        res = research_mod.export_dataset(dest)
        res['export_dir'] = dest
        return res

    @app.get('/api/app/study/export.zip')
    def app_study_export_zip():
        import io
        import tempfile
        import zipfile
        from backend import research as research_mod
        buf = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmp:
            research_mod.export_dataset(tmp)
            with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for fn in sorted(os.listdir(tmp)):
                    if fn.endswith('.csv'):
                        zf.write(os.path.join(tmp, fn), arcname=fn)
        return Response(
            content=buf.getvalue(),
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename="aura_study_export.zip"'},
        )

    @app.get('/api/app/settings')
    def app_settings_get():
        return controller.engine_settings()

    @app.post('/api/app/settings')
    def app_settings_set(body: dict):
        try:
            res = controller.update_engine_settings(body)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        if 'study_condition' in body:
            hub.tick()
        return res

    @app.post('/api/app/lab/lock')
    def app_lab_lock():
        return controller.lock_lab()

    @app.post('/api/app/lab/unlock')
    def app_lab_unlock():
        return controller.unlock_lab()

    @app.post('/api/app/demo')
    def app_demo(body: DemoAction):
        try:
            return controller.demo_action(body.action, body.level)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @app.websocket('/ws/state')
    async def ws_state(ws: WebSocket):
        try:
            _check(ws.query_params.get('t'))
        except HTTPException:
            await ws.close(code=4401)
            return
        await ws.accept()
        last = -1
        try:
            while True:
                v = (store.version, hub.version)
                if v != last:
                    last = v
                    await ws.send_text(json.dumps(_payload()))
                await asyncio.sleep(WS_PUSH_S)
        except (WebSocketDisconnect, RuntimeError):
            return

    if ui_dist:
        assets = os.path.join(ui_dist, 'assets')
        if os.path.isdir(assets):
            app.mount('/assets', StaticFiles(directory=assets), name='assets')

        @app.get('/')
        def index():
            return FileResponse(os.path.join(ui_dist, 'index.html'))
    else:
        @app.get('/')
        def index_placeholder():
            return HTMLResponse(_PLACEHOLDER)

    return app


class SearchServer:
    """Runs uvicorn in a daemon thread; stop() asks it to exit cleanly."""

    def __init__(self, store, port=DEFAULT_PORT, token=None, ui_dist=None, get_collector=None, controller=None):
        self.store = store
        self.get_collector = get_collector
        self.controller = controller
        self.port = port
        self.token = token or secrets.token_urlsafe(24)
        self.ui_dist = ui_dist if ui_dist is not None else find_ui_dist()
        self._server = None
        self._thread = None
        self.error = None

    @property
    def url(self):
        return 'http://{}:{}/?t={}'.format(HOST, self.port, self.token)

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive() and self._server and self._server.started)

    @staticmethod
    def _port_free(port):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return True
            except OSError:
                return False

    def start(self):
        import uvicorn
        for p in range(self.port, self.port + 10):
            if p != 8080 and self._port_free(p):
                if p != self.port:
                    print('[Aura v2] port {} busy; using {}'.format(self.port, p))
                self.port = p
                break
        from backend.search.research_bridge import ResearchBridge
        app = create_app(self.store, self.token, self.ui_dist,
                         research=ResearchBridge(self.get_collector),
                         controller=self.controller)
        self.hub = app.state.hub.start()
        if self.controller is not None:
            self.controller.search_server = self
        config = uvicorn.Config(app, host=HOST, port=self.port, log_level='warning',
                                access_log=False, lifespan='off')
        self._server = uvicorn.Server(config)

        def _run():
            try:
                self._server.run()
            except BaseException as e:
                self.error = str(e)
        self._thread = threading.Thread(target=_run, name='aura-v2-server', daemon=True)
        self._thread.start()
        return self

    def wait_started(self, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            if self._server and self._server.started:
                return True
            if self._thread and not self._thread.is_alive():
                return False
            time.sleep(0.05)
        return False

    def stop(self, timeout=3.0):
        if getattr(self, 'hub', None):
            self.hub.stop()
            if self.hub.camera is not None:
                self.hub.camera.stop()
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout)


def main():
    ap = argparse.ArgumentParser(description='Aura v2 standalone dev server')
    ap.add_argument('--standalone', action='store_true',
                    help='run headless simulated state without pynput/OS hooks')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--token', default=None, help='fixed token (dev only)')
    ap.add_argument('--open', action='store_true', help='open the unified window')
    args = ap.parse_args()
    if not args.standalone:
        ap.error('only --standalone is supported from this module; use python run.py for the full desktop daemon')
    from backend.daemon_controller import AuraController
    store = LiveStateStore()
    ctrl = AuraController(standalone=True, persist=True, live_state=store, lab_unlocked=True).start()
    sim = SimulatedLiveState(store)
    sim.start()
    srv = SearchServer(store, port=args.port, token=args.token, controller=ctrl).start()
    if not srv.wait_started():
        raise SystemExit('server failed to start: {}'.format(srv.error))
    print('[Aura v2] standalone dev server:', srv.url)
    if args.open:
        from backend.search.window import open_search_window
        open_search_window(srv.url)
    try:
        while srv._thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop()
        ctrl.stop()
        srv.stop()


if __name__ == '__main__':
    main()
