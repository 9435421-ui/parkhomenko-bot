# Полная остановка бота на сервере (цепочка рестартов)

## Результат проверки кода

- **subprocess.Popen, multiprocessing, os.exec** — в проекте **нет**. Бот не порождает дочерние процессы из кода.
- **Бесконечные циклы** — есть только внутри одного процесса (scout_parser, run_all run_vk_parser при пустом списке VK). Они **не запускают** новый процесс бота, только держат asyncio-задачу.
- **Авторестарт при сбоях** — в **main.py** и **run_all.py** нет логики «при падении запустить себя заново». Один процесс, один `asyncio.run(main())`.

## Откуда два процесса и «воскрешение»

1. **Два разных unit-файла в репозитории:**
   - `parkhomenko_bot.service` → `venv/bin/python3 main.py` (Restart=always)
   - `anton_bot.service` → `venv/bin/python run_all.py` (Restart=always)
   Если на сервере в systemd включены **оба** (или скопированы под разными именами), будут **два** процесса: один от `main.py`, второй от `run_all.py`. Один через `python3`, другой через `python` — отсюда «один через venv/bin/python, другой через python».

2. **pm2** — при `pm2 save` и `pm2 startup` после перезагрузки (или при срабатывании pm2-resurrect) pm2 сам поднимается и восстанавливает сохранённые процессы.

3. **Timeweb** — в панели хостинга может быть автозапуск приложения или скрипта после перезагрузки/сбоя.

## Команды для ПОЛНОЙ остановки (выполнять на сервере по порядку)

Подключитесь по SSH и выполните:

```bash
# 1. Остановить и отключить все unit'ы бота (все возможные имена)
sudo systemctl stop anton_bot parkhomenko_bot anton-2-bot lad-bot 2>/dev/null
sudo systemctl disable anton_bot parkhomenko_bot anton-2-bot lad-bot 2>/dev/null

# 2. Убить pm2 и отменить автозапуск pm2 при загрузке системы
pm2 kill
pm2 unstartup systemd 2>/dev/null || true

# 3. Убить все процессы Python, связанные с ботом (подставьте свой путь, если не /root)
pkill -9 -f "PARKHOMENKO_BOT|parkhomenko-bot|main.py|run_all.py" 2>/dev/null || true

# 4. Добить оставшиеся (по пути к проекту)
ps aux | grep -E "main\.py|run_all\.py" | grep -v grep
# Если что-то осталось — убить по PID: kill -9 <PID>

# 5. Проверить, что systemd не держит бота (должно быть пусто или "not found")
systemctl list-units --all | grep -E "anton|parkhomenko|bot"
ls -la /etc/systemd/system/*.service | grep -E "anton|parkhomenko|bot"
# Если есть файлы — удалить или переименовать:
# sudo rm /etc/systemd/system/anton_bot.service
# sudo rm /etc/systemd/system/parkhomenko_bot.service
# sudo systemctl daemon-reload

# 6. Проверить cron (в т.ч. root)
crontab -l
sudo crontab -l -u root
```

После этого ни systemd, ни pm2, ни процессы по пути к боту не должны перезапускаться. Если процессы снова появятся — источник в панели Timeweb (автозапуск) или в другом скрипте/сервисе на сервере.

## Рекомендация: один способ запуска

Чтобы не было дублей, на сервере должен быть **один** способ запуска:

- **Либо** pm2: `pm2 start main.py --name anton-2-bot --interpreter /root/PARKHOMENKO_BOT/venv/bin/python` и больше **никаких** systemd-unit'ов для этого бота,
- **Либо** один systemd unit (один из: `anton_bot` или `parkhomenko_bot`), а pm2 для этого бота не использовать.

Оба unit'а (main.py и run_all.py) одновременно держать не нужно — это и даёт два процесса.
