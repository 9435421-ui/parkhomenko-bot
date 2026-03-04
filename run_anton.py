"""
Скрипт-обертка для запуска основного бота ТЕРИОН.
"""
import asyncio
import sys
import os

# Добавляем текущую директорию в путь импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"💥 Критическая ошибка бота: {e}")
        sys.exit(1)
