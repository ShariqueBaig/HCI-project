"""OpenCV YuNet + ONNX HSEmotion computer vision pipeline with thread-safe webcam management."""

from __future__ import annotations

import base64
import logging
import math
import threading
import time
from typing import Any

import cv2
import numpy as np

from backend.vision.model_manager import ModelBundle

logger = logging.getLogger("aura.vision")

EMOTION_KEYS = ["anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"]


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exps = np.exp(shifted)
    denom = np.sum(exps)
    return exps / denom if denom > 0 else np.ones_like(exps) / len(exps)


class VisionEngine:
    """Runs OpenCV capture + YuNet face/landmark detection + ONNX emotion inference."""

    def __init__(self, models: ModelBundle) -> None:
        self.models = models
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cap: cv2.VideoCapture | None = None
        self._camera_enabled: bool = False
        self._camera_error: str | None = None
        self._detector = models.create_yunet(640, 480)
        self._detector_size: tuple[int, int] = (640, 480)
        self._haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._latest_result: dict[str, Any] = self._empty_result(camera_active=False)

    @staticmethod
    def _empty_result(camera_active: bool = False, error: str | None = None) -> dict[str, Any]:
        probs = {k: (1.0 if k == "neutral" else 0.0) for k in EMOTION_KEYS}
        return {
            "timestamp": time.time(),
            "camera_active": camera_active,
            "camera_error": error,
            "face_detected": False,
            "face_count": 0,
            "dominant_emotion": "neutral",
            "confidence": 0.0,
            "emotions": probs,
            "attention_score": 1.0 if not camera_active else 0.5,
            "head_roll_deg": 0.0,
            "head_yaw_proxy": 0.0,
            "head_pitch_proxy": 0.0,
            "annotated_frame_b64": None,
            "latency_ms": 0.0,
        }

    def start_camera(self) -> dict[str, Any]:
        with self._lock:
            if self._camera_enabled and self._thread and self._thread.is_alive():
                return {"camera_active": True, "error": self._camera_error}
            self._stop_event.clear()
            self._camera_error = None
            self._camera_enabled = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="aura-vision")
            self._thread.start()
            return {"camera_active": True, "error": None}

    def stop_camera(self) -> dict[str, Any]:
        with self._lock:
            self._camera_enabled = False
            self._stop_event.set()
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self._thread = None
            self._latest_result = self._empty_result(camera_active=False)
        return {"camera_active": False, "error": None}

    @property
    def camera_active(self) -> bool:
        with self._lock:
            return self._camera_enabled

    def get_latest(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest_result)

    def _open_capture(self) -> cv2.VideoCapture | None:
        for backend in (cv2.CAP_DSHOW, cv2.CAP_ANY):
            cap = cv2.VideoCapture(0, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return cap
            cap.release()
        return None

    def _capture_loop(self) -> None:
        cap = self._open_capture()
        if cap is None:
            with self._lock:
                self._camera_error = "Unable to access webcam device 0."
                self._camera_enabled = False
                self._latest_result = self._empty_result(
                    camera_active=False, error=self._camera_error
                )
            return

        with self._lock:
            self._cap = cap

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.08)
                    continue

                frame = cv2.flip(frame, 1)
                result = self.analyze_frame(frame, include_jpeg=False)   # frames never leave this process
                result["camera_active"] = True
                result["camera_error"] = None
                with self._lock:
                    if not self._camera_enabled:
                        break
                    self._latest_result = result
                # ~10-12 Hz CPU-friendly cadence
                time.sleep(0.085)
        finally:
            try:
                cap.release()
            except Exception:
                pass
            with self._lock:
                self._cap = None

    def _detect_faces(self, bgr: np.ndarray) -> list[dict[str, Any]]:
        h, w = bgr.shape[:2]
        faces_out: list[dict[str, Any]] = []

        if self._detector is not None:
            if self._detector_size != (w, h):
                self._detector.setInputSize((w, h))
                self._detector_size = (w, h)
            _, faces = self._detector.detect(bgr)
            if faces is not None and len(faces) > 0:
                for row in faces:
                    x, y, bw, bh = [float(v) for v in row[:4]]
                    score = float(row[14])
                    landmarks = {
                        "right_eye": (float(row[4]), float(row[5])),
                        "left_eye": (float(row[6]), float(row[7])),
                        "nose": (float(row[8]), float(row[9])),
                        "right_mouth": (float(row[10]), float(row[11])),
                        "left_mouth": (float(row[12]), float(row[13])),
                    }
                    faces_out.append(
                        {
                            "bbox": (int(x), int(y), int(bw), int(bh)),
                            "score": score,
                            "landmarks": landmarks,
                        }
                    )
        else:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            rects = self._haar.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(48, 48))
            for (x, y, bw, bh) in rects:
                faces_out.append(
                    {
                        "bbox": (int(x), int(y), int(bw), int(bh)),
                        "score": 0.75,
                        "landmarks": None,
                    }
                )

        faces_out.sort(key=lambda f: f["bbox"][2] * f["bbox"][3] * max(0.1, f["score"]), reverse=True)
        return faces_out

    def _compute_pose_cues(self, landmarks: dict[str, tuple[float, float]] | None) -> tuple[float, float, float, float]:
        if not landmarks:
            return 0.0, 0.0, 0.0, 0.85

        rx, ry = landmarks["right_eye"]
        lx, ly = landmarks["left_eye"]
        nx, ny = landmarks["nose"]
        rmx, rmy = landmarks["right_mouth"]
        lmx, lmy = landmarks["left_mouth"]

        dx = lx - rx
        dy = ly - ry
        eye_dist = max(1.0, math.hypot(dx, dy))
        roll_deg = math.degrees(math.atan2(dy, dx))

        eye_mid_x = 0.5 * (rx + lx)
        eye_mid_y = 0.5 * (ry + ly)
        mouth_mid_y = 0.5 * (rmy + lmy)

        # Horizontal asymmetry of nose relative to eyes
        yaw_proxy = min(1.0, abs(nx - eye_mid_x) / (0.45 * eye_dist))
        # Vertical ratio indicating pitch / droop
        eye_to_mouth = max(1.0, mouth_mid_y - eye_mid_y)
        pitch_ratio = (ny - eye_mid_y) / eye_to_mouth
        pitch_proxy = min(1.0, max(0.0, (pitch_ratio - 0.55) / 0.35))

        attention = 1.0 - min(
            1.0, 0.65 * yaw_proxy + 0.35 * min(1.0, abs(roll_deg) / 32.0)
        )
        return round(roll_deg, 2), round(yaw_proxy, 3), round(pitch_proxy, 3), round(attention, 3)

    def _predict_emotions(self, face_bgr: np.ndarray) -> dict[str, float]:
        if not self.models.ready or self.models.emotion_session is None:
            return {k: (1.0 if k == "neutral" else 0.0) for k in EMOTION_KEYS}

        if self.models.emotion_kind == "hsemotion":
            rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
            arr = resized.astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            arr = (arr - mean) / std
            tensor = np.transpose(arr, (2, 0, 1))[None, ...]
        else:
            gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
            tensor = resized.astype(np.float32)[None, None, ...]

        outputs = self.models.emotion_session.run(
            None, {self.models.emotion_input_name: tensor}
        )
        logits = np.asarray(outputs[self.models.emotion_output_index][0], dtype=np.float32)
        probs = _softmax(logits)

        mapped: dict[str, float] = {k: 0.0 for k in EMOTION_KEYS}
        for idx, cls_name in enumerate(self.models.emotion_classes):
            if idx < len(probs):
                mapped[cls_name.lower()] = float(probs[idx])
        return mapped

    def _draw_overlay(
        self,
        frame: np.ndarray,
        face: dict[str, Any] | None,
        dominant: str,
        conf: float,
        attention: float,
    ) -> np.ndarray:
        canvas = frame.copy()
        h, w = canvas.shape[:2]

        if face is not None:
            x, y, bw, bh = face["bbox"]
            x1, y1 = max(4, x), max(4, y)
            x2, y2 = min(w - 4, x + bw), min(h - 4, y + bh)
            corner = max(10, int(min(bw, bh) * 0.18))
            color = (130, 210, 175) if attention >= 0.55 else (110, 185, 245)

            # Minimal corner-bracket bounding box
            for (px, py, dx, dy) in [
                (x1, y1, corner, corner),
                (x2, y1, -corner, corner),
                (x1, y2, corner, -corner),
                (x2, y2, -corner, -corner),
            ]:
                cv2.line(canvas, (px, py), (px + dx, py), color, 2, cv2.LINE_AA)
                cv2.line(canvas, (px, py), (px, py + dy), color, 2, cv2.LINE_AA)

            # Subtle 5-point landmarks
            if face["landmarks"]:
                for pt in face["landmarks"].values():
                    cv2.circle(canvas, (int(pt[0]), int(pt[1])), 2, (230, 240, 255), -1, cv2.LINE_AA)

            badge = f"{dominant.upper()} {int(conf * 100)}% | ATTN {int(attention * 100)}%"
            cv2.rectangle(canvas, (x1, max(0, y1 - 24)), (min(w - 2, x1 + 225), y1), (20, 24, 31), -1)
            cv2.putText(
                canvas,
                badge,
                (x1 + 6, max(14, y1 - 7)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (235, 242, 248),
                1,
                cv2.LINE_AA,
            )
        else:
            cv2.putText(
                canvas,
                "NO FACE IN FRAME",
                (14, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 190, 205),
                1,
                cv2.LINE_AA,
            )
        return canvas

    def analyze_frame(self, bgr_frame: np.ndarray, include_jpeg: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        if bgr_frame is None or bgr_frame.size == 0:
            return self._empty_result(camera_active=self.camera_active)

        h, w = bgr_frame.shape[:2]
        if w > 640:
            scale = 640.0 / w
            work = cv2.resize(bgr_frame, (640, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        else:
            work = bgr_frame

        wh, ww = work.shape[:2]
        faces = self._detect_faces(work)
        if not faces:
            annotated_b64 = None
            if include_jpeg:
                overlay = self._draw_overlay(work, None, "neutral", 0.0, 0.5)
                ok_enc, buf = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok_enc:
                    annotated_b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            res = self._empty_result(camera_active=self.camera_active)
            res["annotated_frame_b64"] = annotated_b64
            res["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
            return res

        primary = faces[0]
        x, y, bw, bh = primary["bbox"]
        pad_x = int(bw * 0.12)
        pad_y = int(bh * 0.12)
        cx1 = max(0, x - pad_x)
        cy1 = max(0, y - pad_y)
        cx2 = min(ww, x + bw + pad_x)
        cy2 = min(wh, y + bh + pad_y)

        crop = work[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            crop = work

        probs = self._predict_emotions(crop)
        dominant = max(probs, key=lambda k: probs[k])
        confidence = float(probs[dominant])
        roll, yaw, pitch, attention = self._compute_pose_cues(primary["landmarks"])

        annotated_b64 = None
        if include_jpeg:
            overlay = self._draw_overlay(work, primary, dominant, confidence, attention)
            ok_enc, buf = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 72])
            if ok_enc:
                annotated_b64 = base64.b64encode(buf.tobytes()).decode("ascii")

        return {
            "timestamp": time.time(),
            "camera_active": self.camera_active,
            "camera_error": None,
            "face_detected": True,
            "face_count": len(faces),
            "dominant_emotion": dominant,
            "confidence": round(confidence, 4),
            "emotions": {k: round(v, 4) for k, v in probs.items()},
            "attention_score": attention,
            "head_roll_deg": roll,
            "head_yaw_proxy": yaw,
            "head_pitch_proxy": pitch,
            "annotated_frame_b64": annotated_b64,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }
