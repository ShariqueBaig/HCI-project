// Mirrors backend/search/live_state.py build_snapshot()
export interface LiveFeatures {
  keys_per_second?: number;
  error_rate?: number;
  mean_dwell?: number;
  std_dwell?: number;
  mean_flight?: number;
  std_flight?: number;
  flight_count?: number;
  mouse_distance?: number;
  mouse_clicks?: number;
  cov?: number;
}

export interface LiveState {
  ts: number;
  score: number;
  tier: 0 | 1 | 2;
  label: 'Calm' | 'Mild' | 'Elevated';
  features: LiveFeatures;
  condition: string; // 'intervention' (Active B) | 'control' (Control A)
  calibrated: boolean;
  baseline_cov: number;
  baseline_err: number;
  dnd_active: boolean;
  focus_blocking: boolean;
  breathing_active: boolean;
  held_count: number;
  simulated: boolean;
  demo: boolean;
  recording: boolean;
  brightness: number | null;
  session_stats: Record<string, unknown>;
}

export type HciState = 'focused' | 'overwhelmed' | 'fatigued' | 'energized' | 'disoriented';

// Mirrors backend/search/xai.py explain()
export interface XaiCondition {
  label: string;
  value: number | boolean | null;
  op: '>=' | '>' | '<' | 'is';
  threshold: number | boolean;
  unit: string;
  met: boolean;
  progress: number;
}

export interface XaiClause {
  name: string;
  conditions: XaiCondition[];
  met: boolean;
  closeness: number;
}

export interface XaiMood {
  state: HciState;
  clauses: XaiClause[];
  matched: boolean;
  closeness: number;
  chosen: boolean;
  priority: number;
}

export interface Xai {
  model: string;
  priority: HciState[];
  moods: XaiMood[];
  stress_fusion: {
    parts: { source: string; value: number; weight: number; share: number }[];
    fused: number | null;
    formula: string;
  };
}

// Mirrors backend/vision/sensor.py explain_detail() + GET /api/camera/explain
export interface CameraDetail {
  ts: number;
  frame_jpeg_b64: string | null;
  face: boolean;
  face_count: number;
  raw_emotions: Record<string, number>;
  emotions: Record<string, number>;
  dominant: string | null;
  detector_confidence: number;
  valence: number;
  arousal: number;
  attention: number;
  head_pitch: number;
  volatility: number;
  cognitive_load: number;
  load_parts: { label: string; value: number; weight: number; contribution: number }[];
  camera_state: HciState | null;
  camera_candidate: HciState | null;
  camera_state_confidence: number;
  anchors: Record<string, [number, number]>;
  latency_ms: number | null;
}

export interface CameraExplain {
  active: boolean;
  detail: CameraDetail | null;
  used_by_fusion: boolean;
}

export interface Simulation {
  state: HciState;
  remaining_s: number;
  inputs: Record<string, unknown>;
}

// Mirrors backend/search/state_fusion.py fuse() + StateTracker
export interface FusedState {
  xai?: Xai;
  state: HciState;
  confidence: number;
  stress: number | null;
  evidence: string[];
  contributions: Record<string, number>;
  sources: string[];
  quiet: boolean;
  committed_state: HciState;
  candidate_state: HciState | null;
  dwell_progress: number;
  flickers_prevented: number;
  transitions: number;
}

// Mirrors backend/search/policy.py
export interface Policy {
  name: HciState | 'neutral';
  label: string;
  summary: string;
  answer_word_budget: number;
  reading_level: string;
  max_primary_options: number;
  max_key_facts: number;
  required_widgets: string[];
  allowed_widgets: string[];
  density: 'sparse' | 'regular' | 'dense';
  tone: string;
  show_facets: boolean;
  show_sources_inline: boolean;
  proactive: { clarifiers: boolean; followups: boolean; breathing_nudge: boolean };
  allow_custom_widget: boolean;
  tokens: { targetScale: number; typographyScale: number; lineHeight: number; accent: 'calm' | 'mild' | 'elev' };
}

