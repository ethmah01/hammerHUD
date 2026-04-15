import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory_reader import GameStateTracker

def test_activity_window():
    tracker = GameStateTracker()
    
    # Mock MemoryReader to access game_info
    class MockReader:
        def __init__(self, state):
            self.state = state
            self.reader = type('obj', (object,), {'find_ignition_pids': lambda: [123]})
        @property
        def game_info(self):
            last_seen = self.state.last_seen_hand_id
            counter = self.state.hand_counter
            seated = [s for s, h in last_seen.items() if counter - h <= 1]
            return {
                'active_seats': seated,
                'table_capacity': self.state.table_capacity
            }
            
    reader = MockReader(tracker)
    # Everyone acts in Hand 0
    tracker.current_hand_id = "HAND_0"
    tracker.hand_phase = "preflop"
    tracker.process_messages([
        {'pid': 'CO_BLIND_INFO', 'seat': 1},
        {'pid': 'CO_BLIND_INFO', 'seat': 2},
        {'pid': 'CO_SELECT_INFO', 'seat': 3},
        {'pid': 'CO_RESULT_INFO', 'account': [100, 100, 100, 0, 0, 0, 0, 0, 0]}
    ])
    
    info = reader.game_info
    print(f"After Hand 0: {sorted(info['active_seats'])} (Expected [1, 2, 3])")
    
    # Start Hand 1
    tracker.reset_hand()
    tracker.current_hand_id = "HAND_1"
    tracker.hand_phase = "preflop"
    tracker.process_messages([
        {'pid': 'CO_BLIND_INFO', 'seat': 1},
        {'pid': 'CO_BLIND_INFO', 'seat': 3}
        # Seat 2 hasn't acted yet
    ])
    info = reader.game_info
    print(f"During Hand 1 (Seat 2 should stay visible): {sorted(info['active_seats'])} (Expected [1, 2, 3])")
    
    # Hand 1 Ends: Seat 2 busted (0 chips)
    tracker.process_messages([
        {'pid': 'CO_RESULT_INFO', 'account': [100, 0, 100, 0, 0, 0, 0, 0, 0]}
    ])
    
    info = reader.game_info
    print(f"End of Hand 1 (Seat 2 should be gone INSTANTLY because chips=0): {sorted(info['active_seats'])} (Expected [1, 3])")
    
    # Start Hand 2
    tracker.reset_hand()
    info = reader.game_info
    print(f"Start of Hand 2: {sorted(info['active_seats'])} (Expected [1, 3])")

    # Test forced 9-max
    tracker.process_messages([
        {'pid': 'CO_SELECT_INFO', 'seat': 9}
    ])
    info = reader.game_info
    print(f"After Seat 9 acts: Capacity = {info['table_capacity']} (Expected 9)")

if __name__ == "__main__":
    test_activity_window()
