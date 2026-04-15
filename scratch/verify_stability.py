import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory_reader import GameStateTracker

def test_authoritative_sync():
    tracker = GameStateTracker()
    
    # Mock MemoryReader to access game_info
    class MockReader:
        def __init__(self, state):
            self.state = state
            self.reader = type('obj', (object,), {'find_ignition_pids': lambda: [123]})
        @property
        def game_info(self):
            return {
                'active_seats': list(self.state.confirmed_seated),
                'table_capacity': self.state.table_capacity
            }
            
    reader = MockReader(tracker)
    
    print("--- Test 1: Initial Sync from Ante ---")
    tracker.process_messages([
        {'pid': 'PLAY_TOUR_LEVEL_INFO'},
        {'pid': 'TCO_ANTE_INFO_ALL', 'flag': [1, 1, 1, 0, 0, 0, 0, 0, 0], 'account': [100, 100, 100, 0, 0, 0, 0, 0, 0], 'ante': [5, 5, 5, 0, 0, 0, 0, 0, 0]}
    ])
    info = reader.game_info
    print(f"Seated after Ante: {sorted(info['active_seats'])} (Expected [1, 2, 3])")
    
    print("\n--- Test 2: Mid-hand stability (Heuristics removed) ---")
    tracker.reset_hand() # New hand starts
    # Some other player acts, but we don't have an Ante yet
    tracker.process_messages([
        {'pid': 'CO_BLIND_INFO', 'seat': 1},
        {'pid': 'CO_BLIND_INFO', 'seat': 3}
    ])
    info = reader.game_info
    # Seat 2 didn't act, but in the new architecture, they stay confirmed from the last Ante/Result
    print(f"Seated during Hand 2: {sorted(info['active_seats'])} (Expected [1, 2, 3])")
    
    print("\n--- Test 3: Instant Elimination in Results ---")
    tracker.process_messages([
        {'pid': 'CO_RESULT_INFO', 'account': [150, 0, 150, 0, 0, 0, 0, 0, 0]}
    ])
    info = reader.game_info
    print(f"Seated after Seat 2 busts: {sorted(info['active_seats'])} (Expected [1, 3])")
    
    print("\n--- Test 4: High-index Protection (6-max) ---")
    # Tracker is in 6-max mode by default. CO_RESULT_INFO for 9-max indices (7-9) should NOT blacklist them.
    # We already processed CO_RESULT_INFO with index 6,7,8 = 0.
    # Now if we switch to 9-max and Seat 9 acts...
    tracker.process_messages([
        {'pid': 'CO_SELECT_INFO', 'seat': 9}
    ])
    info = reader.game_info
    print(f"Capacity after Seat 9 actions: {info['table_capacity']} (Expected 9)")
    # Seat 9 should be visible? NO, it wasn't in confirmed_seated yet (only Ante/Result update that)
    # Actually, RESULT updates it too.
    tracker.process_messages([
        {'pid': 'CO_RESULT_INFO', 'account': [150, 0, 150, 0, 0, 0, 0, 0, 500]}
    ])
    info = reader.game_info
    print(f"Seated after Seat 9 result: {sorted(info['active_seats'])} (Expected [1, 3, 9])")

if __name__ == "__main__":
    test_authoritative_sync()
