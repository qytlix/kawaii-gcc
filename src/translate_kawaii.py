#!/usr/bin/env python3
import re
import json
import urllib.request
import time
import sys
from pathlib import Path

API_URL = "http://192.168.1.103:11434/v1/chat/completions"
MODEL = "kawaii-translate:tsundere"

SRC_DIR = Path("src")
INPUT_PO = SRC_DIR / "zh_CN-kawaii.po"
ORIGIN_PO = SRC_DIR / "zh-origin.po"
STATE_FILE = SRC_DIR / "translate_state.json"

# How many entries to translate before saving progress
SAVE_INTERVAL = 20


def parse_po_blocks(content):
    blocks = re.split(r'\n\n(?=#)', content.strip())
    entries = []
    for block in blocks:
        if 'msgstr "' not in block:
            continue
        m = re.search(r'msgid "(.*)"', block, re.DOTALL)
        s = re.search(r'msgstr "(.*)"', block, re.DOTALL)
        if m and s:
            msgid_raw = m.group(1)
            msgstr_raw = s.group(1)
            msgid_clean = msgid_raw.replace('"\n"', '')
            msgstr_clean = msgstr_raw.replace('"\n"', '')
            loc_m = re.search(r'#:\s*(.+)', block)
            entries.append({
                'block': block,
                'msgid': msgid_clean,
                'msgstr': msgstr_clean,
                'location': loc_m.group(1).strip() if loc_m else '',
            })
    return entries


def get_origin_translations():
    with open(ORIGIN_PO, 'r', encoding='utf-8') as f:
        content = f.read()
    result = {}
    blocks = re.split(r'\n\n(?=#)', content.strip())
    for block in blocks:
        m = re.search(r'msgid "(.*)"', block, re.DOTALL)
        s = re.search(r'msgstr "(.*)"', block, re.DOTALL)
        if m and s:
            mid = m.group(1).replace('"\n"', '')
            mstr = s.group(1).replace('"\n"', '')
            if mid.strip():
                result[mid] = mstr
    return result


def classify_entries(entries, origin):
    cat_a = []
    cat_b = []
    cat_c = []

    for e in entries:
        mid = e['msgid']
        mstr = e['msgstr']
        has_translation = bool(mstr.strip())
        in_origin = mid in origin
        origin_has_text = in_origin and bool(origin[mid].strip())

        if has_translation and in_origin and mstr == origin[mid]:
            cat_a.append(e)
        elif not has_translation and origin_has_text:
            cat_b.append(e)
        elif not has_translation and not origin_has_text:
            cat_c.append(e)

    return cat_a, cat_b, cat_c


def clean_translation(text):
    text = text.strip(' "\n\t')
    text = re.sub(r'^["\']+|["\']+$', '', text)
    text = re.sub(r'\s*["\']?\s*msgstr\s*["\']?\s*["\']*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text or text == 'msgstr':
        return None
    return text


def call_kawaii_api(text, retries=2):
    for attempt in range(retries + 1):
        try:
            data = {
                "model": MODEL,
                "messages": [{"role": "user", "content": text}],
                "temperature": 0.85,
                "max_tokens": 500,
            }
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                raw = result['choices'][0]['message']['content'].strip()
                cleaned = clean_translation(raw)
                return cleaned if cleaned else None
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
    return None


def escape_po(text):
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    return text


def replace_msgstr(block, new_msgstr):
    escaped = escape_po(new_msgstr)
    pattern = r'msgstr\s+"(?:[^"]*(?:"\n")*[^"]*?)?"'
    return re.sub(pattern, f'msgstr "{escaped}"', block, count=1, flags=re.DOTALL)


def write_output(output_path, header, entries):
    lines = [header]
    for e in entries:
        lines.append('')
        lines.append(e['block'])
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    print(f"Model: {MODEL}")
    print(f"Input: {INPUT_PO}")
    print()

    with open(INPUT_PO, 'r', encoding='utf-8') as f:
        content = f.read()

    first_sep = content.index('\n\n#:')
    header = content[:first_sep]
    body = content[first_sep:]

    all_entries = parse_po_blocks(body)
    print(f"Total entries: {len(all_entries)}")

    origin = get_origin_translations()
    cat_a, cat_b, cat_c = classify_entries(all_entries, origin)
    print(f"Category A (has Chinese, needs kawaii-fy): {len(cat_a)}")
    print(f"Category B (empty msgstr, origin has Chinese): {len(cat_b)}")
    print(f"Category C (pure English, no origin translation): {len(cat_c)}")

    state = {}
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        print(f"Resuming from saved state ({len(state)} completed)")

    cat_map = {'a': cat_a, 'b': cat_b, 'c': cat_c}
    cat_names = {'a': 'A (kawaii-fy existing)', 'b': 'B (origin Chinese -> kawaii)', 'c': 'C (English -> kawaii)'}

    for cat_key in ['a', 'b', 'c']:
        todo = [e for e in cat_map[cat_key] if e['msgid'] not in state]
        done_count = len(cat_map[cat_key]) - len(todo)
        print(f"\n--- Category {cat_names[cat_key]}: {done_count}/{len(cat_map[cat_key])} ---")

        for idx, entry in enumerate(todo):
            msgid = entry['msgid']
            clean_msgid = msgid.replace('\n', ' ').strip()[:80]
            prefix = f"[{idx+1}/{len(todo)}]"

            loc = entry['location']
            loc_short = loc[:50] if loc else '?'

            sys.stdout.write(f"  {prefix} {loc_short}: {clean_msgid}... ")
            sys.stdout.flush()

            translation = call_kawaii_api(clean_msgid)

            if translation:
                escaped = escape_po(translation)
                entry['block'] = replace_msgstr(entry['block'], translation)
                sys.stdout.write(f"OK\n")
            else:
                sys.stdout.write(f"FAIL (kept original)\n")

            sys.stdout.flush()
            state[msgid] = 1
            time.sleep(0.5)

            if (idx + 1) % SAVE_INTERVAL == 0:
                with open(STATE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)

    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    output_path = SRC_DIR / "zh_CN-kawaii-translated.po"
    write_output(output_path, header, all_entries)

    total = len(cat_a) + len(cat_b) + len(cat_c)
    completed = len(state)
    print(f"\n{'='*60}")
    print(f"Output: {output_path}")
    print(f"Completed: {completed}/{total}")
    print(f"Remaining: {total - completed}")

    print(f"\nRun check: python3 src/check_translations.py {output_path} --tsundere")


if __name__ == '__main__':
    main()