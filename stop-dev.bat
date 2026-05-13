@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "BACKEND_TITLE=M-Flow Backend Dev"
set "FRONTEND_TITLE=M-Flow Frontend Dev"

call :stop_process "%BACKEND_TITLE%" "backend"
call :stop_process "%FRONTEND_TITLE%" "frontend"
call :stop_port 8000 "backend"
call :stop_port 3000 "frontend"

echo [INFO] Stop command finished.
exit /b 0

:stop_process
set "WINDOW_TITLE=%~1"
set "SERVICE_NAME=%~2"

taskkill /FI "WINDOWTITLE eq %WINDOW_TITLE%*" /T /F >nul 2>nul
if errorlevel 1 (
  echo [INFO] %SERVICE_NAME% was not running.
) else (
  echo [INFO] Stopped %SERVICE_NAME% process tree.
)
exit /b 0

:stop_port
set "PORT=%~1"
set "SERVICE_NAME=%~2"
set "PORT_KILLED=0"

for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  taskkill /PID %%I /T /F >nul 2>nul
  if not errorlevel 1 (
    echo [INFO] Stopped %SERVICE_NAME% process on port %PORT% via PID %%I.
    set "PORT_KILLED=1"
  )
)

if "!PORT_KILLED!"=="0" (
  echo [INFO] No %SERVICE_NAME% process was listening on port %PORT%.
)
exit /b 0
