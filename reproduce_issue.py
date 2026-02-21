from src.spotify_client import SpotifyClient
import sys

def test_search():
    client = SpotifyClient()
    if not client.sp:
        print("Spotify not connected")
        return

    queries = ["Bollywood Unplugged", "Arijit Singh"]
    
    for q in queries:
        print(f"Testing query: {q} with limit=20")
        try:
            # Isolate the raw spotipy call usually made in search_playlist
            # client.search_playlist(q, limit=20, random_pick=True)
            
            # Let's try calling search_playlist directly which does the logic
            uri = client.search_playlist(q, limit=20, random_pick=True)
            print(f"Result: {uri}")
        except Exception as e:
            print(f"Failed with limit=20: {e}")

        print(f"Testing query: {q} with limit=10")
        try:
             uri = client.search_playlist(q, limit=10, random_pick=True)
             print(f"Result: {uri}")
        except Exception as e:
             print(f"Failed with limit=10: {e}")

if __name__ == "__main__":
    test_search()
