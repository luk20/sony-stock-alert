@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 텔레그램 챗ID 확인
py 챗ID_확인.py
echo.
pause
