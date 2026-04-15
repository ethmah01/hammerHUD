"""
Ignition Poker WebSocket Protocol Memory Reader.
Scans renderer/main process memory for the sequential JSON protocol log
and emits structured game events for the HUD tracker.
"""
import sys
import threading
import time
import re
import json
import ctypes
import ctypes.wintypes
import psutil
import logging
import traceback
from typing import Optional, Callable, List, Dict

def _print(*args, **kwargs):
    """Internal print that ensures output is flushed immediately."""
    print(*args, **kwargs, flush=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]

# Button codes from the game protocol (bitmask)
BTN_CHECK = 64
BTN_BET = 128
BTN_CALL = 256
BTN_RAISE = 512
BTN_FOLD = 1024
BTN_ALLIN_CALL = 2048
BTN_ALLIN_RAISE = 4096
BTN_SB = 2
BTN_BB = 4

# Table states (Street info)
TS_NEW_HAND = 2
TS_PREFLOP = 8
TS_FLOP = 32
TS_TURN = 64
TS_RIVER = 32768
TS_SHOWDOWN = 65536

def decode_card(c: int) -> str:
    """Decode Ignition card integer (0-51) to [Rank][Suit] format."""
    if c < 0 or c > 51: return "??"
    ranks = "23456789TJQKA"
    suits = "cdhs" # rank * 4 + suit: 0=c, 1=d, 2=h, 3=s
    return f"{ranks[c // 4]}{suits[c % 4]}"

class ProtocolReader:
    """Reads and parses the Ignition WebSocket protocol from process memory."""
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        
    def find_ignition_pids(self) -> List[int]:
        pids = []
        possible_names = ['IgnitionCasino', 'Lobby', 'Bovada', 'Bodog', 'Ignition']
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name']
                if name and any(pn.lower() in name.lower() for pn in possible_names):
                    pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied): continue
        if pids:
            logging.debug(f"ProtocolReader: Found potential PIDs: {pids}")
        return pids
    
    def extract_ws_log(self, pid: int) -> Optional[str]:
        # Try to open process
        handle = self.kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            err = self.kernel32.GetLastError()
            if err == 5:
                logging.warning(f"ProtocolReader: Access Denied to PID {pid} (Error 5). Needs Admin.")
            else:
                logging.debug(f"ProtocolReader: Could not open PID {pid} (Error {err})")
            return None

        mbi = MEMORY_BASIC_INFORMATION()
        address, best_log, best_len = 0, None, 0
        
        # We search for these anchors to find the WebSocket log
        anchors = [b'"gid":"Joined"', b'"pid":"PLAY_STAGE_INFO"', b'{"seq":']
        
        logging.debug(f"ProtocolReader: Scanning memory of PID {pid}...")
        
        while self.kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            # Only scan committed, writable memory under 50MB (logs are usually small)
            if (mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE) and mbi.RegionSize < 50_000_000):
                try:
                    buf = ctypes.create_string_buffer(mbi.RegionSize)
                    if self.kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, None):
                        data = buf.raw
                        
                        # Search for any of our anchors
                        found_anchor = False
                        for anchor in anchors:
                            idx = data.find(anchor)
                            if idx != -1:
                                found_anchor = True
                                # Extract content from anchor onwards, until null terminator or end of region
                                decoded = data[max(0, idx - 400):].decode('utf-8', errors='replace').split('\x00')[0]
                                if len(decoded) > best_len: 
                                    best_log, best_len = decoded, len(decoded)
                                break 
                except Exception: pass
            
            address += mbi.RegionSize
            # Stop scan if we exceed reasonable memory bounds
            if address > 0x7FFFFFFFFFFF: break
            
        self.kernel32.CloseHandle(handle)
        if best_log:
            logging.info(f"ProtocolReader: Successfully extracted log from PID {pid} (len: {best_len})")
        return best_log

    def parse_messages(self, log_text: str) -> List[dict]:
        messages = []
        pattern = re.compile(r'\{"seq":(\d+),"tDiff":\d+,"data":(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|\[[^\]]*\])\}')
        for match in pattern.finditer(log_text):
            seq, data_str = int(match.group(1)), match.group(2)
            try:
                data = json.loads(data_str)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'pid' in item: messages.append({'seq': seq, **item})
                elif isinstance(data, dict): messages.append({'seq': seq, **data})
            except json.JSONDecodeError: continue
        messages.sort(key=lambda m: m.get('seq', 0))
        return messages

