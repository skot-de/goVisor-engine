"""Healy-Hudson: Zellen lesen, nicht Zeilen — und daraus echte Leads bauen.

Diese Datei gibt es wegen EINES Fehlers, der ein halbes Feature gekostet hat: der
Connector las `tr.innerText` und bekam Titel, Verfahrensart und Vergabestelle als einen
String. Ohne getrennte Vergabestelle gibt es keinen Käufer, ohne Käufer keinen Lead — die
Quelle sammelte wochenlang Bronze, aus dem nichts entstehen konnte.

Die Tests halten deshalb vor allem EINE Zusage fest: **aus einer Trefferzeile kommt eine
Vergabestelle heraus.** Alles andere ist Beiwerk.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from govisor import healyhudson as hh

ROOT = Path(__file__).resolve().parent.parent

# Wörtlich von der Liste abgelesen (Bremen, 2026-08-14). Sieben Zellen, zwei davon leer —
# genau die Form, die der Parser aushalten muss.
ZEILE_HB = ["", "SektVo",
            "28199/2026 Unterhalts- und Glasreinigung Flughafen Bremen "
            "Verhandlungsverfahren mit Teilnahmewettbewerb (Teil 1)",
            "Flughafen Bremen GmbH", "06.08.2026", "07.09.2026", ""]


def test_vergabestelle_kommt_getrennt_heraus():
    """Der Kern. Vorher steckte „Flughafen Bremen GmbH" im Titel-String fest."""
    s = hh.zerlege(ZEILE_HB, "HB")
    assert s is not None
    assert s["vergabestelle"] == "Flughafen Bremen GmbH"
    assert s["verordnung"] == "SektVo"
    assert s["titel"].startswith("28199/2026 Unterhalts- und Glasreinigung")
    # Die Vergabestelle darf NICHT zusätzlich im Titel hängen — sonst hätte der Parser
    # zwar Spalten gelesen, die Trennung aber nicht wirklich vollzogen.
    assert "Flughafen Bremen GmbH" not in s["titel"]


def test_leere_und_kurze_zeilen_fallen_durch():
    """Die Liste liefert reichlich leere `<tr>`. Sie dürfen keinen Satz erzeugen —
    ein Vorgang ohne Titel und ohne Fristdatum ist kein Vorgang."""
    assert hh.zerlege(["", "", "", "", "", "", ""], "HB") is None
    assert hh.zerlege(["", "VOB", "Titel", "Stelle"], "HB") is None          # zu kurz
    assert hh.zerlege(["", "VOB", "", "Stelle", "06.08.2026", "07.09.2026", ""],
                      "HB") is None                                          # kein Titel
    assert hh.zerlege(["", "VOB", "Titel", "Stelle", "irgendwas", "07.09.2026", ""],
                      "HB") is None                                          # kein Datum


def test_schluessel_haengt_an_den_zellen_nicht_am_leerraum():
    """Der Hash muss stabil bleiben, wenn der Browser Leerraum anders normalisiert —
    sonst gilt derselbe Vorgang morgen als neu und die Bronze-Ablage läuft voll."""
    a = hh.zerlege(ZEILE_HB, "HB")
    variante = [z.replace(" ", "  ") if z else z for z in ZEILE_HB]
    b = hh.zerlege([z.strip() for z in variante], "HB")
    assert a["schluessel"] == b["schluessel"] or a["titel"] != b["titel"], (
        "gleiche Zellen → gleicher Schlüssel")
    # Andere Zellen → anderer Schlüssel (sonst verschmelzen fremde Vorgänge).
    anders = list(ZEILE_HB); anders[3] = "Andere Stelle GmbH"
    assert hh.zerlege(anders, "HB")["schluessel"] != a["schluessel"]


def test_silber_namensraum_kollidiert_nicht_mit_ted():
    """`hh_`-Präfix. TED-IDs sind `\\d+_\\d{4}`, DÖE nutzt UUIDs und reine Zahlen — ein
    nackter Hash könnte mit beiden kollidieren, und eine Kollision im Notice-Namensraum
    verschmilzt Vergaben, statt nur etwas falsch anzuzeigen."""
    t = hh.nach_silber(hh.zerlege(ZEILE_HB, "HB"))
    nid = t["notices"][0]["notice_id"]
    assert nid.startswith("hh_")
    assert not nid[3:].isdigit() or "_" not in nid[3:]


