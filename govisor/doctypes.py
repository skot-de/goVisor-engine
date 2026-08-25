"""Dokumenttyp-Klassifikation für Vergabeunterlagen (Ticket #23, §6.1).

Zwei Ebenen: (1) **Extraktions-Doktypen** — die fünf Typen mit eigener Extraktionsaufgabe
(§6a.3), in **Prioritätsreihenfolge** (§6.1); (2) ein **Dateiname**-Klassifikator; (3) eine
**Inhaltsprobe** für die Dateien, deren Name nichts hergibt. ``classify(name, text)`` fasst
(2) und (3) zusammen — der Name entscheidet, solange er etwas hergibt, er ist genauer und
kostet nichts. Was übrig bleibt, erscheint als ``sonstiges`` unter „Weitere Dokumente" (§7.5).

⚠ **Die „69 %" aus der Struktur-Studie (Q3) sind nicht die Betriebszahl.** Sie lief auf einer
kleinen, handverlesenen Stichprobe. Gegen den echten Bestand gemessen (2026-08-21, alte
deutsche Regeln → heute):

    DE Volltext, 134.522 Dateien     50,2 % → 73,2 %   (Dateiname allein)
    DE Portalliste, 16.537 Namen     31,5 % → 67,3 %
    AT Portalliste, 3.043 Namen      24,4 % → 53,7 %

Mit Inhaltsprobe, auf den 121.453 Dokumenten, für die überhaupt Text vorliegt:
**74,5 % → 78,0 %**. Auf Vorgangsebene ist der Zugewinn größer als diese 3,5 pp vermuten
lassen, weil er sich auf die verteilt, denen der Typ ganz fehlte: Aufforderung +784,
Eignung +211, Vertrag +136, LB +73, Zuschlagskriterien +27 Vorgänge. Vorgänge mit allen
fünf priorisierten Typen: 771 → 817.

⚠ **Die Zuschlagskriterien-Abdeckung SINKT — das ist die Korrektur eines Fehlalarms.** Auf
Vorgangsebene 2.036 → 1.192. Das alte Muster zählte 880 Preisformulare („Preisermittlung bei
Zuschlagskalkulation") und 121 Eignungskriterien-Dokumente mit. Wer die
Vollständigkeitsprüfung (§4.3, ``missing_expected``) gegen alte Zahlen vergleicht, sieht hier
einen Einbruch, wo eine Bereinigung stattgefunden hat. Alle übrigen priorisierten Typen
gewinnen: Eignung +307, LB +510, Vertrag +173, Aufforderung +187 Vorgänge.

Bewusst KEIN Textmuster-Cache (Q1b): der Name steuert nur die Auswahl, der Inhalt wird
einzeln verarbeitet.
"""
from __future__ import annotations

import re

# Extraktions-Doktypen in Prioritätsreihenfolge (§6.1: Eignung → Zuschlag → LB → Vertrag → Aufforderung).
PRIORITY: tuple[str, ...] = (
    "eignung", "zuschlagskriterien", "leistungsbeschreibung", "vertrag", "aufforderung",
)

