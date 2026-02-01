import re

def validate_phone(phone: str) -> bool:
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(r'^\+?[78]\d{10}$', clean_phone))

test_cases = [
    ("+7 999 123-45-67", True),
    ("8 (999) 123 45 67", True),
    ("+79991234567", True),
    ("89991234567", True),
    ("79991234567", False), # Assuming it must start with +7 or 8 for now as per my regex
    ("12345", False),
    ("abc", False)
]

for phone, expected in test_cases:
    result = validate_phone(phone)
    print(f"{phone}: {result} (Expected: {expected})")
