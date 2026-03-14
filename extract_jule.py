#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import zipfile
import os
import sys

zip_path = r'C:\Program Files (x86)\Жюль.zip'
extract_path = r'Jule_temp'

if not os.path.exists(zip_path):
    print(f"Archive not found: {zip_path}")
    sys.exit(1)

os.makedirs(extract_path, exist_ok=True)

print(f"Extracting: {zip_path}")
print(f"To: {extract_path}")

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)
    print(f"Extracted {len(zip_ref.namelist())} files")

print("\nStructure:")
for root, dirs, files in os.walk(extract_path):
    level = root.replace(extract_path, '').count(os.sep)
    indent = ' ' * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = ' ' * 2 * (level + 1)
    for file in files[:10]:
        print(f"{subindent}{file}")