class GameStateTracker:
    """Tracks the current game state from protocol messages across all streets."""
    def __init__(self):
        self.dealer_seat = None
        self.player_stacks = {} # seat -> current chips
        self.table_capacity = 6 # Default to 6-max
        self.confirmed_seated = set() # Authoritative list of players at the table
        self.reset_hand()
        self._processed_hand_ids = set()
        
    def reset_hand(self):
        self.current_hand_id = None
        self.bb_amount = 0
        self.sb_amount = 0
        self.hand_phase = "waiting"
        self.active_seats = set()
        self.actions = []
        self.board = []
        self.hole_cards = {}
        self.winners = []
        self.initial_stacks = {} # seat -> start chips for this hand
        self._hand_started_properly = False

    def process_messages(self, messages: List[dict]) -> List[dict]:
        new_hands = []
        for msg in messages:
            pid = msg.get('pid', '')
            
            if pid in ['PLAY_STAGE_INFO', 'PLAY_TOUR_STAGENUMBER']:
                hand_id = str(msg.get('stageNo', ''))
                if hand_id and hand_id != self.current_hand_id:
                    if self.current_hand_id and self.current_hand_id not in self._processed_hand_ids:
                        h = self._finalize_hand()
                        if h: new_hands.append(h)
                    
                    old_dealer = self.dealer_seat
                    self.reset_hand()
                    self.current_hand_id = hand_id
                    self.dealer_seat = old_dealer
                    for s, chips in self.player_stacks.items():
                        self.initial_stacks[s] = chips
            
            elif pid == 'TCO_ANTE_INFO_ALL':
                # Tournament Antes and Stacks
                accounts = msg.get('account', [])
                antes = msg.get('ante', [])
                flags = msg.get('flag', [])
                
                # Auto-detect table capacity from array length (usually 9 or 6)
                if len(flags) > 0:
                    new_capacity = len(flags)
                    
                    # If message has 9 slots, only switch to 9-max if seats 7-9 are actually active.
                    if new_capacity == 9:
                        indices_7_9 = flags[6:9]
                        has_active_high_seats = any(f == 1 for f in indices_7_9)
                        if has_active_high_seats:
                            if self.table_capacity != 9:
                                logging.info(f"GameStateTracker: Forcing 9-max due to active high seats")
                                self.table_capacity = 9
                        elif self.table_capacity == 6:
                            new_capacity = 6
                            
                    if new_capacity != self.table_capacity:
                        logging.info(f"GameStateTracker: Detected table capacity change: {self.table_capacity} -> {new_capacity}")
                        self.table_capacity = new_capacity

                self._hand_started_properly = True
                new_seated_set = set()
                for i, (acc, ante, active) in enumerate(zip(accounts, antes, flags)):
                    seat = i + 1
                    if active == 1:
                        self.active_seats.add(seat)
                        new_seated_set.add(seat)
                        self.player_stacks[seat] = acc
                        if ante > 0:
                            self.actions.append({
                                'seat': seat,
                                'action': 'ante',
                                'amount': ante,
                                'phase': 'blind'
                            })
                
                # Authoritative update from the tournament ante snapshot
                if new_seated_set:
                    self.confirmed_seated = new_seated_set
            
            elif pid in ['CO_DEALER_SEAT', 'PLAY_TOUR_LEVEL_INFO']:
                if pid == 'CO_DEALER_SEAT':
                    self.dealer_seat = msg.get('seat')
                else: # PLAY_TOUR_LEVEL_INFO
                    self.bb_amount = msg.get('bblind', self.bb_amount)
                    self.sb_amount = msg.get('sblind', self.sb_amount)

            elif pid == 'CO_OPTION_INFO':
                self.bb_amount = msg.get('bblind', self.bb_amount)
                self.sb_amount = msg.get('sblind', self.sb_amount)
            
            elif pid == 'CO_TABLE_STATE':
                state = msg.get('tableState', 0)
                if state == TS_PREFLOP: self.hand_phase = "preflop"
                elif state == TS_FLOP: self.hand_phase = "flop"
                elif state == TS_TURN: self.hand_phase = "turn"
                elif state == TS_RIVER: self.hand_phase = "river"
                elif state == TS_SHOWDOWN: self.hand_phase = "showdown"
            
            elif pid == 'CO_BLIND_INFO':
                seat = msg.get('seat')
                if seat is not None:
                    self.active_seats.add(seat)
                    # We don't update confirmed_seated here; we rely on snapshots
                    btn = msg.get('btn', 0)
                    amt = msg.get('bet', 0)
                    self.actions.append({
                        'seat': seat, 
                        'action': 'sb' if btn == BTN_SB else 'bb', 
                        'amount': amt,
                        'phase': 'blind'
                    })
                    if seat not in self.initial_stacks and seat in self.player_stacks:
                        self.initial_stacks[seat] = self.player_stacks[seat]
            
            elif pid == 'CO_SELECT_INFO':
                seat = msg.get('seat')
                if seat is not None:
                    self.active_seats.add(seat)
                    if seat > 6 and self.table_capacity == 6:
                        self.table_capacity = 9
                    btn = msg.get('btn', 0)
                    amt = msg.get('bet', 0)
                    current_account = msg.get('account')
                    if current_account is not None:
                        self.player_stacks[seat] = current_account
                        if seat not in self.initial_stacks:
                            self.initial_stacks[seat] = current_account + (msg.get('bet', 0) or 0) + (msg.get('raise', 0) or 0)
                    
                    self.actions.append({
                        'seat': seat,
                        'action': self._decode_action(btn),
                        'amount': amt,
                        'phase': self.hand_phase
                    })
            
            elif pid == 'CO_BCARD3_INFO':
                self.board = [decode_card(c) for c in msg.get('bcard', [])]
            
            elif pid == 'CO_BCARD1_INFO':
                card = decode_card(msg.get('card', -1))
                if card != "??": self.board.append(card)
            
            elif pid == 'CO_PCARD_INFO':
                seat = msg.get('seat')
                if seat is not None:
                    self.active_seats.add(seat)
                    if seat > 6 and self.table_capacity == 6:
                        self.table_capacity = 9
                cards = [decode_card(c) for c in msg.get('card', [])]
                if cards: self.hole_cards[seat] = cards
            
            elif pid == 'CO_RESULT_INFO':
                payouts = msg.get('account', [])
                for i, amt in enumerate(payouts):
                    seat = i + 1
                    self.player_stacks[seat] = amt # Update stacks for next hand
                    if amt > 0:
                        self.winners.append({'seat': seat, 'chips': amt})
                        # If they possess chips, they are definitively seated
                        self.confirmed_seated.add(seat)
                    elif amt == 0 and seat in self.confirmed_seated and seat <= self.table_capacity:
                        # Only remove from confirmed if they are within the table capacity
                        # This prevents blacklisting future 7-8-9 seats in 6-max games
                        self.confirmed_seated.remove(seat)
                
                # Hand Finalization
                if self.current_hand_id and self.current_hand_id not in self._processed_hand_ids:
                    h = self._finalize_hand()
                    if h: 
                        new_hands.append(h)

            elif pid == 'PLAY_STAGE_END_REQ':
                if self.current_hand_id and self.current_hand_id not in self._processed_hand_ids:
                    h = self._finalize_hand()
                    if h: new_hands.append(h)
        
        return new_hands

    def _decode_action(self, btn: int) -> str:
        if btn & BTN_FOLD: return 'fold'
        if btn & BTN_ALLIN_RAISE: return 'allin_raise'
        if btn & BTN_ALLIN_CALL: return 'allin_call'
        if btn & BTN_RAISE: return 'raise'
        if btn & BTN_BET: return 'bet'
        if btn & BTN_CALL: return 'call'
        if btn & BTN_CHECK: return 'check'
        return f'unknown_{btn}'

    def _finalize_hand(self) -> Optional[dict]:
        if not self.current_hand_id or not self.active_seats: return None
        self._processed_hand_ids.add(self.current_hand_id)
        
        res = {
            'hand_id': self.current_hand_id,
            'dealer_seat': self.dealer_seat,
            'table_capacity': self.table_capacity,
            'active_seats': list(self.active_seats),
            'confirmed_seated': list(self.confirmed_seated),
            'seats': {},
            'actions': self.actions,
            'board': self.board,
            'hole_cards': self.hole_cards,
            'winners': self.winners,
            'initial_stacks': self.initial_stacks
        }
        
        for seat in self.active_seats:
            pf_actions = [a for a in self.actions if a['seat'] == seat and a['phase'] == 'preflop']
            vpip = any(a['action'] in ('call', 'raise', 'allin_raise', 'allin_call') for a in pf_actions)
            pfr = any(a['action'] in ('raise', 'allin_raise') for a in pf_actions)
            res['seats'][seat] = {'vpip': vpip, 'pfr': pfr}
            
        return res

