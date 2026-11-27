export type HciState = 'focused' | 'overwhelmed' | 'fatigued' | 'energized' | 'disoriented';
export type AgencyMode = 'copilot' | 'autonomous' | 'manual';
export type ScenarioType = 'commerce' | 'workspace' | 'research';
export type ExperimentCondition = 'emotional_agent' | 'prompt_only_control';

export interface MicroStep {
  id: string;
  text: string;
  done: boolean;
}

export interface TaskItem {
  id: string;
  title: string;
  priority: 'high' | 'medium' | 'low';
  estimatedMinutes: number;
  completed: boolean;
  category: string;
  microSteps: MicroStep[];
  createdAt: number;
}

export interface NoteItem {
  id: string;
  title: string;
  content: string;
  updatedAt: number;
}

export interface IdeaItem {
  id: string;
  text: string;
  tag: string;
  createdAt: number;
}

export interface WorkspaceSettings {
  agency_mode: AgencyMode;
  dwell_seconds: number;
  reduced_motion: boolean;
}

export interface WorkspaceData {
  tasks: TaskItem[];
  notes: NoteItem[];
  ideas: IdeaItem[];
  settings: WorkspaceSettings;
}

export interface PendingProposal {
  id: string;
  from_state: HciState;
  target_state: HciState;
  target_mode_name?: string;
  confidence: number;
  source: string;
  cue_summary: string;
  structural_diff?: string[];
  created_at: number;
}

export interface TelemetryData {
  timestamp: number;
  source: string;
  camera_active: boolean;
  camera_error: string | null;
  face_detected: boolean;
  raw_confidence: number;
  dominant_emotion: string;
  emotions: Record<string, number>;
  valence: number;
  arousal: number;
  attention_score: number;
  head_pitch_proxy: number;
  volatility: number;
  cognitive_load: number;
  active_state: HciState;
  previous_state: HciState | null;
  candidate_state: HciState;
  state_confidence: number;
  dwell_progress: number;
  dwell_seconds: number;
  agency_mode: AgencyMode;
  simulated_state: HciState | null;
  pending_proposal: PendingProposal | null;
  circumplex_trail: Array<{ valence: number; arousal: number }>;
  metrics: {
    flickers_prevented: number;
    proposals_accepted: number;
    proposals_dismissed: number;
    transitions_count: number;
    time_in_state: Record<string, number>;
  };
}

export interface UIComponentNode {
  id: string;
  type:
    | 'TaskTriagerWidget'
    | 'SomaticResetWidget'
    | 'QuickWinDeckWidget'
    | 'HydrationStretchCard'
    | 'DeepDocumentEditor'
    | 'TaskQueuePanel'
    | 'DivergentIdeaCanvas'
    | 'ContextAnchorBanner'
    | 'AdaptiveFocusTimer';
  region: string;
  priority: number;
  title: string;
  hciRule: string;
  props: Record<string, unknown>;
}

export interface HciRationaleItem {
  principle: string;
  citation: string;
  trigger: string;
  uiMutation: string;
}

export interface UISchema {
  schemaVersion: string;
  generatedAt: number;
  targetState: HciState;
  modeName: string;
  modeSubtitle: string;
  layout: {
    topology: 'tri-pane-studio' | 'single-focus-tunnel' | 'low-friction-deck' | 'divergent-board' | 'orientation-split';
    visualType?: string;
    navType?: string;
    columns: number;
    density: string;
    navigationChrome: string;
    maxVisibleTasks: number;
    showSidebar: boolean;
  };
  interaction: {
    targetScale: number;
    typographyScale: number;
    lineHeight: number;
    notificationPolicy: string;
    timerPreset: {
      label: string;
      focusMinutes: number;
      breakMinutes: number;
      description: string;
    };
    voiceAssistRecommended: boolean;
  };
  surfaceTokens: {
    canvasBg: string;
    panelBg: string;
    panelAltBg: string;
    accent: string;
    accentSoft: string;
    textPrimary: string;
    textMuted: string;
    border: string;
  };
  components: UIComponentNode[];
  hciRationale: HciRationaleItem[];
  structuralDiff: string[];
}

export interface ModelStatus {
  ready: boolean;
  yunet_available: boolean;
  emotion_model: string;
  emotion_file: string | null;
  classes: string[];
  error: string | null;
}

export interface ProductItem {
  id: string;
  name: string;
  brand: string;
  category: string;
  pricePkr: number;
  priceUsd: number;
  rating: number;
  batteryHours: number;
  deliveryDays: number;
  warranty: string;
  vendor: string;
  specs: Record<string, string>;
  pros: string[];
  cons: string[];
  bestFor: string;
  isBudgetPick: boolean;
}

export interface AgentResult {
  prompt: string;
  scenario: string;
  condition: ExperimentCondition;
  emotionState: string;
  dominantEmotion: string;
  visualType: string;
  navType: string;
  agentTone: string;
  headline: string;
  message: string;
  rationaleBullets: string[];
  scaffoldingCue: string;
  criteriaTags: string[];
  spotlightItem: ProductItem | TaskItem | null;
  matchedItems: Array<ProductItem | TaskItem>;
  totalCatalogCount: number;
  hciExplanation: string;
  uiOverrides: {
    maxCards: number;
    showSpecMatrix: boolean;
    showPromos: boolean;
    voiceRecommended: boolean;
    targetScale: number;
    typographyScale: number;
    lineHeight: number;
  };
  usedLlm: boolean;
  llmError: string | null;
}

export interface LlmConfig {
  enabled: boolean;
  provider: 'gemini' | 'openai';
  api_key: string;
}

export interface ActiveTrial {
  sessionId: string;
  participantId: string;
  scenario: 'commerce' | 'workspace';
  condition: ExperimentCondition;
  taskPrompt: string;
  startedAtMs: number;
}

export interface WhiteboardRow {
  id: string;
  participant_id: string;
  scenario: string;
  condition: ExperimentCondition;
  task_prompt: string;
  dominant_emotion: string;
  visual_type: string;
  nav_type: string;
  efficiency_score: number;
  effectiveness_score: number;
  satisfaction_sus: number;
  delta_valence: number;
  cv_sam_alignment: number;
  time_on_task_sec: number;
  click_count: number;
  rage_click_count: number;
  notes: string;
}

export interface WhiteboardAggregate {
  count: number;
  avg_efficiency: number;
  avg_effectiveness: number;
  avg_satisfaction_sus: number;
  avg_delta_valence: number;
  avg_cv_sam_alignment: number;
  avg_time_sec: number;
}

export interface WhiteboardSummary {
  rows: WhiteboardRow[];
  aggregates: {
    emotional_agent: WhiteboardAggregate;
    prompt_only_control: WhiteboardAggregate;
  };
  counts: {
    completed_sessions: number;
    affective_samples: number;
    interaction_events: number;
    agent_generations: number;
  };
}
