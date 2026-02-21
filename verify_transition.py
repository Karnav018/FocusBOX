import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.dj import AIDJ

def main():
    dj = AIDJ()
    # Mocking cooldown so it triggers immediately
    dj.cooldown = 0
    dj.last_switch_time = 0
    
    print("DJ Initialized. Current state:", dj.state)
    
    # Simulate a mood change
    print("Simulating mood change to STRESS")
    dj.update_state("STRESS")
    
    print("Waiting for thread to process transition...", dj._switch_thread)
    
    for _ in range(15):
        print(f"Target: {dj.target_state}, State: {dj.state}")
        time.sleep(1)
        if dj.state == "STRESS":
            print("✅ Successfully transitioned state to STRESS in background thread!")
            break
            
if __name__ == "__main__":
    main()
