#!/usr/bin/env python
"""Проверка callback_data между keyboards и ВСЕМИ handlers"""
import re

# callbacks в keyboards/main_menu.py
with open('keyboards/main_menu.py', encoding='utf-8') as f:
    kb = f.read()
kb_callbacks = set(re.findall(r'callback_data=[\"\']([^\"\']+)[\"\']', kb))

# F.data во ВСЕХ handlers
hw_callbacks = set()
for fname in ['handlers/start.py', 'handlers/content.py', 'handlers/admin.py', 'handlers/quiz.py']:
    try:
        with open(fname, encoding='utf-8') as f:
            content = f.read()
        # Ищем F.data == "xxx" и F.data.startswith("xxx")
        for m in re.finditer(r'F\.data[==\.startswith\\(]+[\"\']([^\"\']+)[\"\']', content):
            hw_callbacks.add(m.group(1))
    except:
        pass

print("KEYBOARDS:", sorted(kb_callbacks))
print()
print("HANDLERS:", sorted(hw_callbacks))
print()
print("MISSING in handlers:", kb_callbacks - hw_callbacks)
print("MISSING in keyboards:", hw_callbacks - kb_callbacks)
