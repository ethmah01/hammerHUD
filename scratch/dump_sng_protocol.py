import psutil
import ctypes
import ctypes.wintypes
import json
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

def dump_sng_json():
    print("Searching for Ignition/Bovada/Bodog processes...")
    pids = []
    possible = ['ignition', 'lobby', 'bovada', 'bodog']
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if any(p.lower() in name.lower() for p in possible):
                pids.append(proc.info['pid'])
        except: continue
    
    print(f"Found PIDs: {pids}")
    
    kernel32 = ctypes.windll.kernel32
    for pid in pids:
        handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not handle: continue
        
        print(f"Scanning PID {pid}...")
        address = 0
        mbi = MEMORY_BASIC_INFORMATION()
        while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE) and mbi.RegionSize < 100_000_000:
                try:
                    buf = ctypes.create_string_buffer(mbi.RegionSize)
                    if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, None):
                        data = buf.raw
                        # Find all JSON-like objects with "pid"
                        # We look for something that looks like the game protocol
                        matches = re.findall(rb'\{"seq":\d+,"tDiff":\d+,"data":\{[^}]+\}\}', data)
                        if matches:
                            print(f"  [!] Found {len(matches)} protocol messages in PID {pid}")
                            with open(f"sng_dump_PID{pid}.jsonl", "a") as f:
                                for m in matches:
                                    try:
                                        # Clean up markers and trailing junk
                                        decoded = m.decode('utf-8', errors='ignore')
                                        f.write(decoded + "\n")
                                    except: pass
                except: pass
            address += mbi.RegionSize
            if address > 0x7FFFFFFFFFFF: break
        kernel32.CloseHandle(handle)

if __name__ == "__main__":
    dump_sng_json()
