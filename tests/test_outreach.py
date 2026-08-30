"""Die Adresse einer Vertriebsseite IST ihr Zugang — `/t/<token>` ist öffentlich.

Der Token war bis zum 2026-08-30 `sha1(identity_id)[:10]`: ungesalzen und deterministisch.
Die Kennung, die hineingeht, gibt die Anwendung selbst heraus — `/api/entity-search` steht
bewusst offen, weil das Onboarding sie vor der Anmeldung braucht, und liefert je Treffer die
`identity_id`. Damit war die Kette geschlossen:

    Firmenname suchen → Kennung bekommen → sha1 → fremde Vertriebsseite öffnen

An den echten Daten durchgerechnet: von 9.456 Seiten waren **4.127** so erreichbar, davon
3.622 bereits verschickte. Preisgegeben hätten sie die firmenspezifische Auswertung und im
Feld `zustellung` Empfängerdomain und Versanddatum — also wen wir angesprochen haben, wann,
und womit.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SALZ = "0" * 64          # fürs Testen; das echte liegt in .secrets/outreach.salt


def _modul(monkeypatch):
    monkeypatch.setenv("GOVISOR_OUTREACH_SALT", SALZ)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("eo", ROOT / "scripts" / "export_outreach.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_token_ist_ohne_geheimnis_nicht_herleitbar(monkeypatch):
    """Aus der öffentlichen Kennung darf sich der Token nicht ausrechnen lassen."""
    m = _modul(monkeypatch)
    kennung = "grp:rosenbauer"          # so, wie `/api/entity-search` sie herausgibt
    token = m.token_of(kennung)

    assert token != hashlib.sha1(kennung.encode()).hexdigest()[:10], \
        "der Token ist wieder das blanke sha1 der Kennung"
    assert len(token) == 16, f"64 Bit erwartet, bekommen: {len(token) * 4} Bit"

    # Gleiche Kennung, gleiches Salz → gleicher Token. Ohne diese Eigenschaft brechen bei
    # jedem Export alle verschickten Links.
    assert m.token_of(kennung) == token

    # Anderes Salz → anderer Token. Sonst waere das Geheimnis wirkungslos.
    monkeypatch.setenv("GOVISOR_OUTREACH_SALT", "1" * 64)
    assert m.token_of(kennung) != token


def test_ohne_salz_laeuft_der_export_gar_nicht(monkeypatch):
    """Fail-closed: kein Geheimnis, kein Export.

    ⚠ Ein Rückfall auf „ohne Salz" wäre die gefährlichste Variante. Die Token sähen gleich
    aus, wären aber wieder öffentlich ableitbar — und niemand hätte einen Anlass hinzusehen.
    """
    m = _modul(monkeypatch)
    monkeypatch.delenv("GOVISOR_OUTREACH_SALT", raising=False)
    monkeypatch.setattr(m, "SALZ_PFAD", ROOT / "gibt-es-nicht" / "outreach.salt")
    with pytest.raises(SystemExit) as fehler:
        m.token_of("grp:rosenbauer")
    assert "Salz" in str(fehler.value), "die Meldung sagt nicht, was fehlt"

    monkeypatch.setenv("GOVISOR_OUTREACH_SALT", "zu-kurz")
    with pytest.raises(SystemExit):
        m.token_of("grp:rosenbauer")


@pytest.mark.skipif(not (ROOT / "web" / "data" / "outreach.json").exists()
                    or not (ROOT / "web" / "data" / "suppliers-basis.json").exists(),
                    reason="kein Export vorhanden")
def test_im_echten_bestand_ist_kein_token_mehr_errechenbar():
    """Der eigentliche Wächter: die Probe am ausgelieferten Stand.

    Sie geht denselben Weg wie ein Fremder — jede Kennung aus der öffentlich abfragbaren
    Firmenliste durch das alte Verfahren schicken und nachsehen, ob dabei ein gültiger
    Token herauskommt.
    """
    store = set(json.loads((ROOT / "web" / "data" / "outreach.json")
                           .read_text(encoding="utf-8")))
    basis = json.loads((ROOT / "web" / "data" / "suppliers-basis.json")
                       .read_text(encoding="utf-8"))
    eintraege = basis if isinstance(basis, list) else list(basis.values())

    treffer = {hashlib.sha1(str(e.get("id")).encode()).hexdigest()[:10]
               for e in eintraege} & store
    assert not treffer, (
        f"{len(treffer)} Vertriebsseiten sind wieder aus der oeffentlichen Kennung "
        f"erreichbar (z. B. /t/{sorted(treffer)[0]})")

    kurz = [t for t in store if len(t) < 16]
    assert not kurz, f"{len(kurz)} Token sind kuerzer als 64 Bit, z. B. {kurz[0]}"
