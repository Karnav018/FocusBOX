
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import time
import random

# Load environment variables if .env exists
load_dotenv()

class SpotifyClient:
    def __init__(self, client_id=None, client_secret=None):
        """
        Initializes the Spotify Client.
        Requires Client ID and Secret to be passed or set as env vars:
        SPOTIPY_CLIENT_ID
        SPOTIPY_CLIENT_SECRET
        """
        self.client_id = client_id or os.getenv("SPOTIPY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIPY_CLIENT_SECRET")
        self.redirect_uri = "http://127.0.0.1:8888/callback"
        
        self.sp = None
        
        if not self.client_id or not self.client_secret:
            print("⚠️ Spotify Credentials Missing! Music control will be disabled.")
            return

        try:
            # Scope: What we need permission for
            scope = "user-modify-playback-state,user-read-playback-state"
            
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=scope
            ))
            
            # Test connection
            user = self.sp.current_user()
            print(f"✅ Connected to Spotify as: {user['display_name']}")
            
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            self.sp = None

    def play_track(self, uri=None, uris=None):
        """Plays a specific track/playlist URI or a list of track URIs."""
        if not self.sp: return
        try:
            # 1. Check for active device
            devices = self.sp.devices()
            if not devices or not devices['devices']:
                print("⚠️ No Spotify devices found! Please OPEN Spotify on your computer/phone.")
                return
                
            active_device = next((d for d in devices['devices'] if d['is_active']), None)
            device_id = active_device['id'] if active_device else devices['devices'][0]['id']
            
            # 2. If no device is explicitly active, wake the first one up
            if not active_device:
                print(f"💤 Waking up device: {devices['devices'][0]['name']}...")
                self.sp.transfer_playback(device_id=device_id, force_play=False)
                time.sleep(0.5) # Small delay for the cloud to sync
            
            # 3. Play
            if uris:
                self.sp.start_playback(device_id=device_id, uris=uris)
            elif uri:
                self.sp.start_playback(device_id=device_id, context_uri=uri)
            
        except Exception as e:
            print(f"Error playing track: {e}")

    def set_volume(self, volume):
        """Sets the volume (0-100)."""
        if not self.sp: return False
        try:
            self.sp.volume(volume)
            return True
        except Exception as e:
            # Volume control might be restricted on some devices (mobile)
            # print(f"⚠️ Could not set volume: {e}") # Silenced to avoid spam
            return False

    def get_current_track(self):
        """Returns {'track': str, 'artist': str} for the currently playing song, or None."""
        if not self.sp: return None
        try:
            playback = self.sp.current_playback()
            if playback and playback.get('is_playing') and playback.get('item'):
                item = playback['item']
                track_name = item.get('name', 'Unknown')
                artists = item.get('artists', [])
                artist_name = artists[0]['name'] if artists else 'Unknown'
                return {'track': track_name, 'artist': artist_name}
        except Exception:
            pass
        return None

    def get_remaining_time(self):
        """Returns the remaining time of the current track in seconds. None if not playing."""
        if not self.sp: return None
        try:
            playback = self.sp.current_playback()
            if playback and playback.get('is_playing') and playback.get('item'):
                progress = playback['progress_ms']
                duration = playback['item']['duration_ms']
                return (duration - progress) / 1000.0
        except Exception as e:
            # Silently ignore to avoid spamming logs
            pass
        return None

    def search_playlist(self, query, limit=1, random_pick=False):
        """
        Searches for playlists.
        If random_pick is True, picks a random one from the top 'limit' results.
        """
        if not self.sp: return None
        try:
            results = self.sp.search(q=query, type='playlist', limit=limit)
            # Check if results exist and have items
            if results and 'playlists' in results and results['playlists'] and results['playlists']['items']:
                items = [i for i in results['playlists']['items'] if i is not None]
                
                if not items: return None

                if random_pick:
                    # Pick a random one from the results
                    choice = random.choice(items)
                    if choice and 'uri' in choice:
                        print(f"🎲 Randomly picked: '{choice.get('name', 'Unknown')}' from top {len(items)} results.")
                        return choice['uri']
                else:
                    # Return the top result
                    if items[0] and 'uri' in items[0]:
                        return items[0]['uri']
                    
        except Exception as e:
            print(f"Error searching playlist: {e}")
        return None

    def search_item(self, query, type='artist'):
        """
        Searches for an item (artist/track) and returns its ID/URI.
        """
        if not self.sp: return None
        try:
            results = self.sp.search(q=query, type=type, limit=1)
            items = results[type + 's']['items']
            if items:
                return items[0]['id']
        except Exception as e:
            print(f"Error searching for {type} '{query}': {e}")
        return None

    def get_recommendations(self, seed_artists=None, seed_tracks=None, limit=20, **kwargs):
        """
        Get Recommendations based on seeds and audio features.
        kwargs can be target_valence, target_energy, etc.
        """
        if not self.sp: return []
        try:
            # Spotify allows max 5 seeds total
            seeds_count = (len(seed_artists) if seed_artists else 0) + (len(seed_tracks) if seed_tracks else 0)
            if seeds_count > 5:
                print("⚠️ Too many seeds! Truncating to 5.")
                if seed_artists: seed_artists = seed_artists[:5]
                if seed_tracks: seed_tracks = seed_tracks[:5 - len(seed_artists)]

            results = self.sp.recommendations(seed_artists=seed_artists, seed_tracks=seed_tracks, limit=limit, **kwargs)
            if results and 'tracks' in results:
                return [track['uri'] for track in results['tracks']]
        except Exception as e:
            print(f"Error getting recommendations: {e}")
        return []

    def get_tracks_by_search(self, query, limit=5, offset=0, random_pick=True):
        """
        Searches for tracks by a query (e.g. Artist Name) and returns their URIs.
        If random_pick is True, it shuffles the results to avoid always playing the top hits.
        """
        if not self.sp: return []
        try:
            # Search for tracks
            results = self.sp.search(q=query, type='track', limit=limit, offset=offset)
            if results and 'tracks' in results and results['tracks']['items']:
                items = results['tracks']['items']
                uris = [item['uri'] for item in items]
                
                if random_pick:
                    random.shuffle(uris)
                    
                print(f"🔎 Found {len(uris)} tracks for '{query}' (Offset: {offset})")
                return uris
        except Exception as e:
            print(f"Error searching tracks for '{query}': {e}")
        return []

    def pause(self):
        """Pauses playback."""
        if not self.sp: return
        try:
            self.sp.pause_playback()
        except Exception as e:
            print(f"Error pausing: {e}")

    def set_shuffle(self, state):
        """Toggles shuffle mode (True/False)."""
        if not self.sp: return
        try:
            self.sp.shuffle(state)
        except Exception as e:
            print(f"Error setting shuffle: {e}")

if __name__ == "__main__":
    # Test Run
    print("Testing Spotify Client...")
    client = SpotifyClient()
    if client.sp:
        print("✅ Client Ready!")
    else:
        print("❌ Client Failed to Initialize.")
