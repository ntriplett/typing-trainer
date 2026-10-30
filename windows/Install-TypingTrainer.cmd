@echo off
rem Double-click to install (or repair) Typing Trainer for this Windows user.
rem No admin needed. It fetches install.ps1 from the newest GitHub release
rem and runs it; your progress is kept if it's already installed.
title Typing Trainer installer
echo Installing Typing Trainer...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $f=Join-Path $env:TEMP 'typing-trainer-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://github.com/ntriplett/typing-trainer/releases/latest/download/install.ps1' -OutFile $f; & $f"
if errorlevel 1 (
  echo.
  echo Something went wrong. Press any key to close.
  pause >nul
  exit /b 1
)
timeout /t 5
