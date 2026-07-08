@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Telegram chat_id Finder
py find_chat_id.py
echo.
pause