# Reihenfolge = Vorrang bei Mehrfachtreffer; Prioritäts-Typen zuerst, damit ein
# „Bewerbungsbedingungen"-Dokument als eignung (nicht als sonstiges) landet.
# ── REGELN JE SPRACHRAUM ────────────────────────────────────────────────────────────────
#
# **Warum getrennt.** Die erste Fassung war deutsch, und zwar nicht nur sprachlich: sie suchte
# nach `vob|vol|zvb|bvb` — Vergabe- und Vertragsordnungen der Bundesrepublik. Gemessen am
# 2026-08-21 an **2.788 echten oesterreichischen Dateinamen** (aus
# `data/docs/AT/doc_listing_vergabeportal.parquet`) fielen damit **75,7 %** in `sonstiges`.
# Bei franzoesisch- und italienischsprachigen Schweizer Unterlagen waren es 100 %.
#
# Die Regeln stehen deshalb je Sprachraum, werden aber zu EINEM Muster je Doktyp vereinigt:
# ein Dateiname traegt keine Sprachangabe, und ein Erkennungsschritt davor waere eine
# Fehlerquelle mehr. Die Trennung dient der Pflege, nicht der Laufzeit.
#
# ⚠ **Belegstand je Sprachraum — wer erweitert, sollte wissen, was gemessen ist:**
#   de  an DE-Bestand gewachsen, im Betrieb bewaehrt
#   at  an 2.788 echten Dateinamen gemessen (s. o.)
#   fr  NICHT gemessen — es liegt kein einziges franzoesisches Dokument vor (CH-Abruf ist zu,
#       s. [[govisor-at-ch-dokumente]]). Begriffe aus simap.ch-Terminologie, ungeprueft.
#   it  ebenso ungeprueft.
#   pl  ungeprueft; PL-Bekanntmachungen liegen seit 2026-08-18 vor, Unterlagen nicht.
#
# ⚠ **Oesterreich sagt „Bestimmungen", Deutschland „Bedingungen".** Das ist der haeufigste
# Einzelunterschied: `Allgemeine Angebotsbestimmungen`, `Teilnahmebestimmungen`,
# `Vertragsbestimmungen`. Dazu die Abkuerzung `Erkl` (BieErkl, SubUErkl, SolidarhaftErkl)
# und `Ausschreibungsunterlage` als Sammelbegriff.
_REGELN: tuple[tuple[str, dict[str, str]], ...] = (
    ("eignung", {
        "de": r"eignung|eignungsnachw|eignungskrit|praequalif|präqualif|"
              r"bewerbungsbed|teilnahmebed|vergabebed|referenz|"
              r"mindestanforderung|qualifikationsnachweis|bef[aä]higungsnachweis",  # +439
        "at": r"teilnahmebestimm|befugnis|ksv[- _]?rating|bonitaet|bonität|"
              r"gewerbeberechtig|berufliche.?zuverlaess|ausschreibungsbed|"
              r"verfahrensbestimm|verfahrensordnung|eignungsprüf",
        "fr": r"conditions?.{0,3}de.{0,3}participation|aptitude|qualification|"
              r"capacit[eé]s?|r[eé]f[eé]rences?|attestation",
        "it": r"requisiti|idoneit|capacit[aà]|referenze",
        "pl": r"warunki.{0,3}udzia|kwalifikacj|referencj",
    }),
    ("zuschlagskriterien", {
        # ⚠ `zuschlag` MUSS „Zuschlagskalkulation" ausschliessen: das ist VHB 221
        # „Preisermittlung bei Zuschlagskalkulation", ein Preisblatt. 948 Dateien tragen
        # das Wort, nur 406 tragen „Zuschlagskriterien".
        "de": r"zuschlag(?!skalkulation)|wertung|wertungsmatrix|kriterienkatalog|"
              r"bewertungsmatrix|kriterien",
        "at": r"bestbieter|billigstbieter|zuschlagsprinzip",
        "fr": r"crit[eè]res?|notation",
        "it": r"criteri.{0,3}di.{0,3}aggiudicazione|valutazione",
        "pl": r"kryteri",
    }),
    ("leistungsbeschreibung", {
        "de": r"leistungsbeschr|leistungsverz|\blv\b|lastenheft|leistungskatalog|baubeschr|"
              r"leistungsprogramm",
        "at": r"leistungsverzeichnis|ausschreibungsunterlage|positionsverz|"
              r"technische.{0,3}(beschreib|spezifik|anforderung)",
        "fr": r"cahier.{0,3}des.{0,3}charges|descriptif|bordereau|cctp|sp[eé]cifications?",
        "it": r"capitolato|descrizione.{0,3}(della.{0,3})?prestazion|elenco.{0,3}prezzi",
        "pl": r"opis.{0,3}przedmiotu|specyfikacj|\bopz\b|\bswz\b",
    }),
    ("vertrag", {
        # ⚠ Nur MIT Teilbuchstabe: „VOB/B" ist die Vertragsordnung, blankes „VOB" ist bei
        # 1.340 Dateien blosses Praefix — „VOB ANGEBOTSSCHREIBEN", „VOB KVHB KEV 179
        # Eigenerklaerung zur Eignung". Ohne diese Enge zieht das Kuerzel jede Datei
        # einer VOB-Vergabe in den Vertrag.
        "de": r"vertrag|\bevb\b|\bvo[bl][ /-]?[abc]\b|\bagb\b|\bzvb\b|\bbvb\b|"
              r"besondere.*bedingung|zusaetzliche.*bedingung|zusätzliche.*bedingung",
        "at": r"vertragsbestimm|rahmenvereinbarung|\boenorm\b|\bönorm\b|"
              r"allg.{0,4}(vb|vertragsb)|werkvertrag",
        "fr": r"contrat|conditions?.{0,3}g[eé]n[eé]rales|acte.{0,3}(d.{0,3})?engagement|ccap|ccag",
        "it": r"contratto|condizioni.{0,3}generali",
        "pl": r"umow|wzór.{0,3}umowy|istotne.{0,3}postanowienia",
    }),
    ("aufforderung", {
        "de": r"aufforder|anschreiben|angebotsauff|deckblatt.*angebot|begleitschreiben",
        "at": r"angebotsbestimm|einladung.{0,3}zur.{0,3}angebot|ausschreibungsschreiben|"
              r"angebotsschreiben",
        "fr": r"invitation|lettre.{0,3}de.{0,3}consultation|avis.{0,3}d.{0,3}appel",
        "it": r"invito|lettera.{0,3}d.{0,3}invito",
        "pl": r"zaproszenie|ogłoszenie.{0,3}o.{0,3}zam",
    }),
    # ── Nicht-priorisierte Typen (erscheinen unter „Weitere Dokumente", §7.5) ──
    #
    # ⚠ **Die Reihenfolge hier ist SPEZIFISCH VOR ALLGEMEIN, nicht Wichtigkeit.** `formblatt`
    # steht bewusst zuletzt: „Formular", „Formblatt" und „Vergabeformulare/" stehen als
    # Ordner- oder Sammelbegriff vor Dateien, die inhaltlich etwas Genaueres sind. Gemessen:
    # „Vergabeformulare/222 Preisermittlung bei Kalkulation" gehoert unter preisblatt,
    # „Formulare/Information nach Art. 13 DSGVO" unter datenschutz. Wer `formblatt` nach
    # vorne zieht, verliert beide — und merkt es nicht, weil beide Typen nicht priorisiert
    # sind und deshalb in keiner Vollstaendigkeitspruefung auftauchen.
    ("datenschutz", {
        "de": r"datenschutz|dsgvo|\bavv\b|vertraulichk|verschwiegen|"
              r"datenverarbeitung",                                            # +425
        "at": r"geheimhaltung|datenschutzerkl",
        "fr": r"confidentialit|rgpd|protection.{0,3}des.{0,3}donn[eé]es",
        "it": r"riservatezza|privacy",
        "pl": r"poufno|rodo",
    }),
    ("preisblatt", {
        "de": r"preisblatt|preisverz|kalkulat|angebotspreis|preistabelle|\bpreise?\b|"
              r"aufgliederung|einheitspreis|stundenverrechnung|zuschlagssatz",   # +628
        # ⚠ `\bk-?blatt\b` MIT Wortgrenzen: ohne sie traf das Muster „Merkblatt",
        # „Deckblatt", „Beiblatt" — 551 Dateien landeten faelschlich unter preisblatt.
        "at": r"preisaufgliederung|\bk-?blatt\b|kalkulationsformblatt",
        "fr": r"bordereau.{0,3}des.{0,3}prix|d[eé]composition.{0,3}du.{0,3}prix|\bdpgf\b",
        "it": r"lista.{0,3}prezzi|offerta.{0,3}economica",
        "pl": r"formularz.{0,3}cenowy|kosztorys",
    }),
    ("eigenerklaerung", {
        "de": r"eigenerkl|verpflichtungserkl|\beee\b|einheitliche.?europ|espd|"
              # Nachunternehmer-/Tariftreue-Erklaerungen: der Bieter erklaert etwas ueber
              # Dritte. VHB 235 „Verzeichnis der Nachunternehmerleistungen" u. Ae.  +2.081
              r"nachunternehmer|unterauftragnehmer|tariftreue|mindestlohn|"
              r"kapazit[aä]t|eignungsleihe",
        # ⚠ `Erkl` ist die AT-Kurzform: BieErkl, SubUErkl, SolidarhaftErkl, PatrErkl, ErklBieG.
        "at": r"\berkl\b|erkl[aä]rung|bieerkl|subuerkl|solidarhaft|patronats|"
              r"subunternehmerliste|bietergemeinschaft",
        "fr": r"d[eé]claration|engagement.{0,3}sur.{0,3}l.{0,3}honneur|dume",
        "it": r"dichiarazione|dgue",
        "pl": r"oświadcz|jedz",
    }),
    ("fragenantworten", {
        "de": r"bieterfrage|fragen.{0,3}und.{0,3}antworten|fragenkatalog|\bfaq\b|"
              r"frage.{0,3}antwort",
        "at": r"fragenbeantwortung|beantwortung.{0,3}der.{0,3}frage",
        "fr": r"questions?.{0,3}r[eé]ponses|demandes?.{0,3}de.{0,3}pr[eé]cision",
        "it": r"chiarimenti|domande.{0,3}e.{0,3}risposte",
        "pl": r"pytania|wyjaśnien|odpowiedzi",
    }),
    # ⚠ `schnitt` OHNE Wortgrenze traf „Abschnitt"/„Ausschnitt"/„Schnittstelle" (653 Namen),
    # MIT Wortgrenze verlor es „Fassadenschnitt"/„Regelquerschnitt" (168) — beides echte
    # Zeichnungen. Deshalb Ausschluss statt Grenze.
    ("technische_anlage", {                                                    # +5.412
        "de": r"lageplan|grundriss|(?<!ab)(?<!aus)(?<!durch)schnitt(?!stelle)|ansicht|"
              r"zeichnung|plan|baugrund|gutachten|schema|gaeb|\bdwg\b|\bdxf\b|\bifc\b",
        "at": r"planbeilage|einreichplan",
        "fr": r"plans?\b|dessin|croquis|expertise",
        "it": r"planimetri|disegn|perizia",
        "pl": r"rysun|plan\b|ekspertyz",
    }),
    ("informationsblatt", {                                                    # +2.498
        "de": r"hinweis|merkblatt|informationsblatt|erl[aä]uter|infoblatt",
        "at": r"informationsbl|hinweisbl",
        "fr": r"note.{0,3}d.{0,3}information|notice",
        "it": r"nota.{0,3}informativa|avvertenz",
        "pl": r"informacj|wskazów",
    }),
    ("formblatt", {
        "de": r"formbl(a|ä|ae)tt|form[_ ]|\bvhb\b",
        # ⚠ KEINE reinen Behaelterwoerter hier („Beilage", „Annexe", „Allegato",
        # „Załącznik"). Sie stehen vor fast jedem Anhang und stehlen den spezifischen
        # Regeln die Treffer — gemessen: „Beilage G - Kalkulationsgrundlage.xlsx" landete
        # damit unter Formblatt statt Preisblatt.
        "at": r"formular|checkliste|teilnahmeantrag",
        "fr": r"formulaire",
        "it": r"modulo",
        "pl": r"formularz",
    }),
)

