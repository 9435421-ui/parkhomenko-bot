# Скрипт для быстрого коммита и пуша изменений
# Использование: .\scripts\git_push.ps1 "описание коммита"

param(
    [Parameter(Mandatory=$true)]
    [string]$CommitMessage
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Git Push Script" -ForegroundColor Cyan
Write-Host "Repository: https://github.com/9435421-ui/parkhomenko-bot" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot\..

# Удаляем lock файл если есть
if (Test-Path ".git\index.lock") {
    Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Lock file removed" -ForegroundColor Green
}

# Проверяем статус
Write-Host "[1/4] Checking status..." -ForegroundColor Yellow
$status = git status --short
if (-not $status) {
    Write-Host "⚠️  No changes to commit" -ForegroundColor Yellow
    exit 0
}

Write-Host "Changes found:" -ForegroundColor Green
git status --short

# Добавляем все изменения
Write-Host ""
Write-Host "[2/4] Adding files..." -ForegroundColor Yellow
git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR: Failed to add files" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Files added" -ForegroundColor Green

# Создаем коммит
Write-Host ""
Write-Host "[3/4] Creating commit..." -ForegroundColor Yellow
git commit -m $CommitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR: Failed to create commit" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Commit created" -ForegroundColor Green

# Пушим
Write-Host ""
Write-Host "[4/4] Pushing to origin/main..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR: Failed to push" -ForegroundColor Red
    Write-Host "Check your GitHub credentials and network connection" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ SUCCESS: Changes pushed to GitHub!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Repository: https://github.com/9435421-ui/parkhomenko-bot" -ForegroundColor Cyan
