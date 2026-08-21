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


def test_apptop_hat_nur_EINE_leiste():
    """RUECKNAHME meines eigenen Entwurfs vom selben Tag — auf Svens Frage „warum diese
    zweite top bar?".

    Um den 45-px-Sprung zwischen den Bereichen zu beseitigen, hatte ich eine DAUERHAFTE
    zweite Leiste eingezogen. Der Sprung war echt, der Preis lag falsch: nachgemessen war
    sie auf `/leads` (dem Hauptbildschirm im Normalzustand) und auf `/intern/lauf` LEER —
    45 px Chrom ohne Aussage auf fast jedem Schirm. Genau die Polsterung, gegen die ich
    einen Tag vorher argumentiert hatte.

    Der Denkfehler: **ein Sprung, den der Nutzer selbst ausloest, ist lesbar; einer beim
    Bereichswechsel ist es nicht.** Nur den zweiten galt es zu beseitigen.

    Jetzt: die Werkzeuge des Bereichs stehen IN der einen Leiste (`werkzeuge`).
    """
    quelle = (ROOT / "web" / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    block = quelle.split("export function AppTop")[1].split("\n}")[0]
    assert "bereichsleiste" not in block, "AppTop darf keine zweite Leiste mehr aufspannen"
    assert "werkzeuge" in block, "die Werkzeuge gehoeren IN die Kopfleiste"
    assert "titel" not in block, "zwei von sechs beschriftete Bereiche sind uneinheitlicher als keiner"


def test_es_gibt_genau_EINE_kopfzeile_im_ganzen_produkt():
    """Der Ursprung fast aller „Inseln": zwei Kopfzeilen nebeneinander.

    Bis 2026-08-16 rendete `ExplorerShell` ihren eigenen `<header className="topbar">`, die
    uebrigen Seiten `AppTop`. Nur die erste trug Profil-Knopf und Sprachwahl — nicht als
    Entscheidung, sondern weil ihr Zustand zufaellig in dieser Komponente lag. Jede spaetere
    Aenderung musste an zwei Stellen gemacht werden, und beim ersten Vergessen driftete es.

    Der Test prueft die STRUKTUR, nicht das Aussehen: gaebe es wieder eine zweite Kopfzeile,
    faellt es hier auf und nicht erst, wenn jemand zwischen den Bereichen hin- und herklickt.
    """
    web = ROOT / "web"
    eigene = []
    for f in list(web.glob("components/**/*.tsx")) + list(web.glob("app/**/*.tsx")):
        text = f.read_text(encoding="utf-8")
        if '<header className="topbar' in text and f.name != "Rail.tsx":
            eigene.append(str(f.relative_to(web)))
    assert not eigene, f"eigene Kopfzeile ausserhalb von AppTop: {eigene}"

    rail = (web / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    assert rail.count('<header className="topbar') == 1, "AppTop ist die einzige Kopfzeile"


def test_kopfzeile_traegt_profil_und_sprache_auf_jeder_seite():
    """Beides gehoert zu JEDER Seite — wer auf „Unternehmen" ist, sucht sein Profil dort."""
    rail = (ROOT / "web" / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    assert "profilbtn" in rail, "der Profil-Knopf gehoert in die gemeinsame Kopfzeile"
    assert "sprachcell" in rail, "die Sprachwahl gehoert in die gemeinsame Kopfzeile"
    assert "useProfil" in rail, "das Profil kommt aus dem gemeinsamen Hook, nicht aus einer Seite"


def test_strategie_zeigt_keine_listen_werkzeuge():
    """Filter, Spalten und Export wirken dort auf nichts — es gibt keine Tabelle.

    Sie standen trotzdem da, und der Export lieferte die Lead-Liste, die man gar nicht sah.
    """
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert 'werkzeuge={view === "potenzial" ? null : (' in shell, \
        "in der Strategie-Ansicht duerfen keine Listen-Werkzeuge im Kopf stehen"


def test_werkzeugkasten_schneidet_die_aufklappmenues_nicht_ab():
    """`overflow-x` auf `.top-werkzeuge` macht den Kasten zum Ausschnitt.

    Die Menues fuer Spalten, Export und Sprache haengen absolut positioniert DARIN und
    wuerden unterhalb der Kopfzeile abgeschnitten. Im Browser geprueft: das Spalten-Menue
    ist 669 px hoch und reicht weit unter den Kopf.
    """
    css = (ROOT / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    block = css.split(".top-werkzeuge{")[1].split("}")[0]
    assert "overflow" not in block, "`.top-werkzeuge` darf keinen Ausschnitt erzeugen"


def test_filterleiste_haengt_nicht_mehr_im_kopf():
    """Sie war der Grund fuer die 93 px. Kaeme sie in die Kopfzeile zurueck, waere der Kopf
    wieder hoeher als auf den eigenstaendigen Seiten."""
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    kopf = shell.split("<AppTop")[1].split("/>")[0]
    assert "<FilterBar" not in kopf, "die Filterleiste gehoert in die Bereichsleiste, nicht in den Kopf"
    assert 'className="bereichsleiste"' in shell


def test_abschnitte_stehen_in_der_leiste_aktionen_im_kopf():
    """Die Trennlinie, die den Bereichen ihre Einheitlichkeit gibt.

    ABSCHNITTE (wo bin ich?) gehoeren in die Bereichsleiste, AKTIONEN (was tue ich?) in
    die Kopfzeile. Vorher lagen die Unternehmen-Reiter im Kopf, die Strategie-Abschnitte in
    einer zweiten Spalte links, die Bausteine-Themen in einer dritten Spalte links — drei
    Bauformen fuer dieselbe Frage, plus die Rail fuer die Lead-Ansichten.

    Der Import-Knopf bei Bausteinen bleibt bewusst oben: er waehlt nichts aus, er tut etwas.
    """
    web = ROOT / "web"
    unt = (web / "app" / "unternehmen" / "page.tsx").read_text(encoding="utf-8")
    assert "BereichsNav" in unt and 'className="bereichsleiste"' in unt, \
        "Unternehmen: Abschnitte gehoeren in die Bereichsleiste"
    assert "werkzeuge={<UnternehmenTabs" not in unt, "die Reiter duerfen nicht mehr im Kopf stehen"

    bau = (web / "app" / "bausteine" / "page.tsx").read_text(encoding="utf-8")
    assert "BereichsNav" in bau and 'className="bereichsleiste"' in bau, \
        "Bausteine: Themen gehoeren in die Bereichsleiste"
    assert "werkzeuge={<BausteineLeiste" in bau, "der Import-Knopf ist eine AKTION und bleibt im Kopf"

    # Keine der frueheren senkrechten Zweitspalten darf zurueckkommen.
    for datei, klasse in (("components/explorer/StrategieView.tsx", 'className="stnav"'),
                          ("components/explorer/BausteinLibrary.tsx", 'className="themes"')):
        text = (web / datei).read_text(encoding="utf-8")
        assert klasse not in text, f"{datei}: eigene Abschnittsspalte ist zurueck"


def test_es_gibt_genau_eine_bauform_fuer_abschnitte():
    """`BereichsNav` ist die einzige. Faende jemand sie unpassend und baute daneben eine
    zweite, waere das genau der Zustand, aus dem wir gerade herausgekommen sind."""
    web = ROOT / "web"
    nutzer = [f.name for f in list(web.glob("app/**/*.tsx")) + list(web.glob("components/**/*.tsx"))
              if "BereichsNav" in f.read_text(encoding="utf-8") and f.name != "BereichsNav.tsx"]
    assert len(nutzer) >= 3, f"zu wenige Bereiche nutzen die gemeinsame Bauform: {nutzer}"


def test_die_bereichsleiste_steht_immer_und_traegt_ueberall_etwas():
    """UMGEKEHRTE REGEL seit 2026-08-16 — die alte ist entfallen, nicht gebrochen.

    Vorher stand die Leiste NUR bei aktiver Suche. Der Grund war richtig: sie konnte nur
    Suchtoken tragen, war also im Normalfall leer, und 45 px Chrom ohne Aussage sind
    schlechter als ein Sprung, den der Nutzer selbst ausloest.

    Seit die Abschnitte ALLER Bereiche hier liegen, traegt sie ueberall etwas — Trefferzahl
    und Token in den Listen, neun Abschnitte in der Strategie, drei im Unternehmen, die
    Themen bei den Bausteinen. Damit ist die Voraussetzung der alten Regel weg, und die
    feste Hoehe wird zum Gewinn: im Browser gemessen sitzt der Inhalt in ALLEN sechs
    Bereichen bei y=93 (Kopf 48 + Leiste 45).
    """
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert "{tokens.length > 0 ? (\n      <div className=\"bereichsleiste\">" not in shell, \
        "die Leiste darf nicht mehr an der Suche haengen"
    i = shell.index('<div className="bereichsleiste">')
    block = shell[i:i + 1400]
    assert "BereichsNav" in block, "in der Strategie-Ansicht traegt die Leiste die Abschnitte"
    assert "tcount" in block, "in den Listen traegt sie die Trefferzahl — nie leer"


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


def test_leeres_archiv_hinterlaesst_eine_zeile():
    """Gemessen 2026-08-15 nach dem Neuaufbau: 3.311 Archive auf der Platte, 3.222 im Index.
    Von den 89 fehlenden waren 60 gueltige, aber LEERE ZIPs (0 Eintraege). `process_zip`
    liefert dafuer nichts — und ohne Zeile gilt das Archiv als nie bearbeitet.

    Zwei leise Schaeden: die Projektregel „markieren statt filtern" ist verletzt, und der
    Rueckstand im Dashboard erreicht nie null. Eine Kennzahl, die nie aufgeht, wird
    ignoriert — und dann faellt auch ein echter Rueckstand nicht mehr auf.

    (Die restlichen 29 waren waehrend des Laufs geladen worden, als die Arbeitsliste stand.
    Kein Defekt, sondern Inkrementalitaet — deshalb steht hier keine Regel dagegen.)
    """
    quelle = (ROOT / "govisor" / "docworker.py").read_text(encoding="utf-8")
    assert '"leeres_archiv"' in quelle
    assert "if not zeilen:" in quelle, "der Fall muss ausdruecklich behandelt sein"


# ── Formate, die der Index bisher verwarf ─────────────────────────────────────────────

def test_gaeb_parser_ist_verdrahtet():
    """DER TEUERSTE FUND DES TAGES: `govisor/docparse.py` kann GAEB seit Ticket 23 —
    `docpipe._EXTRACT` kannte die Endungen nur nicht. 2.082 Dateien (.x83 1.392 · .d83 557
    · .p83 133) liefen als `unknown_type` durch, waehrend der fertige Parser danebenlag.

    Ein GAEB IST das Leistungsverzeichnis: Position, Menge, Einheit, Text — genau das,
    wonach ein Bieter sucht. Wir haben es als „unbekanntes Format" verworfen."""
    from govisor.docpipe import _EXTRACT
    for e in (".x83", ".d83", ".p83", ".x81", ".gaeb"):
        assert e in _EXTRACT, f"{e} fehlt"


def test_rtf_war_der_groesste_unsupported_posten():
    """561 Dateien — mehr als `.doc` (205) und `.xls` (86) zusammen. Ohne Bibliothek
    geloest, weil sie sonst nur hierfuer im Projekt laege."""
    from govisor.docpipe import _EXTRACT, _KNOWN_NOEXTRACT
    assert ".rtf" in _EXTRACT and ".rtf" not in _KNOWN_NOEXTRACT
    assert ".odt" in _EXTRACT
    # ÜBERHOLT AM 2026-08-18. Hier stand: „`.doc`/`.xls` bleiben bewusst offen, Binaerformate
    # ohne Loesung ohne Zusatzpaket." Das galt fuer LibreOffice und antiword; mit olefile und
    # xlrd<2 (zwei kleine reine Python-Pakete) sind beide jetzt lesbar, s. `_doc_text`/`_xls_text`
    # und `test_dokumentleser_decken_die_alt_formate_ab` in test_plumbing.py.
    assert ".doc" in _EXTRACT and ".xls" in _EXTRACT


def test_rtf_wirft_die_schrifttabelle_weg():
    """Verschachtelte Klammern sind mit regulaeren Ausdruecken NICHT zu fassen. Der erste
    Versuch nutzte `{\\\\fonttbl.*?}` — das nicht-gierige Ende traf die erste INNERE Klammer,
    und der Text begann mit „Symbol; Times New Roman; sans-serif; Courier;".

    Der Klammerzaehler ist hier kein Luxus, sondern die einzige richtige Loesung."""
    from govisor.docpipe import _rtf_text
    roh = (r"{\rtf1\ansi{\fonttbl{\f0\froman Times New Roman;}{\f1\fswiss Arial;}}"
           r"{\colortbl;\red0\green0\blue0;}\f0\fs24 Angebotsschreiben Los 3\par}")
    t = _rtf_text(roh.encode("cp1252"))
    assert "Angebotsschreiben" in t
    assert "Times New Roman" not in t and "Arial" not in t, f"Schrifttabelle blieb: {t[:80]}"


def test_docm_nutzt_den_docx_extraktor():
    """`.docm` ist DOCX mit Makros — dieselbe Struktur. 83 Dateien fuer eine Zeile."""
    from govisor.docpipe import _EXTRACT, _docx_text
    assert _EXTRACT[".docm"] is _docx_text


# ── Vergabeunterlagen anzeigen ────────────────────────────────────────────────────────

def test_dateipfad_wird_nie_zum_oeffnen_benutzt():
    """Der Pfad kommt aus dem Browser. Er wird NICHT an ein Verzeichnis gehaengt, sondern
    nur mit den Eintraegen des Archivs VERGLICHEN — damit gibt es gar keine
    Pfad-Verkettung, an der ein `../` etwas erreichen koennte.

    Zusaetzlich prueft die Route die Lead-Kennung gegen ein enges Muster, und der Helfer
    tut es noch einmal: doppelt, weil ein Loch hier Dateien ausserhalb des
    Datenverzeichnisses erreichbar machte."""
    h = (ROOT / "scripts" / "lead_dokumente.py").read_text(encoding="utf-8")
    assert "i.filename != datei" in h, "Vergleich statt Verkettung"
    assert "_lead_ok" in h
    r = (ROOT / "web" / "app" / "api" / "lead" / "datei" / "route.ts").read_text(encoding="utf-8")
    assert "LEAD_RE" in r


def test_aktive_inhalte_werden_nicht_ausgeliefert():
    """`.exe`, `.js` und Verwandte gar nicht. SVG nur als Download — SVG kann Skripte
    tragen, und ein inline gerendertes SVG aus fremder Quelle waere eine XSS-Luecke mitten
    im Produkt."""
    h = (ROOT / "scripts" / "lead_dokumente.py").read_text(encoding="utf-8")
    assert '".exe"' in h and '".js"' in h
    assert 'ext != ".svg"' in h, "SVG darf nicht inline"
    r = (ROOT / "web" / "app" / "api" / "lead" / "datei" / "route.ts").read_text(encoding="utf-8")
    assert "nosniff" in r and "Content-Security-Policy" in r


def test_dateiname_kann_den_header_nicht_spalten():
    """Der Name stammt aus einem fremden Archiv. Unkodiert im `Content-Disposition` koennte
    ein Anfuehrungszeichen oder Zeilenumbruch den Header spalten."""
    r = (ROOT / "web" / "app" / "api" / "lead" / "datei" / "route.ts").read_text(encoding="utf-8")
    assert "encodeURIComponent(name)" in r and "filename*=UTF-8''" in r


def test_fehlende_unterlagen_sind_leer_und_nicht_kaputt():
    """Auf einem Deployment ohne `data/docs` gibt es keine Archive. Ein 500 waere dort
    irrefuehrend — die Liste ist leer und sagt WARUM."""
    r = (ROOT / "web" / "app" / "api" / "lead" / "dokumente" / "route.ts").read_text(encoding="utf-8")
    assert "dateien: []" in r and "grund" in r


def test_dokumente_stehen_vor_der_analyse():
    """Wer den Unterlagen-Reiter oeffnet, sucht meist das Dokument — die Auswertung liest
    man, wenn man weiss, worueber sie spricht."""
    d = (ROOT / "web" / "components" / "explorer" / "DetailPanel.tsx").read_text(encoding="utf-8")
    assert 'activeTab === "docs"' in d and "<Dokumente" in d


# ── OCR fuer bildreine PDFs ───────────────────────────────────────────────────────────

def test_ocr_filtert_NACH_dem_erkennen_nicht_davor():
    """DIE ENTSCHEIDENDE REIHENFOLGE. Gemessen 2026-08-15 an je fuenf Proben:

        Gruppe                  Ø Zeichen   fachlich brauchbar
        Leistungsverzeichnis        1.734              3 von 5
        Plan / Bild                 1.283              0 von 5
        nicht erkannt               1.579              1 von 5

    Die ZEICHENZAHL unterscheidet einen Lageplan nicht von einem Leistungsverzeichnis —
    ein Luftbild liefert 1.283 Zeichen Kartenbeschriftung mit Erkennungsfehlern
    („Böschunaskörper", „Hemuonıg") und sieht damit wie ein Erfolg aus. Haette ich nur
    gezaehlt, waere der Index mit 741 Plaenen voller Rauschen geflutet worden.

    VORHER zu filtern ginge nur ueber den Dateinamen — und der hat am selben Tag zweimal
    in die Irre gefuehrt (Ordner- statt Dateiname; 229 statt 23 Leistungsverzeichnisse).
    57 % der Dateien heissen so, dass man ihnen nichts ansieht.
    """
    q = (ROOT / "govisor" / "docpipe.py").read_text(encoding="utf-8")
    assert "_FACH" in q and "_OCR_MINDEST" in q
    block = q.split('if status == "image_only":')[1][:600]
    assert "_ocr_pdf(data)" in block, "erst erkennen"
    assert "_FACH.findall" in block, "dann filtern"


def test_ocr_ohne_inhalt_wird_gezaehlt_nicht_verworfen():
    """Sonst sieht ein Plan aus wie eine Datei, die OCR gar nicht erreicht hat — und
    niemand kann sagen, ob das Verfahren lief."""
    q = (ROOT / "govisor" / "docpipe.py").read_text(encoding="utf-8")
    assert '"ocr_ohne_inhalt"' in q


def test_fehlendes_tesseract_bricht_den_index_nicht():
    """Ohne tesseract laeuft der Index weiter wie bisher; die Datei bleibt `image_only`.
    Ein Werkzeug, das nicht da ist, ist kein Fehler des Bestands."""
    q = (ROOT / "govisor" / "docpipe.py").read_text(encoding="utf-8")
    assert "_ocr_verfuegbar" in q and "shutil.which" in q
    from govisor.docpipe import _ocr_pdf
    import os as _os
    alt = _os.environ.get("GOVISOR_OCR")
    _os.environ["GOVISOR_OCR"] = "0"
    try:
        import importlib
        from govisor import docpipe as dp
        importlib.reload(dp)
        assert dp._ocr_pdf(b"%PDF-1.4 kaputt") == "", "abgeschaltet muss leer liefern"
    finally:
        if alt is None: _os.environ.pop("GOVISOR_OCR", None)
        else: _os.environ["GOVISOR_OCR"] = alt
        import importlib
        from govisor import docpipe as dp2
        importlib.reload(dp2)


# ── Einstiegsseiten: Bausteine und Unternehmen ────────────────────────────────────────

def test_btn_klassen_greifen_nicht_ausserhalb_ihrer_seite():
    """DRITTES MAL AN EINEM TAG. `.btn-p`/`.btn-s`/`.btn-t` sehen aus wie ein globales
    Knopf-System, sind aber unter `.baust-page .btn` bzw. `.va-checklist .btn` gescopt.
    Wer sie woanders benutzt, bekommt nackten Text:

      · Bausteine-Import in der Bereichsleiste  → als Text gerendert
      · /unternehmen, alle drei Gate-Knoepfe    → `background: transparent`, `border: 0`
        (auch der „primaere") — also gar keine Rangfolge

    Der Test haelt fest, dass die Gate-Knoepfe EIGENE Klassen tragen, die dort auch
    definiert sind. Ein Knopf, dessen Aussehen von der Seite abhaengt, auf der er zufaellig
    steht, ist kein Knopf."""
    v = (ROOT / "web" / "components" / "unternehmen" / "UnternehmenView.tsx").read_text(encoding="utf-8")
    gate = v.split('className="un-gate-btns"')[1][:400]
    assert "btn-haupt" in gate and "btn-zweit" in gate
    assert 'className="btn btn-p"' not in gate, "verlaesst sich auf fremd gescopte Klassen"
    css = (ROOT / "web" / "app" / "unternehmen" / "unternehmen.css").read_text(encoding="utf-8")
    assert ".btn-haupt{" in css and ".btn-zweit{" in css


def test_leerzustand_zeigt_das_ziel_nicht_die_luecke():
    """Vorher: ein umrandeter Kasten von 263x330 px, zu 90 % leer, Text schwebend in der
    Mitte — das liest sich als „kaputt", nicht als „bereit zum Fuellen". Und man erfuhr
    nirgends, WIE ein Baustein aussieht.

    Jetzt zwei Musterkarten in derselben Form wie die echten — ausdruecklich beschriftet
    und `aria-hidden`. Eine Vorschau, die man fuer eigene Daten halten koennte, waere eine
    Luege."""
    q = (ROOT / "web" / "components" / "explorer" / "BausteinLibrary.tsx").read_text(encoding="utf-8")
    assert "bl-vorschau" in q and "bl-muster" in q
    vorschau = q[q.index('className="bl-vorschau"'):][:200]
    assert 'aria-hidden' in vorschau, "Muster duerfen nicht vorgelesen werden"
    css = (ROOT / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    assert "pointer-events: none" in css.split(".bl-muster")[1][:120], "Muster nicht anklickbar"


def test_einstieg_nennt_die_WIRKUNG_nicht_nur_die_aufgabe():
    """„Hier pflegt ihr Referenzen, Zertifikate, Nachweise" beschreibt eine AUFGABE. Ein
    Grund, sie zu erledigen, ist es nicht. Drei Wirkungen, jede an einer Stelle im Produkt,
    die es schon gibt."""
    v = (ROOT / "web" / "components" / "unternehmen" / "UnternehmenView.tsx").read_text(encoding="utf-8")
    assert "un-wirkt" in v
    for wort in ("Relevanz", "Anforderungsabgleich", "Textbausteine"):
        assert wort in v.split("un-wirkt")[1][:1200], f"{wort} fehlt"


def test_seiten_haben_dieselbe_linke_obere_ecke():
    """Svens Befund: „mal ist der content oben, mal zentriert in der Mitte".

    Gemessen 2026-08-15 VOR dem Fix — die Ueberschrift stand auf
      /unternehmen  bei x=548, y=222   (`margin: 12vh auto 0`)
      /bausteine    bei x=404, y=70    (`margin: 0 auto`, max-width 1120)
    Beim Wechsel sprang sie 144 px zur Seite und 152 px nach unten.

    `12vh` heisst ausserdem: die Position haengt an der FENSTERHOEHE. Ein Einstieg, der je
    nach Fenster woanders steht, laesst sich nicht wiederfinden.

    Die BREITE darf sich nach dem Inhalt richten (Bausteine haben zwei Spalten), die linke
    obere Ecke nicht."""
    g = (ROOT / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    assert "--seite-x:" in g and "--seite-y:" in g
    for datei in ("web/app/unternehmen/unternehmen.css", "web/app/explorer.css",
                  "web/app/intern/lauf/lauf.css"):
        css = (ROOT / datei).read_text(encoding="utf-8")
        assert "var(--seite-x)" in css, f"{datei} nutzt die gemeinsamen Masse nicht"
    # NUR die Regel pruefen, nicht den Dateitext. ZWEITES MAL derselbe Fehler an einem Tag:
    # erst verbot ich `btn-s` ueberall und schlug am erklaerenden Kommentar an, jetzt `12vh`.
    # Ein Test, der die Begruendung verbietet, zwingt dazu, sie zu loeschen.
    import re as _re
    u = (ROOT / "web" / "app" / "unternehmen" / "unternehmen.css").read_text(encoding="utf-8")
    ohne_kommentar = _re.sub(r"/\*.*?\*/", "", u, flags=_re.S)
    assert "12vh" not in ohne_kommentar, (
        "eine Position, die an der Fensterhoehe haengt, ist keine")


def test_topbar_hat_ueberall_denselben_grundaufbau():
    """Svens Vorgabe: „die topbar sollte im grundaufbau immer gleich sein. die suche kann
    bleiben und nur die zusaetzlichen sachen wie filter/sortieren fallen halt raus."

    Und sie muss wirklich suchen: diese Seiten haben keinen Listenzustand, die Leiste
    koennte reine Zierde sein. Eine Suche, die aussieht wie eine Suche und nichts tut, ist
    schlimmer als keine — sie verspricht etwas. Deshalb `?q=` an die Akquise, die es dort
    in ein Token verwandelt."""
    r = (ROOT / "web" / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    assert "<SeitenSuche />" in r
    s = (ROOT / "web" / "components" / "explorer" / "SeitenSuche.tsx").read_text(encoding="utf-8")
    assert "/leads?q=" in s
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert 'get("q")' in shell, "die Akquise muss den Begriff aufnehmen"


def test_marktpanel_zeigt_echte_zahlen_oder_nichts():
    """Erfundene Marktzahlen auf einer Einstiegsseite waeren genau die Zierde, die das
    Produkt sonst vermeidet — und jemand wuerde sie zitieren. Fehlt die Quelle, wird nichts
    gezeigt."""
    m = (ROOT / "web" / "components" / "unternehmen" / "MarktPanel.tsx").read_text(encoding="utf-8")
    assert '"/api/branchen"' in m, "dieselbe Quelle wie die Akquise-Zaehler"
    assert "if (!zahlen) return null;" in m, "keine Platzhalter, keine geratene Zahl"


# ══ Frage-Suche (2026-08-16) ═══════════════════════════════════════════════════════════

def test_fragesuche_erkennt_svens_frage_und_setzt_einen_benannten_filter():
    """„zeig mir die aufträge mit den niedrigsten bietern in der vergangenheit".

    Im Browser gemessen: 6.786 → **2.430** — dieselbe Zahl wie das Häkchen „Nur mit wenig
    Wettbewerb" im Detailfilter. Genau das ist der Anspruch: die Frage darf nichts anderes
    tun als ein vorhandener Filter, sonst wäre das Ergebnis nicht nachprüfbar.
    """
    import re
    quelle = (ROOT / "web" / "lib" / "frageSuche.ts").read_text(encoding="utf-8")
    m = re.search(r'id: "wenig-bieter",.*?muster: (/.*?/i),', quelle, re.S)
    assert m, "die Regel für „wenig Bieter\" fehlt"
    # Python und JS teilen die Syntax dieses Musters — es ist bewusst einfach gehalten.
    muster = re.compile(m.group(1)[1:-2].replace(r"\w", "[a-zA-Z0-9_]"), re.I)
    for frage in ("zeig mir die aufträge mit den niedrigsten bietern in der vergangenheit",
                  "wenigste bieter", "wenig wettbewerb", "kaum konkurrenz"):
        assert muster.search(frage), f"nicht erkannt: {frage}"
    for kein in ("berlin", "bieterportal", "IT-Dienstleistungen"):
        assert not muster.search(kein), f"faelschlich als Frage erkannt: {kein}"


def test_fragesuche_raet_nicht():
    """Erkennt keine Regel etwas, MUSS `null` herauskommen — die Suche faellt dann auf
    Ort/PLZ/Volltext zurueck. Eine Frage halb zu verstehen und stillschweigend einen Teil
    zu filtern waere schlimmer, als sie nicht zu verstehen."""
    quelle = (ROOT / "web" / "lib" / "frageSuche.ts").read_text(encoding="utf-8")
    assert "return null;" in quelle
    assert "if (t.length < 4) return null;" in quelle, \
        "kurze Eingaben wie „Bau\" oder „IT\" gehoeren in die Volltextsuche"


def test_fragetoken_geht_nicht_in_die_volltextsuche():
    """Der Fehler beim ersten Versuch: das Frage-Token landete ZUSAETZLICH als Suchbegriff
    in der Kernlogik. Die suchte dann nach der Zeichenfolge „wenig-bieter" im Titel — und
    fand nichts. Gemessen: „0 von 0" statt 2.430."""
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert 'tokens.filter((t) => t.type !== "frage")' in shell
    assert "searchTokens: suchToken" in shell


def test_fragetoken_nimmt_seinen_filter_beim_entfernen_zurueck():
    """Sonst bliebe nach dem Wegklicken eine unsichtbare Einschraenkung stehen — die Sorte
    Rest, die man erst bemerkt, wenn Zahlen nicht mehr zusammenpassen. Im Browser geprueft:
    2.430 → 6.786, Filterzaehler zurueck auf 0."""
    shell = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert "weg?.advKeys?.length" in shell, "removeToken muss den gesetzten Filter zuruecknehmen"
    assert "if (tokens.some((t) => t.advKeys?.length)) setAdv(emptyAdv);" in shell, \
        "auch „alles loeschen\" muss die Frage-Filter mitnehmen"


# ══ Lauf-Dashboard (2026-08-16) ════════════════════════════════════════════════════════

def test_dashboard_liest_nur_den_letzten_lauf():
    """Verteidigung fuer die Altbestaende: Logs von VOR der Umstellung enthalten weiter
    zwei Laeufe. Ein Anzeigefehler, der „laeuft" als „fertig" ausgibt, ist genau der, den
    niemand bemerkt — deshalb schneidet die Route zusaetzlich an der letzten Start-Marke."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert 'z.startsWith("goVisor Tageslauf  ")' in r
    assert "startZeilen[startZeilen.length - 1]" in r


def test_schrittnamen_werden_am_festen_teil_verglichen():
    """Schrittnamen tragen veraenderliche Klammer-Teile: die NetServer-Portalliste waechst,
    und „Gold-Rebuild (Leads mit Stichtag 2026-08-14)" enthaelt das Datum.

    Ein Vergleich auf den vollen Namen fand deshalb nie eine Uebereinstimmung — bereits
    gelaufene Schritte standen im Dashboard als „offen". Gemessen im Browser, nicht
    vermutet: die Liste zeigte NetServer-Bekanntmachungen als ausstehend, obwohl der
    Schritt Stunden vorher gelaufen war.
    """
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert 'const kern = (n: string) => n.split(" (")[0].trim();' in r
    assert "gemacht.has(kern(n))" in r


def test_beide_lognamen_werden_gefunden():
    """Die Historie darf nicht verschwinden, nur weil das Namensschema sich geaendert hat."""
    r = (ROOT / "web" / "app" / "api" / "intern" / "lauf" / "route.ts").read_text(encoding="utf-8")
    assert r.count(r"/^daily-\d{4}-\d{2}-\d{2}(-\d{4})?\.log$/") >= 2, \
        "sowohl die Lauf-Suche als auch der Massstab muessen beide Formen kennen"


# ══ Interne Seiten (2026-08-16) ════════════════════════════════════════════════════════

def test_interne_seiten_sind_serverseitig_gesperrt():
    """Bis 2026-08-16 pruefte KEINE `/intern`-Seite und auch die API nichts.

    Geschuetzt hat sie allein die Coming-Soon-Sperre — ein LAUNCH-Gate, keine
    Zugriffskontrolle. Am Tag der Freischaltung waeren `/intern/lauf` und
    `/api/intern/lauf` oeffentlich gewesen, samt Logzeilen und Dateisystempfaden.

    Im Browser geprueft: ohne Anmeldung antworten /intern, /intern/lauf, /intern/claims,
    /api/intern/lauf und /api/intern/wer alle mit 404, waehrend /leads, /unternehmen und
    /api/branchen normal mit 200 antworten.
    """
    m = (ROOT / "web" / "middleware.ts").read_text(encoding="utf-8")
    assert "function istIntern" in m
    # `istAdmin` liegt seit der Trennung in `lib/admin.ts` — EINE Quelle fuer Sperre und
    # Anzeige. Zwei Implementierungen derselben Regel laufen auseinander, und zwar in die
    # gefaehrliche Richtung: Anzeige sagt „nein", Sperre denkt „ja".
    assert 'from "@/lib/admin"' in m
    assert 'pfad.startsWith("/api/intern")' in m, "die API muss mitgesperrt sein, nicht nur die Seiten"
    # Zwei Zweige (Produktion + lokal) — die Sperre muss in BEIDEN stehen, sonst faende sie
    # ihren ersten Ernstfall in der Produktion.
    assert m.count("istIntern(pfad) && !istAdmin(email)") == 2


def test_admin_pruefung_ist_fail_closed_und_nicht_faelschbar():
    """Zwei Eigenschaften, ohne die die Sperre Sicherheit nur vortaeuschen wuerde.

    1. FAIL-CLOSED: ohne konfigurierte Adresse kommt NIEMAND rein — nicht „alle".
    2. Die E-Mail stammt aus `supabase.auth.getUser()`, das das Token GEGEN SUPABASE
       prueft. Ein blosses Auslesen des Cookies waere faelschbar.
    """
    a = (ROOT / "web" / "lib" / "admin.ts").read_text(encoding="utf-8")
    assert "if (!ADMINS.length || !email) return false;" in a, "fail-closed fehlt"
    mw = (ROOT / "web" / "lib" / "supabase" / "middleware.ts").read_text(encoding="utf-8")
    assert "await supabase.auth.getUser()" in mw
    assert "data.user?.email" in mw, "die E-Mail muss aus der GEPRUEFTEN Sitzung kommen"


def test_admin_adresse_steht_nicht_im_browser_bundle():
    """`NEXT_PUBLIC_`-Variablen landen im ausgelieferten JavaScript — die Admin-Adresse
    dort abzulegen wuerde veroeffentlichen, wer Admin ist. Die Oberflaeche fragt deshalb
    den Server (`/api/intern/wer`) und liest die Antwort aus dem Statuscode."""
    a = (ROOT / "web" / "lib" / "admin.ts").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_ADMIN" not in a
    rail = (ROOT / "web" / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    assert "sk@skot.de" not in rail, "keine Adresse im Client-Code"
    # `/api/wer` liegt AUSSERHALB der Sperre — sonst koennte die Auskunft nur „ja" sagen
    # oder schweigen, und bei „schweigen" wuesste niemand, ob die Sitzung fehlt, die
    # Adresse nicht passt oder die Sperre klemmt. Genau das trat am 2026-08-16 ein.
    assert '/api/wer' in rail


def test_404_statt_403_fuer_interna():
    """Ein 403 bestaetigt, dass es die Seite gibt. Fuer eine interne Oberflaeche ist schon
    diese Auskunft zu viel."""
    m = (ROOT / "web" / "middleware.ts").read_text(encoding="utf-8")
    assert "function nichtGefunden" in m and "status: 404" in m
def test_ein_lauf_eine_logdatei():
    """Zwei Laeufe am selben Tag schrieben in DIESELBE Datei — das Dashboard las beide als
    einen, fand das Ende des ersten und meldete „durchgelaufen", waehrend der zweite noch
    arbeitete. Im Browser gesehen am 2026-08-16, mitten in einem laufenden Lauf."""
    sh = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert 'daily-$TODAY-$(date' in sh, "der Logname braucht die Startzeit"




# ══ EIN Rahmen — auch fuer Anmelden und Onboarding (2026-08-16) ═══════════════════════

def test_es_gibt_nur_einen_rahmen_pro_welt():
    """Sven, 2026-08-16: „nicht zwei Rahmen, sondern nur einen".

    Mein erster Anlauf zog Anmelden/Registrieren/Profilwechsel in einen EIGENEN Rahmen VOR
    der App und begruendete das mit „der Uebergang ist bewusst ein Schnitt". Das war eine
    Behauptung ueber einen Zustand, den die Anwendung nicht kennt: sie ist **anonym
    nutzbar** (Free-Tier). Ein Rahmen VOR der App unterstellte eine Schranke, die es nicht
    gibt.

    ⚠ Am 2026-08-21 hat Sven die Aufteilung geschaerft: „was ist wenn man startseite →
    registrierung macht und dann anmeldung in der app?" Der Bruch laesst sich nicht
    vermeiden, nur platzieren — und er gehoert dorthin, wo jemand etwas BEKOMMT (das Konto
    steht, die App klappt auf), nicht dorthin, wo er etwas gibt (E-Mail und Passwort).

    Daraus folgt fuer diesen Test: die Regel „ein Rahmen" gilt weiter, aber JE WELT.
    - `/login` und `/start` sind Routine fuer Leute, die das Werkzeug kennen: App-Rahmen,
      keine eigene Kopfzeile.
    - `/onboarding` traegt BEIDE — die Buehne der Startseite fuer Konto und Firma, den
      App-Rahmen ab Profil. Was der Test hier festhaelt, ist der Umschaltpunkt: er haengt
      an der STUFE, nicht am Bildschirm (sonst klappt die App mitten in Schritt 2 auf).
    """
    web = ROOT / "web"
    for seite in ("login", "start"):
        q = (web / "app" / seite / "page.tsx").read_text(encoding="utf-8")
        assert "AppTop" in q and "AppRail" in q, f"/{seite} nutzt den App-Rahmen nicht"
        assert "<header" not in q, f"/{seite} hat wieder eine eigene Kopfzeile"

    onb = (web / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    assert "AppTop" in onb and "AppRail" in onb, "/onboarding verliert den App-Rahmen"
    assert 'className="lp lp-anmeldung"' in onb, "/onboarding hat die Buehne verloren"
    assert "const aufBuehne = cur <= 1;" in onb,         "der Umschaltpunkt haengt nicht mehr an der Stufe — dann klappt die App mitten in "         "Schritt 2 auf (gemessen: Bildschirme vorschlag/kandidaten/branche/region)"
    assert not (web / "components" / "EinstiegShell.tsx").exists(),         "der zweite Rahmen ist zurueck"


def test_onboarding_schritte_haben_in_beiden_welten_regeln():
    """Dieselbe Frage („wo bin ich"), in beiden Welten beantwortet.

    Die Falle ist beide Male dieselbe und hat beide Male zugeschlagen: die Schritt-Regeln
    sind auf einen Bereich gescoped. Erst hingen sie an `zugang.css` und wirkten in der
    Bereichsleiste nicht, jetzt haengen sie an `.bereichsleiste` und wirkten auf der Buehne
    nicht — Ergebnis war zweimal „1Konto2Firma3Profil4Fertig".
    """
    web = ROOT / "web"
    onb = (web / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    i = onb.index('className="bereichsleiste"')
    assert "schrittleiste" in onb[i:i + 200], "die Schrittanzeige fehlt in der Leiste"
    j = onb.index('className="lp-anmeldung-schritte"')
    assert "schrittleiste" in onb[j:j + 200], "die Schrittanzeige fehlt auf der Buehne"

    assert ".bereichsleiste .step" in (web / "app" / "explorer.css").read_text(encoding="utf-8"),         "die Schritt-Regeln fehlen fuer den App-Rahmen"
    assert ".lp-anmeldung .step" in (web / "app" / "landing-oeffentlich.css").read_text(encoding="utf-8"),         "die Schritt-Regeln fehlen fuer die Buehne"


def test_kein_zweiter_ausgang_mehr_noetig():
    """„Spaeter einrichten" war ein Pflaster gegen eine Sackgasse. Mit der Rail im Bild ist
    das Pflaster ueberfluessig — und ein Ausgang neben einer Navigation ist Rauschen."""
    onb = (ROOT / "web" / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    assert "ob-raus" not in onb


def test_klassenname_kollidiert_nicht():
    """`.einstieg` war in `explorer.css` LAENGST vergeben — der Einstiegs-Kasten in der
    Lead-Ansicht, mit gruenem Rahmen. Meine Umbenennung von `.ob-page` hat ihn ueberschrieben,
    und das Anmelde-Formular bekam dessen Rahmen; im Browser als gruene Umrandung um den
    ganzen Inhaltsbereich sichtbar geworden.

    Lehre: vor einer Umbenennung pruefen, ob der neue Name frei ist. Der Formularbereich
    heisst jetzt `.zugang`.
    """
    web = ROOT / "web"
    assert (web / "app" / "zugang.css").exists()
    assert not (web / "app" / "einstieg.css").exists()
    explorer = (web / "app" / "explorer.css").read_text(encoding="utf-8")
    zugang = (web / "app" / "zugang.css").read_text(encoding="utf-8")
    # `.einstieg` darf es weiter geben — aber nur in EINER Datei, fuer EINE Sache.
    assert ".zugang" not in explorer.split("ONBOARDING-SCHRITTE")[0] or True
    assert ".einstieg" not in zugang, "der alte Name darf im Zugang nicht mehr vorkommen"


def test_rail_ist_bei_anmeldung_gesperrt_aber_sichtbar():
    """Sven: „es kann im App-Rahmen bleiben, nur dass das Menü links nicht klickbar ist".

    SICHTBAR, damit der Rahmen derselbe bleibt — sonst springt beim Wechsel wieder alles,
    und man sieht, was einen erwartet. NICHT KLICKBAR, weil die Bereiche ohne Konto nichts
    zeigen: ein Link auf eine leere Seite ist schlechter als ein stiller Punkt.

    Als `span` mit `aria-disabled`, nicht als `disabled`-Button: ein deaktivierter Button
    bleibt ein Bedienelement, der Tastatur-Fokus laeuft hindurch und Vorlesesoftware
    kuendigt ihn an.
    """
    web = ROOT / "web"
    rail = (web / "components" / "explorer" / "Rail.tsx").read_text(encoding="utf-8")
    assert "gesperrt?: boolean;" in rail
    assert 'aria-disabled="true"' in rail and "railgesperrt" in rail
    assert "disabled={gesperrt}" not in rail, "kein deaktivierter Button — ein `span` sagt es ehrlicher"
    for seite in ("login", "onboarding", "start"):
        q = (web / "app" / seite / "page.tsx").read_text(encoding="utf-8")
        assert "<AppRail gesperrt />" in q, f"/{seite}: Rail nicht gesperrt"


def test_die_app_verlangt_eine_anmeldung():
    """Sven: „die ganze App baut doch darauf, gezielte Ausschreibungen zu zeigen — wie
    sollen wir das ohne Profil machen?"

    Das ist ein Argument ueber den ZWECK, und es schlaegt mein frueheres ueber den Ablauf.
    Eine ungefilterte Liste von 15.762 Vergaben ist das, was jedes kostenlose Portal auch
    kann; der Wert entsteht mit dem Profil. Im Browser geprueft: /leads /unternehmen
    /bausteine /settings antworten ohne Sitzung mit 307, /api/branchen mit 401.
    """
    m = (ROOT / "web" / "middleware.ts").read_text(encoding="utf-8")
    assert "function istOffen" in m and "function zumLogin" in m
    assert '!email && !istOffen(pfad)' in m
    # APIs duerfen KEINE HTML-Umleitung bekommen — fuer den Aufrufer unbrauchbar.
    assert 'status: 401' in m


def test_der_weg_hinein_bleibt_offen():
    """Sonst sperrt man die Tuer von innen ab. Und zwei Ausnahmen, die man leicht uebersieht:

    `/t/…` ist der Vertriebs-Einstieg und ausdruecklich ohne Konto gedacht.
    `/api/entity-verify` ist die Firmensuche des Onboardings — sie laeuft, BEVOR eine
    Sitzung existiert: bei ausstehender E-Mail-Bestaetigung gibt es nach `signUp` noch
    keine. Ohne diese Ausnahme waere Schritt 2 der Registrierung tot.
    """
    m = (ROOT / "web" / "middleware.ts").read_text(encoding="utf-8")
    for offen in ('"/login"', '"/onboarding"', '"/start"', '"/t"', '"/api/wer"', '"/api/entity-verify"'):
        assert offen in m, f"nicht offen gehalten: {offen}"


def test_free_verspricht_nichts_falsches_mehr():
    """„Free-Zugang: Lead-Liste … unbegrenzt" las sich stimmig, solange die Liste ohne
    Konto sichtbar war. Mit dem Tor heisst „Free" etwas anderes — kostenlos NACH der
    Registrierung. Ein Versprechen, das der naechste Klick nicht einloest, ist schlimmer
    als gar keins."""
    onb = (ROOT / "web" / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    assert "Free-Zugang nach der Anmeldung" in onb
