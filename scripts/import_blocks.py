#!/usr/bin/env python3
"""Alt-Angebot-Text (stdin) → Bausteine mit PII-Schwärzung (Ticket #23 §10). JSON auf stdout.

Der Web-Import (/api/blocks-import) pipet den Text hierher. Wir speichern NUR den geschwärzten
Baustein, nie das Original (§10.2) — das Original bleibt im Aufrufer/Arbeitsspeicher.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from govisor import blocks  # noqa: E402

text = sys.stdin.read()
print(json.dumps(blocks.extract_blocks(text or ""), ensure_ascii=False))