# Jeder Doktyp, den `classify` vergeben kann — ABGELEITET aus den Regeln, nicht getippt.
# `sonstiges` ist der Rueckfall und steht bewusst nicht drin; wer eine vollstaendige Achse
# fuer einen Bericht braucht, haengt ihn an: ``ALLE + ("sonstiges",)``.
#
# ⚠ Es gab hier schon eine getippte Zweitliste. `scripts/doc_structure_study.py` trug bis
# zum 2026-08-21 eine eigene Kopie der Regeln; beim Umstellen auf dieses Modul blieben zwei
# Nutzungen ihres Namens `DOCTYPES` stehen und rissen den Bericht mit `NameError` ab —
# gefunden am 2026-08-25. Eine abgeleitete Liste kann nicht auf diese Weise veralten.
ALLE: tuple[str, ...] = tuple(dt for dt, _ in _REGELN)

# Ein Muster je Doktyp, aus allen Sprachraeumen vereinigt.
_COMPILED = tuple(
    (dt, re.compile("|".join(v for v in sprachen.values() if v), re.I))
    for dt, sprachen in _REGELN
)

# Rueckwaertskompatibel: manche Auswertungen lasen die flache Liste.
_FILENAME_RULES: tuple[tuple[str, str], ...] = tuple(
    (dt, "|".join(v for v in sprachen.values() if v)) for dt, sprachen in _REGELN
)


