
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
from collections import deque
import time

# Constants
MODEL_PATH = 'src/models/focus_guard_final.h5'
IMG_HEIGHT = 48
IMG_WIDTH = 48
EMOTION_LABELS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']

# OpenCV DNN Face Detector (ResNet-SSD) -- handles tilted & partial faces
DNN_PROTO = 'models/deploy.prototxt'
DNN_MODEL = 'models/res10_300x300_ssd_iter_140000.caffemodel'
DNN_CONFIDENCE = 0.5

# Tuning Parameters
SMOOTHING_WINDOW = 8       # Lowered for "Real Time" feeling
STRESS_THRESHOLD = 0.30    # Sensitivity to negative emotions

class FaceStabilizer:
    """Smooths the bounding box coordinates to stop jittering."""
    def __init__(self, alpha=0.5): # Increased alpha (0.15 -> 0.5) for less lag
        self.alpha = alpha 
        self.box = None    # [x, y, w, h]

    def update(self, x, y, w, h):
        current_box = np.array([x, y, w, h], dtype=np.float32)
        
        if self.box is None:
            self.box = current_box
        else:
            # Use explicit calculation to help type checker
            self.box = (self.box * (1 - self.alpha)) + (current_box * self.alpha)
        
        if self.box is None: return current_box.astype(int) # Should never happen
        return self.box.astype(int)

class MoodInertia:
    """
    Maintains the state of a strong emotion (Happy/Stress) even if the user's face relaxes.
    Default duration: 45s. Both HAPPY and STRESS break if Neutral is held long enough.
    """
    def __init__(self, duration=45):
        self.active_mood = None
        self.start_time = 0
        self.duration = duration
        self.focus_timer_start = None  # Tracks how long we've been Neutral while locked

    def update(self, current_detected_state):
        # 1. If we detect a STRONG emotion, lock it in.
        if current_detected_state in ["HAPPY", "STRESS"]:
            self.focus_timer_start = None  # Reset neutral timer on strong emotion

            # If it's different from current lock, switch immediately (Override)
            if current_detected_state != self.active_mood:
                if self.active_mood is not None:
                    print(f"🎯 Target Mood Updated: {self.active_mood} -> {current_detected_state}")
                else:
                    print(f"🎯 Target Mood Updated: FOCUS -> {current_detected_state}")
                self.active_mood = current_detected_state
                self.start_time = time.time()
            return current_detected_state

        # 2. If Locked, decide whether to hold or release
        if self.active_mood:
            # Check total duration expiry first
            if time.time() - self.start_time > self.duration:
                self.active_mood = None
                self.focus_timer_start = None
                return current_detected_state

            # Both HAPPY and STRESS: break lock after 6s of continuous Neutral/Focus
            if current_detected_state == "FOCUS":
                if self.focus_timer_start is None:
                    self.focus_timer_start = time.time()
                if time.time() - self.focus_timer_start > 6:
                    print(f"🔓 {self.active_mood} lock released (user relaxed)")
                    self.active_mood = None
                    self.focus_timer_start = None
                    return "FOCUS"
                return self.active_mood  # Still counting down
            else:
                # Non-FOCUS, non-HAPPY/STRESS (e.g. DISTRACTION) resets neutral timer
                self.focus_timer_start = None
                return self.active_mood

        # 3. No lock? Return actual state
        return current_detected_state

def preprocess_face(face_img):
    """
    Preprocesses a face image for the Mini-Xception model.
    Uses CLAHE (Contrast Limited Adaptive Histogram Equalization) for better
    performance under poor/uneven lighting compared to basic equalizeHist.
    """
    try:
        # 1. Grayscale
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)

        # 2. Mild Gaussian blur to reduce webcam sensor noise before contrast boost
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # 3. CLAHE — adaptive contrast equalization (better than global equalizeHist)
        #    clipLimit=2.0 prevents over-amplifying noise in flat regions
        #    tileGridSize=(8,8) divides face into 64 local cells for local contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # 4. Resize to 48x48
        resized = cv2.resize(gray, (IMG_WIDTH, IMG_HEIGHT), interpolation=cv2.INTER_AREA)

        # 5. Normalize [0, 1]
        normalized = resized / 255.0

        # 6. Reshape for model input
        return np.reshape(normalized, (1, IMG_HEIGHT, IMG_WIDTH, 1))
    except Exception:
        return None

