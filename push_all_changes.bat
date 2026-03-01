@echo off
echo ========================================
echo Git Commit and Push - All Changes
echo Repository: https://github.com/9435421-ui/parkhomenko-bot
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Removing lock file...
if exist ".git\index.lock" (
    del /f /q ".git\index.lock" 2>nul
    timeout /t 1 /nobreak >nul
    echo Lock file removed.
) else (
    echo No lock file found.
)

echo.
echo [2/5] Checking changes...
git status --short
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to check status.
    pause
    exit /b 1
)

echo.
echo [3/5] Adding files to staging...
git add services/lead_hunter/discovery.py
git add .vscode/settings.json
git add REPOSITORY.md
git add scripts/git_push.ps1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to add files.
    pause
    exit /b 1
)
echo Files added successfully.

echo.
echo [4/5] Creating commit...
git commit -m "fix(discovery): игнорировать SCOUT_KEYWORDS если менее 5 слов + настройки репозитория"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create commit.
    pause
    exit /b 1
)
echo Commit created successfully.

echo.
echo [5/5] Pushing to remote...
git push origin main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to push. Check your network connection and GitHub credentials.
    echo.
    echo If you see authentication error, try:
    echo 1. Use GitHub Desktop or VS Code Git interface
    echo 2. Or configure Git credentials manually
    pause
    exit /b 1
)
echo.
echo ========================================
echo SUCCESS: Changes pushed to GitHub!
echo ========================================
echo.
echo Repository: https://github.com/9435421-ui/parkhomenko-bot
pause
