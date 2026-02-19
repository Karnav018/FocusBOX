
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
    Default duration: 3 minutes (180s).
    """
    def __init__(self, duration=180):
        self.active_mood = None
        self.start_time = 0
        self.duration = duration
        self.focus_timer_start = None  # To track how long we've been engaging in "Focus" (Neutral)

    def update(self, current_detected_state):
        # 1. If we detect a STRONG emotion, lock it in.
        if current_detected_state in ["HAPPY", "STRESS"]:
            self.focus_timer_start = None # Reset focus timer if we see strong emotion
            
            # If it's different from current lock, switch immediately (Override)
            if current_detected_state != self.active_mood:
                self.active_mood = current_detected_state
                self.start_time = time.time()
                return current_detected_state
            else:
                return self.active_mood

        # 2. If Locked, check logic based on Mood Type
        if self.active_mood:
            # Check total duration first
            if time.time() - self.start_time > self.duration:
                self.active_mood = None # Lock expired
                return current_detected_state

            # Special Handling for "STRESS" -> Break lock if Neutral for > 12s
            if self.active_mood == "STRESS" and current_detected_state == "FOCUS":
                if self.focus_timer_start is None:
                     self.focus_timer_start = time.time()
                
                # If we've been Focus for > 12 seconds, break the Stress lock
                if time.time() - self.focus_timer_start > 12:
                     self.active_mood = None
                     return "FOCUS"
                
                return "STRESS" # Still locked, but counting down...

            # Special Handling for "HAPPY" -> Ignore Neutral completely (Keep the vibe)
            if self.active_mood == "HAPPY":
                 return "HAPPY"

            # Default fallback
            return self.active_mood

        # 3. No lock? Return actual state
        return current_detected_state

def preprocess_face(face_img):
    """
    Preprocesses a face image for the Mini-Xception model.
    """
    try:
        # 1. Grayscale
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        
        # 2. Histogram Equalization (Improves contrast)
        gray = cv2.equalizeHist(gray)
        
        # 3. Resize to 48x48
        resized = cv2.resize(gray, (IMG_WIDTH, IMG_HEIGHT))
        
        # 4. Normalize [0, 1]
        normalized = resized / 255.0
        
        # 5. Reshape
        reshaped = np.reshape(normalized, (1, IMG_HEIGHT, IMG_WIDTH, 1))
        return reshaped
    except Exception as e:
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

from src.dj import AIDJ

def main():
    print("Loading AI Model...")
    try:
        model = load_model(MODEL_PATH)
        print("Model Loaded!")
    except Exception as e:
        print(f"Error: {e}")
        return

    # Initialize DJ
    dj = AIDJ() # <--- New

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Webcam not found.")
        return

    # Use Haar Cascade (Fastest on CPU)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    stabilizer = FaceStabilizer(alpha=0.5) # Instant movement
    inertia = MoodInertia(duration=180)    # 3 mins sticky mood
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            # Find largest face (closest to camera)
            faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
            (x, y, w, h) = faces[0]

            # Smooth Coordinates
            sx, sy, sw, sh = stabilizer.update(x, y, w, h)

            # 1. Minimum Size Check (Avoid noisy distant faces)
            if w < 80 or h < 80:
                # Face too small, treat as No Face (Focus)
                current_preds = np.array([0, 0, 0, 0, 1.0, 0, 0]) # Force Neutral
            else:
                # Predict
                face_roi = frame[0:frame.shape[0], 0:frame.shape[1]] # Safe fallback
                try:
                    # Add padding for better recognition context
                    pad = 10
                    face_roi = frame[max(0, sy-pad):min(frame.shape[0], sy+sh+pad), 
                                     max(0, sx-pad):min(frame.shape[1], sx+sw+pad)]
                    
                    processed = preprocess_face(face_roi)
                    if processed is not None:
                        preds = model.predict(processed, verbose=0)[0]
                        emotion_window.append(preds)
                        current_preds = np.mean(emotion_window, axis=0)
                except:
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
            current_preds = np.array([0, 0, 0, 0, 1.0, 0, 0]) # Force Neutral
        
        # -----------------------------------------------------------
        # GLOBAL LOGIC (Runs even if no face)
        # -----------------------------------------------------------

        # --- Industry Standard Classification Logic ---
        # Instead of arbitrary thresholds, we use the "Dominant Emotion" (Argmax).
        # This ensures that if 'Neutral' is the highest probability, we respect it.
        
        dominant_idx = np.argmax(current_preds)
        dominant_emotion = EMOTION_LABELS[dominant_idx]
        confidence = current_preds[dominant_idx]

        # Map Emotion -> System State
        if dominant_emotion == 'Neutral':
            current_state = "FOCUS"
        elif dominant_emotion == 'Happy':
            current_state = "HAPPY"
        elif dominant_emotion in ['Angry', 'Disgust', 'Fear', 'Sad']:
            # Only trigger stress if fairly confident, otherwise bias towards Focus (Neutral)
            if confidence > 0.4:
                current_state = "STRESS"
            else:
                current_state = "FOCUS"
        elif dominant_emotion == 'Surprise':
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
        # --------------------------------------

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

        if len(faces) > 0:
            # ... (face detection code) ...
            pass # Keep existing logic

        # Draw HUD (Always visible)
        draw_hud(frame, current_preds, current_state)
        
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