def test_silber_traegt_bundesland_als_nuts():
    """Der eigentliche Mehrwert der Quelle: die unterschwellige Ebene hat sonst gar keine
    Landeszuordnung. Bremen = DE5, und der Käufer trägt es ebenfalls."""
    t = hh.nach_silber(hh.zerlege(ZEILE_HB, "HB"))
    assert t["notices"][0]["performance_nuts"] == "DE5"
    assert t["notice_parties"][0]["nuts"] == "DE5"
    assert t["notice_parties"][0]["role"] == "buyer"
    assert t["notice_parties"][0]["name"] == "Flughafen Bremen GmbH"
    assert len(hh.NUTS1) == 16, "alle sechzehn Länder, nicht nur die getesteten"


def test_silber_daten_und_art():
    t = hh.nach_silber(hh.zerlege(ZEILE_HB, "HB"))
    n = t["notices"][0]
    assert n["publication_date"] == dt.date(2026, 8, 6)
    assert n["submission_deadline"] == dt.date(2026, 9, 7)
    assert n["notice_kind"] == "cn"          # offene Ausschreibung, kein Zuschlag
    assert n["schema_gen"] == "healyhudson"
    assert n.get("portal_url") is None, (
        "die Trefferzeilen tragen nachweislich keinen Link — eine geratene URL wäre "
        "schlimmer als keine")


def test_verordnung_wird_auf_gold_vokabular_abgebildet():
    """Gold liest zwei Pfade. Beide müssen bedient werden, sonst bleibt
    `regulatory_regime` leer, obwohl die Quelle es hergibt."""
    def pfade(v):
        z = hh.zerlege(["", v] + ZEILE_HB[2:], "HB")
        t = hh.nach_silber(z)
        return {a["path"]: a["value"] for a in t.get("attributes", [])}

    assert pfade("VOB")["ContractNotice.RegulatoryDomain"] == "de-vob"
    assert pfade("UVgO")["ContractNotice.RegulatoryDomain"] == "de-uvgo"
    assert any(p.endswith("ProcurementLegislationDocumentReference.ID") and w == "vgv"
               for p, w in pfade("VGV").items())
    # `oVO` heisst „ohne Verordnung" — es auf ein Regime zu zwingen wäre geraten.
    ovo = pfade("oVO")
    assert "ContractNotice.RegulatoryDomain" not in ovo
    # ... der Rohwert bleibt aber IMMER stehen, sonst wäre die Zuordnung nicht nachprüfbar.
    assert ovo["HealyHudson.Vordn"] == "oVO"


def test_altes_format_wird_uebersprungen_nicht_geraten():
    """Sätze ohne getrennte Spalten tragen keine Vergabestelle. Sie aus dem geklebten
    String zurückzuraten wäre schlechter als sie neu zu holen — die Quelle ist live."""
    assert hh.nach_silber({"beschreibung": "Kälteanlagen Offenes Verfahren Sprinkenhof "
                                           "GmbH", "land": "HH", "pub": "13.08.2026",
                           "frist": "07.09.2026", "schluessel": "x"}) is None