def draw_hud(frame, predictions, current_state):
    """Draws a professional HUD with probability bars."""
    h, w, _ = frame.shape
    
    # 1. Sidebar Background
    sidebar_w = 220
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (sidebar_w, h), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

    # 2. Main Status
    color = (0, 255, 0) # Green
    if current_state == "STRESS": color = (0, 0, 255)
    elif current_state == "DISTRACTION": color = (0, 255, 255)
    
    cv2.putText(frame, "STATUS:", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(frame, current_state, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    # 3. Probability Bars
    y_start = 100
    for i, label in enumerate(EMOTION_LABELS):
        prob = predictions[i]
        bar_w = int(prob * (sidebar_w - 20))
        
        # Determine bar color based on emotion type
        bar_color = (200, 200, 200) # Neutral/Gray
        if label in ['Angry', 'Disgust', 'Fear', 'Sad']: bar_color = (0, 0, 255) # Red/Stress
        elif label in ['Happy', 'Surprise']: bar_color = (0, 255, 255) # Yellow/Distraction
        elif label == 'Neutral': bar_color = (0, 255, 0) # Green/Focus

        # Draw Bar
        cv2.rectangle(frame, (10, y_start), (10 + bar_w, y_start + 15), bar_color, -1)
        # Draw Label
        text = f"{label}: {int(prob*100)}%"
        cv2.putText(frame, text, (10, y_start - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        y_start += 40

def draw_lock_in_bar(frame, progress):
    """Draws a progress bar for the 10s lock-in at the bottom center."""
    h, w, _ = frame.shape
    bar_w = 400
    bar_h = 20
    x_start = (w - bar_w) // 2
    y_start = h - 40

    # Background
    cv2.rectangle(frame, (x_start, y_start), (x_start + bar_w, y_start + bar_h), (50, 50, 50), -1)

    # Fill
    fill_w = int(bar_w * progress)
    cv2.rectangle(frame, (x_start, y_start), (x_start + fill_w, y_start + bar_h), (0, 255, 255), -1)

    # Text
    cv2.putText(frame, "HOLD TO SWITCH MUSIC...", (x_start, y_start - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def draw_now_playing(frame, track_info):
    """
    Draws a floating 'Now Playing' pill at the top-right corner of the frame.
    track_info: {'track': str, 'artist': str}
    """
    if not track_info:
        return

    h, w, _ = frame.shape

    # Truncate long names so they don't overflow
    track = track_info['track']
    artist = track_info['artist']
    if len(track) > 28:  track  = track[:26] + '..'
    if len(artist) > 28: artist = artist[:26] + '..'

    line1 = f"\u266b  {track}"
    line2 = f"   {artist}"

    # Measure text sizes
    font       = cv2.FONT_HERSHEY_SIMPLEX
    scale1, t1 = 0.55, 2
    scale2, t2 = 0.45, 1
    (w1, h1), _ = cv2.getTextSize(line1, font, scale1, t1)
    (w2, h2), _ = cv2.getTextSize(line2, font, scale2, t2)

    box_w   = max(w1, w2) + 24
    box_h   = h1 + h2 + 24
    margin  = 12
    x_start = w - box_w - margin
    y_start = margin

    # Semi-transparent dark background pill
    overlay = frame.copy()
    cv2.rectangle(overlay, (x_start, y_start),
                  (x_start + box_w, y_start + box_h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    # Thin accent line on the left edge of pill (mood-colored would need state; use teal)
    cv2.rectangle(frame, (x_start, y_start),
                  (x_start + 3, y_start + box_h), (0, 210, 180), -1)

    # Text
    cv2.putText(frame, line1, (x_start + 10, y_start + h1 + 6),
                font, scale1, (255, 255, 255), t1, cv2.LINE_AA)
    cv2.putText(frame, line2, (x_start + 10, y_start + h1 + h2 + 14),
                font, scale2, (180, 180, 180), t2, cv2.LINE_AA)


from src.dj import AIDJ

def main():
    print("Loading AI Model...")
    try:
        model = load_model(MODEL_PATH)
        print("Model Loaded!")
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # Initialize DJ
    dj = AIDJ() # <--- New

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Webcam not found.")
        return

    # Use OpenCV DNN Face Detector (ResNet-SSD, handles tilted/partial faces)
    face_net = cv2.dnn.readNetFromCaffe(DNN_PROTO, DNN_MODEL)
    print("DNN Face Detector loaded!")

    stabilizer = FaceStabilizer(alpha=0.5)  # Instant movement
    inertia = MoodInertia(duration=45)      # 45s sticky mood
    emotion_window = deque(maxlen=SMOOTHING_WINDOW)
    
    # Defaults
    current_preds = np.zeros(7)
    current_state = "FOCUS"

    print("Running... Press 'q' to quit.")

    # Music Trigger Logic
    pending_state = "FOCUS"
    pending_start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame = cv2.flip(frame, 1)
        h_frame, w_frame, _ = frame.shape

        # Detect faces using OpenCV DNN (ResNet-SSD)
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                     (300, 300), (104.0, 177.0, 123.0))
        face_net.setInput(blob)
        detections = face_net.forward()

        mp_faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > DNN_CONFIDENCE:
                box = detections[0, 0, i, 3:7] * np.array([w_frame, h_frame, w_frame, h_frame])
                x1, y1, x2, y2 = box.astype(int)
                x, y = max(0, x1), max(0, y1)
                w, h = max(0, x2 - x1), max(0, y2 - y1)
                mp_faces.append((x, y, w, h))

        # Sort by area (largest = closest face)
        mp_faces = sorted(mp_faces, key=lambda f: f[2]*f[3], reverse=True)

        if len(mp_faces) > 0:
            (x, y, w, h) = mp_faces[0]

            # Smooth Coordinates
            sx, sy, sw, sh = stabilizer.update(x, y, w, h)

            # 1. Minimum Size Check (Avoid noisy distant faces)
            if w < 80 or h < 80:
                # Face too small, treat as No Face (Focus)
                current_preds = np.array([0, 0, 0, 0, 1.0, 0, 0]) # Force Neutral
            else:
                # Crop face ROI with padding, then run Mini-Xception emotion analysis
                try:
                    pad = 10
                    face_roi = frame[max(0, sy-pad):min(frame.shape[0], sy+sh+pad),
                                     max(0, sx-pad):min(frame.shape[1], sx+sw+pad)]
                    processed = preprocess_face(face_roi)
                    if processed is not None:
                        preds = model.predict(processed, verbose=0)[0]
                        emotion_window.append(preds)
                        current_preds = np.mean(emotion_window, axis=0)
                except Exception:
                    pass

            # Draw Box
            color = (0, 255, 0)
            if current_state == "STRESS": color = (0, 0, 255)
            elif current_state == "HAPPY": color = (255, 0, 255) # Magenta for Happy
            elif current_state == "DISTRACTION": color = (0, 255, 255)
            
            # --- Added Text Label ---
            # Show "Angry (80%)" instead of just the color
            top_emotion_idx = np.argmax(current_preds)
            emotion_text = f"{EMOTION_LABELS[top_emotion_idx]} ({int(current_preds[top_emotion_idx]*100)}%)"
            
            # Draw Box & Text
            cv2.rectangle(frame, (sx, sy), (sx+sw, sy+sh), color, 2)
            cv2.putText(frame, emotion_text, (sx, sy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # Show Lock Status if Inertia is holding the mood
            if inertia.active_mood and inertia.active_mood == current_state:
                 remaining_time = int(inertia.duration - (time.time() - inertia.start_time))
                 cv2.putText(frame, f"LOCKED ({remaining_time}s)", (sx, sy-40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        else:
            # NO FACES DETECTED
            # Assume Neutral / Focus
            current_preds = np.array([0, 0, 0, 0, 1.0, 0, 0])  # Force Neutral
        
        # -----------------------------------------------------------
        # GLOBAL LOGIC (Runs even if no face)
        # -----------------------------------------------------------

        # --- Confidence-Gated Classification ---
        # Requires BOTH a minimum confidence AND a gap over the runner-up.
        # Prevents flickering when two emotions score similarly.

        sorted_preds = np.sort(current_preds)[::-1]   # descending
        dominant_idx = np.argmax(current_preds)
        dominant_emotion = EMOTION_LABELS[dominant_idx]
        confidence    = sorted_preds[0]                # top score
        runner_up     = sorted_preds[1]                # 2nd highest
        gap           = confidence - runner_up         # margin over runner-up

        # Map Emotion -> System State (with per-state thresholds)
        if dominant_emotion == 'Neutral':
            # Neutral only needs moderate confidence; it's the "default" state
            if confidence > 0.30 and gap > 0.10:
                current_state = "FOCUS"
            # else: keep previous state (don't thrash on weak neutrals)

        elif dominant_emotion == 'Happy':
            # Happy needs clear confidence — a subtle smile shouldn't trigger HAPPY
            if confidence > 0.40 and gap > 0.15:
                current_state = "HAPPY"

        elif dominant_emotion in ['Angry', 'Disgust', 'Fear', 'Sad']:
            # Stress needs the highest bar — false positives ruin the mood
            if confidence > 0.45 and gap > 0.15:
                current_state = "STRESS"
            elif confidence <= 0.30:
                current_state = "FOCUS"  # Weak signal -> bias toward focus
            # else: ambiguous, keep current state

        elif dominant_emotion == 'Surprise':
            if confidence > 0.35 and gap > 0.12:
                current_state = "DISTRACTION"

        # --- Apply Mood Inertia (Sticky Logic) ---
        # Even if face says FOCUS, if we were recently HAPPY/STRESS, stay there.
        current_state = inertia.update(current_state)
        # -----------------------------------------

        # --- DJ TRIGGER LOGIC (5s Sustain) ---
        # Note: Because inertia overrides 'current_state' instantly, 
        # the user doesn't need to HOLD the face for 5s continuously if inertia kicks in. 
        # But the FIRST trigger still needs 5s of consistent detection.
        
        if current_state == pending_state:
            # User is holding the state... check how long
            duration = time.time() - pending_start_time
            
            # Update visual bar logic relies on pending_state
            if duration > 5.0:
                # Held for 5s! Send to DJ.
                dj.update_state(current_state)
        else:
            # State changed! Reset timer.
            pending_state = current_state
            pending_start_time = time.time()

        if len(mp_faces) > 0:
            pass  # Face box already drawn above

        # Draw HUD (Always visible)
        draw_hud(frame, current_preds, current_state)

        # Draw Now Playing overlay (top-right)
        draw_now_playing(frame, dj.now_playing)

        # Draw Lock-In Bar if waiting for music switch
        if dj.state != pending_state:
             elapsed = time.time() - pending_start_time
             progress = min(elapsed / 5.0, 1.0)
             if progress < 1.0:
                 draw_lock_in_bar(frame, progress)

        cv2.imshow('Focus Guard AI (Ultra Smooth)', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'): 
            break
        elif key == ord('s'):
            timestamp = int(time.time())
            filename = f"screenshots/focus_guard_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            print(f"📸 Screenshot saved: {filename}")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
