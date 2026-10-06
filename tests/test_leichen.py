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
# ⚠ **ERSTER ENTWURF NAGELTE DEN STAND VON HEUTE FEST — und bestrafte damit das Beheben.**
# Er verlangte, dass Spur 1 `Band.tsx` meldet. Loescht jemand `Band.tsx`, also GENAU das, was
# der Bericht empfiehlt, wird der Test rot und sagt „Spur meldet Band.tsx nicht mehr" — das
# liest sich wie ein Defekt der Sonde. Derselbe Fehler ist in dieser Sitzung schon zweimal
# passiert (ein festgenagelter Zweigname, ein festgenagelter Pfad).
#
# Richtig ist eine Pruefung auf STIMMIGKEIT: solange die Ursache da ist, muss der Fund
# erscheinen; ist die Ursache weg, ist Schweigen die richtige Antwort und der Fall wird
# uebersprungen. Der Test haelt damit die Sonde ehrlich, ohne den Bestand einzufrieren.
@pytest.mark.parametrize("spur,nadel,ursache", [
    ("komponenten", "components/Band.tsx", ROOT / "web/components/Band.tsx"),
    ("wege", "/authority", ROOT / "web/app/authority/page.tsx"),
    ("symbole", "hatDichte", ROOT / "web/lib/docAnalysis.ts"),
    ("dienste", "antwort_arbeiter.py", ROOT / "scripts/antwort_arbeiter.py"),
])
def test_belegter_fund_wird_gemeldet(spur, nadel, ursache):
    """Jeder dieser vier Funde ist am 2026-10-06 von Hand nachgemessen worden.

    `antwort_arbeiter.py` zum Beispiel: kein Prozess (`pgrep`), kein Dienst (vier sind
    eingetragen), und kein anderer Abnehmer der Tabelle `user_antwortauftrag` im Repo —
    waehrend die Oberflaeche Auftraege ablegt und auf Ergebnisse wartet.
    """
    if not ursache.exists():
        pytest.skip(f"{ursache.name} ist weg — Fund behoben, Schweigen ist richtig")
    _, fn = L.SPUREN[spur]
    treffer = fn(False)
    assert any(nadel in z for z in treffer), \
        f"Spur {spur} meldet {nadel} nicht mehr, obwohl {ursache.name} noch da ist:\n  " \
        + "\n  ".join(treffer)


def test_geparkte_ausnahme_wird_gemeldet():
    """Steht eine Ausnahme ueber der Grenze, muss die Spur ihr Alter nennen.

    ⚠ Nicht „die zwei vom 2026-08-25" festnageln: werden sie behoben, soll der Test
    schweigen und nicht rot werden. Geprueft wird die Mechanik — gibt es im Quelltext einen
    `offen seit`-Vermerk, der aelter als die Grenze ist, muss er auftauchen.
    """
    import datetime as dt
    import re as _re
    heute = dt.date.today()
    alt = []
    for p in (ROOT / "scripts").glob("pruefe_*.py"):
        roh = L._ohne_prosa(p, p.read_text(encoding="utf-8", errors="replace"))
        for m in _re.finditer(r"offen seit (\d{4})-(\d{2})-(\d{2})", roh):
            tage = (heute - dt.date(*map(int, m.groups()))).days
            if tage > L.AUSNAHME_TAGE:
                alt.append(p.name)
    if not alt:
        pytest.skip("keine Ausnahme ueber der Grenze — nichts zu melden")
    treffer = L.spur_ausnahmen()
    for name in set(alt):
        assert any(name in z and "parkt seit" in z for z in treffer), \
            f"{name} parkt zu lange, wird aber nicht gemeldet:\n  " + "\n  ".join(treffer)


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
    for name, grund in {**L.RUHEND, **L.RUHENDE_DIENSTE, **L.RUHENDE_WEGE}.items():
        assert len(grund) > 30, f"{name} hat keine tragfaehige Begruendung: {grund!r}"


