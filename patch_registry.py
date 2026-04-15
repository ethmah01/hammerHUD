"""
Patch the poker-ign registry to use our wrapper script,
or restore the original IgnitionCasino.exe entry.
"""
import winreg
import sys
import os

WRAPPER_PATH = os.path.abspath("launch_ignition_debug.cmd")
ORIGINAL_CMD = r'"C:\Program Files (x86)\Ignition Casino Poker\IgnitionCasino.exe" "%1"'
WRAPPER_CMD = f'cmd /c "{WRAPPER_PATH}" "%1"'

TARGETS = [
    (winreg.HKEY_CLASSES_ROOT, r"poker-ign\shell\open\command", "HKCR"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes\poker-ign\shell\open\command", "HKCU"),
]

def read_current(hive, path):
    try:
        key = winreg.OpenKey(hive, path)
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        return value
    except:
        return None

def write_value(hive, path, value):
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        return True
    except PermissionError:
        print("    [X] Permission denied — run as Administrator!")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("  Ignition Wrapper Launcher Patcher")
    print("=" * 70)
    
    print(f"\n  Wrapper script: {WRAPPER_PATH}")
    print(f"  Wrapper exists: {os.path.exists(WRAPPER_PATH)}")
    
    print("\nCurrent registry values:")
    for hive, path, name in TARGETS:
        val = read_current(hive, path)
        if val:
            print(f"  [{name}] {val}")

    print(f"\nOptions:")
    print(f"  1. PATCH   — Point registry to our wrapper script")
    print(f"  2. RESTORE — Restore original IgnitionCasino.exe entry")
    print(f"  3. EXIT")
    
    choice = input("\nChoose (1/2/3): ").strip()
    
    if choice == "1":
        # First, undo the old debug-flag patch if present
        print("\nPatching to wrapper...\n")
        for hive, path, name in TARGETS:
            print(f"  [{name}]")
            print(f"    Setting to: {WRAPPER_CMD}")
            if write_value(hive, path, WRAPPER_CMD):
                print(f"    [+] DONE!")
        
        print("\n" + "-" * 70)
        print("NEXT STEPS:")
        print("  1. Close Ignition completely")
        print("  2. Log in through the browser again")
        print("  3. The wrapper will auto-relaunch with debug port 9222")
        print("  4. Run:  python diagnostic3.py")
        print("-" * 70)
    
    elif choice == "2":
        print("\nRestoring original...\n")
        for hive, path, name in TARGETS:
            print(f"  [{name}]")
            print(f"    Setting to: {ORIGINAL_CMD}")
            if write_value(hive, path, ORIGINAL_CMD):
                print(f"    [+] RESTORED!")
    
    else:
        print("Exiting.")