# GAEB-Austauschformate. Ein Leistungsverzeichnis per Definition — auch wenn die Datei
# „3923240.d83" heisst, was bei Staatsanzeiger-Vergaben die Regel ist. Nur Rueckfallebene:
# steht im Namen etwas Genaueres, gewinnt der Name.
_GAEB_ENDUNG = re.compile(r"\.(d8[1-4]|x8[1-3]|p8\d)$", re.I)


# ── VHB-/VOL-FORMBLATTNUMMERN ──────────────────────────────────────────────────────────
#
# Die Nummer im Dateinamen kodiert den Doktyp genauer als jedes Wort: „VE17_VHB 211_EU.pdf"
# traegt kein einziges Typwort, ist aber die Aufforderung zur Angebotsabgabe. Ohne diese
# Tabelle gewann `\bvhb\b` und machte daraus ein Formblatt.
#
# **Abgeleitet, nicht behauptet.** Fuer jede dreistellige Zahl im Bestand (134.522 Dateien)
# wurde geprueft, wie der Rest des Dateinamens klassifiziert — der dominante Typ steht unten
# mit seinem Anteil. Aufgenommen ist nur, was deutlich dominiert. Runde Zahlen (100, 200,
# 300, 500) sind absichtlich NICHT drin: dort liegt der beste Typ unter 25 %, das sind
# Projekt- und Anlagennummern, keine Formblaetter.
#
# ⚠ **Die frueheren Zahlen in der `formblatt`-Regel waren falsch.** 124, 234, 521, 522, 531
# standen dort; der Bestand weist sie als eignung bzw. eigenerklaerung aus (67–92 %).
_NUMMER_TYP: dict[str, str] = {
    # Aufforderung / Angebotsschreiben
    "211": "aufforderung",          # 79 %, n=1.563   Aufforderung zur Angebotsabgabe
    "213": "aufforderung",          # 68 %, n=1.534   Angebotsschreiben
    "324": "aufforderung",          # 90 %, n=204
    "631": "aufforderung",          # 90 %, n=340
    # Eignung / Bewerbungsbedingungen
    "124": "eignung",               # 67 %, n=2.238
    "212": "eignung",               # 83 %, n=1.461   Teilnahme-/Bewerbungsbedingungen
    "444": "eignung",               # 79 %, n=148     Referenzbescheinigung
    "511": "eignung",               # 86 %, n=213
    "534": "eignung",               # 99 %, n=315     Eignungsleihe
    "632": "eignung",               # 95 %, n=328
    # Vertrag
    "214": "vertrag",               # 76 %, n=1.763
    "215": "vertrag",               # 80 %, n=136
    "421": "vertrag",               # 75 %, n=195     Vertragserfuellungsbuergschaft
    "512": "vertrag",               # 82 %, n=228
    "513": "vertrag",               # 96 %, n=448
    "634": "vertrag",               # 95 %, n=263
    "635": "vertrag",               # 96 %, n=279
    # Preis
    # ⚠ 221 zeigte in der Ableitung „zuschlagskriterien" (64 %) — ein Artefakt: das Formblatt
    # heisst „Preisermittlung bei ZUSCHLAGSkalkulation", das Wort taeuscht die Wortregel.
    # Die Begleitwoerter (preisermittlung, zuschlagskalkulation) weisen es als Preisblatt aus.
    "221": "preisblatt",            # n=1.505
    "222": "preisblatt",            # 61 %, n=1.426   Preisermittlung ueber die Endsumme
    "223": "preisblatt",            # 61 %, n=1.298   Aufgliederung der Einheitspreise
    # Eigenerklaerungen
    "233": "eigenerklaerung",       # 60 %, n=1.255
    "234": "eigenerklaerung",       # n=1.722         Erklaerung Bieter-/Arbeitsgemeinschaft
    "235": "eigenerklaerung",       # n=1.214         Verzeichnis Nachunternehmerleistungen
    "236": "eigenerklaerung",       # 79 %, n=1.182
    "521": "eigenerklaerung",       # 92 %, n=359     Ausschlussgruende
    "522": "eigenerklaerung",       # 80 %, n=111     Mindestlohngesetz
    "523": "eigenerklaerung",       # 95 %, n=350     Sanktionspaket
    "531": "eigenerklaerung",       # 92 %, n=205     Bietergemeinschaftserklaerung
    "576": "eigenerklaerung",       # 86 %, n=257     Sanktionen
    # Sonstige
    "227": "zuschlagskriterien",    # 61 %, n=71      Zuschlagskriterien/Gewichtung
    "244": "datenschutz",           # 78 %, n=859     Datenverarbeitung
}

