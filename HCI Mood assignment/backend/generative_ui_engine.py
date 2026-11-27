"""Schema-driven Generative UI Engine synthesizing structural topologies and HCI rules."""

from __future__ import annotations

import time
from typing import Any

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

STATE_DESCRIPTIONS: dict[str, dict[str, Any]] = {
    "focused": {
        "modeName": "Deep Flow Studio",
        "modeSubtitle": "Balanced tri-pane productivity layout with full document & task visibility.",
        "visualType": "Focused & Spotlight",
        "navType": "Bento Box",
        "topology": "tri-pane-studio",
        "columns": 12,
        "density": "compact",
        "navigationChrome": "full",
        "maxVisibleTasks": 20,
        "targetScale": 1.0,
        "typographyScale": 1.0,
        "lineHeight": 1.55,
        "notificationPolicy": "standard",
        "voiceAssistRecommended": False,
        "timerPreset": {
            "label": "Deep Block",
            "focusMinutes": 50,
            "breakMinutes": 10,
            "description": "Sustained deep-work sprint matched to steady neutral attention.",
        },
        "surfaceTokens": {
            "canvasBg": "#F5F7FA",
            "panelBg": "#FFFFFF",
            "panelAltBg": "#EEF2F7",
            "accent": "#2563EB",
            "accentSoft": "#DBEAFE",
            "textPrimary": "#0F172A",
            "textMuted": "#475569",
            "border": "#CBD5E1",
        },
    },
    "overwhelmed": {
        "modeName": "De-Escalation Tunnel",
        "modeSubtitle": "Single-task Hick's Law triage, enlarged Fitts targets, and somatic reset.",
        "visualType": "Focused & Spotlight",
        "navType": "Single-Path Guided Stepper",
        "topology": "single-focus-tunnel",
        "columns": 1,
        "density": "spacious",
        "navigationChrome": "minimal",
        "maxVisibleTasks": 1,
        "targetScale": 1.26,
        "typographyScale": 1.1,
        "lineHeight": 1.72,
        "notificationPolicy": "silent-shield",
        "voiceAssistRecommended": False,
        "timerPreset": {
            "label": "2-Min Micro-Start",
            "focusMinutes": 2,
            "breakMinutes": 2,
            "description": "Ultra-low commitment threshold to break overwhelm paralysis.",
        },
        "surfaceTokens": {
            "canvasBg": "#F3F6F4",
            "panelBg": "#FFFFFF",
            "panelAltBg": "#E6EFEA",
            "accent": "#2F6F5E",
            "accentSoft": "#D5EBE3",
            "textPrimary": "#132A23",
            "textMuted": "#4A665D",
            "border": "#BDD3C9",
        },
    },
    "fatigued": {
        "modeName": "Low-Friction Deck",
        "modeSubtitle": "Filters to <=15m quick wins, increases readability, and enables voice assist.",
        "visualType": "Minimalist Calm List",
        "navType": "Low-Friction Linear Stack",
        "topology": "low-friction-deck",
        "columns": 12,
        "density": "comfortable",
        "navigationChrome": "minimal",
        "maxVisibleTasks": 4,
        "targetScale": 1.16,
        "typographyScale": 1.14,
        "lineHeight": 1.82,
        "notificationPolicy": "gentle-digest",
        "voiceAssistRecommended": True,
        "timerPreset": {
            "label": "Gentle Sprint",
            "focusMinutes": 10,
            "breakMinutes": 5,
            "description": "Short recovery-aware cadence prioritizing effortless momentum.",
        },
        "surfaceTokens": {
            "canvasBg": "#FAF6F0",
            "panelBg": "#FFFDF9",
            "panelAltBg": "#F3ECE1",
            "accent": "#B45309",
            "accentSoft": "#FDE68A",
            "textPrimary": "#292018",
            "textMuted": "#6B5A48",
            "border": "#E5D8C5",
        },
    },
    "energized": {
        "modeName": "Divergent Ideation Studio",
        "modeSubtitle": "Surfaces spatial idea canvas & Kanban board to harness high positive arousal.",
        "visualType": "Visual Bento & Card Grid",
        "navType": "Bento Box + Visual Facets",
        "topology": "divergent-board",
        "columns": 12,
        "density": "balanced",
        "navigationChrome": "full",
        "maxVisibleTasks": 12,
        "targetScale": 1.04,
        "typographyScale": 1.02,
        "lineHeight": 1.6,
        "notificationPolicy": "standard",
        "voiceAssistRecommended": False,
        "timerPreset": {
            "label": "Creative Jam",
            "focusMinutes": 25,
            "breakMinutes": 5,
            "description": "High-momentum creative interval paired with 1-click idea promotion.",
        },
        "surfaceTokens": {
            "canvasBg": "#F6F5FB",
            "panelBg": "#FFFFFF",
            "panelAltBg": "#ECEAF8",
            "accent": "#5B21B6",
            "accentSoft": "#EDE9FE",
            "textPrimary": "#1E1633",
            "textMuted": "#594D73",
            "border": "#D6CFF0",
        },
    },
    "disoriented": {
        "modeName": "Orientation Re-Anchor",
        "modeSubtitle": "Synthesizes 'Where You Left Off' anchor card & pins top 3 clear priorities.",
        "visualType": "Guided Z-Pattern & Anchor",
        "navType": "Horizontal Top-Down + Breadcrumbs",
        "topology": "orientation-split",
        "columns": 12,
        "density": "comfortable",
        "navigationChrome": "guided",
        "maxVisibleTasks": 3,
        "targetScale": 1.1,
        "typographyScale": 1.06,
        "lineHeight": 1.66,
        "notificationPolicy": "silent-shield",
        "voiceAssistRecommended": False,
        "timerPreset": {
            "label": "Re-Anchor Block",
            "focusMinutes": 15,
            "breakMinutes": 3,
            "description": "Structured orientation window to rebuild working-memory context.",
        },
        "surfaceTokens": {
            "canvasBg": "#F3F7FA",
            "panelBg": "#FFFFFF",
            "panelAltBg": "#E5EFF7",
            "accent": "#0369A1",
            "accentSoft": "#E0F2FE",
            "textPrimary": "#0C2438",
            "textMuted": "#476680",
            "border": "#BBD4E8",
        },
    },
}


