@echo off
cd /d "%~dp0"
if exist ".git\index.lock" del /f /q ".git\index.lock" 2>nul
git add services/lead_hunter/discovery.py
git commit -m "fix(discovery): игнорировать SCOUT_KEYWORDS если менее 5 слов, использовать расширенный список

- Если SCOUT_KEYWORDS содержит менее 5 слов (например, только 'чат'), используется расширенный список
- Это предотвращает ситуацию, когда бот ищет только по одному ключевому слову
- Добавлено логирование выбора источника ключевых слов"
git push origin main
pause
