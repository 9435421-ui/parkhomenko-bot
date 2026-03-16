#!/bin/bash
SERVER="root@176.124.219.183"
BOT_DIR="/root/PARKHOMENKO_BOT"

echo "📦 Копируем файлы на сервер..."

scp Жюль/config.py $SERVER:$BOT_DIR/
scp Жюль/main.py $SERVER:$BOT_DIR/
scp Жюль/database/db.py $SERVER:$BOT_DIR/database/
scp Жюль/agents/content_agent.py $SERVER:$BOT_DIR/agents/
scp Жюль/utils/voice_handler.py $SERVER:$BOT_DIR/utils/
scp handlers/admin.py $SERVER:$BOT_DIR/handlers/
scp services/scout_parser.py $SERVER:$BOT_DIR/services/
scp services/lead_hunter/hunter.py $SERVER:$BOT_DIR/services/lead_hunter/

echo "🚀 Перезапускаем бота..."
ssh $SERVER "systemctl restart anton.service && sleep 8 && journalctl -u anton.service -n 20 --no-pager"
