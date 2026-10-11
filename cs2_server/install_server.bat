@echo off
rem DotaCS: double-click to install the CS2 server
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_server.ps1"
