#!/usr/bin/env python3
"""Fix indentation issue in bot.py at line 987"""

with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 987 (0-indexed: 986) is missing indent
# It should be "        conv[\"turns\"]..."
bad_line = 'conv["turns"].append({"from": "vera", "msg": action_body})\n'
fix_line = '        conv["turns"].append({"from": "vera", "msg": action_body})\n'

for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped == bad_line:
        print(f"Found bad line at index {i}: {repr(line)}")
        lines[i] = fix_line
        print(f"Fixed to: {repr(lines[i])}")

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Done.")