def _top_incomplete_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    incomplete = [t for t in tasks if not t.get("completed")]
    if not incomplete:
        return None
    incomplete.sort(key=lambda t: (PRIORITY_RANK.get(t.get("priority", "medium"), 1), t.get("estimatedMinutes", 30)))
    return incomplete[0]


def _quick_win_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    incomplete = [t for t in tasks if not t.get("completed")]
    quick = [t for t in incomplete if int(t.get("estimatedMinutes", 30)) <= 15]
    if not quick:
        quick = sorted(incomplete, key=lambda t: t.get("estimatedMinutes", 30))[:3]
    else:
        quick.sort(key=lambda t: t.get("estimatedMinutes", 15))
    return quick[:4]


def _build_rationale(state: str, telemetry: dict[str, Any]) -> list[dict[str, str]]:
    val = telemetry.get("valence", 0.0)
    aro = telemetry.get("arousal", 0.0)
    load = telemetry.get("cognitive_load", 0.0)
    attn = telemetry.get("attention_score", 1.0)

    if state == "overwhelmed":
        return [
            {
                "principle": "Hick's Law (Choice Overload Reduction)",
                "citation": "Hick (1952); Sweller Cognitive Load Theory",
                "trigger": f"Cognitive Load={int(load*100)}%, Valence={val:+.2f}, Arousal={aro:+.2f}",
                "uiMutation": "Collapsed task queue into 1 atomic micro-step card; suppressed secondary navigation.",
            },
            {
                "principle": "Fitts's Law (Motor Target Enlargement)",
                "citation": "Fitts (1954)",
                "trigger": "High sympathetic arousal reduces fine pointer precision.",
                "uiMutation": "Scaled primary action hit-targets by 1.26x with spacious padding.",
            },
            {
                "principle": "Affective Regulation Scaffolding",
                "citation": "Picard (1997) Affective Computing",
                "trigger": "Sustained high-arousal negative affect beyond dwell threshold.",
                "uiMutation": "Injected Somatic 4-7-8 Breathing Pacer & activated Silent Notification Shield.",
            },
        ]
    if state == "fatigued":
        return [
            {
                "principle": "Low-Friction Task Filtering",
                "citation": "Norman Cognitive Effort Minimization",
                "trigger": f"Low Arousal={aro:+.2f}, Valence={val:+.2f}",
                "uiMutation": "Replaced dense backlog with <=15m Quick Win Deck sorted easiest-first.",
            },
            {
                "principle": "Perceptual Readability & Multi-Modal Offload",
                "citation": "WCAG Cognitive Accessibility Guidelines",
                "trigger": "Visual fatigue & downward pitch cues.",
                "uiMutation": "Scaled typography 1.14x, line-height 1.82, and surfaced Voice Read-Aloud control.",
            },
            {
                "principle": "Micro-Rest Recovery Prompt",
                "citation": "Ergonomic Pacing Guidelines",
                "trigger": "Sustained low-arousal state.",
                "uiMutation": "Injected Hydration & Posture Stretch card alongside 10m Gentle Sprint timer.",
            },
        ]
    if state == "energized":
        return [
            {
                "principle": "Broaden-and-Build Divergent Coupling",
                "citation": "Fredrickson (2001) Broaden-and-Build Theory",
                "trigger": f"High Positive Valence={val:+.2f}, Arousal={aro:+.2f}",
                "uiMutation": "Promoted Divergent Idea Canvas to primary hero region with 1-click Task Promotion.",
            },
            {
                "principle": "Spatial Visual Organization",
                "citation": "Card & Mackinlay Information Visualization",
                "trigger": "High creative engagement bandwidth.",
                "uiMutation": "Switched Task Queue from list to 3-column Kanban Board topology.",
            },
        ]
    if state == "disoriented":
        return [
            {
                "principle": "Recognition Over Recall (Context Anchoring)",
                "citation": "Nielsen's 10 Usability Heuristics (#6)",
                "trigger": f"Attention={int(attn*100)}%, surprise/fragmentation cue",
                "uiMutation": "Injected synthesized 'Where You Left Off' Context Anchor summarizing active goal & note.",
            },
            {
                "principle": "Working Memory Bounding (Miller's Law)",
                "citation": "Miller (1956)",
                "trigger": "Fragmented gaze / attention drop.",
                "uiMutation": "Capped visible tasks to top 3 clear priorities and enabled guided orientation split.",
            },
        ]
    return [
        {
            "principle": "Flow-Preserving Minimal Interference",
            "citation": "Csikszentmihalyi Flow State; Mixed-Initiative UI",
            "trigger": f"Steady baseline (Attention={int(attn*100)}%, Load={int(load*100)}%)",
            "uiMutation": "Maintains high-efficiency Tri-Pane Studio with 50m Deep Block and full keyboard density.",
        }
    ]