# ── Die drei geschlossenen Blindstellen ───────────────────────────────────────────────
def test_blindstelle1_stilblatt_ohne_komponente():
    """Spur 1 las nur `.ts/.tsx/.js/.mjs` und sah kein Stilblatt.

    Beide Richtungen am Bestand: die zwei unverwiesenen Blaetter MUESSEN erscheinen, die zwei
    eingebundenen (`marktpuls.css`, `trefferguete.css`) duerfen NICHT erscheinen. Ohne die
    zweite Haelfte waere die Spur eine, die einfach alles meldet.
    """
    treffer = L.spur_komponenten()
    for tot in ("SiteHeader.module.css", "SiteFooter.module.css"):
        if (ROOT / "web" / "components" / tot).exists():
            assert any(tot in z for z in treffer), f"{tot} wird nicht gemeldet"
    for lebt in ("marktpuls.css", "trefferguete.css"):
        assert not any(lebt in z for z in treffer), \
            f"{lebt} ist eingebunden und wird trotzdem gemeldet"


def test_blindstelle2_pruefwerk_ist_kein_produktaufrufer():
    """`api/org/zuordnung` wird NUR von `web/scripts/test_zuordnung.mjs` gerufen.

    Fuer ein Produktmerkmal ist das kein Aufrufer — die Oberflaeche zur Profilzuweisung
    (Preismodell §7.1) existiert nicht. ⚠ Der Fund fiel zuerst durch, weil der
    Kreuzvergleich ueber die Zweige dasselbe Pruefskript mitlas: die lokale Pruefung trennte
    Produkt und Pruefwerk, der Zweigvergleich nicht.
    """
    if not (ROOT / "web/app/api/org/zuordnung/route.ts").exists():
        pytest.skip("Route ist weg — Fund behoben")
    treffer = L.spur_wege()
    assert any("/api/org/zuordnung" in z and "Pruefwerk" in z for z in treffer), \
        "Route mit nur-Pruefwerk-Aufrufer wird nicht als solche gemeldet:\n  " \
        + "\n  ".join(treffer)
    assert L.ist_pruefwerk(ROOT / "web/scripts/test_zuordnung.mjs")
    assert not L.ist_pruefwerk(ROOT / "web/components/Landing.tsx")


def test_blindstelle2_webhook_bleibt_verschont():
    """Ein Webhook hat konstruktionsbedingt keinen internen Aufrufer — Stripe ruft ihn."""
    assert "/api/kauf/webhook" in L.RUHENDE_WEGE
    assert not any("/api/kauf/webhook" in z for z in L.spur_wege()), \
        "Webhook wird als Leiche gemeldet, obwohl er von aussen gerufen wird"


def test_blindstelle3_namensraum_genau_statt_pauschal():
    """Erst wurde das ganze Modul uebersprungen — 7 von 84, jedes eine Blindstelle.

    Jetzt wird der Aliasname an das Modul gebunden und nur das wirklich abgerufene Glied
    gilt als benutzt. Der Nachweis, dass es genauer ist: `betragCents` (als `P.betragCents`
    gerufen) bleibt draussen, `loadClaim` aus demselben Namensraum-Modul erscheint.
    """
    treffer = L.spur_symbole()
    assert not any("betragCents" in z for z in treffer), \
        "abgerufenes Glied wird als tot gemeldet"
    if (ROOT / "web/lib/supabase/claims.ts").exists():
        assert any("loadClaim" in z for z in treffer), \
            "pauschale Unterdrueckung ist zurueck — toter Export im Namensraum-Modul fehlt"


def test_kreuzvergleich_laesst_pruefwerk_aus():
    """⚠ Eine Ausnahme ist nur so scharf wie ihre unscharfste Haelfte.

    Der Zweigvergleich muss dieselben Pfade auslassen wie die lokale Pruefung, sonst reisst
    er die Trennung wieder ein (genau so fiel `/api/org/zuordnung` zuerst durch).
    """
    blob = L._fremde_sicht(L.lebende_zweige(), ("web",))
    assert "test_zuordnung" not in blob, \
        "Pruefwerk steckt wieder im Zweigvergleich — Produkttrennung ausgehebelt"


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
