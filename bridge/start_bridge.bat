@echo off
rem DotaCS: double-click to start the bridge
cd /d "%~dp0"
chcp 65001 >nul
python bridge.py
pause
