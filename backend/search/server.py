"""Local FastAPI server for Aura Search, run in a daemon thread inside Aura.

Security model: binds to 127.0.0.1 only, and every /api and /ws request must
carry the random per-launch token (header ``X-Aura-Token`` or query ``t``).
The token is only ever handed to the search window through its URL, so other
local processes and web pages cannot drive the API. The static UI itself is
served without a token; it holds no data.

Dev mode (no Aura window, simulated stress wave):
    python -m backend.search.server --standalone
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

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.paths import resource_dirs
from backend.search.live_state import LiveStateStore, SimulatedLiveState

HOST = '127.0.0.1'
# never 8080: Spotify PKCE uses it during connect(). AURA_SEARCH_PORT lets a second
# copy (e.g. a test build) run alongside an open Aura.
DEFAULT_PORT = int(os.environ.get('AURA_SEARCH_PORT', '8765'))
WS_PUSH_S = 0.5              # 2 Hz state push

_PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>Aura Search</title>
<body style="font-family:system-ui;background:#0b0a10;color:#e8e6ed;padding:32px">
<h2>Aura Search</h2><p>The search UI has not been built yet. Run
<code>npm install</code> and <code>npm run build</code> in <code>search_ui/</code>.</p>
<p id="s">Waiting for live state&hellip;</p>
<script>
const t=new URLSearchParams(location.search).get('t');
setInterval(async()=>{try{const r=await fetch('/api/state',{headers:{'X-Aura-Token':t}});
const j=await r.json();document.getElementById('s').textContent=
'Aura stress: '+j.live.score.toFixed(0)+' ('+j.live.label+')';}catch(e){}},1000);
</script>"""


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
    now: float                       # browser performance.now() in ms


class BehaviourEvent(BaseModel):
    type: str = Field(pattern='^(rage_click|hesitation|backtrack)$')


MAX_SEARCHES = 50


class RerenderRequest(BaseModel):
    policy: str = Field(pattern='^(neutral|focused|overwhelmed|fatigued|energized|disoriented)$')


class ViewChoice(BaseModel):
    policy: str = Field(pattern='^(neutral|focused|overwhelmed|fatigued|energized|disoriented)$')


class ProposalAction(BaseModel):
    proposal_id: str = Field(default='', max_length=40)
    action: str = Field(pattern='^(accept|dismiss|undo)$')


class CameraToggle(BaseModel):
    enabled: bool


class TaskStart(BaseModel):
    task_id: str = Field(min_length=1, max_length=60)


class SurveyBody(BaseModel):
    kind: str = Field(pattern='^(task|sus)$')
    task_id: str = Field(default='', max_length=60)
    answers: dict = Field(default_factory=dict)
    answer_text: str = Field(default='', max_length=500)


UNCERTAIN_ERROR_RATE = 0.2     # backspace-heavy query typing -> offer to narrow it down


