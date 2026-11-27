"""Downloads, caches, and verifies local ONNX models for YuNet face detection and HSEmotion."""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort

logger = logging.getLogger("aura.models")

MODELS_DIR = Path(__file__).resolve().parent / "models"

YUNET_SPEC = {
    "filename": "face_detection_yunet_2023mar.onnx",
    "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "min_bytes": 150_000,
}

HSEMOTION_SPEC = {
    "filename": "enet_b0_8_best_vgaf.onnx",
    "url": "https://github.com/HSE-asavchenko/face-emotion-recognition/raw/main/models/affectnet_emotions/onnx/enet_b0_8_best_vgaf.onnx",
    "min_bytes": 10_000_000,
    "classes": ["anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"],
}

FERPLUS_SPEC = {
    "filename": "emotion-ferplus-8.onnx",
    "url": "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
    "min_bytes": 20_000_000,
    "classes": ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"],
}


def _download_file(url: str, dest: Path, min_bytes: int) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        return dest

    tmp_path = dest.with_suffix(".tmp")
    logger.info("Downloading %s -> %s", url, dest)
    req = urllib.request.Request(url, headers={"User-Agent": "AURA-HCI/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp_path.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 128)
            if not chunk:
                break
            out.write(chunk)

    if tmp_path.stat().st_size < min_bytes:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file {dest.name} is unexpectedly small.")
    tmp_path.replace(dest)
    return dest


class ModelBundle:
    """Container holding verified YuNet face detector and ONNX emotion session."""

    def __init__(self) -> None:
        self.yunet_path: Path | None = None
        self.emotion_path: Path | None = None
        self.emotion_kind: str = "none"  # 'hsemotion' | 'ferplus' | 'none'
        self.emotion_classes: list[str] = list(HSEMOTION_SPEC["classes"])
        self.emotion_session: ort.InferenceSession | None = None
        self.emotion_input_name: str = ""
        self.emotion_output_name: str = ""
        self.emotion_output_index: int = 0
        self.yunet_available: bool = False
        self.ready: bool = False
        self.error: str | None = None

    def load(self) -> "ModelBundle":
        """Ensure models are downloaded and validated with dry-run inference."""
        try:
            yunet_dest = MODELS_DIR / YUNET_SPEC["filename"]
            _download_file(YUNET_SPEC["url"], yunet_dest, YUNET_SPEC["min_bytes"])
            # Test instantiating YuNet
            detector = cv2.FaceDetectorYN.create(str(yunet_dest), "", (320, 320), 0.7, 0.3, 5000)
            if detector is None:
                raise RuntimeError("FaceDetectorYN.create returned None")
            self.yunet_path = yunet_dest
            self.yunet_available = True
        except Exception as exc:
            logger.warning("YuNet unavailable, falling back to Haar cascade: %s", exc)
            self.yunet_available = False

        # Try HSEmotion first, fallback to FER+ if needed
        for kind, spec in [("hsemotion", HSEMOTION_SPEC), ("ferplus", FERPLUS_SPEC)]:
            try:
                dest = MODELS_DIR / spec["filename"]
                _download_file(spec["url"], dest, spec["min_bytes"])
                session = ort.InferenceSession(str(dest), providers=["CPUExecutionProvider"])
                inp = session.get_inputs()[0]
                outputs = session.get_outputs()

                if kind == "hsemotion":
                    dummy = np.zeros((1, 3, 224, 224), dtype=np.float32)
                else:
                    dummy = np.zeros((1, 1, 64, 64), dtype=np.float32)

                res = session.run(None, {inp.name: dummy})
                chosen_idx = None
                for idx, arr in enumerate(res):
                    if arr.ndim == 2 and arr.shape[-1] == 8:
                        chosen_idx = idx
                        break
                if chosen_idx is None:
                    raise RuntimeError(f"Unexpected output shapes {[a.shape for a in res]}")

                self.emotion_path = dest
                self.emotion_kind = kind
                self.emotion_classes = list(spec["classes"])
                self.emotion_session = session
                self.emotion_input_name = inp.name
                self.emotion_output_name = outputs[chosen_idx].name
                self.emotion_output_index = chosen_idx
                self.ready = True
                self.error = None
                logger.info(
                    "Loaded emotion model %s (%s), output=%s shape=%s",
                    kind,
                    dest.name,
                    self.emotion_output_name,
                    res[chosen_idx].shape,
                )
                return self
            except Exception as exc:
                logger.warning("Failed to load %s: %s", kind, exc)
                self.error = str(exc)

        self.ready = False
        return self

    def create_yunet(self, width: int = 320, height: int = 320) -> Any | None:
        if not self.yunet_available or self.yunet_path is None:
            return None
        return cv2.FaceDetectorYN.create(
            str(self.yunet_path),
            "",
            (max(1, width), max(1, height)),
            score_threshold=0.65,
            nms_threshold=0.3,
            top_k=5000,
        )

    def status_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "yunet_available": self.yunet_available,
            "emotion_model": self.emotion_kind,
            "emotion_file": self.emotion_path.name if self.emotion_path else None,
            "classes": self.emotion_classes,
            "error": self.error,
        }
