# Единая модель лида ТОРИОН

Модель данных для унифицированного сбора и обработки заявок из всех модулей (Квиз, Консультант, Калькуляторы, Контент).

---

## 1. Спецификация полей

| Поле | Тип | Описание | Обязательно |
| :--- | :--- | :--- | :--- |
| `user_id` | Integer | Telegram ID пользователя | Да |
| `source` | String | Источник (quiz / consult / calc / content) | Да |
| `contact` | String | Номер телефона или @username | Да |
| `status` | String | Статус лида (new / processing / qualified / lost) | Да |
| `date` | Timestamp | Дата и время создания | Да |
| `comment` | Text | Дополнительная информация (результаты квиза, вопрос и т.д.) | Нет |

---

## 2. Реализация в БД (parkhomenko_bot.db)

```sql
CREATE TABLE IF NOT EXISTS unified_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    contact TEXT NOT NULL,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comment TEXT,
    raw_data JSON -- Для хранения специфичных данных модулей
);
```

---

## 3. Расширяемость

- Поле `raw_data` позволяет сохранять специфические детали (например, параметры инвест-расчета или полные ответы квиза) без изменения схемы таблицы.
- Модель готова к экспорту в CRM или Google Таблицы.
