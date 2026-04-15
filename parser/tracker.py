"""
Session tracker that processes live game events from the memory reader
and maintains per-seat VPIP/PFR statistics.
"""
from core.models import SessionStats, PlayerStats
from core.database import load_hero_stats, save_hero_stats


class SessionTracker:
    def __init__(self):
        self.session_stats = SessionStats()
        self.hero_stats = load_hero_stats()
        self.processed_hand_ids = set()
        self.seat_players = {}
        self.hero_seat = None
        self.hands_this_session = 0
    
    def process_hand_event(self, hand: dict) -> bool:
        """
        Process a completed hand event from the memory reader.
        hand = {
            'hand_id': str,
            'dealer_seat': int,
            'seats': {
                seat_num: {'vpip': bool, 'pfr': bool, 'actions': [...]}
            }
        }
        Returns True if new data was processed.
        """
        hand_id = hand.get('hand_id', '')
        if not hand_id or hand_id in self.processed_hand_ids:
            return False
            
        self.processed_hand_ids.add(hand_id)
        self.hands_this_session += 1
        
        seats_data = hand.get('seats', {})
        
        for seat, stats in seats_data.items():
            vpip = stats.get('vpip', False)
            pfr = stats.get('pfr', False)
            
            # Assign a generic name — Ignition is anonymous
            player_name = f"Player {seat}"
            self.seat_players[seat] = player_name
            
            # Update session stats
            player_stats = self.session_stats.get_seat(seat)
            player_stats.add_hand(vpip, pfr)
            
            # Update hero lifetime stats if this is our seat
            if seat == self.hero_seat:
                self.hero_stats.add_hand(vpip, pfr)
                save_hero_stats(self.hero_stats)
        
        print(f"tracker: Hand #{hand_id} processed "
              f"({len(seats_data)} seats, total {self.hands_this_session} hands)")
        
        return True
    
    # Legacy method for backward compatibility with manual paste
    def process_hand_text(self, text: str) -> bool:
        """Legacy: Parse raw hand history text. Returns True if new data found."""
        try:
            from parser.ignition_parser import extract_hands, parse_hand
            updated = False
            hands = extract_hands(text)
            for h in hands:
                res = parse_hand(h)
                if res.is_valid() and res.hand_id not in self.processed_hand_ids:
                    self.processed_hand_ids.add(res.hand_id)
                    for seat, stats in res.player_stats.items():
                        player = self.session_stats.get_seat(seat)
                        player.add_hand(stats["vpip"], stats["pfr"])
                    updated = True
            return updated
        except Exception:
            return False
    
    def set_hero_seat(self, seat: int):
        """Set/update the hero's seat number."""
        if seat != self.hero_seat:
            self.hero_seat = seat
            print(f"tracker: Hero seat set to {seat}")
    
    def clear_session(self):
        self.session_stats = SessionStats()
        self.processed_hand_ids.clear()
        self.seat_players.clear()
        self.hands_this_session = 0

    def reset_seat(self, seat_num: int):
        """Reset stats for a specific seat index."""
        if seat_num in self.session_stats.seat_stats:
            from core.models import PlayerStats
            self.session_stats.seat_stats[seat_num] = PlayerStats()
            print(f"tracker: Stats reset for seat {seat_num}")
