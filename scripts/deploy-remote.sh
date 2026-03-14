#!/usr/bin/env bash
# Деплой и проверка бота на 176.124.219.183
# Использование: ./deploy-remote.sh deploy | check

set -e

SERVER="${DEPLOY_HOST:-176.124.219.183}"
USER="${DEPLOY_USER:-root}"
PATH_ON_SERVER="${DEPLOY_PATH:-~/Lad_v_kvartire_bot}"

run_ssh() {
  ssh "$USER@$SERVER" "$@"
}

case "${1:-}" in
  deploy)
    echo "Запуск деплоя на $USER@$SERVER..."
    run_ssh "cd $PATH_ON_SERVER && git pull && docker compose up -d --build 2>/dev/null || (source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart lad-bot)"
    echo "Готово."
    ;;
  check)
    echo "Проверка статуса на $USER@$SERVER..."
    run_ssh "cd $PATH_ON_SERVER 2>/dev/null && (docker compose ps && docker compose logs --tail=30 bot) || (sudo systemctl status lad-bot --no-pager; journalctl -u lad-bot -n 30 --no-pager)"
    ;;
  *)
    echo "Использование: $0 deploy | check"
    echo "  deploy — обновить код и перезапустить на сервере"
    echo "  check  — показать статус и последние логи"
    exit 1
    ;;
esac
