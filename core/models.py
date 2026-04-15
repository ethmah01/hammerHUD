from dataclasses import dataclass, field
from typing import Dict

@dataclass
class PlayerStats:
    vpip_count: int = 0
    pfr_count: int = 0
    hands_played: int = 0

    @property
    def vpip_percent(self) -> float:
        return (self.vpip_count / self.hands_played * 100) if self.hands_played > 0 else 0.0

    @property
    def pfr_percent(self) -> float:
        return (self.pfr_count / self.hands_played * 100) if self.hands_played > 0 else 0.0

    def add_hand(self, vpip: bool, pfr: bool):
        self.hands_played += 1
        if vpip:
            self.vpip_count += 1
        if pfr:
            self.pfr_count += 1

@dataclass
class SessionStats:
    # Seat number (1-6) -> PlayerStats
    seat_stats: Dict[int, PlayerStats] = field(default_factory=dict)
    
    def get_seat(self, seat_num: int) -> PlayerStats:
        if seat_num not in self.seat_stats:
            self.seat_stats[seat_num] = PlayerStats()
        return self.seat_stats[seat_num]
