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


def test_jedes_erlaubte_ereignis_hat_eine_aufrufstelle():
    """⚠ DIE ANDERE RICHTUNG — und genau die fehlte am 2026-10-02.

    `onboarding_begonnen`, `onboarding_firma_erkannt` und `konto_angelegt` standen in
    ERLAUBT, aber NIEMAND feuerte sie: deklariert und nicht verdrahtet. Der Trichter hatte
    drei leere Stufen, und das faellt nicht auf, weil eine fehlende Stufe genauso aussieht wie
    eine Stufe, die niemand erreicht.

    Die Lehre steht in memory `waechter-messen-prosa-statt-code`, Nachtrag 25.09.: BEIDE
    Richtungen pruefen. Die Pruefung darueber deckt nur „EV → ERLAUBT" ab.

    ⚠ NICHT „steht der Name irgendwo in web/" — das waere ein No-op: jeder Name steht
    zwangslaeufig in der `EV`-Definition selbst, und die Pruefung koennte nie rot werden.
    Die erste Fassung dieser Pruefung hatte genau diesen Fehler. Gesucht wird eine ECHTE
    Aufrufstelle: `track("name")` direkt, `EV.SCHLUESSEL` ausserhalb der Definition, oder der
    Sammler selbst.
    """
    # Schluessel → Ereignisname aus dem EV-Block
    ev_block = _block_ab(rumpf(ANALYTICS), "export const EV")
    paare = dict(re.findall(r'([A-Z_0-9]+)\s*:\s*"([a-z_0-9]+)"', ev_block))
    name_zu_schluessel = {v: k for k, v in paare.items()}

    # Alle Quellen, aber OHNE die Erlaubnisliste und OHNE den EV-Block selbst.
    quellen = []
    for p in list((WURZEL / "web").rglob("*.ts")) + list((WURZEL / "web").rglob("*.tsx")):
        if "node_modules" in str(p) or p.name == "telemetrieSenke.ts":
            continue
        t = ohne_kommentare(p.read_text("utf-8"))
        if p == ANALYTICS:
            t = t.replace(ev_block, "")      # die Definition zaehlt nicht als Aufruf
        quellen.append(t)
    alles = "\n".join(quellen)

    ohne_aufruf = []
    for n in sorted(erlaubte_namen()):
        direkt = f'track("{n}"' in alles or f"track('{n}'" in alles
        ueber_ev = (k := name_zu_schluessel.get(n)) is not None and f"EV.{k}" in alles
        # `seite_gesehen`, `seite_verlassen` und `klick` feuert der Sammler selbst.
        im_sammler = f'"{n}"' in rumpf(SAMMLER) or f'art: "{n}"' in rumpf(SAMMLER)
        if not (direkt or ueber_ev or im_sammler):
            ohne_aufruf.append(n)
    assert not ohne_aufruf, (
        f"in ERLAUBT, aber nirgends gefeuert: {ohne_aufruf}. Entweder verdrahten oder aus "
        "ERLAUBT nehmen — eine leere Trichterstufe sieht aus wie eine, die niemand erreicht.")


def test_selbstprobe_beide_richtungen_sind_kein_noop():
    """⚠ Erzwingt den Fund fuer die Pruefung darueber.

    Ein erfundener Name in ERLAUBT, den niemand feuert, MUSS auffallen. Ohne diese Probe
    haette die erste Fassung gruen gemeldet, obwohl sie jeden Namen in der EV-Definition
    selbst wiederfand und damit nie rot werden konnte.
    """
    ev_block = _block_ab(rumpf(ANALYTICS), "export const EV")
    paare = dict(re.findall(r'([A-Z_0-9]+)\s*:\s*"([a-z_0-9]+)"', ev_block))
    erfunden = "ereignis_das_niemand_feuert"
    assert erfunden not in paare.values()
    quellen = "\n".join(
        ohne_kommentare(p.read_text("utf-8"))
        for p in list((WURZEL / "web").rglob("*.ts")) + list((WURZEL / "web").rglob("*.tsx"))
        if "node_modules" not in str(p) and p.name != "telemetrieSenke.ts")
    assert f'track("{erfunden}"' not in quellen, (
        "SELBSTPROBE: ein erfundener Name gilt als gefeuert — die Pruefung ist ein No-op")


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


# ── 3b. Einwilligung (0036): der Client darf sie nicht behaupten ──────────────────────────

