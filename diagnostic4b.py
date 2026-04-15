"""
Diagnostic 4b: Deep registry search for anything related to Ignition.
Searches ALL of HKCR and HKCU\Software\Classes for command values
containing 'Ignition' or 'Lobby.exe'.
"""
import winreg
import os

def search_commands_in_hive(hive, hive_name, root_path=""):
    """Recursively search for shell\open\command values containing Ignition."""
    results = []
    
    try:
        if root_path:
            root_key = winreg.OpenKey(hive, root_path)
        else:
            root_key = winreg.OpenKey(hive, "")
    except:
        return results
    
    i = 0
    subkeys = []
    while True:
        try:
            subkeys.append(winreg.EnumKey(root_key, i))
            i += 1
        except OSError:
            break
    winreg.CloseKey(root_key)
    
    for subkey_name in subkeys:
        full_path = f"{root_path}\\{subkey_name}" if root_path else subkey_name
        
        # Check if this key has a shell\open\command
        cmd_path = f"{full_path}\\shell\\open\\command"
        try:
            cmd_key = winreg.OpenKey(hive, cmd_path)
            value, _ = winreg.QueryValueEx(cmd_key, "")
            winreg.CloseKey(cmd_key)
            
            if value and ('ignition' in value.lower() or 'lobby.exe' in value.lower()):
                results.append((hive, hive_name, full_path, cmd_path, value))
        except:
            pass
    
    return results

def search_url_associations():
    """Check RegisteredApplications and URL Associations."""
    print("[*] Checking URL protocol associations...\n")
    
    # Check HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations
    try:
        base = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base)
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
                if 'ignition' in name.lower():
                    print(f"  [!] Found URL association: {name}")
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except:
        pass

def find_in_app_paths():
    """Check App Paths registration."""
    print("[*] Checking App Paths...\n")
    paths_to_check = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    
    for hive, base_path in paths_to_check:
        try:
            key = winreg.OpenKey(hive, base_path)
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                    if 'ignition' in name.lower() or 'lobby' in name.lower():
                        sub_key = winreg.OpenKey(hive, f"{base_path}\\{name}")
                        try:
                            val, _ = winreg.QueryValueEx(sub_key, "")
                            print(f"  [!] Found: {name} -> {val}")
                        except:
                            pass
                        winreg.CloseKey(sub_key)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except:
            pass

def find_protocol_in_capabilities():
    """Check RegisteredApplications for capabilities."""
    print("[*] Checking RegisteredApplications...\n")
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\RegisteredApplications")
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(key, i)
                if 'ignition' in name.lower():
                    print(f"  [!] Found: {name} -> {val}")
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except:
        pass

def find_exe_in_install_dirs():
    """Find the actual Ignition install and check for config files."""
    print("[*] Checking Ignition install directory for config files...\n")
    
    install_dir = r"C:\Program Files (x86)\Ignition Casino Poker"
    if os.path.exists(install_dir):
        print(f"  Install dir: {install_dir}")
        for f in os.listdir(install_dir):
            fpath = os.path.join(install_dir, f)
            size = os.path.getsize(fpath) if os.path.isfile(fpath) else "DIR"
            print(f"    {f:40s} {size}")
    
    # Check user data dir
    user_data = os.path.expandvars(r"%APPDATA%\ignitioncasino-eu-poker")
    if os.path.exists(user_data):
        print(f"\n  User data dir: {user_data}")
        for root, dirs, files in os.walk(user_data):
            level = root.replace(user_data, '').count(os.sep)
            if level > 2:
                continue
            indent = '    ' + '  ' * level
            print(f"{indent}{os.path.basename(root)}/")
            if level <= 1:
                for f in files[:10]:
                    print(f"{indent}  {f}")
                if len(files) > 10:
                    print(f"{indent}  ... and {len(files)-10} more files")

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNOSTIC 4b: Deep Registry & Install Search for Ignition")
    print("=" * 80)
    print()
    
    # Search HKCR top-level
    print("[*] Searching HKCR for commands referencing Ignition/Lobby.exe...")
    results = search_commands_in_hive(winreg.HKEY_CLASSES_ROOT, "HKCR")
    
    # Search HKCU\Software\Classes
    print("[*] Searching HKCU\\Software\\Classes...")
    results += search_commands_in_hive(winreg.HKEY_CURRENT_USER, "HKCU", "Software\\Classes")
    
    # Search HKLM\Software\Classes 
    print("[*] Searching HKLM\\Software\\Classes...")
    results += search_commands_in_hive(winreg.HKEY_LOCAL_MACHINE, "HKLM", "SOFTWARE\\Classes")
    
    if results:
        print(f"\n[+] Found {len(results)} protocol handler(s):")
        for hive, hive_name, key_path, cmd_path, value in results:
            print(f"\n  Key:     {hive_name}\\{key_path}")
            print(f"  Command: {value}")
    else:
        print("\n[-] No protocol handlers found referencing Ignition.")
    
    print()
    search_url_associations()
    find_in_app_paths()
    find_protocol_in_capabilities()
    find_exe_in_install_dirs()
    
    print("\n" + "=" * 80)
