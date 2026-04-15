import psutil
import ctypes
import os

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

def check_ignition():
    print("Checking for Ignition-related processes...")
    found = False
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if any(term.lower() in name.lower() for term in ['ignition', 'casino', 'poker', 'lobby', 'bovada', 'bodog']):
                print(f"Found match: {name} (PID: {proc.info['pid']})")
                found = True
                
                # Try to open process
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, proc.info['pid'])
                if handle:
                    print(f"  [SUCCESS] Successfully opened process {name}")
                    ctypes.windll.kernel32.CloseHandle(handle)
                else:
                    err = ctypes.windll.kernel32.GetLastError()
                    print(f"  [FAILED] Could not open process {name}. Error code: {err}")
                    if err == 5:
                        print("    -> Error 5 is 'Access Denied'. Try running as Administrator.")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not found:
        print("No processes matching 'ignition', 'casino', etc. found.")

if __name__ == "__main__":
    check_ignition()
