"""Affective cognitive-state engine with Russell Circumplex, EMA smoothing, and dwell hysteresis."""

from __future__ import annotations

from collections import deque
import threading
import time
from typing import Any

from backend.vision_engine import EMOTION_KEYS

HCI_STATES = ("focused", "overwhelmed", "fatigued", "energized", "disoriented")

# Validated Valence-Arousal coordinates on Russell's Circumplex (-1.0 to +1.0)
CIRCUMPLEX_ANCHORS: dict[str, tuple[float, float]] = {
    "happiness": (0.85, 0.55),
    "surprise": (0.20, 0.80),
    "neutral": (0.05, -0.10),
    "sadness": (-0.75, -0.55),
    "anger": (-0.75, 0.75),
    "fear": (-0.80, 0.80),
    "disgust": (-0.70, 0.35),
    "contempt": (-0.45, 0.10),
}

SIMULATION_PROFILES: dict[str, dict[str, Any]] = {
    "focused": {
        "emotions": {
            "neutral": 0.72, "happiness": 0.14, "surprise": 0.03, "sadness": 0.03,
            "anger": 0.02, "fear": 0.02, "disgust": 0.02, "contempt": 0.02,
        },
        "attention": 0.92,
        "pitch": 0.10,
    },
    "overwhelmed": {
        "emotions": {
            "fear": 0.34, "anger": 0.26, "disgust": 0.12, "sadness": 0.10,
            "surprise": 0.08, "neutral": 0.06, "contempt": 0.03, "happiness": 0.01,
        },
        "attention": 0.68,
        "pitch": 0.22,
    },
    "fatigued": {
        "emotions": {
            "sadness": 0.52, "neutral": 0.28, "disgust": 0.05, "fear": 0.04,
            "contempt": 0.04, "anger": 0.03, "happiness": 0.02, "surprise": 0.02,
        },
        "attention": 0.60,
        "pitch": 0.74,
    },
    "energized": {
        "emotions": {
            "happiness": 0.68, "surprise": 0.14, "neutral": 0.12, "anger": 0.01,
            "fear": 0.01, "sadness": 0.01, "disgust": 0.01, "contempt": 0.02,
        },
        "attention": 0.90,
        "pitch": 0.08,
    },
    "disoriented": {
        "emotions": {
            "surprise": 0.48, "fear": 0.14, "neutral": 0.18, "sadness": 0.07,
            "happiness": 0.05, "anger": 0.03, "disgust": 0.03, "contempt": 0.02,
        },
        "attention": 0.42,
        "pitch": 0.25,
    },
}