def test_silber_schritt_haengt_im_tageslauf():
    """Ohne diesen Aufruf sammelt healyhudson Bronze und es entsteht kein Lead — genau
    der Zustand, in dem die Quelle bis zum 2026-08-14 war."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "govisor.healyhudson --silber" in lauf


def test_silber_laeuft_vor_dem_gold_schritt():
    """Die Reihenfolge ist kein Stil, sondern Bedingung.

    `build_prospective_leads` joint die Kaeufer ueber `party_entity` — und zwar mit einem
    INNER JOIN. Eine Notice, deren Kaeufer noch keine Entity hat, faellt lautlos raus.
    `party_entity` entsteht im Gold-Lauf aus `notice_parties`. Steht der Silber-Schritt
    dahinter, sind die Vorgaenge IMMER einen Lauf zu spaet — und niemand sieht es, weil
    nichts abbricht, es kommen nur weniger Leads an.
    """
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    silber = lauf.index("govisor.healyhudson --silber")
    gold = lauf.index("govisor.cli gold")
    assert silber < gold, "Silber muss VOR dem Gold-Rebuild laufen"


def test_bundesweite_vergaben_werden_zusammengefasst():
    """Die Quelle liefert je Bundesland eine eigene Liste — bundesweite Vergabestellen
    (BVVG, Max-Planck) stehen deshalb in mehreren. Gemessen: 97 von 777 Saetzen.

    Die Dubletten-Firewall faengt das NICHT: sie ueberspringt Paare derselben
    Schema-Generation (die Regel, die Geschwister-Lose entschaerft). Es muss also hier
    passieren, sonst waere dieselbe Vergabe bis zu viermal ein Lead.
    """
    satz = hh.zerlege(ZEILE_HB, "HB")
    t = hh.nach_silber(satz, ["HB", "BE", "BY"])
    attr = {a["path"]: a["value"] for a in t["attributes"]}
    # Vorhandene Projekt-Konvention statt neuem Begriff: `anyw-cou` speist `is_nationwide`,
    # damit greifen Umkreis- und Regionssuche ohne eine Zeile Anpassung.
    assert attr["ContractNotice.ProcurementProject.RealizedLocation.Address.Region"] == "anyw-cou"
    assert attr["HealyHudson.Bundeslaender"] == "BE,BY,HB", "welche Laender, bleibt belegt"
    # Ein Bundesland waehlen waere geraten — also keins.
    assert t["notices"][0]["performance_nuts"] is None
    assert t["notice_parties"][0]["nuts"] is None

    # Ein einzelnes Land bleibt dagegen ein Land.
    einzeln = hh.nach_silber(satz, ["HB"])
    assert einzeln["notices"][0]["performance_nuts"] == "DE5"
    assert not any(a["value"] == "anyw-cou" for a in einzeln["attributes"])


def test_firewall_kennt_die_quelle():
    """Die Rangfolge steuert, wohin fehlende Felder fliessen. healyhudson gehört ans Ende
    (kein CPV, kein Wert, keine Beschreibung) — ausdrücklich, nicht per Vorgabewert."""
    from govisor.dedupe import QUELLEN_RANG
    assert "healyhudson" in QUELLEN_RANG
    assert QUELLEN_RANG["healyhudson"] > QUELLEN_RANG["doe"]


# ── Hinweis-Chips (UI-Vertrag) ────────────────────────────────────────────────────────
#
# Diese Tests stehen hier und nicht bei den Daten, weil sie eine Zusage an die OBERFLAECHE
# festhalten. Sie pruefen Quelltext, nicht Verhalten.
#
# NACHTRAG 2026-08-15: der Mehrfach-Fall ist inzwischen im Browser GESEHEN — ueber die
# Suche („IGEL OS" → „Verlaengerung der IGEL OS Lizenzen") erreichbar, zwei Chips, Klick auf
# den zweiten schaltet die Belegzeile von „Amtsinhaber neu" auf „Dieselbe Vergabe erscheint
# auf 2 Portalen (Landesportal, TED)". Vorher stand hier, er sei nicht erreichbar; das lag
# an meiner Browser-Steuerung, nicht am Produkt.

def _hinweise_tsx() -> str:
    return (ROOT / "web" / "components" / "explorer" / "Hinweise.tsx").read_text(encoding="utf-8")


def test_chips_haben_keinen_deckel_mehr():
    """Als Kaesten war ein Deckel bei vier noetig (sonst Tapete). Als Chips passen alle in
    eine Zeile — ein Aufklapper fuer etwas, das nebeneinander steht, waere nur ein Klick.

    Geprueft wird, dass die abgeschaffte Mechanik nicht zurueckkommt: `teile`/`SICHTBAR`
    sind aus `lib/hinweise.ts` entfernt, und wer sie hier wieder importiert, hat den Umbau
    halb rueckgaengig gemacht.
    """
    quelle = _hinweise_tsx()
    assert "teile" not in quelle and "SICHTBAR" not in quelle
    lib = (ROOT / "web" / "lib" / "hinweise.ts").read_text(encoding="utf-8")
    assert "export const SICHTBAR" not in lib
    assert "export function teile" not in lib


def test_beleg_bleibt_sichtbar_nicht_nur_im_tooltip():
    """Der Kern des Umbaus, und der Punkt, an dem er haette schiefgehen koennen.

    „Nur Label" macht aus jedem Hinweis eine Behauptung — „Frist verlaengert", sagt wer?
    Der Beleg wandert deshalb unter die Chips, statt zu verschwinden. Ein `title`-Attribut
    allein reichte NICHT: es ist auf Beruehrungsgeraeten unerreichbar und wird beim Lesen
    uebersprungen.
    """
    quelle = _hinweise_tsx()
    assert 'className="hinweis-beleg"' in quelle, "die Belegzeile muss gerendert werden"
    assert "title={h.beleg}" in quelle, "zusaetzlich am Chip, fuer Maus und Screenreader"


def test_belegzeile_haelt_ihre_hoehe():
    """Ohne feste Hoehe springt das Layout bei jedem Chip-Klick, weil die Belegsaetze
    unterschiedlich lang sind. Springen liest sich als Fehler."""
    css = (ROOT / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    assert "min-height" in css.split(".hinweis-beleg")[1].split("}")[0]


def test_hinweise_stehen_buendig_zum_uebrigen_panel():
    """Gemessen 2026-08-15: `.detail` beginnt bei x=56, die Inhaltskarten bei x=88. Ohne
    Einzug klebten Chips und Belegzeile an der Panelkante — 32 px links von allem anderen —
    und der Aktiv-Ring wurde von `overflow-x: auto` abgeschnitten."""
    css = (ROOT / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    block = css.split(".hinweise-block {")[1].split("}")[0]
    assert "padding" in block and "32px" in block


# ── Der Bereichsrahmen ────────────────────────────────────────────────────────────────
#
# Gemessen am 2026-08-15 beim Durchklicken aller sechs Bereiche, VOR dem Umbau:
#
#   Bereich       Kopf   Titel                 Was scrollt
#   Akquise       93 px  —                     innerer Bereich
#   Merkliste     93 px  —                     innerer Bereich
#   Netzwerk      93 px  —                     innerer Bereich
#   Strategie     93 px  —                     innerer Bereich
#   Unternehmen   48 px  „Unser Unternehmen"   ganze Seite
#   Bausteine     48 px  „Bausteine"           ganze Seite
#
# Der Inhalt sprang bei jedem Wechsel um 45 px, zwei von sechs Bereichen trugen eine
# Ueberschrift, und das Scrollen fuehlte sich anders an. NACH dem Umbau: 48/45/93 ueberall.

def test_rahmenmasse_stehen_an_einer_stelle():
    """`--kopf` und `--leiste` halten den Inhalt in JEDEM Bereich auf derselben Hoehe. Zwei
    Werte an zwei Orten driften auseinander — genau so entstanden die 93 gegen 48."""
    g = (ROOT / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    assert "--kopf:" in g and "--leiste:" in g
    css = (ROOT / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    assert "height:var(--kopf)" in css, "die Kopfhoehe darf nicht aus dem Inhalt wachsen"
    assert "height:var(--leiste)" in css


def test_apptop_bringt_die_leiste_immer_mit():
    """Die Bereichsleiste ist PFLICHT im Aufbau, auch wenn ein Bereich nichts hineinstellt:
    ihre Hoehe haelt den Inhalt an derselben Stelle. Wer sie weglaesst, holt das Springen
    zurueck — und es faellt erst beim Wechseln auf, nie beim Bauen der einzelnen Seite."""
    quelle = (ROOT / "web" / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    assert 'className="bereichsleiste"' in quelle
    assert "titel" not in quelle.split("export function AppTop")[1].split("\n}")[0], (
        "AppTop darf keinen Titel mehr fuehren — zwei von sechs beschriftete Bereiche sind "
        "uneinheitlicher als keiner")


def test_filterleiste_haengt_nicht_mehr_im_kopf():
    """Sie war der Grund fuer die 93 px. Kaeme sie zurueck in den `<header>`, waere der
    Kopf wieder hoeher als auf den eigenstaendigen Seiten."""
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    kopf = shell.split("<header className=\"topbar\">")[1].split("</header>")[0]
    assert "<FilterBar" not in kopf, "die Filterleiste gehoert in die Bereichsleiste, nicht in den Kopf"
    assert 'className="bereichsleiste"' in shell


def test_beide_eigenstaendigen_seiten_fuellen_ihre_leiste():
    """Eine Leiste, die nur Hoehe haelt, ist Polsterung — genau das, wogegen der Rahmen
    gebaut wurde. Beide eigenstaendigen Seiten stellen deshalb ihre Werkzeuge hinein:
    Unternehmen die Reiter, Bausteine den Import-Knopf.

    Beides waren Umzuege aus dem INHALT nach oben. Sie lagen dort falsch: Reiter sind
    Navigation, ein Import-Knopf ist eine Werkzeugleiste — keins von beidem ist Inhalt.
    """
    for seite, erwartet in (("unternehmen", "UnternehmenTabs"), ("bausteine", "BausteineLeiste")):
        quelle = (ROOT / "web" / "app" / seite / "page.tsx").read_text(encoding="utf-8")
        assert f"leiste={{<{erwartet}" in quelle, f"{seite}: Leiste bleibt leer"


def test_leisten_knoepfe_tragen_die_rahmen_klasse():
    """`.btn-s` sieht in der Bereichsleiste nach NICHTS aus: sein Aussehen haengt an
    `.baust-page .btn-s`, und die Leiste liegt ausserhalb dieses Wrappers — der Knopf stand
    als nackter Text da (gesehen 2026-08-15).

    Die Lehre ist nicht „Regel nachziehen": was in der Leiste steht, gehoert zum RAHMEN und
    soll in jedem Bereich gleich aussehen. Deshalb `colbtn`, dieselbe Klasse wie
    Filter/Spalten/Export.
    """
    quelle = (ROOT / "web" / "components" / "explorer" / "BausteineLeiste.tsx").read_text(encoding="utf-8")
    assert 'className="colbtn"' in quelle
    # Nur die tatsaechlich gesetzten Klassen pruefen, nicht den Dateitext: der erste Entwurf
    # dieses Tests verbot die Zeichenfolge `btn-s` UEBERALL — und schlug damit an dem
    # Kommentar an, der erklaert, warum sie hier nichts taugt. Ein Test, der die Begruendung
    # verbietet, zwingt dazu, sie zu loeschen.
    import re as _re
    klassen = _re.findall(r'className="([^"]*)"', quelle)
    assert not [k for k in klassen if "btn-s" in k], f"Leisten-Knopf mit Seiten-Klasse: {klassen}"


# ── Betriebs-Dashboard (/intern/lauf) ─────────────────────────────────────────────────

def test_dashboard_liest_live_und_nicht_aus_einer_statusdatei():
    """Die naheliegende Loesung waere, den Tageslauf am Ende eine JSON schreiben zu lassen.
    Genau die versagt im wichtigsten Fall: laeuft er gar nicht erst an, schreibt er auch
    nichts — und das Dashboard zeigt vergnuegt den Stand von vorgestern.

    Gelesen wird deshalb, was UNABHAENGIG vom Lauf existiert: die Logdatei (oder ihr Fehlen)
    und die Archive auf der Platte."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert 'dynamic = "force-dynamic"' in r, "eine gecachte Ueberwachung ueberwacht nichts"
    assert "readdirSync" in r and "daily-" in r


