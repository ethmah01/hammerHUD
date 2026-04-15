"""
Diagnostic 4: Find and optionally patch the Ignition protocol handler
in the Windows Registry to inject --remote-debugging-port=9222.
"""
import winreg
import sys

# Common protocol handler names Electron poker clients use
PROTOCOL_NAMES = [
    "ignitioncasino",
    "ignitioncasino-eu-poker",
    "ignition-casino",
    "ignitionpoker",
    "IgnitionCasino",
]

def find_protocol_handler():
    """Search the registry for the Ignition protocol handler."""
    print("[*] Searching Windows Registry for Ignition protocol handlers...\n")
    
    found = []
    
    for proto_name in PROTOCOL_NAMES:
        for hive, hive_name in [(winreg.HKEY_CLASSES_ROOT, "HKCR"), (winreg.HKEY_CURRENT_USER, "HKCU")]:
            # Check direct protocol key
            try:
                key_path = proto_name
                key = winreg.OpenKey(hive, key_path)
                print(f"  [!] Found registry key: {hive_name}\\{key_path}")
                
                # Check for shell\open\command
                try:
                    cmd_path = f"{key_path}\\shell\\open\\command"
                    cmd_key = winreg.OpenKey(hive, cmd_path)
                    value, _ = winreg.QueryValueEx(cmd_key, "")
                    print(f"      Command: {value}")
                    found.append((hive, hive_name, cmd_path, value))
                    winreg.CloseKey(cmd_key)
                except FileNotFoundError:
                    pass
                    
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            
            # Also check under Software\Classes
            try:
                key_path = f"Software\\Classes\\{proto_name}"
                key = winreg.OpenKey(hive, key_path)
                print(f"  [!] Found registry key: {hive_name}\\{key_path}")
                
                try:
                    cmd_path = f"{key_path}\\shell\\open\\command"
                    cmd_key = winreg.OpenKey(hive, cmd_path)
                    value, _ = winreg.QueryValueEx(cmd_key, "")
                    print(f"      Command: {value}")
                    found.append((hive, hive_name, cmd_path, value))
                    winreg.CloseKey(cmd_key)
                except FileNotFoundError:
                    pass
                    
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
    
    # Also do a broader search for anything mentioning IgnitionCasino or Lobby.exe
    print("\n[*] Doing broader search for IgnitionCasino/Lobby.exe in HKCR...")
    try:
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(winreg.HKEY_CLASSES_ROOT, i)
                if 'ignition' in subkey_name.lower() or 'lobby' in subkey_name.lower():
                    print(f"  [?] Found potentially related key: HKCR\\{subkey_name}")
                    try:
                        cmd_path = f"{subkey_name}\\shell\\open\\command"
                        cmd_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, cmd_path)
                        value, _ = winreg.QueryValueEx(cmd_key, "")
                        print(f"      Command: {value}")
                        found.append((winreg.HKEY_CLASSES_ROOT, "HKCR", cmd_path, value))
                        winreg.CloseKey(cmd_key)
                    except FileNotFoundError:
                        pass
                i += 1
            except OSError:
                break
    except Exception as e:
        print(f"  Error during broad search: {e}")
    
    return found

def patch_handler(hive, hive_name, cmd_path, current_value):
    """Add --remote-debugging-port=9222 to the command if not already present."""
    DEBUG_FLAG = "--remote-debugging-port=9222"
    
    if DEBUG_FLAG in current_value:
        print(f"\n[*] Debug flag already present in {hive_name}\\{cmd_path}")
        return
    
    # Insert the debug flag before the "%1" argument placeholder
    if '"%1"' in current_value:
        new_value = current_value.replace('"%1"', f'{DEBUG_FLAG} "%1"')
    elif '%1' in current_value:
        new_value = current_value.replace('%1', f'{DEBUG_FLAG} %1')
    else:
        # Just append it
        new_value = current_value.rstrip('"') + f' {DEBUG_FLAG}"' if current_value.endswith('"') else current_value + f' {DEBUG_FLAG}'
    
    print(f"\n[*] Proposed patch for {hive_name}\\{cmd_path}:")
    print(f"    BEFORE: {current_value}")
    print(f"    AFTER:  {new_value}")
    
    confirm = input("\n    Apply this patch? (yes/no): ").strip().lower()
    if confirm == 'yes':
        try:
            key = winreg.OpenKey(hive, cmd_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, new_value)
            winreg.CloseKey(key)
            print("    [+] PATCH APPLIED SUCCESSFULLY!")
            print("    Now close Ignition fully, log in again through the browser,")
            print("    and run diagnostic3.py to verify the debug port is open.")
        except PermissionError:
            print("    [X] Permission denied! Try running this script as Administrator:")
            print("        Right-click Command Prompt -> Run as Administrator")
        except Exception as e:
            print(f"    [X] Failed to apply patch: {e}")
    else:
        print("    Patch not applied.")

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNOSTIC 4: Ignition Protocol Handler Registry Patcher")
    print("=" * 80)
    print()
    
    handlers = find_protocol_handler()
    
    if not handlers:
        print("\n[-] No Ignition protocol handlers found in the registry!")
        print("    The app may use a different registration method.")
    else:
        print(f"\n[+] Found {len(handlers)} handler(s). We can patch them to enable CDP.")
        for hive, hive_name, cmd_path, value in handlers:
            patch_handler(hive, hive_name, cmd_path, value)
    
    print("\n" + "=" * 80)