def _structural_diff(from_state: str, to_state: str) -> list[str]:
    if from_state == to_state:
        return ["No structural change required."]
    diffs = {
        "overwhelmed": [
            "Layout switches to 1-column Single-Focus Tunnel",
            "Hides backlog and isolates #1 task's 2-min micro-step",
            "Injects interactive 4-7-8 Somatic Breathing widget",
            "Enlarges buttons 1.26x (Fitts's Law) & silences alerts",
        ],
        "fatigued": [
            "Layout switches to spacious Low-Friction Deck",
            "Filters tasks down to <=15m Quick Wins",
            "Increases font scale (1.14x) + enables Voice Read-Aloud",
            "Injects Hydration & Stretch recovery card",
        ],
        "energized": [
            "Promotes Divergent Idea Canvas to top workspace",
            "Transforms Task List into 3-column Kanban Board",
            "Sets Focus Timer to 25m Creative Jam",
        ],
        "disoriented": [
            "Injects 'Where You Left Off' Context Anchor Banner",
            "Caps task list to top 3 clear priorities",
            "Resets focus cadence to 15m Re-Anchor block",
        ],
        "focused": [
            "Restores full Tri-Pane Deep Work Studio",
            "Shows full compact task queue + main note editor",
            "Sets Focus Timer to 50m Deep Block",
        ],
    }
    return diffs.get(to_state, ["Re-configures workspace layout."])