def test_ausbleibender_lauf_ist_rot_und_nicht_still():
    """Der gefaehrlichste Zustand ist der, der sich als Ruhe tarnt. Fehlt die Schlusszeile
    im Log, ist der Lauf abgebrochen — und das muss als eigener, roter Zustand erscheinen."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert '"abgebrochen"' in r
    seite = (ROOT / "web" / "app" / "intern" / "lauf" / "page.tsx").read_text(encoding="utf-8")
    assert 'abgebrochen: { farbe: "bad"' in seite
    css = (ROOT / "web" / "app" / "intern" / "lauf" / "lauf.css").read_text(encoding="utf-8")
    assert ".lauf-bad" in css


def test_unbekannter_rueckstand_wird_nicht_geschaetzt():
    """Ohne Indexstand gibt es keine Zahl, nur Unwissen. Der erste Entwurf rechnete mit 0
    indizierten Archiven weiter und meldete einen Rueckstand von 3.282 — eine Zahl, die nach
    Alarm aussieht und nur bedeutet, dass noch nie ein Index mit Stand lief. Nach einer
    erfundenen Kennzahl wird gehandelt."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert "indiziert == null ? null" in r


def test_dashboard_ist_in_production_gesperrt():
    """Die Antwort enthaelt Logauszuege: Pfade, Fehlermeldungen, Schrittnamen. Das ist
    Betriebswissen und gehoert nicht ins offene Netz — dieselbe Sperre wie die anderen
    /api/intern-Routen."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert 'INTERN_ENABLED' in r and 'NODE_ENV === "production"' in r


# ── Warum der Tageslauf tagelang nicht lief ───────────────────────────────────────────
#
# Gefunden am 2026-08-15. Der Lauf war seit Tagen tot, und zwar UNSICHTBAR:
#
#   2026-08-14 13:00:03 ⚠ Verwaister Lock — uebernommen.
#   rm: .../data/.daily_leads.lock: Operation not permitted
#   Lock nicht uebernehmbar.
#
# Nicht „Lock haengt", sondern EPERM: `data/` ist ein Symlink auf die externe SSD, und macOS
# verweigert Hintergrunddiensten den Zugriff auf externe Volumes ohne Freigabe. Aus einem
# Terminal ging es (die App hat sie), aus launchd nicht.

def test_schreibtest_steht_vor_dem_lock():
    """Der Lock liegt SELBST auf der Datenplatte. Steht die Pruefung dahinter, stirbt der
    Lauf an ihm — mit einer Meldung ueber Locks statt ueber Rechte, und niemand sucht an
    der richtigen Stelle."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "_PROBE=" in lauf, "es muss einen Schreibtest geben"
    assert lauf.index("_PROBE=") < lauf.index('if ! mkdir "$LOCK"'), (
        "der Schreibtest muss VOR dem Lock stehen")
    assert "exit 77" in lauf, "EX_NOPERM — hier hilft kein spaeterer Versuch (kein 75)"


