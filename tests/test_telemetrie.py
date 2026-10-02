"""Wache: die Telemetrie ist VERDRAHTET und schreibt nichts Personenbezogenes.

WARUM DIESE WACHE EXISTIERT. Zwischen Ticket #8 und dem 2026-10-02 feuerte
`web/lib/analytics.ts` neun Ereignisse an acht Aufrufstellen — in einen Ring-Puffer im
Browser. Der PostHog-Zweig war tot (keine Abhaengigkeit, keine Initialisierung), und beim
Schliessen des Tabs war alles weg. Es gab also eine vollstaendige Analytik-Schicht, die nie
etwas gemessen hat, und niemandem fiel es auf, weil nichts kaputt war. „Gebaut, nicht
verdrahtet" ist in diesem Projekt die haeufigste Fehlerklasse; bei einer Messung ist sie
besonders tueckisch, weil der stille Ausfall wie ein Ergebnis aussieht (eine leere Tabelle
ist von „niemand klickt" nicht zu unterscheiden).

⚠ ALLE PRUEFUNGEN LAUFEN AUF DEM RUMPF OHNE KOMMENTARE. Die Begruendungen in den Quellen
nennen dieselben Woerter wie die Pruefungen (`sendeEreignis`, `textContent`, `nutzer_id`),
eine naive Suche schlaegt also an der eigenen Dokumentation an. Siehe memory
`waechter-messen-prosa-statt-code` — das ist an einem Tag fuenfmal passiert.
"""
import pathlib
import re

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
ANALYTICS = WURZEL / "web" / "lib" / "analytics.ts"
SENKE = WURZEL / "web" / "lib" / "telemetrieSenke.ts"
SAMMLER = WURZEL / "web" / "lib" / "telemetrie.ts"
ROUTE = WURZEL / "web" / "app" / "api" / "ereignis" / "route.ts"
LAYOUT = WURZEL / "web" / "app" / "layout.tsx"
NACHTLAUF = WURZEL / "scripts" / "daily_leads.sh"


def ohne_kommentare(quelle: str) -> str:
    """TS/JS-Rumpf ohne Block- und Zeilenkommentare."""
    quelle = re.sub(r"/\*.*?\*/", "", quelle, flags=re.S)
    return "\n".join(z.split("//", 1)[0] for z in quelle.splitlines())


def rumpf(p: pathlib.Path) -> str:
    assert p.exists(), f"{p.relative_to(WURZEL)} fehlt"
    return ohne_kommentare(p.read_text(encoding="utf-8"))


# ── 1. Ist die Senke ueberhaupt angeschlossen? ────────────────────────────────────────────

def test_track_ruft_die_eigene_senke():
    r = rumpf(ANALYTICS)
    assert "sendeEreignis" in r, (
        "track() ruft die eigene Senke nicht — die Ereignisse landen wieder nur im "
        "Ring-Puffer und verschwinden mit dem Tab (genau der Zustand vor dem 2026-10-02)")
    # Der Aufruf muss IN track() stehen, nicht irgendwo in der Datei.
    i = r.index("export function track")
    ende = r.index("\n}", i)
    assert "sendeEreignis" in r[i:ende], "sendeEreignis steht nicht im Rumpf von track()"


def test_provider_haengt_im_layout():
    r = rumpf(LAYOUT)
    assert "Telemetrie" in r, (
        "der Telemetrie-Provider ist nicht im Wurzel-Layout eingehaengt — ohne ihn gibt es "
        "weder Seitenaufrufe noch Verweildauer noch Klicks")


def test_aufbewahrung_laeuft_im_nachtlauf():
    r = NACHTLAUF.read_text(encoding="utf-8")
    nackt = "\n".join(z.split("#", 1)[0] for z in r.splitlines())
    assert "telemetrie_aufraeumen.py" in nackt, (
        "die Aufbewahrungsgrenze wird nirgends gerufen. Postgres hat keinen Zeitgeber: ohne "
        "diesen Aufruf waechst gov_ereignisse unbegrenzt (DSGVO Art. 5 Abs. 1 lit. e)")


# ── 2. Kennt der Server jedes Ereignis, das der Client schickt? ───────────────────────────

def _block_ab(r: str, anfang: str) -> str:
    """Von `anfang` bis zur ersten Zeile, die nur eine schliessende Klammer traegt.

    ⚠ NICHT nach `};` suchen: der EV-Block endet mit `} as const;`, der ERLAUBT-Block mit
    `]);`. Ein Parser, der eine bestimmte Schreibweise erwartet, bricht beim naechsten Umbau —
    und bricht dann LAUT (ValueError), was noch der gute Fall ist. Schlimmer waere ein Parser,
    der still einen leeren Block liefert: dann waere die Mengenpruefung unten trivial erfuellt
    und die Wache ein No-op.
    """
    i = r.index(anfang)
    zeilen = r[i:].splitlines()
    gesammelt = [zeilen[0]]
    for z in zeilen[1:]:
        gesammelt.append(z)
        if re.match(r"^\s*[}\]]", z):
            break
    block = "\n".join(gesammelt)
    assert len(gesammelt) > 2, f"Block `{anfang}` sieht leer aus — Parser pruefen"
    return block


def ev_namen() -> set[str]:
    """Die Werte aus `export const EV = { ... }` in analytics.ts."""
    namen = set(re.findall(r':\s*"([a-z_0-9]+)"', _block_ab(rumpf(ANALYTICS), "export const EV")))
    assert namen, "keine EV-Ereignisse gefunden — Parser pruefen, nicht die Pruefung streichen"
    return namen


