#!/usr/bin/env python3
"""
Test script for AI DJ recommendation system
Run with: ./venv/bin/python test_dj_recommendation.py
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.dj import AIDJ, MOOD_PROFILES

def test_spotify_connection():
    """Test if Spotify connection is working"""
    print("=" * 50)
    print("🔧 TESTING SPOTIFY CONNECTION")
    print("=" * 50)
    
    dj = AIDJ()
    
    if dj.use_spotify:
        print("✅ Spotify connection successful!")
        return dj
    else:
        print("❌ Spotify connection failed!")
        print("\nTroubleshooting tips:")
        print("1. Check if .env file exists with SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET")
        print("2. Verify your Spotify credentials are correct")
        print("3. Make sure you've accepted the app permissions in browser")
        return None

def test_mood_search(dj, mood):
    """Test search for a specific mood using playlists"""
    print("\n" + "=" * 50)
    print(f"🎵 TESTING MOOD: {mood}")
    print("=" * 50)
    
    if mood not in MOOD_PROFILES:
        print(f"❌ Mood '{mood}' not found in profiles!")
        return
    
    profile = MOOD_PROFILES[mood]
    print(f"Energy target: {profile.get('energy', 'N/A')}")
    print(f"Dance target: {profile.get('dance', 'N/A')}")
    print(f"Search queries: {profile['queries'][:3]}...")  # Show first 3
    
    # Test playlist search
    for query in profile['queries'][:2]:  # Test first 2 queries
        print(f"\n🔍 Searching Playlist: '{query}'")
        playlist_uri = dj.spotify.search_playlist(
            query=query,
            limit=5,
            random_pick=True
        )
        
        if playlist_uri:
            print(f"   ✅ Found playlist: {playlist_uri}")
        else:
            print(f"   ❌ No playlist found for '{query}'")

def test_recommendation_pipeline():
    """Test the full recommendation pipeline"""
    print("\n" + "=" * 50)
    print("🔄 TESTING FULL RECOMMENDATION PIPELINE")
    print("=" * 50)
    
    dj = AIDJ()
    if not dj.use_spotify:
        print("❌ Cannot test pipeline without Spotify connection")
        return
    
    # Test each mood
    moods = ["FOCUS", "HAPPY", "STRESS", "DISTRACTION"]
    
    for mood in moods:
        print(f"\n🎯 Testing {mood} pipeline...")
        
        # Get profile
        profile = MOOD_PROFILES[mood]
        
        # Simulate recommend_and_play logic (Deep Dive version)
        queries = profile["queries"]
        query = random.choice(queries)
        print(f"   Picked query: '{query}'")
        
        playlist_uri = dj.spotify.search_playlist(
            query=query,
            limit=10,
            random_pick=True
        )
        
        if playlist_uri:
            print(f"   ✅ Found playlist: {playlist_uri} for {mood}")
        else:
            print(f"   ⚠️ No playlist found for {mood}")
        
        # Small delay
        time.sleep(1)

def main():
    """Main test function"""
    print("🎵 AI DJ RECOMMENDATION SYSTEM TEST (DEEP DIVE)")
    print("Version: 2.0 (Playlist Mode)")
    print()
    
    # Test 1: Spotify Connection
    dj = test_spotify_connection()
    if not dj:
        sys.exit(1)
    
    # Test 2: Test each mood search
    print("\n" + "=" * 50)
    print("🔍 TESTING INDIVIDUAL MOOD SEARCHES")
    print("=" * 50)
    
    moods_to_test = ["FOCUS", "HAPPY"]  # Test FOCUS and HAPPY first
    for mood in moods_to_test:
        test_mood_search(dj, mood)
        time.sleep(1)  # Be nice to Spotify API
    
    # Test 3: Full pipeline
    test_recommendation_pipeline()
    
    # Test 4: Quick play test (optional - will actually play music)
    print("\n" + "=" * 50)
    print("▶️  QUICK PLAY TEST (Optional)")
    print("=" * 50)
    print("Do you want to test actual playback? (y/n): ", end='')
    
    # Uncomment below if you want interactive playback test
    """
    response = input().lower()
    if response == 'y':
        print("\n🎧 Testing playback with FOCUS mood...")
        dj.trigger_music("FOCUS")
        print("✅ Playback started! Check your Spotify device.")
    """
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 50)

if __name__ == "__main__":
    import random
    import time
    main()