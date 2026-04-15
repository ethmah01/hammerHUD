import os
import psutil
import pymem
import ctypes

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

def scan_process(pid):
    MEM_COMMIT = 0x1000
    PAGE_READWRITE = 0x04
    PAGE_EXECUTE_READWRITE = 0x40
    
    kernel32 = ctypes.windll.kernel32
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
        
    try:
        # Chromium sandboxes heavily block PROCESS_ALL_ACCESS or PROCESS_VM_WRITE.
        # We only need PROCESS_VM_READ (0x0010) and PROCESS_QUERY_INFORMATION (0x0400)
        PROCESS_VM_READ = 0x0010
        PROCESS_QUERY_INFORMATION = 0x0400
        raw_handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        
        if not raw_handle:
            print(f"[X] Failed to scan PID {pid}: Access Denied (Sandbox/Admin required)")
            return
            
        pm = pymem.Pymem()
        # Manually inject the process handle to bypass pymem's aggressive permissions request
        try:
            # For older pymem
            pm.process_id = pid
            pm.process_handle = raw_handle
        except:
            pass
            
        print(f"[*] Attached to PID {pid} successfully (Read-Only). Scanning...")
        
        address = 0
        mbi = MEMORY_BASIC_INFORMATION()
        found_matches = 0
        
        while kernel32.VirtualQueryEx(raw_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
                try:
                    data = pm.read_bytes(mbi.BaseAddress, mbi.RegionSize)
                    # We look for "Seat 1" or "Hand #" or "Total pot" just in case Hand # isn't used.
                    signatures = [b"Hand #", b"Seat 1", b"Total pot", b"Ignition Hand"]
                    
                    for sig in signatures:
                        sig_16 = sig.decode('utf-8').encode('utf-16le')
                        if sig in data or sig_16 in data:
                            print(f"    [!] FOUND SIGNATURE '{sig}' in PID {pid} at region {hex(mbi.BaseAddress)}!")
                            with open(f"memory_dump_PID{pid}.txt", "ab") as f:
                                # dump the snippet surrounding the data
                                idx = data.find(sig)
                                if idx == -1: idx = data.find(sig_16)
                                
                                snippet = data[max(0, idx-500) : min(len(data), idx+2000)]
                                f.write(f"\n--- MATCH '{sig}' ---\n".encode('utf-8'))
                                f.write(snippet)
                            found_matches += 1
                            break # Go to next memory region
                except:
                    pass
            address += mbi.RegionSize
            
        print(f"[*] PID {pid} scan complete. Found {found_matches} hitting regions.")
    except Exception as e:
        print(f"[X] Failed to scan PID {pid}: {e}")

if __name__ == "__main__":
    print("Searching for Ignition Casino processes...")
    pids = find_ignition_pids()
    if not pids:
        print("No Ignition processes found! Make sure the client is open.")
    else:
        print(f"Found Ignition PIDs: {pids}. Ignition is an Electron app, so we must scan ALL of its renderer processes.")
        for p in pids:
            scan_process(p)
    print("Done. Look for 'memory_dump_PID<...>.txt' files in this folder!")
