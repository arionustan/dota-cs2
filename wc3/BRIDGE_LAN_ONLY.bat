@echo off
title DotaWC3 LAN bridge
cd /d "%~dp0"
chcp 65001 >nul
python bridge_lan.py
pause