# Ein Formblatt-Marker macht aus einer Zahl im Namen erst eine Formblattnummer. Ohne ihn
# koennte „Anlage 213" eine Planbezeichnung sein — die Zahl zaehlt dann nur als Rueckfall.
_FORM_MARKER = re.compile(r"vhb|formbl|formular|vordruck|heftung|vergabehandbuch|\bfb ?\d", re.I)
_DREISTELLIG = re.compile(r"(?<!\d)(\d{3})(?!\d)")


def _nummer_typ(text: str) -> str | None:
    for m in _DREISTELLIG.finditer(text):
        t = _NUMMER_TYP.get(m.group(1))
        if t:
            return t
    return None


def _treffer(text: str) -> str:
    for doctype, rx in _COMPILED:
        if rx.search(text):
            return doctype
    return "sonstiges"


def classify(filename: str, text: str | None = None) -> str:
    """Doktyp aus dem Dateinamen; mit ``text`` faellt er auf die Inhaltsprobe zurueck.

    Der Name entscheidet, solange er etwas hergibt — er ist genauer und kostet nichts. Erst
    wenn er ``sonstiges`` ergibt, zaehlt der Inhalt (§6.1, Schritt 2).

    Sprachraum-uebergreifend: ein Dateiname traegt keine Sprachangabe, deshalb wird gegen
    alle Regeln geprueft. Reihenfolge der Regeln = Vorrang bei Mehrfachtreffer.
    """
    # ⚠ Unterstrich → Leerzeichen, BEVOR gesucht wird. Fuer Python ist ``_`` ein Wortzeichen,
    # also greift ``\bvob\b`` in „VOB_B_2019.pdf" nicht und ``\b234\b`` nicht in
    # „Formblatt_234_Erkl.pdf" — in Dateinamen ist der Unterstrich aber genau das, was
    # anderswo das Leerzeichen ist. Der Fehler steckte seit der ersten Fassung drin und ist
    # beim Sprachausbau nur aufgefallen, weil ein Test ihn zufaellig traf.
    voll = (filename or "").replace("_", " ")

    # ⚠ **DER DATEINAME SCHLAEGT DEN ORDNER.** 77,6 % der Namen im Bestand tragen einen Pfad,
    # und die Portale benennen die Ordner nach Doktyp („leistungsbeschreibungen/",
    # „vertragsbedingungen/", „anschreiben/"). Wird der ganze Pfad in einem Rutsch geprueft,
    # entscheidet die Regelreihenfolge statt der Naehe zur Datei — gemessen 1.845 Faelle, in
    # denen der Ordner gewinnt, obwohl der Dateiname genauer ist:
    #     anschreiben/Information_Datenschutz.pdf        → aufforderung statt datenschutz
    #     vertragsbedingungen/FB2_Erklärung BieGe.pdf    → vertrag       statt eigenerklaerung
    # Der Ordner bleibt Rueckfallebene: 19.565 Dateien sind NUR ueber ihn erkennbar
    # („Anlage 3.pdf" in „leistungsbeschreibungen/"). Erst der Name, dann der Pfad.
    # ``::`` trennt bei uns das Archiv vom Eintrag darin und zaehlt hier wie ein Pfadtrenner.
    basis = voll.replace("::", "/").rsplit("/", 1)[-1]
    for kandidat in (basis, voll):
        t = _treffer(kandidat)
        # Die Nummer schlaegt die Wortregel nur, wenn diese nichts Genaueres gefunden hat als
        # „irgendein Formblatt" — dann macht `\bvhb\b` aus „VHB 211" faelschlich ein
        # Formblatt statt der Aufforderung. Steht dagegen ein echtes Typwort im Namen
        # („FB 211_EU LV - Akustikrollos"), gewinnt das Wort: es beschreibt den Inhalt,
        # die Nummer nur das Formular, in dem er steckt.
        if t in ("sonstiges", "formblatt") and _FORM_MARKER.search(kandidat):
            nr = _nummer_typ(kandidat)
            if nr:
                return nr
        if t != "sonstiges":
            return t
    # Kein Wort hat gegriffen — jetzt zaehlt die blanke Nummer als letztes Signal.
    for kandidat in (basis, voll):
        t = _nummer_typ(kandidat)
        if t:
            return t
    if _GAEB_ENDUNG.search(filename or ""):
        return "leistungsbeschreibung"
    return classify_content(text) if text else "sonstiges"


