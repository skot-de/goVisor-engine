"""Huelle, damit die Los-XSS-Sonde im Nachtlauf mitlaeuft.

Die eigentliche Pruefung steht in `web/scripts/pruefe-los-xss.mjs`: sie schneidet den echten
Los-Renderer und das echte `esc` aus `explorerCore.js` und weist nach, dass ein Los-Titel
`<img onerror=…>` escaped im HTML landet statt als Tag. Ohne diese Huelle liefe sie
nirgends — dieselbe Fehlerklasse („gebaut, nicht aufgerufen") eine Ebene hoeher, die
`test_verdrahtung.py::test_jedes_pruefskript_wird_auch_aufgerufen` gerade abfaengt.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-los-xss.mjs"


def test_die_sonde_laeuft_gruen():
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-500:]
    assert "Los-Titel tragen kein HTML" in r.stdout