def create_app(store, token, ui_dist=None, chain=None, stage_a=None, hub=None, composer=None,
               research=None):
    app = FastAPI(title='Aura Search', docs_url=None, redoc_url=None, openapi_url=None)
    if research is None:
        from backend.search.research_bridge import ResearchBridge
        research = ResearchBridge()      # no collector -> records nothing
    app.state.research = research
    last_task = {}                        # stats of the task that just ended (for its survey)
    if hub is None:
        from backend.search.hub import StateHub
        hub = StateHub(store)            # ticked by SearchServer; tests call hub.tick()
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
    searches = OrderedDict()          # search_id -> record (Stage B / re-render reuse it later)

    from backend.search.composer import state_summary_from
    from backend.search.policy import get_policy
    from backend.search.validator import referenced_claims

    def _compose(rec, policy, state_summary):
        """Stage B for a stored search; cached per policy (Stage A never changes)."""
        cache = rec['_specs']
        key = policy.get('cache_key', policy['name'])
        if key not in cache:
            spec = composer.compose(rec['query'], rec['stageA'], rec['_sources_full'], policy,
                                    state_summary, trail=rec['_trail'], history=rec['_history'])
            spec['claims_shown'] = sorted(referenced_claims(spec))
            cache[key] = spec
        return cache[key]

    def _with_clarifier(policy):
        """Pre-submit anticipation: the query was typed with many corrections, so
        offer a clarifying question whatever the state (if the facts have axes)."""
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
        return {'live': live, 'state': cur, 'server_ts': time.time()}

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

    @app.post('/api/search')
    def search(body: SearchRequest):
        query = ' '.join(body.query.split())
        if not query:
            raise HTTPException(status_code=422, detail='empty query')
        live = store.get()
        reformulation = hub.behaviour.add_query(query)
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
        rec = {
            'search_id': uuid.uuid4().hex[:12],
            'query': query,
            'created_at': time.time(),
            'condition': (live or {}).get('condition'),
            'state_at_query': {k: (live or {}).get(k) for k in ('score', 'tier', 'label')},
            'reformulation': reformulation,
            'fused_at_query': (snap or {}).get('fused'),
            'adaptive': (snap or {}).get('adaptive', False),
            'policy': (snap or {}).get('policy'),
            'provider': res.provider,
            'provider_note': res.note,
            'sources': [{k: v for k, v in s.items() if k != 'content'} for s in sources],
            'stageA': a,
        }
        policy = rec['policy'] or get_policy('neutral')
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
        quiet = bool(((snap or {}).get('fused') or {}).get('quiet'))
        summary = state_summary_from((snap or {}).get('fused')) if rec['adaptive'] else None
        spec = _compose(rec, policy, summary)
        t3 = time.perf_counter()
        rec['timings_ms'] = {'retrieval': round((t1 - t0) * 1000), 'stageA': round((t2 - t1) * 1000),
                             'stageB': round((t3 - t2) * 1000), 'total': round((t3 - t0) * 1000)}
        searches[rec['search_id']] = rec
        while len(searches) > MAX_SEARCHES:
            searches.popitem(last=False)
        hub.on_search(rec['search_id'], query, policy['name'],
                      [c['type'] for c in spec['components']],
                      ((snap or {}).get('fused') or {}).get('committed_state'), reformulation)
        research.record_search(rec, spec, snap)
        return _public(rec, spec=spec, quiet=quiet, task_id=research.active_task_id())

    @app.post('/api/search/{search_id}/rerender')
    def rerender(search_id: str, body: RerenderRequest):
        """Same facts (cached Stage A), another layout policy -- used by 'Standard view'
        and by state changes while reading. Only Stage B runs."""
        rec = _get(search_id)
        t0 = time.perf_counter()
        policy = get_policy(body.policy)
        summary = None if body.policy == 'neutral' else {
            'state': body.policy, 'confidence': None, 'why': ['layout requested for this state']}
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
        """User switched between cached layouts (e.g. back to the adapted view)."""
        _get(search_id)
        hub.anticipator.user_choice(search_id, body.policy)
        research.record_event('standard_view' if body.policy == 'neutral' else 'adapted_view',
                              search_id, target=body.policy)
        return {'ok': True}

    @app.post('/api/search/{search_id}/proposal')
    def proposal(search_id: str, body: ProposalAction):
        """Answer an offer: accept (show the new layout), dismiss, or undo the last accept."""
        rec = _get(search_id)
        try:
            target = hub.anticipator.respond(body.proposal_id, body.action)
        except KeyError as e:
            raise HTTPException(status_code=409, detail=str(e).strip("'"))
        hub.text.add_event(search_id, '{} offer'.format(body.action))
        hub.tick()                         # push the cleared offer to the window now
        if target is None:
            return {'search_id': search_id, 'action': body.action, 'policy': None, 'spec': None}
        policy = get_policy(target)
        fused = (hub.current() or {}).get('fused')
        summary = None if target == 'neutral' else (
            state_summary_from(fused) if fused and fused.get('committed_state') == target
            else {'state': target, 'confidence': None, 'why': ['offered by Aura and accepted']})
        spec = _compose(rec, policy, summary)
        return {'search_id': search_id, 'action': body.action, 'policy': policy, 'spec': spec}

    # ----------------------------------------------------------- camera --
    @app.get('/api/camera')
    def camera_status():
        from backend.vision.sensor import CameraSensor, vision_available
        if hub.camera is None:
            ok, why = vision_available()
            return {'available': ok, 'active': False, 'loading': False, 'error': None if ok else why,
                    'latest': None}
        return hub.camera.status()

    @app.post('/api/camera')
    def camera_toggle(body: CameraToggle):
        """Off by default; models load (and download, first time only) on enable."""
        from backend.vision.sensor import CameraSensor
        if hub.camera is None:
            hub.camera = CameraSensor()
        st = hub.camera.start() if body.enabled else hub.camera.stop()
        research.record_event('camera_on' if st['active'] else 'camera_off')
        return st

    # ------------------------------------------------------------ study --
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
        """The same search laid out for every policy (demo / figures tool)."""
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

    def __init__(self, store, port=DEFAULT_PORT, token=None, ui_dist=None, get_collector=None):
        self.store = store
        self.get_collector = get_collector
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
        return bool(self._thread and self._thread.is_alive() and self._server
                    and self._server.started)

    def start(self):
        import uvicorn
        from backend.search.research_bridge import ResearchBridge
        app = create_app(self.store, self.token, self.ui_dist,
                         research=ResearchBridge(self.get_collector))
        self.hub = app.state.hub.start()
        config = uvicorn.Config(app, host=HOST, port=self.port, log_level='warning',
                                access_log=False, lifespan='off')
        self._server = uvicorn.Server(config)

        def _run():
            try:
                self._server.run()
            except BaseException as e:        # port in use, etc. -- never kill Aura
                self.error = str(e)
        self._thread = threading.Thread(target=_run, name='aura-search-server', daemon=True)
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
                self.hub.camera.stop()          # release the webcam on quit
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout)


def main():
    ap = argparse.ArgumentParser(description='Aura Search server (dev mode)')
    ap.add_argument('--standalone', action='store_true',
                    help='run without Aura, with a simulated stress wave')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--token', default=None, help='fixed token (dev only)')
    ap.add_argument('--open', action='store_true', help='open the search window')
    args = ap.parse_args()
    if not args.standalone:
        ap.error('only --standalone is supported from the command line; '
                 'inside Aura the server is started by run.py')
    store = LiveStateStore()
    sim = SimulatedLiveState(store)
    sim.start()
    srv = SearchServer(store, port=args.port, token=args.token).start()
    if not srv.wait_started():
        raise SystemExit('server failed to start: {}'.format(srv.error))
    print('[Aura Search] standalone dev server:', srv.url)
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
        srv.stop()


if __name__ == '__main__':
    main()