def generate_ui_schema(
    target_state: str,
    telemetry: dict[str, Any],
    workspace: dict[str, Any],
    from_state: str | None = None,
) -> dict[str, Any]:
    """Synthesize a complete declarative Generative UI Schema for `target_state`."""
    state = target_state if target_state in STATE_DESCRIPTIONS else "focused"
    spec = STATE_DESCRIPTIONS[state]
    tasks = workspace.get("tasks", [])
    notes = workspace.get("notes", [])
    ideas = workspace.get("ideas", [])

    top_task = _top_incomplete_task(tasks)
    quick_wins = _quick_win_tasks(tasks)
    latest_note = sorted(notes, key=lambda n: n.get("updatedAt", 0), reverse=True)[0] if notes else None
    completed_count = sum(1 for t in tasks if t.get("completed"))
    hidden_count = max(0, sum(1 for t in tasks if not t.get("completed")) - 1)

    components: list[dict[str, Any]] = []

    if state == "overwhelmed":
        components = [
            {
                "id": "w-triager",
                "type": "TaskTriagerWidget",
                "region": "tunnel-primary",
                "priority": 1,
                "title": "Single Next Micro-Step",
                "hciRule": "Hick's Law + Fitts's Law (1.26x CTA)",
                "props": {
                    "task": top_task,
                    "hiddenTaskCount": hidden_count,
                },
            },
            {
                "id": "w-somatic",
                "type": "SomaticResetWidget",
                "region": "tunnel-secondary",
                "priority": 2,
                "title": "Somatic Breathing Reset",
                "hciRule": "Autonomic Down-Regulation (4-7-8 / Box)",
                "props": {"defaultPattern": "4-7-8"},
            },
            {
                "id": "w-timer",
                "type": "AdaptiveFocusTimer",
                "region": "tunnel-secondary",
                "priority": 3,
                "title": "Micro-Start Timer",
                "hciRule": "Low-Threshold Behavioral Activation",
                "props": {"preset": spec["timerPreset"]},
            },
            {
                "id": "w-editor",
                "type": "DeepDocumentEditor",
                "region": "tunnel-collapsible",
                "priority": 4,
                "title": "Distraction-Free Scratchpad",
                "hciRule": "Progressive Disclosure",
                "props": {"collapsible": True, "defaultCollapsed": True, "voiceAssist": False},
            },
        ]
    elif state == "fatigued":
        components = [
            {
                "id": "w-quickwins",
                "type": "QuickWinDeckWidget",
                "region": "main-left",
                "priority": 1,
                "title": "Low-Friction Quick Wins (<=15m)",
                "hciRule": "Cognitive Effort Minimization",
                "props": {"quickTasks": quick_wins},
            },
            {
                "id": "w-hydration",
                "type": "HydrationStretchCard",
                "region": "main-right",
                "priority": 2,
                "title": "Gentle Recovery Cue",
                "hciRule": "Ergonomic Fatigue Mitigation",
                "props": {},
            },
            {
                "id": "w-timer",
                "type": "AdaptiveFocusTimer",
                "region": "main-right",
                "priority": 3,
                "title": "Gentle Sprint Cadence",
                "hciRule": "Micro-Interval Pacing",
                "props": {"preset": spec["timerPreset"]},
            },
            {
                "id": "w-editor",
                "type": "DeepDocumentEditor",
                "region": "bottom-full",
                "priority": 4,
                "title": "Readable Notes + Voice Assist",
                "hciRule": "1.14x Typography + SpeechSynthesis Offload",
                "props": {"collapsible": False, "defaultCollapsed": False, "voiceAssist": True},
            },
        ]
    elif state == "energized":
        components = [
            {
                "id": "w-ideas",
                "type": "DivergentIdeaCanvas",
                "region": "hero-top",
                "priority": 1,
                "title": "Divergent Idea Canvas",
                "hciRule": "Broaden-and-Build Capture",
                "props": {"ideasCount": len(ideas)},
            },
            {
                "id": "w-tasks-kanban",
                "type": "TaskQueuePanel",
                "region": "main-left",
                "priority": 2,
                "title": "Momentum Kanban Board",
                "hciRule": "Spatial Priority Mapping",
                "props": {"viewMode": "kanban", "maxVisible": spec["maxVisibleTasks"]},
            },
            {
                "id": "w-timer",
                "type": "AdaptiveFocusTimer",
                "region": "sidebar-right",
                "priority": 3,
                "title": "Creative Jam Timer",
                "hciRule": "High-Momentum Timeboxing",
                "props": {"preset": spec["timerPreset"]},
            },
            {
                "id": "w-editor",
                "type": "DeepDocumentEditor",
                "region": "sidebar-right",
                "priority": 4,
                "title": "Rapid Synthesis Pad",
                "hciRule": "Concurrent Note Capture",
                "props": {"collapsible": False, "defaultCollapsed": False, "voiceAssist": False},
            },
        ]
    elif state == "disoriented":
        components = [
            {
                "id": "w-anchor",
                "type": "ContextAnchorBanner",
                "region": "hero-top",
                "priority": 1,
                "title": "Where You Left Off",
                "hciRule": "Recognition Over Recall (Nielsen #6)",
                "props": {
                    "activeGoal": top_task["title"] if top_task else "All tasks complete — review notes or add next goal.",
                    "lastNoteTitle": latest_note["title"] if latest_note else "No active note",
                    "lastNoteExcerpt": (latest_note["content"][:180] + "...") if latest_note and len(latest_note["content"]) > 180 else (latest_note["content"] if latest_note else ""),
                    "completedCount": completed_count,
                    "totalCount": len(tasks),
                },
            },
            {
                "id": "w-tasks-guided",
                "type": "TaskQueuePanel",
                "region": "main-left",
                "priority": 2,
                "title": "Top 3 Clear Priorities",
                "hciRule": "Miller's Law Bounded List",
                "props": {"viewMode": "guided", "maxVisible": 3},
            },
            {
                "id": "w-editor",
                "type": "DeepDocumentEditor",
                "region": "main-right",
                "priority": 3,
                "title": "Anchored Workspace Note",
                "hciRule": "Single-Context Continuity",
                "props": {"collapsible": False, "defaultCollapsed": False, "voiceAssist": False},
            },
            {
                "id": "w-timer",
                "type": "AdaptiveFocusTimer",
                "region": "sidebar-right",
                "priority": 4,
                "title": "Re-Anchor Block",
                "hciRule": "Structured Re-Entry Window",
                "props": {"preset": spec["timerPreset"]},
            },
        ]
    else:  # focused
        components = [
            {
                "id": "w-editor",
                "type": "DeepDocumentEditor",
                "region": "studio-center",
                "priority": 1,
                "title": "Deep Work Document Studio",
                "hciRule": "Flow-Preserving Primary Canvas",
                "props": {"collapsible": False, "defaultCollapsed": False, "voiceAssist": True},
            },
            {
                "id": "w-tasks",
                "type": "TaskQueuePanel",
                "region": "studio-left",
                "priority": 2,
                "title": "Structured Task Queue",
                "hciRule": "High Information Density",
                "props": {"viewMode": "compact", "maxVisible": spec["maxVisibleTasks"]},
            },
            {
                "id": "w-timer",
                "type": "AdaptiveFocusTimer",
                "region": "studio-right",
                "priority": 3,
                "title": "Deep Block Timer",
                "hciRule": "50/10 Ultradian Rhythm",
                "props": {"preset": spec["timerPreset"]},
            },
            {
                "id": "w-ideas-compact",
                "type": "DivergentIdeaCanvas",
                "region": "studio-right",
                "priority": 4,
                "title": "Quick Idea Inbox",
                "hciRule": "Zero-Friction Capture",
                "props": {"ideasCount": len(ideas), "compact": True},
            },
        ]

    return {
        "schemaVersion": "1.0",
        "generatedAt": time.time(),
        "targetState": state,
        "modeName": spec["modeName"],
        "modeSubtitle": spec["modeSubtitle"],
        "layout": {
            "topology": spec["topology"],
            "visualType": spec["visualType"],
            "navType": spec["navType"],
            "columns": spec["columns"],
            "density": spec["density"],
            "navigationChrome": spec["navigationChrome"],
            "maxVisibleTasks": spec["maxVisibleTasks"],
            "showSidebar": state in ("focused", "energized", "disoriented"),
        },
        "interaction": {
            "targetScale": spec["targetScale"],
            "typographyScale": spec["typographyScale"],
            "lineHeight": spec["lineHeight"],
            "notificationPolicy": spec["notificationPolicy"],
            "timerPreset": spec["timerPreset"],
            "voiceAssistRecommended": spec["voiceAssistRecommended"],
        },
        "surfaceTokens": spec["surfaceTokens"],
        "components": components,
        "hciRationale": _build_rationale(state, telemetry),
        "structuralDiff": _structural_diff(from_state or state, state),
    }
