@echo off
title DotaCS
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0files\dotacs.ps1" -Mode uninstall
