#!/usr/bin/env python3
"""
Scan the repository for files that cannot be decoded with UTF-8.
Useful when tools like `pipreqs` crash with UnicodeDecodeError.

Usage:
    python tools/find_non_utf8.py [path]

If no path is given the script scans the current repository root.
"""
import sys
import os
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.').resolve()

binary_like_exts = {'.png', '.jpg', '.jpeg', '.gif', '.nii', '.nii.gz', '.pdf', '.zip', '.tar', '.gz', '.mp4', '.mov'}

bad_files = []

for p in ROOT.rglob('*'):
    if p.is_dir():
        continue
    # Skip common binary file extensions quickly
    if p.suffix.lower() in binary_like_exts:
        continue
    try:
        with p.open('r', encoding='utf-8') as f:
            f.read()
    except UnicodeDecodeError as ude:
        bad_files.append((str(p), repr(ude)))
    except Exception:
        # Some files might raise other errors (permission, etc.); report them too
        try:
            with p.open('rb') as fb:
                fb.read(256)
        except Exception as e:
            bad_files.append((str(p), f"Error reading: {e}"))

if not bad_files:
    print("No non-UTF-8 files detected (skipping obvious binary extensions).")
    sys.exit(0)

print("Found files that are not UTF-8 decodable:")
for fn, err in bad_files:
    print(f" - {fn}: {err}")

print('\nNext steps:')
print(' - Inspect the listed files. If they are binary (images, .nii, compiled files), exclude their folders when running pipreqs:')
print("     pipreqs . --force --ignore 'html,docs,build,dist' # adjust the comma-separated list as needed")
print(' - Or run pipreqs only on `src/` to limit scanning to Python source:')
print('     pipreqs src --force --savepath=requirements.txt')
print(' - If a text file contains non-UTF8 content but is legitimately text, re-save it as UTF-8 or provide pipreqs with a smaller scope.')
