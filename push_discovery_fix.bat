@echo off
echo ========================================
echo Git Commit and Push Script
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Removing lock file...
if exist ".git\index.lock" (
    del /f /q ".git\index.lock" 2>nul
    timeout /t 1 /nobreak >nul
    echo Lock file removed.
) else (
    echo No lock file found.
)

echo.
echo [2/4] Adding files to staging...
git add services/lead_hunter/discovery.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to add files.
    pause
    exit /b 1
)
echo Files added successfully.

echo.
echo [3/4] Creating commit...
git commit -m "fix(discovery): игнорировать SCOUT_KEYWORDS если менее 5 слов, использовать расширенный список"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create commit.
    pause
    exit /b 1
)
echo Commit created successfully.

echo.
echo [4/4] Pushing to remote...
git push origin main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to push. Check your network connection and GitHub credentials.
    echo.
    echo If you see authentication error, you may need to:
    echo 1. Use GitHub Desktop or VS Code Git interface
    echo 2. Or configure Git credentials manually
    pause
    exit /b 1
)
echo.
echo ========================================
echo SUCCESS: Changes pushed to remote!
echo ========================================
pause
