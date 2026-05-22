#!/usr/bin/env python3
import re
import json
import urllib.request
import time
import sys

API_URL = "http://192.168.1.103:11434/v1/chat/completions"
INPUT_PO = "src/zh_CN-kawaii.po"
OUTPUT_PO = "src/zh_CN-kawaii-demo.po"
MAX_ENTRIES = 20


def parse_po_blocks(content):
    blocks = re.split(r'\n\n(?=#)', content.strip())
    entries = []
    for block in blocks:
        if 'msgstr "' not in block:
            continue
        m = re.search(r'msgid "(.*)"', block, re.DOTALL)
        if m:
            msgid_raw = m.group(1)
            msgid_clean = msgid_raw.replace('"\n"', '')
            entries.append((block, msgid_clean))
    return entries


def get_origin_msgids():
    with open('src/zh-origin.po', 'r', encoding='utf-8') as f:
        content = f.read()
    result = set()
    blocks = re.split(r'\n\n(?=#)', content.strip())
    for block in blocks:
        m = re.search(r'msgid "(.*)"', block, re.DOTALL)
        if m:
            mid = m.group(1).replace('"\n"', '')
            if mid.strip():
                result.add(mid)
    return result


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
                "model": "kawaii-translate:latest",
                "messages": [{"role": "user", "content": text}],
                "temperature": 0.8,
                "max_tokens": 500
            }
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                raw = result['choices'][0]['message']['content'].strip()
                cleaned = clean_translation(raw)
                return cleaned if cleaned else text
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
    return None


def escape_for_po(text):
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    return text


def main():
    with open(INPUT_PO, 'r', encoding='utf-8') as f:
        content = f.read()

    first_sep = content.index('\n\n#:')
    header = content[:first_sep]
    body = content[first_sep:]

    entries = parse_po_blocks(body)
    print(f"Total entries parsed: {len(entries)}", flush=True)

    untranslated = [(b, m) for b, m in entries if not re.search(r'msgstr\s+"[^"]', b)]
    print(f"Untranslated entries: {len(untranslated)}", flush=True)

    origin_ids = get_origin_msgids()
    cat_c = [(b, m) for b, m in untranslated if m not in origin_ids]
    print(f"Category C (pure English): {len(cat_c)}", flush=True)

    to_translate = cat_c[:MAX_ENTRIES]
    print(f"Translating {len(to_translate)} entries...\n", flush=True)

    output_lines = [header]

    ok_count = 0
    fail_count = 0

    for i, (block, msgid) in enumerate(to_translate, 1):
        clean_msgid = msgid.replace('\n', ' ').strip()
        prefix = clean_msgid[:60]
        sys.stdout.write(f"[{i}/{len(to_translate)}] {prefix}... ")
        sys.stdout.flush()

        translation = call_kawaii_api(clean_msgid)

        if translation:
            escaped = escape_for_po(translation)
            new_block = re.sub(r'msgstr\s+"(?:[^"]*(?:"\n")*[^"]*)?"', f'msgstr "{escaped}"', block, count=1, flags=re.DOTALL)
            output_lines.append('')
            output_lines.append(new_block)
            ok_count += 1
            print(f"OK -> {translation[:50]}", flush=True)
        else:
            output_lines.append('')
            output_lines.append(block)
            fail_count += 1
            print("FAIL -> kept original", flush=True)

        time.sleep(0.3)

        if i % 5 == 0 or i == len(to_translate):
            with open(OUTPUT_PO, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines) + '\n')

    with open(OUTPUT_PO, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')

    print(f"\nDone! Output: {OUTPUT_PO}", flush=True)
    print(f"OK: {ok_count}, Failed: {fail_count}", flush=True)


if __name__ == '__main__':
    main()