class IgnitionMemoryReader(threading.Thread):
    def __init__(self, callback: Callable):
        super().__init__(daemon=True)
        self.callback = callback
        self._running = False
        self.reader = ProtocolReader()
        self.state = GameStateTracker()
        self._last_seq = -1
        self._active_pid = None

    def run(self):
        self._running = True
        logging.info("mem_reader: Thread started")
        while self._running:
            try:
                pids = self.reader.find_ignition_pids()
                if pids:
                    targets = ([self._active_pid] if self._active_pid in pids else []) + [p for p in pids if p != self._active_pid]
                    for pid in targets:
                        log = self.reader.extract_ws_log(pid)
                        if not log: continue
                        msgs = self.reader.parse_messages(log)
                        
                        # Handle Sequence Reset or PID change
                        if pid != self._active_pid:
                            logging.info(f"mem_reader: PID changed ({self._active_pid} -> {pid}). Resetting state.")
                            self._last_seq = -1
                            self._active_pid = pid
                            self.state = GameStateTracker() # Full state reset
                        
                        # Detect sequence wrap-around/reset on same PID
                        max_seq = max((m.get('seq', 0) for m in msgs), default=-1)
                        if max_seq != -1 and max_seq < self._last_seq - 500:
                            logging.info(f"mem_reader: Large sequence drop detected ({self._last_seq} -> {max_seq}). Resetting state.")
                            self._last_seq = -1
                            self.state = GameStateTracker() # Full state reset

                        new_msgs = [m for m in msgs if m.get('seq', 0) > self._last_seq]
                        if new_msgs:
                            self._last_seq = max(m.get('seq', 0) for m in new_msgs)
                            hands = self.state.process_messages(new_msgs)
                            for h in hands: self.callback(h)
                            break
            except Exception as e:
                logging.error(f"mem_reader: Loop Error: {e}\n{traceback.format_exc()}")
            time.sleep(1.0)
    def stop(self): self._running = False

    @property
    def game_info(self):
        pids = self.reader.find_ignition_pids()
        return {
            'hand_id': self.state.current_hand_id,
            'phase': self.state.hand_phase,
            'hands_processed': len(self.state._processed_hand_ids),
            'active_seats': list(self.state.confirmed_seated),
            'table_capacity': self.state.table_capacity,
            'pids_found': len(pids) if pids else 0
        }
