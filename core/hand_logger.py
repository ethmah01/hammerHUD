"""
Hand History Logger.
Takes structured hand data extracted from memory and saves it to text files.
"""
import os
from datetime import datetime

class HandLogger:
    def __init__(self, save_path: str = ""):
        self.save_path = save_path
        if self.save_path:
            os.makedirs(self.save_path, exist_ok=True)
            
    def set_path(self, path: str):
        self.save_path = path
        if self.save_path:
            os.makedirs(self.save_path, exist_ok=True)

    def log_hand(self, hand: dict):
        """Saves a hand to a session file in the save path."""
        if not self.save_path:
            return
            
        hand_id = hand.get('hand_id', 'unknown')
        now = datetime.now()
        filename = f"HH_{now.strftime('%Y%m%d')}.txt"
        filepath = os.path.join(self.save_path, filename)
        
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(self._format_hand(hand))
                f.write("\n\n" + "-"*40 + "\n\n")
        except Exception as e:
            print(f"hand_logger: Error saving hand {hand_id}: {e}")

    def _format_hand(self, hand: dict) -> str:
        """Formats the internal hand dict into a human-readable string."""
        hand_id = hand.get('hand_id', 'unknown')
        dealer = hand.get('dealer_seat', 'None')
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        
        lines = []
        lines.append(f"Ignition Hand #{hand_id}: Hold'em No Limit - {timestamp}")
        lines.append(f"Table 'Live Session' 6-max Seat #{dealer} is the button")
        
        seats = hand.get('seats', {})
        hole_cards = hand.get('hole_cards', {})
        initial_stacks = hand.get('initial_stacks', {})
        
        # Player list
        for seat in sorted(hand.get('active_seats') or seats.keys()):
            stack = initial_stacks.get(seat, 0)
            cards_str = ""
            if seat in hole_cards:
                cards_str = f" [{ ' '.join(hole_cards[seat]) }]"
            lines.append(f"Seat {seat}: Player {seat} ({stack}){cards_str}")
            
        actions = hand.get('actions', [])
        
        def write_street(phase_name, street_actions):
            if not street_actions: return
            lines.append(f"*** {phase_name.upper()} ***")
            board = hand.get('board', [])
            if phase_name == "flop" and board:
                lines.append(f"Board: [{ ' '.join(board[:3]) }]")
            elif phase_name == "turn" and len(board) >= 4:
                lines.append(f"Board: [{ ' '.join(board[:4]) }]")
            elif phase_name == "river" and len(board) >= 5:
                lines.append(f"Board: [{ ' '.join(board[:5]) }]")
                
            for act in street_actions:
                seat = act.get('seat')
                name = act.get('action')
                amt = act.get('amount', 0)
                
                verbs = {
                    'sb': 'posts small blind',
                    'bb': 'posts big blind',
                    'fold': 'folds',
                    'check': 'checks',
                    'call': 'calls',
                    'bet': 'bets',
                    'raise': 'raises',
                    'allin_raise': 'raises (all-in)',
                    'allin_call': 'calls (all-in)'
                }
                verb = verbs.get(name, name)
                lines.append(f"Seat {seat}: {verb} {amt}")

        # Process streets
        write_street("blinds", [a for a in actions if a['phase'] == 'blind'])
        write_street("preflop", [a for a in actions if a['phase'] == 'preflop'])
        write_street("flop", [a for a in actions if a['phase'] == 'flop'])
        write_street("turn", [a for a in actions if a['phase'] == 'turn'])
        write_street("river", [a for a in actions if a['phase'] == 'river'])
        
        lines.append("*** SUMMARY ***")
        board = hand.get('board', [])
        if board:
            lines.append(f"Total Board: [{ ' '.join(board) }]")
            
        winners = hand.get('winners', [])
        winner_found = False
        for w in winners:
            seat = w['seat']
            final_chips = w['chips']
            start_chips = initial_stacks.get(seat, 0)
            
            # Simple heuristic: if chips increased, they won a pot
            if final_chips > start_chips:
                profit = final_chips - start_chips
                lines.append(f"Seat {seat} won {profit} chips (Final: {final_chips})")
                winner_found = True
        
        if not winner_found and winners:
            # Fallback: just show who collected the most if profit calculation failed
            top_winner = max(winners, key=lambda x: x['chips'])
            lines.append(f"Seat {top_winner['seat']} collected the main pot ({top_winner['chips']} chips)")
        elif not winners:
            lines.append("No winner data captured.")
            
        lines.append(f"Hand #{hand_id} complete.")
        return "\n".join(lines)
