import cv2
import mediapipe as mp
from enum import Enum, auto


class GestureCommand(Enum):
    NONE       = auto()
    TAKEOFF    = auto()
    LAND       = auto()
    MOVE_RIGHT = auto()
    MOVE_LEFT  = auto()
    HOVER      = auto()


FINGERTIPS   = [4, 8, 12, 16, 20]
FINGER_MIDS  = [3, 7, 11, 15, 19]
FINGER_BASES = [2, 6, 10, 14, 18]


def _is_extended(lm, tip, mid, base, is_thumb=False):
    if is_thumb:
        return abs(lm[tip].x - lm[base].x) > abs(lm[mid].x - lm[base].x) * 0.8
    return lm[tip].y < lm[base].y


def _fingers(lm):
    return [_is_extended(lm, *args, is_thumb=(i == 0))
            for i, args in enumerate(zip(FINGERTIPS, FINGER_MIDS, FINGER_BASES))]


def classify_gesture(lm, w) -> GestureCommand:
    ext = _fingers(lm)
    n   = sum(ext)

    if n >= 4:
        return GestureCommand.TAKEOFF

    if n == 0:
        return GestureCommand.LAND

    # سبابة فقط
    if ext[1] and not ext[2] and not ext[3] and not ext[4]:
        tip = lm[8]
        mcp = lm[5]
        dx  = tip.x - mcp.x
        dy  = tip.y - mcp.y

        if abs(dx) > abs(dy):
            if dx > 0.06:
                return GestureCommand.MOVE_RIGHT
            elif dx < -0.06:
                return GestureCommand.MOVE_LEFT
        else:
            if dy < -0.06:   # سبابة فوق
                return GestureCommand.HOVER

    return GestureCommand.NONE


class GestureSmoothing:
    def __init__(self, window=12):
        self.window  = window
        self.history = []

    def update(self, cmd):
        self.history.append(cmd)
        if len(self.history) > self.window:
            self.history.pop(0)
        counts = {}
        for c in self.history:
            counts[c] = counts.get(c, 0) + 1
        return max(counts, key=counts.get)


class HandGestureDetector:
    def __init__(self, camera_index=0, smoothing_window=12, show_debug=True):
        self.cap        = cv2.VideoCapture(camera_index)
        self.show_debug = show_debug
        self.smoother   = GestureSmoothing(window=smoothing_window)
        mp_hands        = mp.solutions.hands
        self.mp_draw    = mp.solutions.drawing_utils
        self.hands      = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6,
        )
        self.HAND_CONNECTIONS = mp_hands.HAND_CONNECTIONS

        self.label_map = {
            GestureCommand.NONE:       ("---",       (100, 100, 100)),
            GestureCommand.TAKEOFF:    ("TAKEOFF",   (0,   220, 0)),
            GestureCommand.LAND:       ("LAND",      (0,   80,  255)),
            GestureCommand.MOVE_RIGHT: (">> RIGHT",  (255, 165, 0)),
            GestureCommand.MOVE_LEFT:  ("LEFT <<",   (0,   165, 255)),
            GestureCommand.HOVER:      ("HOVER",     (255, 255, 0)),
        }

    def get_frame_gesture(self):
        ret, frame = self.cap.read()
        if not ret:
            return GestureCommand.NONE, None

        frame  = cv2.flip(frame, 1)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)
        raw    = GestureCommand.NONE

        if result.multi_hand_landmarks:
            for hlm in result.multi_hand_landmarks:
                if self.show_debug:
                    self.mp_draw.draw_landmarks(frame, hlm, self.HAND_CONNECTIONS)
                raw = classify_gesture(hlm.landmark, frame.shape[1])
                break

        cmd = self.smoother.update(raw)

        if self.show_debug:
            label, color = self.label_map[cmd]
            cv2.putText(frame, f"CMD: {label}", (15, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, color, 3)
            cv2.putText(frame, "Q=quit", (15, frame.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

        return cmd, frame

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()