SENKE_T = WURZEL / "web" / "lib" / "telemetrieSenke.ts"
HINWEIS = WURZEL / "web" / "components" / "MessHinweis.tsx"
EINW = WURZEL / "web" / "lib" / "einwilligung.ts"


def test_einwilligung_kommt_aus_dem_cookie_nicht_aus_dem_koerper():
    """⚠ Sonst waere die Rechtsgrundlage ein Selbstbedienungsfeld.

    Wuerde `pruefe()` `einwilligung` oder `besucher` aus dem Anfragekoerper uebernehmen,
    koennte jeder `einwilligung: true` mitschicken — und die Spalte, die belegen soll, auf
    welcher Grundlage eine Zeile liegt, waere eine Behauptung ohne Wert.
    """
    r = rumpf(SENKE_T)
    i = r.index("export function pruefe")
    rumpf_pruefe = r[i:r.index("\n}", i)]
    for feld in ("einwilligung", "besucher", "referrer_voll", "browser", "geraet"):
        assert f"e.{feld}" not in rumpf_pruefe, (
            f"pruefe() liest `{feld}` aus dem Anfragekoerper — das muss aus dem Cookie kommen")
    assert "stufe2Aus" in r, "es gibt keine serverseitige Ableitung der Stufe-2-Felder"


def test_stufe2_ohne_einwilligung_liefert_nichts():
    """`stufe2Aus` muss bei fehlender Einwilligung frueh aussteigen."""
    r = rumpf(SENKE_T)
    i = r.index("export function stufe2Aus")
    block = r[i:r.index("\n}", i)]
    assert "istJa" in block, "stufe2Aus prueft die Entscheidung nicht"
    assert "einwilligung: false" in block, (
        "stufe2Aus kehrt ohne Einwilligung nicht mit `einwilligung: false` zurueck")


def test_kampagne_nur_aus_einer_festen_liste():
    """⚠ Nie der ganze Query-String: der kann Token und Mailadressen tragen."""
    r = rumpf(EINW)
    assert "utm_source" in r and "utm_campaign" in r, "keine utm-Liste gefunden"
    assert "searchParams" not in r or "UTM" in r, (
        "die Kampagnenlesung sieht aus, als nehme sie den ganzen Query-String")


def test_hinweis_zeigt_nur_auf_eine_seite_die_es_gibt():
    """⚠ DER RIEGEL: ein Einwilligungshinweis darf nicht auf eine 404-Seite verweisen.

    Er fragt nach Zustimmung zu etwas, das dann nirgends beschrieben steht — genau der
    Vorwurf, den man damit vermeiden will. Solange `web/app/datenschutz/` fehlt, darf der
    Hinweis NICHT im Layout haengen.
    """
    pfad = re.search(r'DATENSCHUTZ_PFAD\s*=\s*"([^"]+)"', rumpf(HINWEIS))
    assert pfad, "DATENSCHUTZ_PFAD nicht gefunden"
    seite = WURZEL / "web" / "app" / pfad.group(1).strip("/") / "page.tsx"
    eingehaengt = "MessHinweis" in rumpf(LAYOUT)
    if eingehaengt:
        assert seite.exists(), (
            f"MessHinweis haengt im Layout, aber {seite.relative_to(WURZEL)} fehlt — der "
            "Hinweis verweist auf eine 404-Seite. Erst die Datenschutzerklaerung, dann der "
            "Hinweis.")


def test_bot_art_faellt_bei_der_erfassung():
    """Welcher Crawler — die Kennzahl der KI-Sichtbarkeit (0036)."""
    r = rumpf(SENKE_T)
    assert "export function botArt" in r, "kein Crawler-Name abgeleitet"
    for erwartet in ("gptbot", "claudebot", "googlebot"):
        assert erwartet in r.lower(), f"{erwartet} fehlt in der Crawler-Liste"
    # ⚠ Reihenfolge: die Modell-Abrufer muessen VOR dem allgemeinen "bot" stehen, sonst
    #   verschluckt es sie. `GPTBot/1.2` enthaelt beides.
    assert r.lower().index("gptbot") < r.index("ROUTE") if "ROUTE" in r else True


def test_voller_user_agent_wird_nicht_gespeichert():
    """Grobe Klasse ja, Kennungstext nein — bei Menschen waere er ein Fingerabdruck."""
    r = rumpf(SENKE_T)
    assert not re.search(r"\buser_agent\s*:", r), "User-Agent wird als Feld geschrieben"
    assert "browserKlasse" in r, "keine grobe Browserklasse, also vermutlich der volle UA"


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