// Mirrors backend/search/anticipation.py Anticipator snapshot
export interface Proposal {
  id: string;
  search_id: string;
  from: string;
  target: HciState;
  reason: string;
  text: string;
  created_at: number;
}

export interface Anticipation {
  proposal: Proposal | null;
  ack: { text: string } | null;
  can_undo: boolean;
  view: { search_id: string; policy: string } | null;
}

export interface ProposalResponse {
  search_id: string;
  action: 'accept' | 'dismiss' | 'undo';
  policy: Policy | null;
  spec: Spec | null;
}

export interface StateSnapshot {
  fused: FusedState;
  adaptive: boolean;
  anticipation?: Anticipation;
  camera?: { active: boolean; face: boolean };
  policy: Policy;
  typing: { fresh: boolean; age_s: number | null; score: number; features: LiveFeatures };
  behaviour: { rage_clicks: number; hesitations: number; backtracks: number; reformulations: number };
  query_trail: string[];
  simulation?: Simulation | null;
}

export interface StatePayload {
  live: LiveState | null;
  state: StateSnapshot | null;
  server_ts: number;
}

// Mirrors backend/search/composer.py + validator.py
export type WidgetType =
  | 'AnswerCard' | 'KeyFactsList' | 'GuidedSteps' | 'ComparisonTable' | 'ProsCons' | 'Timeline'
  | 'SourceList' | 'FacetChips' | 'FollowUpChips' | 'ClarifierChips' | 'QueryTrail'
  | 'BreathingNudge' | 'ReadAloud';

export interface SpecComponent {
  id: string;
  type: WidgetType;
  region: 'main' | 'side';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  props: Record<string, any>;
}

export interface Spec {
  topology: 'stack' | 'split' | 'stepper';
  components: SpecComponent[];
  custom_widget: { title: string; html: string } | null;
  rationale: string;
  tokens?: Policy['tokens'];
  policy: string;
  source: 'llm' | 'template';
  model: string | null;
  note: string;
  ms: number;
  claims_shown: string[];
  report: {
    fixes?: string[];
    dropped?: string[];
    grounding_failures?: { where: string; novel_ratio: number; novel_words: string[]; novel_numbers: string[] }[];
    ungrounded_before_fix?: number;
    evaluative_cells?: number;
    truth_invariant?: boolean;
  };
}

// Mirrors backend/search/server.py POST /api/search
export interface SourceItem {
  id: string;
  title: string;
  url: string;
  snippet: string;
  published: string;
  provider: string;
}

export interface Claim {
  id: string;
  text: string;
  source_ids: string[];
  importance: 1 | 2 | 3;
}

export interface StageA {
  tldr: string;
  tldr_source_ids: string[];
  claims: Claim[];
  key_entities: string[];
  comparison_axes: string[];
  steps: string[];
  used_llm: boolean;
  model: string | null;
  note: string;
  cached: boolean;
}

export interface SearchResponse {
  search_id: string;
  query: string;
  condition: string | null;
  state_at_query: { score: number | null; tier: number | null; label: string | null };
  provider: 'fixture' | 'tavily' | 'wikipedia' | string;
  provider_note: string;
  sources: SourceItem[];
  stageA: StageA;
  reformulation: boolean;
  fused_at_query: FusedState | null;
  adaptive: boolean;
  policy: Policy;
  spec: Spec;
  quiet: boolean;
  timings_ms: { retrieval: number; stageA: number; stageB: number; total: number };
}

export interface RerenderResponse {
  search_id: string;
  policy: Policy;
  spec: Spec;
  ms: number;
}

export interface FixtureInfo {
  id: string;
  query: string;
  task: string;
  n_sources: number;
}

// Mirrors backend/search/server.py GET /api/study
export interface StudyTask {
  id: string;
  task: string;
  started: number;
  searches: number;
  elapsed_s?: number;
}

export interface StudyStatus {
  recording: boolean;
  task: StudyTask | null;
  tasks: FixtureInfo[];
  sus_items: string[];
}

export type ConnectionStatus = 'connecting' | 'live' | 'offline' | 'unauthorized';
