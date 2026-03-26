
import time
import os
import random
import threading
import typing
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
        self.target_state = "FOCUS"
        self._switch_thread: typing.Optional[threading.Thread] = None
        self.last_switch_time = time.time()
        self.cooldown = 20  # Base cooldown; opposite-mood switches use 10s (see _transition_worker)

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
        self.failed_queries = set()  # optimization: don't retry known bad queries

        # Now Playing cache — updated every 5s in background (so main loop has zero latency)
        self.now_playing: typing.Optional[typing.Dict[str, str]] = None
        _poll = threading.Thread(target=self._track_poller, daemon=True)
        _poll.start()

    def _track_poller(self):
        """Background thread: refreshes now_playing every 5s with zero impact on the main loop."""
        while True:
            if self.use_spotify:
                self.now_playing = self.spotify.get_current_track()
            time.sleep(5)

    def update_state(self, new_state):
        """
        Called every frame by main.py.
        Registers the target mood and starts the transition worker if needed.
        """
        if new_state == self.target_state:
            return # No change in target mood
            
        print(f"🎯 Target Mood Updated: {self.target_state} -> {new_state}")
        self.target_state = new_state
        
        # Start transition thread if not already running
        start_thread = False
        if self._switch_thread is None:
            start_thread = True
        elif hasattr(self._switch_thread, "is_alive") and not self._switch_thread.is_alive():
            start_thread = True
            
        if start_thread:
            new_thread = threading.Thread(target=self._transition_worker, daemon=True)
            self._switch_thread = new_thread
            new_thread.start()

    def _transition_worker(self):
        """
        Runs in background to wait for the optimal time to switch tracks.
        Waits until last 15s of current song, then switches.
        """
        while self.target_state != self.state:
            target = self.target_state

            # Cooldown logic:
            # - Switching to a completely different mood (e.g. HAPPY -> STRESS): short 10s cooldown
            # - Switching within the same "vibe" (e.g. FOCUS -> FOCUS after inertia): normal 20s
            # This prevents the long HAPPY cooldown from blocking urgent mood changes.
            opposite_switch = (self.state == "HAPPY" and target == "STRESS") or \
                              (self.state == "STRESS" and target == "HAPPY")
            required_cooldown = 10 if opposite_switch else self.cooldown

            if time.time() - self.last_switch_time < required_cooldown:
                time.sleep(2)
                continue

            # Check Spotify remaining time to delay transition
            if self.use_spotify:
                remaining = self.spotify.get_remaining_time()
                if remaining is not None and remaining > 15.0:
                    # Sleep dynamically but check frequently in case target changes
                    sleep_time = min(remaining - 15.0, 5.0)
                    time.sleep(sleep_time)
                    continue

            # If target changed during our sleep, the loop will catch it
            if target != self.target_state:
                continue

            print(f"🔄 Mood Switch: {self.state} -> {target}")
            self.state = target
            self.last_switch_time = time.time()
            self.trigger_music(target)

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

    def _smart_play(self, mood_name, queries, fallback_key):
        """
        Tries to play ANY playlist from the list. 
        Retries if one fails. Falls back to local if all fail.
        """
        print(f"🎵 {mood_name}: Searching for the perfect track...")
        
        played_spotify = False
        if self.use_spotify:
            # 1. Shuffle to randomize
            random.shuffle(queries)
            
            # 2. Try each query until one works
            for query in queries:
                if query in self.failed_queries:
                    continue # Skip known bad ones
                
                uri = self._get_playlist(query)
                if uri:
                    self._transition_to(uri)
                    played_spotify = True
                    break # Success! Stop searching.
                else:
                    print(f"⚠️ Playlist '{query}' not found. Retrying...")
                    self.failed_queries.add(query) # Remember this failed
            
            if not played_spotify:
                print(f"❌ Could not find ANY valid {mood_name} playlist on Spotify.")

        # 3. Fallback
        if not played_spotify:
            print("Using Local Fallback.")
            self.play_local_file(self.sounds[fallback_key])


    def play_happy_flow(self):
        # HAPPY = Gujarati Romantic * energetic, no garba and bhajan.
        queries = ["Gujarati Romantic Hits 2026", "Gujarati Urban Pop", "Jigardan Gadhavi", "Priya Saraiya", "Gujarati Love Anthems"]
        self._smart_play("HAPPY VIBES", queries, "lofi")

    def play_rescue_protocol(self):
        # RESCUE = Bollywood (Soothing/Sad/Trending/New/Recently release movies song)
        queries = ["Latest Bollywood Sad 2026", "Arijit Singh Emotional Hits", "Bollywood Acoustic Melodies", "B Praak Sad Songs", "Hindi Lofi Revibe"]
        self._smart_play("RESCUE PROTOCOL", queries, "rain")

    def play_focus_flow(self):
        # FOCUS = Pop/Trending/New/Recently release movies song/espessially bollywood
        queries = ["Trending Bollywood 2026", "Fresh Hindi Pop", "Bollywood Chill Hits", "New Release Bollywood", "Indian Indie Pop Focus"]
        self._smart_play("FOCUS FLOW", queries, "lofi")
        
    # def play_happy_flow(self):
    #     # HAPPY = Gujarati Romantic
    #     queries = ["Gujarati Romantic Hits", "Gujarati Love Songs", "Kinjal Dave", "Geeta Rabari", "Gujarati Wedding Songs"]
    #     self._smart_play("HAPPY VIBES", queries, "lofi")

    # def play_rescue_protocol(self):
    #     # RESCUE = Bollywood (Soothing/Sad/Acoustic)
    #     queries = ["Bollywood Lofi", "Bollywood Acoustic", "Sad Hindi Songs", "Arijit Singh", "Bollywood Unplugged"]
    #     self._smart_play("RESCUE PROTOCOL", queries, "rain")

    # def play_focus_flow(self):
    #     # FOCUS = Pop/Acoustic with Vocals
    #     queries = ["Focus Flow", "Chill Pop Hits", "Acoustic Pop Focus", "Deep Focus with Vocals", "Soft Pop Study"]
    #     self._smart_play("FOCUS FLOW", queries, "lofi")
            
    def _get_playlist(self, query):
        """Helper to find/cache playlists."""
        if query in self.playlist_cache:
            return self.playlist_cache[query]
        
        print(f"🔍 Searching Spotify for: '{query}'...")
        # DEEP DIVE: Fetch top 10 and pick random one for variety (Limit=10 to avoid 400 Error)
        uri = self.spotify.search_playlist(query, limit=10, random_pick=True)
        if uri:
            self.playlist_cache[query] = uri
            return uri
        return None

    def _transition_to(self, playlist_uri):
        """Smoothly transitions to a new playlist."""
        if not playlist_uri: return

        # Enable Shuffle for variety
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
