"""Optional webcam affect sensor for Aura Search (pip install ".[vision]").

Ported from the webcam app (HCI Mood assignment/backend): OpenCV YuNet face
detection + HSEmotion EfficientNet-B0 emotions -> valence/arousal (Russell's
circumplex) in AffectiveEngine. Off by default. Frames stay in memory, are never
stored, encoded or sent anywhere; only the smoothed affect numbers reach state
fusion. Turning the camera off releases the device immediately.
"""
