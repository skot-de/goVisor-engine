"""Huelle, damit die HTML-Escape-Sonde im Nachtlauf mitlaeuft.

Die eigentliche Regel steht in `web/scripts/pruefe-html-escape.mjs`: sie parst den echten
Quelltext von explorerCore.js (+ ExplorerShell) und faellt, sobald ein Datenfeld OHNE
`esc()` direkt in HTML landet. Sie laeuft zusaetzlich per `npm run prebuild` vor jedem
`next build` (s. web/package.json). Diese Huelle bindet sie in die pytest-Suite und
befriedigt `test_verdrahtung.py::test_jedes_pruefskript_wird_auch_aufgerufen`.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-html-escape.mjs"


def test_die_sonde_laeuft_gruen():
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL / "web")
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-500:]
    assert "Kein rohes Datenfeld" in r.stdout
