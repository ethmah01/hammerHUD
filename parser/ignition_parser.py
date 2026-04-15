import re
from typing import List, Dict

class HandResult:
    def __init__(self, hand_id: str):
        self.hand_id = hand_id
        # seat number -> {"vpip": bool, "pfr": bool}
        self.player_stats: Dict[int, Dict[str, bool]] = {}
        # player name -> seat number
        self.name_to_seat: Dict[str, int] = {}
        # The seat number of the hero
        self.hero_seat: int = -1

    def is_valid(self) -> bool:
        return len(self.player_stats) > 0


def extract_hands(text: str) -> List[str]:
    """Splits a full hand history file string into individual hands."""
    # Hands are usually separated by blank lines. We can split by double newlines.
    raw_hands = re.split(r'\n\s*\n', text)
    valid_hands = []
    for h in raw_hands:
        if "Hand #" in h or "Ignition Hand" in h:
            valid_hands.append(h.strip())
    return valid_hands

def parse_hand(hand_text: str) -> HandResult:
    """Parses a single hand string and returns the HandResult."""
    lines = hand_text.split('\n')
    hand_id = "unknown"
    
    # 1. Match Hand ID
    match = re.search(r'Hand #(\d+)', hand_text)
    if match:
        hand_id = match.group(1)
        
    result = HandResult(hand_id)
    
    # Regex definitions
    # Matches: Seat 1: Player 1 ($10 in chips) or Seat 2: Hero ($20)
    seat_re = re.compile(r'^Seat (\d+): (.+?) \(')
    action_re = re.compile(r'^(.+?): (folds|calls|raises|checks|bets)')
    
    in_preflop = False
    
    for line in lines:
        line = line.strip()
        
        # Extract seat info
        seat_match = seat_re.match(line)
        if seat_match:
            seat_num = int(seat_match.group(1))
            player_name = seat_match.group(2).strip()
            
            result.name_to_seat[player_name] = seat_num
            result.player_stats[seat_num] = {"vpip": False, "pfr": False}
            
            if "Hero" in player_name or "[ME]" in player_name.upper():
                 result.hero_seat = seat_num
            continue
            
        # Check phases
        if "*** HOLE CARDS ***" in line:
            in_preflop = True
            continue
            
        if "*** FLOP ***" in line or "*** SUMMARY ***" in line:
            in_preflop = False
            continue
            
        # Parse preflop actions for VPIP and PFR
        if in_preflop:
            action_match = action_re.match(line)
            if action_match:
                actor = action_match.group(1).strip()
                action = action_match.group(2)
                
                seat_num = result.name_to_seat.get(actor)
                if seat_num is not None:
                    # Posting blinds does not trigger vpip, only voluntary actions
                    if action in ["calls", "raises", "bets"]:
                        result.player_stats[seat_num]["vpip"] = True
                    if action == "raises":
                        result.player_stats[seat_num]["pfr"] = True

    # GTO_MODULE_HOOK — pass completed HandResult object here for analysis
    # Future modules can attach here. Example: review_gto_decisions(hand_text, result)
    
    # GAME_REVIEW_MODULE_HOOK — post-session full hand data available here
    
    return result
