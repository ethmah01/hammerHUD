import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory_reader import GameStateTracker

def test_capacity_detection():
    tracker = GameStateTracker()
    print(f"Initial capacity: {tracker.table_capacity}")
    
    # Test case 1: TCO_ANTE_INFO_ALL with 9 elements but seats 7-9 are empty
    msg1 = {
        'pid': 'TCO_ANTE_INFO_ALL',
        'flag': [1, 1, 1, 1, 1, 1, 0, 0, 0], # 6 active players, 3 empty slots
        'ante': [5]*9,
        'account': [1000]*9
    }
    tracker.process_messages([msg1])
    print(f"Capacity after 9-slot msg with empty high seats: {tracker.table_capacity} (Expected: 6)")
    
    # Test case 2: TCO_ANTE_INFO_ALL with 9 elements and seat 7 is active
    msg2 = {
        'pid': 'TCO_ANTE_INFO_ALL',
        'flag': [1, 1, 1, 1, 1, 1, 1, 0, 0], # 7 active players
        'ante': [5]*9,
        'account': [1000]*9
    }
    tracker.process_messages([msg2])
    print(f"Capacity after 9-slot msg with active seat 7: {tracker.table_capacity} (Expected: 9)")
    
    # Test case 3: Switch back to 6-max (e.g. new game)
    msg3 = {
        'pid': 'TCO_ANTE_INFO_ALL',
        'flag': [1, 1, 1, 1, 1, 1],
        'ante': [5]*6,
        'account': [1000]*6
    }
    tracker.process_messages([msg3])
    print(f"Capacity after 6-slot msg: {tracker.table_capacity} (Expected: 6)")

if __name__ == "__main__":
    test_capacity_detection()
