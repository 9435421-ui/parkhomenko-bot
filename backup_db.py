"""
Скрипт для создания бэкапов базы данных
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем путь к базе данных из .env или используем значение по умолчанию
DATABASE_PATH = os.getenv("DATABASE_PATH", "parkhomenko_bot.db")


def backup_database():
    """Создание бэкапа базы данных"""
    
    # Путь к базе данных из конфигурации
    db_path = Path(DATABASE_PATH)
    
    if not db_path.exists():
        print("❌ База данных не найдена. Возможно, бот ещё не запускался.")
        return False
    
    # Создаём папку для бэкапов
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Генерируем имя файла с датой и временем
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"bot_db_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename
    
    # Копируем базу данных
    try:
        shutil.copy2(db_path, backup_path)
        
        # Получаем размер файла
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        
        print(f"✅ Бэкап успешно создан!")
        print(f"📁 Файл: {backup_path}")
        print(f"📊 Размер: {size_mb:.2f} MB")
        print(f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Удаляем старые бэкапы (старше 30 дней)
        cleanup_old_backups(backup_dir, days=30)
        
        return True
    
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
        return False


def cleanup_old_backups(backup_dir: Path, days: int = 30):
    """Удаление старых бэкапов"""
    import time
    
    now = time.time()
    deleted_count = 0
    
    for backup_file in backup_dir.glob("bot_db_backup_*.db"):
        # Проверяем возраст файла
        file_age_days = (now - backup_file.stat().st_mtime) / (24 * 3600)
        
        if file_age_days > days:
            try:
                backup_file.unlink()
                deleted_count += 1
                print(f"🗑️ Удалён старый бэкап: {backup_file.name}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить {backup_file.name}: {e}")
    
    if deleted_count > 0:
        print(f"🧹 Удалено старых бэкапов: {deleted_count}")


def restore_database(backup_file: str):
    """Восстановление базы данных из бэкапа"""
    backup_path = Path(backup_file)
    # Используем путь к базе данных из конфигурации
    db_path = Path(DATABASE_PATH)
    
    if not backup_path.exists():
        print(f"❌ Файл бэкапа не найден: {backup_path}")
        return False
    
    # Создаём бэкап текущей БД перед восстановлением
    if db_path.exists():
        current_backup = Path("backups") / f"before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        shutil.copy2(db_path, current_backup)
        print(f"💾 Текущая БД сохранена в: {current_backup}")
    
    try:
        shutil.copy2(backup_path, db_path)
        print(f"✅ База данных восстановлена из: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "restore":
            if len(sys.argv) < 3:
                print("❌ Укажите файл бэкапа для восстановления")
                print("Использование: python backup_db.py restore backups/bot_db_backup_YYYYMMDD_HHMMSS.db")
            else:
                restore_database(sys.argv[2])
        else:
            print("❌ Неизвестная команда")
            print("Использование:")
            print("  python backup_db.py           - создать бэкап")
            print("  python backup_db.py restore <файл> - восстановить из бэкапа")
    else:
        backup_database()
