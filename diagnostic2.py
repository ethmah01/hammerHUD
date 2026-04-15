"""
Diagnostic 2: Decode the memory dumps and also do a live scan
to print what the hand data actually looks like in memory.
"""
import os
import psutil
import ctypes
import ctypes.wintypes

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

def find_ignition_pids():
    pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and ('IgnitionCasino.exe' in name or 'Lobby.exe' in name):
                pids.append(proc.info['pid'])
        except:
            pass
    return pids

def scan_and_print(pid):
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        print(f"  [X] Cannot open PID {pid}")
        return

    print(f"  [*] Scanning PID {pid}...")
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    match_count = 0

    # Search for multiple possible signatures
    search_terms_8 = [b"Hand #", b"Ignition Hand", b"Stage #", b"Seat 1:", b"Total pot", 
                      b"*** HOLE CARDS ***", b"*** SUMMARY ***", b"*** FLOP ***",
                      b"posts small blind", b"posts big blind"]

    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]
                    
                    for sig in search_terms_8:
                        if sig in data:
                            idx = data.find(sig)
                            # Get surrounding context (500 bytes before, 3000 bytes after)
                            start = max(0, idx - 500)
                            end = min(len(data), idx + 3000)
                            snippet = data[start:end]
                            
                            # Try UTF-8
                            decoded = snippet.decode('utf-8', errors='replace')
                            # Clean up nulls for readability
                            cleaned = decoded.replace('\x00', '')
                            
                            if len(cleaned.strip()) > 20:  # Only print if meaningful
                                match_count += 1
                                print(f"\n{'='*80}")
                                print(f"  MATCH #{match_count}: Found '{sig.decode()}' in PID {pid} at {hex(mbi.BaseAddress)} + offset {idx}")
                                print(f"{'='*80}")
                                # Print first 2000 chars of cleaned text
                                print(cleaned[:2000])
                                print(f"{'='*80}\n")
                                
                                if match_count >= 10:
                                    print("  [*] Stopping after 10 matches to avoid flooding.")
                                    kernel32.CloseHandle(handle)
                                    return
                            break  # Move to next region after first match
            except:
                pass
        address += mbi.RegionSize
        if address > 0x7FFFFFFFFFFF:
            break
    
    kernel32.CloseHandle(handle)
    print(f"  [*] PID {pid} done. Found {match_count} readable matches.")

def check_existing_dumps():
    """Check if we have dump files from the first diagnostic."""
    dump_files = [f for f in os.listdir('.') if f.startswith('memory_dump_PID') and f.endswith('.txt')]
    if dump_files:
        print(f"\n[*] Found {len(dump_files)} existing dump file(s) from diagnostic 1:")
        for df in dump_files:
            print(f"\n--- Decoding {df} ---")
            with open(df, 'rb') as f:
                raw = f.read()
            # Try to decode and print readable portions
            text = raw.decode('utf-8', errors='replace').replace('\x00', '')
            # Print first 3000 chars
            print(text[:3000])
            print(f"--- End of {df} (showed first 3000 chars) ---\n")

if __name__ == "__main__":
    print("="*80)
    print("DIAGNOSTIC 2: What does Ignition's hand data look like in memory?")
    print("="*80)
    
    # Step 1: Check existing dumps
    check_existing_dumps()
    
    # Step 2: Live scan
    print("\n[*] Starting live memory scan...")
    pids = find_ignition_pids()
    if not pids:
        print("[X] No Ignition processes found!")
    else:
        print(f"[*] Found {len(pids)} Ignition PIDs. Scanning for hand data patterns...")
        for pid in pids:
            scan_and_print(pid)
    
    print("\n[*] Diagnostic 2 complete!")
