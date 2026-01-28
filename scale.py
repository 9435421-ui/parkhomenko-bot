import os
import argparse
from dotenv import load_dotenv

def scale_ecosystem(brand_name, channel_id, cities):
    """
    Масштабирует экосистему на новые города/каналы, обновляя .env
    """
    env_file = ".env"

    # Загружаем текущий .env
    load_dotenv(env_file)

    print(f"🚀 Масштабирование бренда: {brand_name}")
    print(f"📍 Города: {cities}")
    print(f"📺 ID канала: {channel_id}")

    # Добавляем новые записи в конец файла
    with open(env_file, "a") as f:
        f.write(f"\n# Scaled Brand: {brand_name}\n")
        f.write(f"CONTENT_CHANNEL_ID_{abs(int(channel_id))}={channel_id}\n")
        f.write(f"CITIES_{abs(int(channel_id))}={cities}\n")

    print(f"✅ Записи добавлены в {env_file}")
    print("🔔 Не забудьте перезапустить бота для применения изменений.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scale TERION Ecosystem")
    parser.add_argument("--brand", required=True, help="Brand name (e.g. 'ТЕРИОН: Екатеринбург')")
    parser.add_argument("--channel_id", required=True, help="Telegram Channel ID")
    parser.add_argument("--cities", required=True, help="Covered cities (comma separated)")

    args = parser.parse_args()
    scale_ecosystem(args.brand, args.channel_id, args.cities)
