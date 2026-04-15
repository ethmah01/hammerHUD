"""
Diagnostic 5: Search for ACTUAL game action text in memory.
Instead of looking for hand history format, look for the chat log
messages that Ignition renders during play.
"""
import psutil
import ctypes
import ctypes.wintypes
import re

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

# These are actual rendered chat/action strings, NOT templates
SEARCH_TERMS = [
    b"Result for hand",
    b"posts small blind",
    b"posts big blind",  
    b"Player 1 ",
    b"Player 2 ",
    b"Player 3 ",
    b"Player 5 ",
    b"Player 7 ",
    b"wins (",
    b"folds\n",
    b"raises to",
    b"calls ",
    b"Dealt to",
    b"successfully added",
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

def scan_pid(pid):
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return {}
    
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    matches = {}  # search_term -> list of decoded snippets
    
    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]
                    
                    for sig in SEARCH_TERMS:
                        idx = data.find(sig)
                        if idx != -1:
                            # Check it's not a template (contains {{ }})
                            start = max(0, idx - 200)
                            end = min(len(data), idx + 500)
                            snippet = data[start:end]
                            decoded = snippet.decode('utf-8', errors='replace').replace('\x00', '')
                            
                            # Skip if it looks like a template
                            if '{{' in decoded and '}}' in decoded:
                                continue
                            
                            sig_str = sig.decode('utf-8', errors='replace')
                            if sig_str not in matches:
                                matches[sig_str] = []
                            if len(matches[sig_str]) < 3:  # Max 3 per term
                                matches[sig_str].append({
                                    'addr': hex(mbi.BaseAddress + idx),
                                    'text': decoded.strip()[:500]
                                })
            except:
                pass
        address += mbi.RegionSize
        if address > 0x7FFFFFFFFFFF:
            break
    
    kernel32.CloseHandle(handle)
    return matches

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNOSTIC 5: Searching for LIVE game action text in memory")
    print("Make sure you are SEATED at a table with at least 1 hand played!")
    print("=" * 80)
    
    pids = find_ignition_pids()
    if not pids:
        print("\n[X] No Ignition processes found!")
        exit()
    
    print(f"\n[*] Found {len(pids)} Ignition PIDs. Scanning for live game data...\n")
    
    for pid in pids:
        print(f"  Scanning PID {pid}...", end=" ", flush=True)
        matches = scan_pid(pid)
        
        if matches:
            print(f"FOUND {sum(len(v) for v in matches.values())} matches!")
            for term, hits in matches.items():
                for hit in hits:
                    print(f"\n    --- '{term}' at {hit['addr']} ---")
                    print(f"    {hit['text'][:300]}")
        else:
            print("nothing.")
    
    print("\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)
