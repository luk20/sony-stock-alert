@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 소니 입고 알리미
echo ============================================
echo   소니 RX100M7 입고 알리미 (텔레그램)
echo   종료하려면 이 창에서 Ctrl+C 를 누르세요.
echo ============================================
echo.
py sony_stock_alert.py
echo.
echo 프로그램이 종료되었습니다.
pause
