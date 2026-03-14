# Git Push Script для TERION Bot
# Автоматически удаляет lock файл, добавляет изменения, коммитит и пушит

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Git Commit and Push Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Шаг 1: Удаление lock файла
Write-Host "[1/4] Removing lock file if exists..." -ForegroundColor Yellow
$lockFile = ".git\index.lock"
if (Test-Path $lockFile) {
    try {
        Remove-Item $lockFile -Force -ErrorAction Stop
        Write-Host "Lock file removed." -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Warning: Could not remove lock file: $_" -ForegroundColor Red
        Write-Host "Please close Cursor/VS Code and try again, or delete manually:" -ForegroundColor Yellow
        Write-Host "  Remove-Item '$lockFile' -Force" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "No lock file found." -ForegroundColor Green
}

# Небольшая задержка для освобождения файла
Start-Sleep -Seconds 1

# Шаг 2: Добавление файлов
Write-Host ""
Write-Host "[2/4] Adding files to staging..." -ForegroundColor Yellow
try {
    git add .
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Files added successfully." -ForegroundColor Green
    } else {
        Write-Host "⚠️  Warning: git add returned exit code $LASTEXITCODE" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Error adding files: $_" -ForegroundColor Red
    exit 1
}

# Шаг 3: Создание коммита
Write-Host ""
Write-Host "[3/4] Creating commit..." -ForegroundColor Yellow
$commitMessage = "feat: интеграция Hunter V3 & Content Engine - HOT_TRIGGERS, централизация публикации, прогревочный скан, восстановление цепочки визуалов"

try {
    git commit -m $commitMessage
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Commit created successfully." -ForegroundColor Green
    } else {
        Write-Host "⚠️  Warning: git commit returned exit code $LASTEXITCODE" -ForegroundColor Yellow
        Write-Host "This might mean there are no changes to commit." -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Error creating commit: $_" -ForegroundColor Red
    exit 1
}

# Шаг 4: Push в удаленный репозиторий
Write-Host ""
Write-Host "[4/4] Pushing to remote..." -ForegroundColor Yellow
try {
    git push origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "SUCCESS: All changes pushed to remote!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
    } else {
        Write-Host "❌ Error pushing to remote (exit code: $LASTEXITCODE)" -ForegroundColor Red
        Write-Host "Check your git credentials and network connection." -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Error pushing: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
