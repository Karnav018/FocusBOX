import time
from src.spotify_client import SpotifyClient

def test_dynamic_recommendations():
    print("Initializing Spotify Client...")
    client = SpotifyClient()
    if not client.sp:
        print("❌ Spotify Client failed to initialize.")
        return

    queries = ["Arijit Singh", "Mohit Chauhan"]
    print(f"Testing with queries: {queries}")

    # Test Searching
    print("\n--- Testing Search ---")
    seed_artists = []
    for q in queries:
        artist_id = client.search_item(q, type='artist')
        if artist_id:
            print(f"✅ Found artist ID for '{q}': {artist_id}")
            seed_artists.append(artist_id)
        else:
            print(f"❌ Could not find artist ID for '{q}'")

    if not seed_artists:
        print("❌ No seeds found. Aborting.")
        return

    # Test Recommendations
    print("\n--- Testing Recommendations ---")
    try:
        recommendations = client.get_recommendations(seed_artists=seed_artists, limit=5, target_valence=0.5, target_energy=0.5)
        if recommendations:
            print(f"✅ Got {len(recommendations)} recommendations:")
            for uri in recommendations:
                print(f"  - {uri}")
        else:
            print("❌ No recommendations returned.")
    except Exception as e:
        print(f"❌ Error getting recommendations: {e}")

if __name__ == "__main__":
    test_dynamic_recommendations()
