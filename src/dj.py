
import time
import os
import time
import os
import random
import threading
try:
    import pygame
except ImportError:
    print("Pygame not found. Audio will be disabled.")
    pygame = None

from src.spotify_client import SpotifyClient

class AIDJ:
    """
    The Brain that decides WHAT to play based on the User's State.
    """
    def __init__(self):
        self.state = "FOCUS"
        self.last_switch_time = time.time()
        self.cooldown = 30  # Increased to 30s for stability
        
        # Initialize Audio Engines
        self.spotify = SpotifyClient()
        self.use_spotify = self.spotify.sp is not None
        
        if pygame:
            pygame.mixer.init()
            
        # Assets (Placeholders for now)
        self.sounds = {
            "rain": "src/assets/rain.wav",
            "lofi": "src/assets/lofi.wav"
        }
        
        # Cache for found playlists so we don't search every time
        self.playlist_cache = {}

    def update_state(self, new_state):
        """
        Called every frame by main.py.
        Decides if we need to switch the music.
        """
        if new_state == self.state:
            return # No change
            
        # Check Cooldown (Dynamic)
        # If currently HAPPY, hold for 90s. Else default 30s.
        required_cooldown = 90 if self.state == "HAPPY" else self.cooldown
        
        if time.time() - self.last_switch_time < required_cooldown:
            return

        print(f"🔄 Mood Switch: {self.state} -> {new_state}")
        self.state = new_state
        self.last_switch_time = time.time()
        
        # Run music trigger in background thread to avoid freezing video
        threading.Thread(target=self.trigger_music, args=(new_state,), daemon=True).start()

    def trigger_music(self, state):
        """
        The Logic: Which playlist to play?
        """
        if state == "STRESS":
            self.play_rescue_protocol()
        elif state == "FOCUS":
            self.play_focus_flow()
        elif state == "HAPPY":
            self.play_happy_flow()
        elif state == "DISTRACTION":
            self.pause_audio()

    # ... (keep existing methods) ...

    def play_happy_flow(self):
        print("🥰 HAPPY VIBES: Switching to Gujarati Romantic...")
        played_spotify = False
        if self.use_spotify:
            # Search for "Gujarati Romantic"
            uri = self._get_playlist("Gujarati Romantic Hits") 
            if uri:
                self._transition_to(uri)
                played_spotify = True
            else:
                print("❌ Could not find Gujarati playlist. Falling back to local.")
        
        if not played_spotify:
            # Fallback for Happy? Maybe Lofi is fine, or Rain. Let's use Lofi.
            self.play_local_file(self.sounds["lofi"])

    def _get_playlist(self, query):
        """Helper to find/cache playlists."""
        if query in self.playlist_cache:
            return self.playlist_cache[query]
        
        print(f"🔍 Searching Spotify for: '{query}'...")
        uri = self.spotify.search_playlist(query)
        if uri:
            self.playlist_cache[query] = uri
            return uri
        return None

    def _transition_to(self, playlist_uri):
        """Smoothly transitions to a new playlist."""
        if not playlist_uri: return

        # Enable Shuffle for variety
        # self.spotify.set_shuffle(True) # Some devices might not support this, but good to try.
        # Actually, let's just try to set it but silence errors inside the method if it fails.
        self.spotify.set_shuffle(True)

        print("🎚️ Fading Out...")
        # Try one volume command; if it fails, skip the whole fade sequence
        if not self.spotify.set_volume(70):
             print("⚠️ Volume control unavailable. Skipping fade.")
        else:
            for v in range(60, 0, -10):
                self.spotify.set_volume(v)
                time.sleep(0.1)
            
        print("▶️ Playing New Track...")
        self.spotify.play_track(playlist_uri)
        
        print("🎚️ Fading In...")
        # Only try fade in if we know volume control works (or checking again is fine)
        if self.spotify.set_volume(10):
            for v in range(20, 80, 10):
                self.spotify.set_volume(v)
                time.sleep(0.1)

    def play_rescue_protocol(self):
        # RESCUE = Bollywood (Soothing/Sad/Acoustic)
        queries = ["Bollywood Lofi", "Bollywood Acoustic", "Sad Hindi Songs", "Arijit Singh", "Bollywood Unplugged"]
        query = random.choice(queries)
        
        print(f"🚑 RESCUE PROTOCOL: Switching to Bollywood ({query})...")
        played_spotify = False
        if self.use_spotify:
            uri = self._get_playlist(query)
            if uri:
                self._transition_to(uri)
                played_spotify = True
            else:
                print("❌ Could not find Bollywood playlist. Falling back to local.")
        
        if not played_spotify:
            self.play_local_file(self.sounds["rain"])

    def play_focus_flow(self):
        # FOCUS = Hollywood (Scores/Instrumental)
        queries = ["Hollywood Soundtracks", "Hans Zimmer Essentials", "Movie Scores for Study", "Epic Soundtracks", "Interstellar Soundtrack"]
        query = random.choice(queries)
        
        print(f"🧠 FOCUS FLOW: Switching to Hollywood ({query})...")
        played_spotify = False
        if self.use_spotify:
            uri = self._get_playlist(query) 
            if uri:
                self._transition_to(uri)
                played_spotify = True
            else:
                print("❌ Could not find Hollywood playlist. Falling back to local.")
        
        if not played_spotify:
            self.play_local_file(self.sounds["lofi"])
            
    def play_happy_flow(self):
        # HAPPY = Gujarati Romantic (as requested)
        queries = ["Gujarati Romantic Hits", "Gujarati Love Songs", "Kinjal Dave", "Geeta Rabari", "Gujarati Wedding Songs"]
        query = random.choice(queries)

        print(f"🥰 HAPPY VIBES: Switching to Gujarati ({query})...")
        played_spotify = False
        if self.use_spotify:
            uri = self._get_playlist(query) 
            if uri:
                self._transition_to(uri)
                played_spotify = True
            else:
                print("❌ Could not find Gujarati playlist. Falling back to local.")
        
        if not played_spotify:
            self.play_local_file(self.sounds["lofi"])
            
    def pause_audio(self):
        print("⏸️ DISTRACTION DETECTED: Pausing Music.")
        if self.use_spotify:
            self.spotify.pause()
        elif pygame:
            pygame.mixer.music.pause()

    def play_local_file(self, filepath):
        if not pygame: return
        
        # Check if file exists
        if not os.path.exists(filepath):
            print(f"⚠️ Audio file not found: {filepath}")
            # Generate a beep? OR just silent log
            return
            
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play(-1) # Loop forever
        except Exception as e:
            print(f"Error playing local file: {e}")
