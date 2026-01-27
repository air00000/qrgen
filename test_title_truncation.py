#!/usr/bin/env python3
"""
Тест обрезки названия товара до 25 символов
"""
import sys
sys.path.insert(0, '.')

from app.utils.helpers import truncate_title, MAX_LENGTH_TITLE


def test_title_truncation():
    """Тестирование обрезки названия товара"""
    
    print("=" * 60)
    print("ТЕСТ: Обрезка названия товара до 25 символов")
    print("=" * 60)
    print()
    
    # Проверяем константу
    print(f"✓ MAX_LENGTH_TITLE = {MAX_LENGTH_TITLE}")
    assert MAX_LENGTH_TITLE == 25, f"Ошибка: MAX_LENGTH_TITLE должен быть 25, а не {MAX_LENGTH_TITLE}"
    print()
    
    # Тестовые случаи
    test_cases = [
        ("iPhone 14 Pro Max", "iPhone 14 Pro Max"),  # 17 символов - не обрезать
        ("MacBook Pro 16 2023", "MacBook Pro 16 2023"),  # 19 символов - не обрезать
        ("Велосипед горный 29\"", "Велосипед горный 29\""),  # 20 символов - не обрезать
        ("PlayStation 5 console", "PlayStation 5 console"),  # 21 символов - не обрезать
        ("Samsung Galaxy S24 Ultra", "Samsung Galaxy S24 Ultra"),  # 24 символа - не обрезать
        ("Samsung Galaxy S24 Ultra!", "Samsung Galaxy S24 Ultra!"),  # 25 символов - НЕ обрезать (<=25)
        ("Samsung Galaxy S24 Ultra!!", "Samsung Galaxy S24 Ult..."),  # 26 символов - обрезать до 25
        ("Ноутбук игровой ASUS ROG Strix", "Ноутбук игровой ASUS R..."),  # 30 символов - обрезать до 25
        ("Холодильник LG двухкамерный No Frost", "Холодильник LG двухкам..."),  # 36 символов - обрезать до 25
        ("Смартфон Apple iPhone 15 Pro Max 256GB", "Смартфон Apple iPhone ..."),  # 40 символов - обрезать до 25
        ("A" * 50, "A" * 22 + "..."),  # 50 A - обрезать до 22 A + ... (итого 25)
        ("", ""),  # Пустая строка
        ("Bike", "Bike"),  # 4 символа - не обрезать
    ]
    
    print("Результаты тестов:")
    print("-" * 60)
    
    all_passed = True
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = truncate_title(input_text)
        passed = result == expected
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} Тест {i}:")
        print(f"  Входное:  '{input_text}' ({len(input_text)} символов)")
        print(f"  Ожидаемо: '{expected}' ({len(expected)} символов)")
        print(f"  Результат: '{result}' ({len(result)} символов)")
        
        if not passed:
            print(f"  ⚠️  НЕСООТВЕТСТВИЕ!")
            all_passed = False
        
        print()
    
    print("=" * 60)
    if all_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print(f"✓ Все названия длиннее {MAX_LENGTH_TITLE} символов обрезаются до {MAX_LENGTH_TITLE-3} символов + '...'")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        return False
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_title_truncation()
    sys.exit(0 if success else 1)
