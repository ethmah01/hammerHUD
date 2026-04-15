@echo off
REM Wrapper that launches Ignition with CDP enabled.
REM Step 1: Call the original launcher to handle auth
start "" "C:\Program Files (x86)\Ignition Casino Poker\IgnitionCasino.exe" %*

REM Step 2: Wait for Lobby.exe to fully start
timeout /t 5 /nobreak > nul

REM Step 3: Kill the main Lobby.exe (not renderer/gpu children) and relaunch with debug flag
REM We identify the main process by its "launcher=launcher" argument
for /f "tokens=2" %%i in ('wmic process where "name='Lobby.exe' and commandline like '%%launcher=launcher%%'" get processid /format:value ^| findstr ProcessId') do (
    echo Killing main Lobby.exe PID: %%i
    taskkill /PID %%i /F > nul 2>&1
)

REM Step 4: Wait for child processes to die
timeout /t 3 /nobreak > nul

REM Step 5: Relaunch Lobby.exe with the debug port
start "" "C:\Program Files (x86)\Ignition Casino Poker\Lobby.exe" --remote-debugging-port=9222 launcher=launcher "--storageFolder=C:\Program Files (x86)\Ignition Casino Poker"
