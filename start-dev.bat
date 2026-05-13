@echo off
setlocal

cd /d "%~dp0"

set "ROOT_DIR=%CD%"
set "FRONTEND_DIR=%ROOT_DIR%\m_flow-frontend"
set "BACKEND_TITLE=M-Flow Backend Dev"
set "FRONTEND_TITLE=M-Flow Frontend Dev"
set "PNPM_WORKSPACE_FILE=%FRONTEND_DIR%\pnpm-workspace.yaml"

if not exist "%ROOT_DIR%\pyproject.toml" (
  echo [ERROR] Please run this script from the repository root.
  exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
  echo [ERROR] Frontend project not found: %FRONTEND_DIR%\package.json
  exit /b 1
)

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "uv" was not found in PATH.
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "pnpm" was not found in PATH.
  exit /b 1
)

if not exist "%PNPM_WORKSPACE_FILE%" (
  echo [ERROR] Missing frontend config: %PNPM_WORKSPACE_FILE%
  exit /b 1
)

findstr /C:"allowBuilds:" "%PNPM_WORKSPACE_FILE%" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Frontend pnpm build approval config is missing in pnpm-workspace.yaml.
  echo [ERROR] Expected allowBuilds entries for required packages.
  exit /b 1
)

echo [INFO] Starting backend...
start "%BACKEND_TITLE%" cmd /k cd /d "%ROOT_DIR%" ^&^& uv run python -m m_flow.api.client

echo [INFO] Starting frontend...
start "%FRONTEND_TITLE%" cmd /k cd /d "%FRONTEND_DIR%" ^&^& pnpm dev

echo.
echo M-flow dev services launched.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API docs: http://localhost:8000/docs
echo.
echo Use stop-dev.bat to stop both services.
exit /b 0
