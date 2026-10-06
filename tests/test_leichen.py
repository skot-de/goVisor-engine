"""Selbstprobe fuer `scripts/pruefe_leichen.py` — in BEIDE Richtungen.

Eine Sonde, die nur bestaetigt, was man ohnehin glaubt, ist keine Pruefung. Deshalb hier
zweierlei:

* **vorwaerts** — jede Spur MUSS die Funde melden, die am 2026-10-06 von Hand belegt wurden
* **rueckwaerts** — ist die Ursache weg, MUSS die Spur schweigen (ueber einen Fixture-Baum)

⚠ Dazu Regressionsproben fuer die VIER Fallen, in die die Sonde beim Bau gelaufen ist. Jede
hat einen Fehlalarm oder, schlimmer, eine dauergruene Spur erzeugt:

    1. eigene Prosa gemessen   — `--takt` im Docstring machte die Spur zu ihrem eigenen Befund
    2. `.next` mitgelesen      — das Build-Erzeugnis listet JEDE Route → Spur 2 fand nie etwas
    3. Anfuehrungszeichen davor — `/auth/passwort` galt als tot, wird aber per `?next=` erreicht
    4. Namensraum-Import       — `preise.ts → betragCents` galt als tot, laeuft als `P.betragCents`
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _laden():
    pfad = ROOT / "scripts" / "pruefe_leichen.py"
    spec = importlib.util.spec_from_file_location("pruefe_leichen", pfad)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["pruefe_leichen"] = modul
    spec.loader.exec_module(modul)
    return modul


L = _laden()


# ── vorwaerts: die belegten Funde muessen auftauchen ──────────────────────────────────
@pytest.mark.parametrize("spur,nadel", [
    ("komponenten", "components/Band.tsx"),
    ("wege", "/authority"),
    ("symbole", "hatDichte"),
    ("dienste", "antwort_arbeiter.py"),
])
def test_belegter_fund_wird_gemeldet(spur, nadel):
    """Jeder dieser vier Funde ist am 2026-10-06 von Hand nachgemessen worden.

    `antwort_arbeiter.py` zum Beispiel: kein Prozess (`pgrep`), kein Dienst (vier sind
    eingetragen), und kein anderer Abnehmer der Tabelle `user_antwortauftrag` im Repo —
    waehrend die Oberflaeche Auftraege ablegt und auf Ergebnisse wartet.
    """
    _, fn = L.SPUREN[spur]
    treffer = fn(False)
    assert any(nadel in z for z in treffer), \
        f"Spur {spur} meldet {nadel} nicht mehr:\n  " + "\n  ".join(treffer)


def test_geparkte_ausnahme_wird_gemeldet():
    """Zwei Ausnahmen stehen seit dem 2026-08-25 — die Spur muss ihr Alter nennen."""
    treffer = L.spur_ausnahmen()
    assert any("pruefe_verdrahtung.py" in z and "parkt seit" in z for z in treffer), \
        "Die 42-Tage-Ausnahmen werden nicht mehr gemeldet:\n  " + "\n  ".join(treffer)


# ── rueckwaerts: ist die Ursache weg, muss die Spur schweigen ─────────────────────────
def _fixture(tmp: pathlib.Path, verdrahtet: bool) -> pathlib.Path:
    """Ein Mini-`web/` mit genau einer Komponente und genau einer Seite.

    ⚠ Bewusst eigenwillige Namen: der Fixture-Baum wird gegen dieselbe Spur gefahren, und
    ein Name wie `Band` koennte im echten Repo vorkommen und den Test verfaelschen.
    """
    web = tmp / "web"
    (web / "components").mkdir(parents=True)
    (web / "app" / "zzprobe").mkdir(parents=True)
    (web / "components" / "ZzLeiche.tsx").write_text(
        "export function ZzLeiche() { return null; }\n", encoding="utf-8")
    (web / "app" / "zzprobe" / "page.tsx").write_text(
        "export default function Seite() { return null; }\n", encoding="utf-8")
    ruf = ('import { ZzLeiche } from "@/components/ZzLeiche";\n'
           'export const WEG = "/zzprobe";\n') if verdrahtet else "export const X = 1;\n"
    (web / "app" / "rahmen.tsx").write_text(ruf, encoding="utf-8")
    return web


def test_unverdrahtet_schlaegt_an(tmp_path):
    web = _fixture(tmp_path, verdrahtet=False)
    k = L.spur_komponenten(False, wurzel=web)
    w = L.spur_wege(False, wurzel=web)
    assert any("ZzLeiche" in z for z in k), f"Komponente nicht gemeldet: {k}"
    assert any("/zzprobe" in z for z in w), f"Seite nicht gemeldet: {w}"


def test_verdrahtet_schweigt(tmp_path):
    """Die andere Richtung. Ohne sie koennte die Spur alles melden und waere nutzlos."""
    web = _fixture(tmp_path, verdrahtet=True)
    k = L.spur_komponenten(False, wurzel=web)
    w = L.spur_wege(False, wurzel=web)
    assert not any("ZzLeiche" in z for z in k), f"Fehlalarm trotz Import: {k}"
    assert not any("/zzprobe" in z for z in w), f"Fehlalarm trotz Verweis: {w}"


# ── Regression: die vier Fallen aus dem Bau ───────────────────────────────────────────
def test_falle1_keine_eigene_prosa():
    """Die Sonde darf sich nicht selbst melden.

    Sie tat es zweimal: `--takt` steht in ihrem Docstring (Spur 4), und ein Beispieldatum
    „offen seit …" in Spur 5. Beide Male war der Befund die Sonde selbst.
    """
    assert not any("pruefe_leichen" in z for z in L.spur_dienste()), \
        "Spur 4 meldet sich selbst — Prosa wird wieder mitgemessen"
    assert not any("pruefe_leichen" in z for z in L.spur_ausnahmen()), \
        "Spur 5 meldet sich selbst — Prosa wird wieder mitgemessen"


def test_falle2_erzeugtes_bleibt_draussen():
    """`.next` listet jede Route — wer es mitliest, bekommt eine dauergruene Spur."""
    assert ".next" in L.ERZEUGT and "node_modules" in L.ERZEUGT
    gelesen = L._dateien(L.WEB)
    assert not any(".next" in p.parts for p in gelesen), \
        "Build-Erzeugnis wird wieder mitgelesen"


def test_falle3_url_mitten_im_string_zaehlt():
    """`/auth/passwort` wird per `?next=/auth/passwort` erreicht — kein Loeschkandidat.

    ⚠ Der teuerste der vier Fehlalarme: loeschen haette das Passwort-Zuruecksetzen getoetet.
    """
    assert not any("/auth/passwort" in z for z in L.spur_wege()), \
        "Spur 2 meldet /auth/passwort wieder — der Verweis steht in einer laengeren URL"


def test_falle4_namensraum_import_zaehlt():
    """`preise.ts → betragCents` laeuft als `P.betragCents` aus einem Namensraum-Import."""
    assert not any("betragCents" in z for z in L.spur_symbole()), \
        "Spur 3 meldet betragCents wieder — Namensraum-Import wird nicht erkannt"


def test_ruhendes_wird_nicht_gemeldet():
    """`MessHinweis.tsx` ruht absichtlich und ist im Dateikopf begruendet."""
    assert any("MessHinweis" in k for k in L.RUHEND)
    assert not any("MessHinweis" in z for z in L.spur_komponenten()), \
        "Begruendet ruhende Komponente wird als Leiche gemeldet"


def test_ruhend_eintraege_sind_begruendet():
    """Kein Parkplatz: jeder Eintrag nennt einen Grund, keiner ist leer.

    ⚠ Dieselbe Disziplin, die `tests/test_verdrahtung.py` fuer die Sonden-Ausnahmen haelt —
    ohne sie wird aus einer Ausnahmeliste eine Mullhalde.
    """
    for name, grund in {**L.RUHEND, **L.RUHENDE_DIENSTE}.items():
        assert len(grund) > 30, f"{name} hat keine tragfaehige Begruendung: {grund!r}"


def test_fremde_zweige_werden_mitgelesen():
    """⛔ Der Scan MUSS gegen die lebenden Zweige pruefen, nicht nur gegen HEAD.

    Sonst loescht er, was auf `web/grounding-page` gerade eingebunden wurde — dort allein
    51 Dateien Unterschied in `web/`.
    """
    zweige = L.lebende_zweige()
    assert zweige, "keine lebenden Zweige erkannt — der Kreuzvergleich faellt stumm aus"
    blob = L._fremde_sicht(zweige, ("web",))
    assert len(blob) > 1000, \
        f"fremde Sicht ist fast leer ({len(blob)} Zeichen) — git grep liefert nichts"
