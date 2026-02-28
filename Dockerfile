# Dockerfile для бота «Лад в квартире»
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём директории для данных
RUN mkdir -p database backups

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1

# Запуск бота
CMD ["python", "main.py"]