# ── WAS EINGEREICHT WERDEN MUSS — der Ordner sagt es ────────────────────────────────────
#
# Portale trennen die Unterlagen nach PFLICHT, nicht nur nach Art: „Vom Unternehmen
# auszufuellende Dokumente", „Zwingend erforderliche Angebotsdateien", „Verbleibt beim
# Bieter". Gemessen am 2026-08-21 liegen **27.130 Dateien in 3.157 von 5.726 Vorgaengen
# (55 %)** in einem solchen Ordner — allein 21.760 im ersten.
#
# Das ist die direkte Antwort auf die praktisch wichtigste Frage („was muss ich abgeben?"),
# und sie steht in der Struktur, nicht im Text: kein Modell, keine Unsicherheit, kein Zitat.
#
# ⚠ `verbleibt_beim_bieter` ist die UMKEHRUNG und deshalb eigens gefuehrt: „diese Unterlage
# ist NICHT einzureichen". Wer sie mit den Pflichtdateien in einen Topf wirft, macht aus
# einer Entlastung eine Anforderung.
_PFLICHT_REGELN: tuple[tuple[str, str], ...] = (
    # ⚠ `ü` UND `ue` — die Portale schreiben beides, und der haeufigste Ordner im Bestand
    # heisst „vom_unternehmen_auszufUEllende_dokumente" (21.760 Dateien). Ein blosses
    # `[üu]` trifft „fuer" und „auszufuellende" NICHT: dort steht ein zusaetzliches `e`.
    # ⚠ NUR belegte Formulierungen. „Zur Information" und „nicht einzureichen" standen hier
    # zuerst mit dazu und trafen im ganzen Bestand NULL Dateien — eine Behauptung ohne Beleg.
    # Bei „Zur Information" waere sie ausserdem riskant: ein Ordner dieses Namens kann sehr
    # wohl die Leistungsbeschreibung enthalten, und „verbleibt beim Bieter" waere dann falsch.
    ("verbleibt_beim_bieter", r"verbleibt.{0,4}beim.{0,4}bieter|verbleiben.{0,4}beim.{0,4}bieter"),
    ("einzureichen",          r"vom.{0,4}unternehmen.{0,4}auszuf|auszuf(ü|ue|u)llende.{0,4}dokument|"
                              r"zwingend.{0,4}erforderlich|"
                              r"dateien.{0,4}f(ü|ue|u)r.{0,4}(das.{0,4})?angebot|"
                              r"einzureichende.{0,4}(unterlagen|dokumente)|angebotsunterlagen|"
                              r"mit.{0,4}dem.{0,4}angebot.{0,4}einzureichen"),
)
_PFLICHT = tuple((k, re.compile(p, re.I)) for k, p in _PFLICHT_REGELN)


