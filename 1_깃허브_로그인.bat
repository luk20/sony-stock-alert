@echo off
title GitHub Login
echo ============================================
echo   GitHub Login
echo ============================================
echo.
echo  Steps:
echo   1) A one-time code will appear (e.g. ABCD-1234). Copy it.
echo   2) Press Enter -^> browser opens
echo   3) Sign in to GitHub (or Sign up if no account)
echo   4) Paste the code, click the green "Authorize" button
echo   5) Come BACK to this black window and wait for:
echo        Logged in as (your-id)
echo   6) Only then close this window.
echo.
echo  If it asks questions, choose with arrow keys + Enter:
echo    - GitHub.com
echo    - HTTPS
echo    - Login with a web browser
echo.
pause
echo.
"C:\Program Files\GitHub CLI\gh.exe" auth login --hostname github.com --git-protocol https --web
echo.
echo ============================================
echo  If you see "Logged in as ..." above = SUCCESS.
echo  Close this window and tell Claude: done
echo ============================================
pause
