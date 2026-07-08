@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Restock Alerter (Local)
echo ============================================
echo   Restock Alerter - Local Runner
echo   Products: products.json / Settings: config.json
echo   Press Ctrl+C in this window to stop.
echo ============================================
echo.
py sony_stock_alert.py
echo.
echo Program exited.
pause
