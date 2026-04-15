"""
Diagnostic 3: Check if we can connect to Ignition's Chrome DevTools Protocol.
This will:
1. Check Ignition's command line args for an existing debug port
2. Scan common debug ports
3. Try to list available CDP targets
4. If connected, try to monitor WebSocket traffic briefly
"""
import psutil
import json
import time
import socket
import sys

try:
    import urllib.request
    HAS_URLLIB = True
except:
    HAS_URLLIB = False

def find_ignition_debug_port():
    """Check if Ignition was launched with a remote debugging port."""
    print("[*] Step 1: Checking Ignition process command line args...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            if name and ('IgnitionCasino' in name or 'Lobby' in name):
                cmdline = proc.info.get('cmdline', [])
                if cmdline:
                    cmd_str = ' '.join(cmdline)
                    if '--remote-debugging-port' in cmd_str:
                        for arg in cmdline:
                            if '--remote-debugging-port=' in arg:
                                port = arg.split('=')[1]
                                print(f"    [!] Found debug port in PID {proc.info['pid']}: {port}")
                                return int(port)
                    # Print what we found for investigation
                    print(f"    PID {proc.info['pid']} ({name}): {cmd_str[:200]}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return None

def scan_debug_ports():
    """Scan common Chrome/Electron debug ports."""
    print("\n[*] Step 2: Scanning common debug ports...")
    common_ports = [9222, 9229, 9333, 9515, 8315, 5858, 2345, 9223, 9224, 9225]
    
    found_ports = []
    for port in common_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                print(f"    [!] Port {port} is OPEN!")
                # Try to get CDP JSON
                try:
                    resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=2)
                    data = json.loads(resp.read())
                    print(f"        CDP targets found: {len(data)}")
                    for t in data[:5]:
                        print(f"        - Type: {t.get('type')}, Title: {t.get('title', 'N/A')[:80]}, URL: {t.get('url', 'N/A')[:80]}")
                    found_ports.append(port)
                except Exception as e:
                    print(f"        Port open but no CDP response: {e}")
            else:
                pass  # Port closed, don't print
        except:
            pass
    
    return found_ports

def scan_all_listening_ports():
    """Find all ports that Ignition processes are listening on."""
    print("\n[*] Step 3: Finding all ports opened by Ignition processes...")
    
    ignition_pids = set()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and ('IgnitionCasino' in name or 'Lobby' in name):
                ignition_pids.add(proc.info['pid'])
        except:
            continue
    
    if not ignition_pids:
        print("    No Ignition processes found!")
        return []
    
    print(f"    Ignition PIDs: {ignition_pids}")
    
    found_ports = []
    for conn in psutil.net_connections(kind='tcp'):
        if conn.pid in ignition_pids and conn.status == 'LISTEN':
            port = conn.laddr.port
            print(f"    [!] PID {conn.pid} is LISTENING on port {port}")
            found_ports.append(port)
    
    # Also check for established WebSocket connections
    ws_connections = []
    for conn in psutil.net_connections(kind='tcp'):
        if conn.pid in ignition_pids and conn.status == 'ESTABLISHED':
            ws_connections.append((conn.pid, conn.laddr, conn.raddr))
    
    if ws_connections:
        print(f"\n    [*] Found {len(ws_connections)} established TCP connections from Ignition:")
        for pid, local, remote in ws_connections[:15]:
            print(f"        PID {pid}: {local.ip}:{local.port} -> {remote.ip}:{remote.port}")
    
    return found_ports

def try_cdp_connect(port):
    """Try to connect to CDP and list WebSocket targets."""
    print(f"\n[*] Step 4: Attempting CDP connection on port {port}...")
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=3)
        targets = json.loads(resp.read())
        
        print(f"    Found {len(targets)} targets:")
        for i, t in enumerate(targets):
            print(f"    [{i}] Type: {t.get('type')}, Title: {t.get('title', 'N/A')}")
            print(f"        URL: {t.get('url', 'N/A')[:100]}")
            ws_url = t.get('webSocketDebuggerUrl', 'N/A')
            print(f"        WS Debug URL: {ws_url}")
        
        # Also check /json/version
        try:
            resp2 = urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=3)
            version = json.loads(resp2.read())
            print(f"\n    Browser Version: {version.get('Browser', 'Unknown')}")
            print(f"    Protocol Version: {version.get('Protocol-Version', 'Unknown')}")
            print(f"    V8 Version: {version.get('V8-Version', 'Unknown')}")
        except:
            pass
            
        return True
    except Exception as e:
        print(f"    Failed to connect: {e}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNOSTIC 3: Chrome DevTools Protocol (CDP) Discovery for Ignition")
    print("=" * 80)
    
    # Step 1: Check command line args
    declared_port = find_ignition_debug_port()
    
    # Step 2: Scan common ports
    cdp_ports = scan_debug_ports()
    
    # Step 3: Find all Ignition listening ports 
    ignition_ports = scan_all_listening_ports()
    
    # Step 4: Try connecting to any discovered ports
    all_ports = set()
    if declared_port:
        all_ports.add(declared_port)
    all_ports.update(cdp_ports)
    all_ports.update(ignition_ports)
    
    connected = False
    if all_ports:
        for port in sorted(all_ports):
            if try_cdp_connect(port):
                connected = True
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if connected:
        print("[+] SUCCESS: CDP connection is available!")
        print("    We can intercept WebSocket traffic to capture live hand data.")
        print("    Next step: Build a WebSocket frame listener.")
    elif ignition_ports:
        print("[~] PARTIAL: Ignition has open ports but no standard CDP endpoint.")
        print("    We may need to relaunch Ignition with --remote-debugging-port=9222")
    else:
        print("[-] NO CDP AVAILABLE.")
        print("    Ignition was not launched with debugging enabled.")
        print("")
        print("    TO FIX: We need to add a debug flag to Ignition's launch shortcut:")
        print("    1. Find your IgnitionCasino.exe shortcut")
        print("    2. Right-click -> Properties")
        print("    3. In 'Target', add to the END:  --remote-debugging-port=9222")
        print("    4. Restart Ignition using that shortcut")
        print("    5. Run this diagnostic again")
    
    print("=" * 80)
