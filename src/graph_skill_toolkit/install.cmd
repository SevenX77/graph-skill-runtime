@echo off
setlocal DisableDelayedExpansion
set "NODE_OPTIONS="
set "NODE_PATH="
if not exist "%~dp0runtimes\node\node.exe" (
  echo Extract the complete Windows Graph Skill archive before running this installer.
  pause
  exit /b 1
)
"%~dp0runtimes\node\node.exe" "%~dp0bin\graph-skill.mjs" install %*
if errorlevel 1 (
  echo Installation did not complete. Read the error above; existing conflicts are preserved.
  if "%~1"=="" pause
  exit /b 1
)
echo Restart Codex Desktop and Claude Code Desktop, then follow README.md.
if "%~1"=="" pause
