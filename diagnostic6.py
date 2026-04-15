"""
Diagnostic 6: Deep dump of ALL game text from the active renderer PID.
Play at least 2-3 full hands before running this so we capture
the full action log (blinds, folds, calls, raises, results).
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

# Patterns that indicate ACTUAL game data (not templates)
GAME_PATTERNS = [
    b"Result for hand",
    b"posts small blind",
    b"posts big blind",
    b"wins (",
    b"wins main pot",
    b"wins side pot",
    b" folds",
    b" calls ",
    b" raises to ",
    b" checks",
    b" bets ",
    b"Dealt to",
    b"successfully added",
    b"Board:",
    b"Board [",
    b"FLOP",
    b"TURN",
    b"RIVER",
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

def deep_scan_pid(pid):
    """Extract ALL game-related text from a single PID."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return []

    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    all_snippets = []

    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]

                    for pattern in GAME_PATTERNS:
                        offset = 0
                        while True:
                            idx = data.find(pattern, offset)
                            if idx == -1:
                                break

                            start = max(0, idx - 300)
                            end = min(len(data), idx + 800)
                            snippet = data[start:end]
                            decoded = snippet.decode('utf-8', errors='replace').replace('\x00', '')

                            # Skip templates with {{ }}
                            if '{{' in decoded and '}}' in decoded:
                                offset = idx + len(pattern)
                                continue

                            # Skip source code
                            if 'function ' in decoded and '{' in decoded and '}' in decoded and ';' in decoded:
                                offset = idx + len(pattern)
                                continue

                            all_snippets.append({
                                'pattern': pattern.decode('utf-8', errors='replace'),
                                'addr': hex(mbi.BaseAddress + idx),
                                'region': hex(mbi.BaseAddress),
                                'text': decoded.strip()
                            })
                            offset = idx + len(pattern)
            except:
                pass
        address += mbi.RegionSize
        if address > 0x7FFFFFFFFFFF:
            break

    kernel32.CloseHandle(handle)
    return all_snippets

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNOSTIC 6: Full game text extraction from Ignition renderer")
    print("IMPORTANT: Play 2-3 full hands before running this!")
    print("=" * 80)

    pids = find_ignition_pids()
    if not pids:
        print("\n[X] No Ignition processes found!")
        exit()

    print(f"\n[*] Found {len(pids)} Ignition PIDs.\n")

    for pid in pids:
        print(f"  Scanning PID {pid}...", end=" ", flush=True)
        snippets = deep_scan_pid(pid)

        if not snippets:
            print("no game data.")
            continue

        print(f"FOUND {len(snippets)} game text fragments!")

        # Deduplicate by address
        seen_addrs = set()
        unique = []
        for s in snippets:
            if s['addr'] not in seen_addrs:
                seen_addrs.add(s['addr'])
                unique.append(s)

        # Group by memory region
        regions = {}
        for s in unique:
            r = s['region']
            if r not in regions:
                regions[r] = []
            regions[r].append(s)

        print(f"  Unique: {len(unique)} fragments across {len(regions)} memory regions.\n")

        # Write full dump to file
        dump_file = f"game_dump_PID{pid}.txt"
        with open(dump_file, 'w', encoding='utf-8', errors='replace') as f:
            for region, frags in sorted(regions.items()):
                f.write(f"\n{'='*80}\n")
                f.write(f"REGION: {region} ({len(frags)} fragments)\n")
                f.write(f"{'='*80}\n\n")
                for frag in frags:
                    f.write(f"--- [{frag['pattern']}] at {frag['addr']} ---\n")
                    f.write(frag['text'][:600])
                    f.write("\n\n")

        print(f"  Full dump written to: {dump_file}")

        # Print the most interesting snippets to console
        print(f"\n  TOP GAME SNIPPETS FROM PID {pid}:")
        for s in unique[:20]:
            # Extract just the game-relevant line
            text = s['text']
            # Try to find clean game messages
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if any(p in line for p in ['Result for hand', 'wins (', 'folds', 'calls', 
                        'raises', 'checks', 'bets', 'posts small', 'posts big',
                        'Dealt to', 'Board', 'successfully']):
                    if '{{' not in line and 'function' not in line:
                        print(f"    >> {line[:120]}")

    print("\n" + "=" * 80)
    print("CHECK the game_dump_PID*.txt file for full details!")
    print("=" * 80)
