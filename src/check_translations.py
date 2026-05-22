#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def parse_po(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = re.split(r'\n\n(?=#)', content.strip())
    entries = []
    for block in blocks:
        m = re.search(r'msgid "(.*)"', block, re.DOTALL)
        s = re.search(r'msgstr "(.*)"', block, re.DOTALL)
        if m and s:
            mid = m.group(1).replace('"\n"', '')
            mstr = s.group(1).replace('"\n"', '')
            if mid.strip():
                # Extract source location from #: line
                loc = ''
                loc_m = re.search(r'#:\s*(.+)', block)
                if loc_m:
                    loc = loc_m.group(1).strip()
                entries.append({'block': block, 'msgid': mid, 'msgstr': mstr, 'location': loc})
    return entries


def check_entry(entry):
    issues = []
    mid = entry['msgid']
    mstr = entry['msgstr']
    loc = entry['location']
    prefix = f"  [{loc}]" if loc else "  [no location]"

    # 1. Untranslated (empty msgstr)
    if not mstr.strip():
        issues.append(("UNTRANSLATED", f"{prefix} msgstr is empty"))

    # 2. Contains literal "msgstr" text (model artifact)
    if re.search(r'msgstr', mstr, re.IGNORECASE):
        issues.append(("ARTIFACT", f"{prefix} msgstr contains literal 'msgstr'\n         msgid:  {mid[:60]}\n         msgstr: {mstr[:80]}"))

    # 3. Non-standard mixed punctuation: "？～", "～？", "～！", "！～", "？！" (wrong order)
    #    Allowed: "？", "～", "！！！", "！？", "……", "。"
    if re.search(r'[？!][～~]|[～~][？!]|\？！', mstr):
        issues.append(("MIXED_PUNCT", f"{prefix} non-standard mixed punctuation\n         msgid:  {mid[:60]}\n         msgstr: {mstr[:80]}"))

    # 4. Ends with backslash (truncated escape)
    if mstr.endswith('\\') and not mstr.endswith('\\\\'):
        issues.append(("TRUNCATED", f"{prefix} msgstr ends with backslash\n         msgid:  {mid[:60]}\n         msgstr: {mstr[:80]}"))

    # 5. Contains forbidden kawaii word "笨蛋" when tsundere mode is expected
    if '笨蛋' in mstr:
        issues.append(("FORBIDDEN_WORD", f"{prefix} msgstr contains '笨蛋'\n         msgid:  {mid[:60]}\n         msgstr: {mstr[:80]}"))

    # 6. msgstr still contains significant English (more than 50% ASCII letters)
    if len(mstr) > 10:
        ascii_chars = sum(1 for c in mstr if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in mstr if c.isalpha())
        if total_chars > 0 and ascii_chars / total_chars > 0.5:
            issues.append(("ENGLISH_HEAVY", f"{prefix} msgstr is mostly English\n         msgid:  {mid[:60]}\n         msgstr: {mstr[:80]}"))

    # 7. msgstr contains tilde "～" (fullwidth) instead of ASCII "~"
    if '～' in mstr:
        issues.append(("FULLWIDTH_TILDE", f"{prefix} msgstr uses fullwidth ～\n         msgid:  {mid[:60]}\n         msgstr: {mstr[:80]}"))

    return issues


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_translations.py <po_file> [--tsundere]")
        sys.exit(1)

    filepath = sys.argv[1]
    tsundere_mode = '--tsundere' in sys.argv or '-t' in sys.argv

    if not Path(filepath).exists():
        print(f"Error: file not found: {filepath}")
        sys.exit(1)

    print(f"Checking: {filepath}\n")
    entries = parse_po(filepath)
    print(f"Total entries: {len(entries)}")

    all_issues = []
    for entry in entries:
        issues = check_entry(entry)
        if tsundere_mode:
            issues = [i for i in issues if i[0] != 'FORBIDDEN_WORD']
        all_issues.extend(issues)

    if not all_issues:
        print("\nNo issues found. Clean!")
        return

    # Group by category
    categories = {}
    for cat, msg in all_issues:
        categories.setdefault(cat, []).append(msg)

    print(f"\n{'='*60}")
    print(f"Issues found: {len(all_issues)}")
    print(f"{'='*60}\n")

    cat_names = {
        'UNTRANSLATED': 'Empty msgstr',
        'ARTIFACT': 'Literal "msgstr" artifact',
        'MIXED_PUNCT': 'Mixed punctuation',
        'TRUNCATED': 'Truncated (ends with backslash)',
        'FORBIDDEN_WORD': 'Contains "笨蛋" (use 杂鱼 instead)',
        'ENGLISH_HEAVY': 'Mostly English text',
        'FULLWIDTH_TILDE': 'Fullwidth tilde ～',
    }

    for cat in sorted(categories.keys()):
        items = categories[cat]
        print(f"\n--- {cat_names.get(cat, cat)} ({len(items)}) ---")
        for msg in items:
            print(msg)

    print(f"\n{'='*60}")
    print(f"Total: {len(all_issues)} issue(s) across {len(categories)} category(ies)")


if __name__ == '__main__':
    main()