def pflicht(dateiname: str) -> str | None:
    """``einzureichen`` / ``verbleibt_beim_bieter`` / ``None`` — aus den ORDNERN des Pfades.

    ⚠ Nur die Ordner, nicht der Dateiname. Eine Datei namens „Angebotsunterlagen.pdf" ist
    eine Beschreibung; ein ORDNER dieses Namens ist eine Aufforderung.
    """
    pfad = (dateiname or "").replace("::", "/")
    ordner = " / ".join(pfad.split("/")[:-1]).replace("_", " ")
    if not ordner:
        return None
    for art, rx in _PFLICHT:
        if rx.search(ordner):
            return art
    return None


# ── INHALTSPROBE (§6.1, Schritt 2) ─────────────────────────────────────────────────────
#
# Fuer die knapp 29 %, deren Dateiname nichts hergibt: „Gesamtpaket.pdf", „Anlage 3.pdf",
# „3923240.pdf". Der Volltext liegt ohnehin vor (``data/docs/<LAND>/doc_text.parquet``),
# die Probe kostet also keinen neuen Abruf.
#
# **Abgeleitet, nicht erfunden.** Die Merkmale stammen aus einer Trennschaerfe-Rechnung ueber
# 121.453 Dokumente mit Text: fuer jeden Doktyp wurden Woerter und Wortpaare gesucht, die in
# den ersten 1.500 Zeichen ueberdurchschnittlich haeufig und anderswo selten sind. Gemessen
# wurde gegen eine zurueckgehaltene Viertelstichprobe, die in keine Ableitung eingegangen ist.
#
# ⚠ **PUNKTWERTUNG, NICHT ERSTER-TREFFER.** Der erste Anlauf nahm die erste passende Regel —
# und scheiterte daran, dass Woerter wie „Angebotsfrist" in fast jeder Unterlage stehen.
# Ein Dokument spricht mehrere Themen an; entscheidend ist, welches ueberwiegt.
#
# ⚠ **Die Schwelle ist eine Abwaegung, keine Feineinstellung.** Gemessen an der
# Rueckhaltemenge (Genauigkeit = Anteil richtiger unter den abgegebenen Urteilen):
#
#     MIN/MARGE   Genauigkeit   Ausbeute bei namentlich Unerkannten
#      3 / 1         70,7 %        25,1 %
#      4 / 1         86,0 %        13,6 %      ← gewaehlt
#      5 / 1         88,1 %        11,4 %
#     bisherige Fassung (Erster-Treffer, ungemessen):  46,1 %
#
# Die alte Fassung holte mehr (26,3 %), lag dabei aber in ueber der Haelfte der Faelle daneben.
# Ein falscher Doktyp ist hier teuer: er schickt den Text an die falsche Extraktionsaufgabe
# UND meldet einen priorisierten Typ als vorhanden, wo eine echte Luecke ist (§4.3). Deshalb
# Genauigkeit vor Ausbeute.
#
# ⚠ **`technische_anlage` und `formblatt` fehlen hier absichtlich.** Zeichnungen und
# Blankoformulare tragen kaum Text; jede Regel dafuer traf im Versuch nur Fremdes.
_INHALT_REGELN: tuple[tuple[str, tuple[tuple[int, str], ...]], ...] = (
    ("preisblatt", (
        (3, r"verrechnungslohn|mittellohn|soziall[öo]hne|kalkulationslohn"),
        (3, r"aufgliederung der einheitspreise|preisermittlung bei (zuschlagskalkulation|kalkulation)"),
        (2, r"lohngleitklausel|lohnnebenkosten|lohnzulagen"),
        (1, r"angebotssumme|gesamtpreis netto"))),
    ("zuschlagskriterien", (
        (3, r"zuschlagskriterien|wertungskriterien|bewertungsmatrix"),
        (3, r"lineare interpolation|h[öo]chstpunktzahl|punktebewertung"),
        (2, r"punkte erh[äa]lt|mit punkten bewertet|erreichbare punkte"),
        (2, r"gewichtung\s*(von\s*)?\d{1,3}\s*%"),
        (1, r"punktzahl|niedrigsten (angebots)?preis"))),
    ("datenschutz", (
        (3, r"datenschutz-?grundverordnung|\bds-?gvo\b"),
        (3, r"verarbeitung personenbezogener daten|verantwortlicher im sinne"),
        (2, r"datenschutz|betroffenenrechte|auftragsverarbeitung"))),
    ("fragenantworten", (
        (3, r"bieterfrage|bieteranfrage|beantwortung der (bieter)?fragen"),
        (2, r"fragen und antworten"),
        (2, r"frage\s*\d+\s*:"),
        (1, r"^\s*antwort\s*:"))),
    ("eigenerklaerung", (
        (3, r"eigenerkl[äa]rung|verpflichtungserkl[äa]rung|bietergemeinschaftserkl"),
        (2, r"als gesamtschuldner|rechtsverbindlich vertritt"),
        (1, r"hiermit erkl[äa]r|wir erkl[äa]ren|ich erkl[äa]re"))),
    ("eignung", (
        (3, r"eignungskriterien|eignungsnachweis|pr[äa]qualifikation"),
        (3, r"bewerbungsbedingungen|teilnahmebedingungen"),
        (2, r"mindestumsatz|vergleichbare referenzen|ausschlussgr[üu]nde"),
        (2, r"vordrucke der vergabestelle|deutscher sprache abzufassen"),
        (1, r"referenzen der letzten|jahresums[äa]tze"))),
    ("aufforderung", (
        (3, r"aufforderung zur abgabe eines angebot|aufforderung zur angebotsabgabe"),
        (3, r"angebotsschreiben"),
        (2, r"er[öo]ffnungstermin|submissionstermin"),
        (1, r"zuschlagsfrist|angebotsfrist"))),
    ("vertrag", (
        (3, r"vertragsbedingungen|vertragsgegenstand|vertragsparteien"),
        (2, r"vertragsstrafe|ausf[üu]hrungsfristen|hiervon unber[üu]hrt"),
        (2, r"§\s*\d+\s*(haftung|k[üu]ndigung|laufzeit|verg[üu]tung)"),
        (1, r"gew[äa]hrleistung|abnahme der leistung"))),
    ("leistungsbeschreibung", (
        (3, r"leistungsverzeichnis|leistungsbeschreibung|leistungsumfang"),
        (2, r"ordnungszahl|pos\.?\s*-?\s*nr|menge\s+einheit|langtext"),
        (2, r"technische anforderungen|lastenheft"),
        (1, r"vorbemerkungen|baustelleneinrichtung"))),
    ("informationsblatt", (
        (3, r"merkblatt|hinweisblatt|informationsblatt"),
        (1, r"allgemeine hinweise|wichtige hinweise"))),
)
_INHALT = tuple((t, tuple((g, re.compile(p, re.I | re.M)) for g, p in ps))
                for t, ps in _INHALT_REGELN)

