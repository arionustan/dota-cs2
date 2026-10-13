@echo off
title WC3 probe
cd /d "%~dp0"
chcp 65001 >nul
python wc3_probe.py