class AffectiveEngine:
    """Computes stabilized HCI affective states with anti-thrashing dwell hysteresis."""

    def __init__(self, dwell_seconds: float = 3.0, cooldown_seconds: float = 5.0, ema_alpha: float = 0.28) -> None:
        self._lock = threading.Lock()
        self.ema_alpha = ema_alpha
        self.dwell_seconds = dwell_seconds
        self.cooldown_seconds = cooldown_seconds
        self.agency_mode: str = "copilot"  # 'copilot' | 'autonomous' | 'manual'

        self.smoothed_emotions: dict[str, float] = {
            k: (1.0 if k == "neutral" else 0.0) for k in EMOTION_KEYS
        }
        self.smoothed_attention: float = 0.9
        self.smoothed_pitch: float = 0.1

        self.active_state: str = "focused"
        self.previous_state: str | None = None
        self.candidate_state: str = "focused"
        self.candidate_since: float = time.time()
        self.last_transition_at: float = 0.0

        self.simulated_state: str | None = None
        self.pending_proposal: dict[str, Any] | None = None
        self.dismissed_until: dict[str, float] = {}

        self.history_dominants: deque[str] = deque(maxlen=16)
        self.circumplex_trail: deque[dict[str, float]] = deque(maxlen=24)
        self.flickers_prevented: int = 0
        self.proposals_accepted: int = 0
        self.proposals_dismissed: int = 0
        self.transition_events: list[dict[str, Any]] = []
        self._last_update_time: float = time.time()
        self.time_in_state: dict[str, float] = {s: 0.0 for s in HCI_STATES}

    def configure(self, agency_mode: str | None = None, dwell_seconds: float | None = None) -> None:
        with self._lock:
            if agency_mode in ("copilot", "autonomous", "manual"):
                self.agency_mode = agency_mode
                if agency_mode != "copilot":
                    self.pending_proposal = None
            if dwell_seconds is not None:
                self.dwell_seconds = max(0.5, min(10.0, float(dwell_seconds)))

    def set_simulation(self, state: str | None) -> dict[str, Any]:
        with self._lock:
            if state is None:
                self.simulated_state = None
                self.pending_proposal = None
                prof = SIMULATION_PROFILES["focused"]
                self.smoothed_emotions = dict(prof["emotions"])
                self.smoothed_attention = prof["attention"]
                self.smoothed_pitch = prof["pitch"]
                self.candidate_state = "focused"
                self.active_state = "focused"
                return {"simulated_state": None, "active_state": self.active_state}
            if state not in HCI_STATES:
                raise ValueError(f"Unknown HCI state: {state}")
            self.simulated_state = state
            prof = SIMULATION_PROFILES[state]
            self.smoothed_emotions = dict(prof["emotions"])
            self.smoothed_attention = prof["attention"]
            self.smoothed_pitch = prof["pitch"]
            self.candidate_state = state
            self.candidate_since = time.time() - self.dwell_seconds
            # In copilot mode, immediately surface a proposal so the user can experience Co-Pilot UX,
            # or if autonomous, apply immediately.
            if self.agency_mode == "copilot" and state != self.active_state:
                self.pending_proposal = self._build_proposal(state, 0.91, "simulation")
            elif self.agency_mode in ("autonomous", "manual"):
                # Even in manual, allow explicit demo simulator to preview or switch when clicked
                self._commit_transition(state, source="simulation")
            return {"simulated_state": self.simulated_state, "active_state": self.active_state}

    def force_state(self, state: str, source: str = "manual_override") -> None:
        with self._lock:
            if state in HCI_STATES:
                self._commit_transition(state, source=source)

    def respond_to_proposal(self, action: str) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            if action == "accept" and self.pending_proposal:
                target = self.pending_proposal["target_state"]
                self.proposals_accepted += 1
                self.pending_proposal = None
                self._commit_transition(target, source="copilot_accept")
                return {"ok": True, "active_state": self.active_state}
            if action == "dismiss" and self.pending_proposal:
                target = self.pending_proposal["target_state"]
                self.proposals_dismissed += 1
                self.dismissed_until[target] = now + 18.0
                self.pending_proposal = None
                return {"ok": True, "active_state": self.active_state}
            if action == "undo" and self.previous_state:
                prev = self.previous_state
                self.previous_state = None
                self.pending_proposal = None
                self._commit_transition(prev, source="undo", record_previous=False)
                return {"ok": True, "active_state": self.active_state}
            return {"ok": False, "active_state": self.active_state}

    def _commit_transition(self, target: str, source: str, record_previous: bool = True) -> None:
        if target == self.active_state:
            return
        if record_previous:
            self.previous_state = self.active_state
        old = self.active_state
        self.active_state = target
        self.last_transition_at = time.time()
        self.transition_events.append(
            {
                "timestamp": self.last_transition_at,
                "from_state": old,
                "to_state": target,
                "source": source,
            }
        )
        if len(self.transition_events) > 200:
            self.transition_events = self.transition_events[-200:]

    def _compute_circumplex(self, emotions: dict[str, float]) -> tuple[float, float]:
        valence = sum(emotions.get(e, 0.0) * CIRCUMPLEX_ANCHORS[e][0] for e in EMOTION_KEYS)
        arousal = sum(emotions.get(e, 0.0) * CIRCUMPLEX_ANCHORS[e][1] for e in EMOTION_KEYS)
        return round(max(-1.0, min(1.0, valence)), 4), round(max(-1.0, min(1.0, arousal)), 4)

    def _classify_state(
        self,
        emotions: dict[str, float],
        valence: float,
        arousal: float,
        attention: float,
        pitch: float,
        volatility: float,
        cog_load: float,
    ) -> tuple[str, float]:
        stress_sum = emotions.get("anger", 0.0) + emotions.get("fear", 0.0) + emotions.get("disgust", 0.0)
        sadness = emotions.get("sadness", 0.0)
        happiness = emotions.get("happiness", 0.0)
        surprise = emotions.get("surprise", 0.0)

        if stress_sum >= 0.42 or (valence < -0.28 and arousal > 0.22) or cog_load >= 0.72:
            return "overwhelmed", round(min(0.99, max(stress_sum, cog_load)), 3)
        if sadness >= 0.38 or (valence < -0.18 and arousal < -0.20) or (pitch > 0.64 and arousal < 0.05):
            return "fatigued", round(min(0.99, max(sadness, 0.65 if pitch > 0.64 else 0.55)), 3)
        if happiness >= 0.42 or (valence >= 0.32 and arousal >= 0.15):
            return "energized", round(min(0.99, max(happiness, (valence + 0.5) / 1.4)), 3)
        if surprise >= 0.35 or (attention < 0.48 and volatility > 0.12):
            return "disoriented", round(min(0.99, max(surprise, 1.0 - attention)), 3)
        return "focused", round(min(0.99, max(emotions.get("neutral", 0.5), attention * 0.85)), 3)

    def _build_proposal(self, target_state: str, confidence: float, source: str) -> dict[str, Any]:
        cues = {
            "overwhelmed": "Sustained high-arousal strain & elevated cognitive load detected.",
            "fatigued": "Sustained low-arousal fatigue / downward gaze posture detected.",
            "energized": "Sustained positive valence & high creative arousal detected.",
            "disoriented": "Elevated surprise / fragmented gaze attention detected.",
            "focused": "Steady neutral baseline & sustained on-screen attention restored.",
        }
        return {
            "id": f"prop-{int(time.time() * 1000)}",
            "from_state": self.active_state,
            "target_state": target_state,
            "confidence": round(confidence, 3),
            "source": source,
            "cue_summary": cues.get(target_state, "Sustained affective shift detected."),
            "created_at": time.time(),
        }

    def update(self, vision_obs: dict[str, Any], task_pressure: float = 0.2, now: float | None = None) -> dict[str, Any]:
        """Ingest a vision observation (or apply simulation) and return full affective telemetry."""
        with self._lock:
            now = now if now is not None else time.time()
            dt = max(0.0, min(2.0, now - self._last_update_time))
            self._last_update_time = now
            self.time_in_state[self.active_state] = round(
                self.time_in_state.get(self.active_state, 0.0) + dt, 2
            )

            source = "simulation" if self.simulated_state else ("webcam" if vision_obs.get("camera_active") else "idle")

            if self.simulated_state:
                prof = SIMULATION_PROFILES[self.simulated_state]
                raw_emotions = dict(prof["emotions"])
                raw_attention = prof["attention"]
                raw_pitch = prof["pitch"]
                face_detected = True
                obs_conf = 0.92
            elif vision_obs.get("face_detected"):
                raw_emotions = vision_obs["emotions"]
                raw_attention = float(vision_obs.get("attention_score", 0.8))
                raw_pitch = float(vision_obs.get("head_pitch_proxy", 0.1))
                face_detected = True
                obs_conf = float(vision_obs.get("confidence", 0.6))
            else:
                # Gently decay toward calm baseline when no face or camera off
                raw_emotions = {k: (1.0 if k == "neutral" else 0.0) for k in EMOTION_KEYS}
                raw_attention = 0.85 if not vision_obs.get("camera_active") else 0.5
                raw_pitch = 0.1
                face_detected = False
                obs_conf = 0.0

            alpha = 1.0 if self.simulated_state else self.ema_alpha
            for k in EMOTION_KEYS:
                prev = self.smoothed_emotions.get(k, 0.0)
                self.smoothed_emotions[k] = round((1.0 - alpha) * prev + alpha * raw_emotions.get(k, 0.0), 4)
            # Re-normalize
            tot = sum(self.smoothed_emotions.values()) or 1.0
            for k in EMOTION_KEYS:
                self.smoothed_emotions[k] = round(self.smoothed_emotions[k] / tot, 4)

            self.smoothed_attention = round((1.0 - alpha) * self.smoothed_attention + alpha * raw_attention, 4)
            self.smoothed_pitch = round((1.0 - alpha) * self.smoothed_pitch + alpha * raw_pitch, 4)

            dom = max(self.smoothed_emotions, key=lambda k: self.smoothed_emotions[k])
            self.history_dominants.append(dom)
            switches = sum(
                1 for i in range(1, len(self.history_dominants))
                if self.history_dominants[i] != self.history_dominants[i - 1]
            )
            volatility = round(switches / max(1, len(self.history_dominants) - 1), 3)

            valence, arousal = self._compute_circumplex(self.smoothed_emotions)
            self.circumplex_trail.append({"valence": valence, "arousal": arousal})

            stress_signal = (
                self.smoothed_emotions.get("anger", 0.0)
                + self.smoothed_emotions.get("fear", 0.0)
                + self.smoothed_emotions.get("disgust", 0.0)
            )
            cognitive_load = round(
                min(
                    1.0,
                    max(
                        0.0,
                        0.45 * stress_signal
                        + 0.25 * (1.0 - self.smoothed_attention)
                        + 0.15 * volatility
                        + 0.15 * min(1.0, task_pressure),
                    ),
                ),
                3,
            )

            inferred_state, state_conf = self._classify_state(
                self.smoothed_emotions,
                valence,
                arousal,
                self.smoothed_attention,
                self.smoothed_pitch,
                volatility,
                cognitive_load,
            )

            # Temporal hysteresis
            if inferred_state != self.candidate_state:
                if self.candidate_state != self.active_state and (now - self.candidate_since) < self.dwell_seconds:
                    self.flickers_prevented += 1
                self.candidate_state = inferred_state
                self.candidate_since = now

            elapsed_dwell = max(0.0, now - self.candidate_since)
            dwell_progress = (
                1.0
                if self.candidate_state == self.active_state
                else round(min(1.0, elapsed_dwell / max(0.2, self.dwell_seconds)), 3)
            )

            cooldown_ok = (now - self.last_transition_at) >= self.cooldown_seconds
            not_dismissed = now >= self.dismissed_until.get(self.candidate_state, 0.0)

            if (
                self.candidate_state != self.active_state
                and dwell_progress >= 1.0
                and (face_detected or self.simulated_state is not None)
            ):
                if self.agency_mode == "autonomous" and cooldown_ok:
                    self._commit_transition(self.candidate_state, source=source)
                    self.pending_proposal = None
                elif self.agency_mode == "copilot" and not_dismissed:
                    if (
                        self.pending_proposal is None
                        or self.pending_proposal["target_state"] != self.candidate_state
                    ):
                        self.pending_proposal = self._build_proposal(self.candidate_state, state_conf, source)

            # Clear stale proposal if user naturally returned to active_state
            if (
                self.pending_proposal is not None
                and self.candidate_state == self.active_state
                and dwell_progress >= 1.0
                and self.simulated_state is None
            ):
                self.pending_proposal = None

            return {
                "timestamp": now,
                "source": source,
                "camera_active": bool(vision_obs.get("camera_active", False)),
                "camera_error": vision_obs.get("camera_error"),
                "face_detected": face_detected,
                "raw_confidence": round(obs_conf, 3),
                "dominant_emotion": dom,
                "emotions": dict(self.smoothed_emotions),
                "valence": valence,
                "arousal": arousal,
                "attention_score": self.smoothed_attention,
                "head_pitch_proxy": self.smoothed_pitch,
                "volatility": volatility,
                "cognitive_load": cognitive_load,
                "active_state": self.active_state,
                "previous_state": self.previous_state,
                "candidate_state": self.candidate_state,
                "state_confidence": state_conf,
                "dwell_progress": dwell_progress,
                "dwell_seconds": self.dwell_seconds,
                "agency_mode": self.agency_mode,
                "simulated_state": self.simulated_state,
                "pending_proposal": self.pending_proposal,
                "circumplex_trail": list(self.circumplex_trail),
                "metrics": {
                    "flickers_prevented": self.flickers_prevented,
                    "proposals_accepted": self.proposals_accepted,
                    "proposals_dismissed": self.proposals_dismissed,
                    "transitions_count": len(self.transition_events),
                    "time_in_state": dict(self.time_in_state),
                },
            }

    def export_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.transition_events)