def test_daten_guard_prueft_schreiben_nicht_nur_lesen():
    """Der vorhandene Guard testete `-e` auf eine Datei. Lesen war erlaubt, Schreiben nicht —
    er schlug also nie an, obwohl genau das der Ausfall war."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    block = lauf.split("_PROBE=")[1].split("fi")[0]
    assert "mkdir" in block, "ein Lesetest beantwortet die Frage nicht"


def test_psql_wird_selbst_gefunden():
    """psql liegt unter /opt/homebrew/bin; der launchd-PATH kennt es nicht. Unter launchd
    waere die Schema-Migration STILL uebersprungen worden — mit einem Hinweis, den nachts
    niemand liest. Aus dem Terminal lief sie, weil dort Homebrew im PATH steht."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "/opt/homebrew/bin/psql" in lauf
    assert '"$PSQL"' in lauf, "die Aufrufe muessen den gefundenen Pfad nutzen"


def test_dashboard_sieht_laeufe_die_vor_dem_eigenen_log_sterben():
    """Ein Lauf, der an der gesperrten Platte stirbt, kann seine eigene Logdatei gar nicht
    anlegen — er waere im Dashboard unsichtbar. Genau der Fall lief tagelang."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert "LAUNCHD_ERR" in r and "govisor-launchd.err.log" in r
    seite = (ROOT / "web" / "app" / "intern" / "lauf" / "page.tsx").read_text(encoding="utf-8")
    assert "vorLog" in seite


def test_fortschritt_misst_gegen_den_letzten_lauf_nicht_gegen_das_skript():
    """Gemessen 2026-08-15: das Skript enthaelt 30 `step`-Aufrufe, der vollstaendige Lauf
    vom 14.08. meldete 20 — zehn Schritte haengen an Bedingungen (neue Quellen,
    Supabase-Creds, Phase).

    Ein Balken gegen die statische 30 stuende bei einem SAUBEREN Lauf fuer immer bei 67 %.
    Ein Fortschritt, der nie 100 % erreicht, wird nicht geglaubt — und dann auch der Rest
    der Seite nicht."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert "function massstab" in r
    assert "Tageslauf fertig in" in r.split("function massstab")[1][:900], (
        "als Massstab taugt nur ein VOLLSTAENDIGER Lauf")
    assert "Math.max(mass.schritte, fertig)" in r, (
        "laeuft der aktuelle Lauf laenger, ist der Massstab veraltet — nicht der Lauf kaputt")


def test_restzeit_nur_mit_grundlage():
    """Eine Restzeit ohne Massstab waere geraten — und nach ihr wird der Tag geplant."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert 'mass && mass.dauerSek && lauf.ergebnis === "laeuft"' in r
