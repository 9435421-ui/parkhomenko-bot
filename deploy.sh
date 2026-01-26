#!/bin/bash
# Deployment script for Timeweb server - LAD V KVARTIRE

echo "Pulling latest changes from the branch..."
# Replace with the actual branch name if not master
git pull

echo "Installing/Updating dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
python3 database.py

echo "Restarting the Unified Bot (LAD V KVARTIRE)..."
pkill -f bot_unified.py || true
nohup python3 bot_unified.py > bot.log 2>&1 &

echo "Restarting the Content Agent (Optional)..."
# pkill -f auto_poster.py || true
# nohup python3 auto_poster.py > poster.log 2>&1 &

echo "Deployment complete! Bot is running in the background."
