import sys
import os
import re
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.quiz import validate_phone

def test_validation():
    print("--- Тестирование валидации телефона ---")
    test_cases = [
        ("+79991234567", True),
        ("89991234567", True),
        ("79991234567", True),
        ("+7 999 123 45 67", True),
        ("8 (999) 123-45-67", True),
        ("12345", False),
        ("abcdef", False),
        ("", False),
    ]

    for phone, expected in test_cases:
        res = validate_phone(phone)
        print(f"Ввод: '{phone}' -> Валидно: {res} (Ожидалось: {expected})")
        assert res == expected, f"Ошибка на кейсе {phone}"
    print("✅ Тест валидации пройден!")

def simulate_branching():
    print("\n--- Симуляция ветвления финального экрана ---")

    def get_final_text(status, name):
        status = status.lower()
        if "уже выполнена" in status:
            return f"✅ Спасибо, {name}! План легализации..."
        else:
            return f"✅ Спасибо, {name}! Расчет проектирования..."

    case_done = get_final_text("✅ Уже выполнена", "Иван")
    case_planned = get_final_text("📋 Планируется", "Петр")

    print(f"Сценарий 'Сделано': {case_done}")
    print(f"Сценарий 'Планирую': {case_planned}")

    assert "легализации" in case_done
    assert "проектирования" in case_planned
    print("✅ Симуляция ветвления пройдена!")

if __name__ == "__main__":
    try:
        test_validation()
        simulate_branching()
        print("\n🎉 Все тесты пройдены успешно!")
    except Exception as e:
        print(f"\n❌ Тест провален: {e}")
        sys.exit(1)
