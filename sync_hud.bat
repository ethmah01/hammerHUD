@echo off
set /p msg="Enter commit message (default: antigravity update): "
if "%msg%"=="" set msg=antigravity update

echo.
echo === Adding changes ===
git add .

echo.
echo === Committing changes ===
git commit -m "%msg%"

echo.
echo === Pushing to GitHub ===
git push origin main

echo.
echo === Sync Complete ===
pause