def erlaubte_namen() -> set[str]:
    """Die Einträge aus `ERLAUBT` in telemetrieSenke.ts."""
    namen = set(re.findall(r'"([a-z_0-9]+)"', _block_ab(rumpf(SENKE), "ERLAUBT")))
    assert namen, "ERLAUBT sieht leer aus — Parser pruefen"
    return namen


def test_jedes_ev_ereignis_ist_serverseitig_erlaubt():
    """⚠ Der Server VERWIRFT, was nicht in ERLAUBT steht — ohne Fehlermeldung.

    Ein neues Ereignis in EV, das hier fehlt, feuert also fuer immer ins Leere, und die
    Auswertung zeigt einfach nichts an. Das ist dieselbe Stille wie vor dem 2026-10-02,
    nur eine Ebene tiefer.
    """
    fehlt = ev_namen() - erlaubte_namen()
    assert not fehlt, (
        f"in EV, aber nicht in ERLAUBT (werden still verworfen): {sorted(fehlt)}. "
        "Neue Ereignisse gehoeren an BEIDE Stellen.")


def test_direkt_getippte_ereignisnamen_sind_auch_erlaubt():
    """Nicht jede Aufrufstelle benutzt EV — einige tippen den Namen direkt hin."""
    direkt = set()
    for p in (WURZEL / "web" / "app").rglob("*.tsx"):
        direkt |= set(re.findall(r'track\(\s*"([a-z_0-9]+)"', ohne_kommentare(p.read_text("utf-8"))))
    for p in (WURZEL / "web" / "components").rglob("*.tsx"):
        direkt |= set(re.findall(r'track\(\s*"([a-z_0-9]+)"', ohne_kommentare(p.read_text("utf-8"))))
    direkt |= set(re.findall(r'track\(\s*"([a-z_0-9]+)"', rumpf(ANALYTICS)))
    fehlt = direkt - erlaubte_namen()
    assert not fehlt, f"direkt getippte Ereignisnamen fehlen in ERLAUBT: {sorted(fehlt)}"


# ── 3. Darf nicht in die Tabelle: Personenbezug ───────────────────────────────────────────

def test_klickziel_enthaelt_keinen_text():
    """⚠ Auf den App-Seiten stehen Vergabedaten.

    Wuerde die Klickerfassung `textContent` oder `aria-label` mitschicken, lagen Lead-Inhalte
    in der Telemetrie — und das faengt man spaeter nicht mehr ein, weil die Zeilen schon
    geschrieben sind. Fuer Heatmaps genuegt das Element plus die relative Position in ihm.
    """
    r = rumpf(SAMMLER)
    for verboten in ("textContent", "innerText", "innerHTML", "getAttribute(\"aria-label\")", ".value"):
        assert verboten not in r, (
            f"die Klickerfassung liest `{verboten}` — damit koennen Vergabedaten in "
            "gov_ereignisse landen")


def test_senke_speichert_keine_ip_und_keinen_user_agent():
    r = rumpf(SENKE)
    # Der User-Agent DARF gelesen werden (Bot-Erkennung), aber nicht als Feld gesetzt werden.
    assert not re.search(r"\buser_agent\s*:", r), "User-Agent wird als Feld geschrieben"
    assert not re.search(r"\b(ip|ip_adresse|ip_hash)\s*:", r), "IP wird als Feld geschrieben"


def test_route_nimmt_die_nutzerkennung_nicht_aus_dem_koerper():
    """Sonst koennte jeder Ereignisse auf fremde Konten schreiben."""
    r = rumpf(ROUTE)
    assert "auth.getUser()" in r, "die Route ermittelt den Nutzer nicht serverseitig"
    assert not re.search(r"\bnutzer_id\s*[:=]\s*(e|roh|body)\b", r), \
        "nutzer_id stammt aus der Anfrage statt aus der Sitzung"


def test_bot_urteil_faellt_bei_der_erfassung():
    """⚠ Die oeffentlichen Seiten SIND ein SEO-Kanal.

    Ungefiltert ist jede Trichterzahl nach OBEN verzerrt: sie sieht nach Erfolg aus, wo
    keiner ist. Deshalb muss `ist_bot` beim Erfassen entschieden werden, nicht beim Auswerten.
    """
    assert "ist_bot" in rumpf(SENKE), "kein Bot-Urteil in der Senke"
    assert "ist_bot" in rumpf(ROUTE), "die Route setzt kein Bot-Urteil"


# ── 4. Selbstprobe: schlagen die Pruefungen ueberhaupt an? ────────────────────────────────

@pytest.mark.parametrize("pruefung,quelle,entfernen", [
    ("Senke angeschlossen", ANALYTICS, "sendeEreignis"),
    ("Provider eingehaengt", LAYOUT, "Telemetrie"),
    ("kein Elementtext", SAMMLER, "zielVon"),
])
def test_selbstprobe_pruefungen_sind_kein_noop(pruefung, quelle, entfernen):
    """Erzwingt den Fund: nimmt man den geprueften Begriff heraus, MUSS er fehlen.

    Ohne diese Probe koennte eine Pruefung an einem Kommentar haengen und gruen bleiben,
    nachdem die Verdrahtung entfernt wurde — der Fehler, den diese Datei verhindern soll.
    """
    r = rumpf(quelle)
    assert entfernen in r, f"{pruefung}: Begriff `{entfernen}` nicht im Rumpf gefunden"
    verstuemmelt = r.replace(entfernen, "XXX")
    assert entfernen not in verstuemmelt, (
        f"SELBSTPROBE {pruefung}: der Begriff ueberlebt das Entfernen — die Pruefung "
        "misst etwas anderes als sie behauptet (vermutlich einen Kommentar)")
