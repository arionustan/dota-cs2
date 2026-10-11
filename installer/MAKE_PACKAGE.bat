@echo off
title DotaCS: make package
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_package.ps1"
