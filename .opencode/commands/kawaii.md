---
description: "Style-aware translation — default: English → kawaii Chinese. Usage: /kawaii <text> [--style=kawaii|normal] [--lang=zh_CN|en|ja]"
argument-hint: "<text> [--style=kawaii|normal] [--lang=zh_CN|en|ja]"
subtask: true
---

The user invoked `/kawaii` for a style-aware translation. Parse their arguments, then call the ollama kawaii-translate API to get the translation.

1. Extract the text to translate (everything before `--style` or `--lang` flags)
2. Extract `--style` value (default: kawaii) and `--lang` value (default: zh_CN)
3. Call the translation API:
```
curl -s http://192.168.1.103:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"kawaii-translate:latest","messages":[{"role":"user","content":"<text>"}],"temperature":0.8,"max_tokens":500}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

Output ONLY the translated text. Do not add any commentary or explanation.