INHALT_MINDEST = 4   # so viele Punkte muss der beste Typ erreichen
INHALT_MARGE = 1     # ... und um so viele vor dem zweiten liegen
INHALT_PROBE = 4000  # Zeichen; weiter hinten steht der Inhalt, nicht die Art des Dokuments


def classify_content(text: str, sample: int = INHALT_PROBE,
                     mindest: int = INHALT_MINDEST, marge: int = INHALT_MARGE) -> str:
    """Doktyp aus einer Inhaltsprobe. ``sonstiges``, wenn kein Typ deutlich fuehrt.

    Genauigkeit 86 % bei 13,6 % Ausbeute (s. Kopf des Abschnitts). Bewusst zurueckhaltend:
    lieber ``sonstiges`` als ein falscher priorisierter Typ.
    """
    kopf = (text or "")[:sample]
    punkte = sorted((sum(g for g, rx in muster if rx.search(kopf)), t) for t, muster in _INHALT)
    (bester, typ), (zweiter, _) = punkte[-1], punkte[-2]
    return typ if bester >= mindest and bester - zweiter >= marge else "sonstiges"


def sprachraeume() -> tuple[str, ...]:
    """Welche Sprachraeume die Regeln kennen — fuer Diagnose und Tests."""
    return tuple(dict.fromkeys(k for _, v in _REGELN for k in v))


def is_priority(doctype: str) -> bool:
    return doctype in PRIORITY


def priority_rank(doctype: str) -> int:
    """0-basierter Rang für die Extraktionsreihenfolge; sehr groß für Nicht-Prioritäts-Typen."""
    return PRIORITY.index(doctype) if doctype in PRIORITY else len(PRIORITY) + 1
