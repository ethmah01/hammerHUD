"""
Diagnostic 7: Search for WebSocket JSON action messages in memory.
Specifically looking for player actions (fold, call, raise, bet, check)
in the game protocol messages.

IMPORTANT: Play 2-3 hands with different actions before running!
Ideally: fold one hand, call one, raise one.
"""
import psutil
import ctypes
import ctypes.wintypes
import re
import json

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

# JSON patterns to search for in WebSocket messages
JSON_PATTERNS = [
    b'"Fold"',
    b'"Call"',
    b'"Raise"',
    b'"Check"',
    b'"Bet"',
    b'"AllIn"',
    b'"BigBlind"',
    b'"SmallBlind"',
    b'"action"',
    b'"PLAY_ACTION"',
    b'"CYCLIC_MODEL"',
    b'"CYCLIC_DONE"',
    b'"CO_PLAYER_ACTION"',
    b'"PLAY_STAGE"',
    b'"PLAY_DEAL"',
    b'"PLAY_CARDS"',
    b'"CO_DEAL"',
    b'"CO_CARDS"',
    b'"pid":"PLAY_',
    b'"pid":"CO_',
    b'"seat":',
]

def find_ignition_pids():
    pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and ('IgnitionCasino' in name or 'Lobby' in name):
                pids.append(proc.info['pid'])
        except:
            pass
    return pids

def scan_pid_for_json(pid):
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return []
    
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    all_json = []
    
    # Regex to find JSON objects with seq/data/pid fields
    json_re = re.compile(rb'\{["\']seq["\']:\d+.*?"pid".*?\}', re.DOTALL)
    action_re = re.compile(rb'\{[^{}]{5,500}\}')
    
    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]
                    
                    for pattern in JSON_PATTERNS:
                        offset = 0
                        while True:
                            idx = data.find(pattern, offset)
                            if idx == -1:
                                break
                            
                            # Get surrounding context
                            start = max(0, idx - 200)
                            end = min(len(data), idx + 300)
                            snippet = data[start:end]
                            
                            # Try to extract JSON objects from the snippet
                            decoded = snippet.decode('utf-8', errors='replace').replace('\x00', '')
                            
                            # Skip JS source code
                            if 'function' in decoded and 'return' in decoded:
                                offset = idx + len(pattern)
                                continue
                            if 'e.AllIn=' in decoded or 'e.Fold=' in decoded:
                                offset = idx + len(pattern)
                                continue
                            
                            # Try to find complete JSON objects
                            for match in action_re.finditer(snippet):
                                try:
                                    candidate = match.group().decode('utf-8', errors='replace')
                                    # Check if it looks like a game protocol message
                                    if any(k in candidate for k in ['"pid"', '"action"', '"seat"', '"seq"', 
                                           '"Fold"', '"Call"', '"Raise"', '"Check"', '"Bet"', '"AllIn"',
                                           '"BigBlind"', '"SmallBlind"']):
                                        all_json.append({
                                            'addr': hex(mbi.BaseAddress + idx),
                                            'pattern': pattern.decode('utf-8', errors='replace'),
                                            'json': candidate[:300],
                                            'context': decoded[:400]
                                        })
                                except:
                                    pass
                            
                            offset = idx + len(pattern)
            except:
                pass
        address += mbi.RegionSize
        if address > 0x7FFFFFFFFFFF:
            break
    
    kernel32.CloseHandle(handle)
    return all_json

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNOSTIC 7: WebSocket JSON Action Messages")
    print("Play 2-3 hands with DIFFERENT actions before running!")
    print("(fold one, call one, raise one)")
    print("=" * 80)
    
    pids = find_ignition_pids()
    if not pids:
        print("\n[X] No Ignition processes found!")
        exit()
    
    print(f"\n[*] Found {len(pids)} Ignition PIDs.\n")
    
    # Collect ALL unique PIDs from diagnostic6
    all_results = {}
    
    for pid in pids:
        print(f"  Scanning PID {pid}...", end=" ", flush=True)
        results = scan_pid_for_json(pid)
        
        if results:
            print(f"FOUND {len(results)} JSON fragments!")
            all_results[pid] = results
        else:
            print("nothing.")
    
    # Deduplicate and categorize
    print("\n" + "=" * 80)
    print("RESULTS: Unique game protocol messages found")
    print("=" * 80)
    
    seen = set()
    categorized = {
        'actions': [],
        'game_events': [],
        'other': []
    }
    
    for pid, results in all_results.items():
        for r in results:
            json_str = r['json']
            if json_str in seen:
                continue
            seen.add(json_str)
            
            if any(k in json_str for k in ['"Fold"', '"Call"', '"Raise"', '"Check"', '"Bet"', 
                    '"AllIn"', '"BigBlind"', '"SmallBlind"', '"action"', 'PLAYER_ACTION']):
                categorized['actions'].append(r)
            elif any(k in json_str for k in ['"pid":', '"PLAY_', '"CO_']):
                categorized['game_events'].append(r)
            else:
                categorized['other'].append(r)
    
    print(f"\n  ACTION messages: {len(categorized['actions'])}")
    for r in categorized['actions'][:30]:
        print(f"    {r['json'][:200]}")
    
    print(f"\n  GAME EVENT messages: {len(categorized['game_events'])}")
    for r in categorized['game_events'][:30]:
        print(f"    {r['json'][:200]}")
    
    if categorized['other']:
        print(f"\n  OTHER messages: {len(categorized['other'])}")
        for r in categorized['other'][:10]:
            print(f"    {r['json'][:200]}")
    
    # Also dump to file
    with open("json_protocol_dump.txt", "w", encoding="utf-8") as f:
        f.write("=== ACTION MESSAGES ===\n\n")
        for r in categorized['actions']:
            f.write(f"[PID {[p for p,v in all_results.items() if r in v][0] if any(r in v for v in all_results.values()) else '?'}] ")
            f.write(f"Pattern: {r['pattern']}\n")
            f.write(f"JSON: {r['json']}\n")
            f.write(f"Context: {r['context'][:500]}\n\n")
        
        f.write("\n=== GAME EVENTS ===\n\n")
        for r in categorized['game_events']:
            f.write(f"JSON: {r['json']}\n")
            f.write(f"Context: {r['context'][:500]}\n\n")
    
    print(f"\nFull dump written to: json_protocol_dump.txt")
    print("=" * 80)
