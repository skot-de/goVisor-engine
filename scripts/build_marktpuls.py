"""Marktpuls — Saisonalität, Jahres-Layer + aktuelle Marktlage als vorberechnetes JSON.

Ein in sich geschlossenes Anzeige-Element (Briefing `INPUT/v1 Features/add/
govisor-briefing-marktpuls.md`). Drei Teile, alle ausschliesslich aus dem
vorhandenen Silber-/Gold-Bestand (keine neue Quelle):

1. **Saisonalität** — Ø neu veröffentlichte Ausschreibungen je Kalendermonat über die
   letzten 5 *vollen* Jahre, plus Abweichung vom Jahresmittel.
2. **Jahres-Layer** — ein Wert je Kalenderjahr, **je Quelle eine eigene Reihe**, plus
   markierte Bruchstellen. Über `--ab-jahr` bis 2004 zurück (Historie).
3. **Aktuelle Lage** — laufende Verfahren (Frist in der Zukunft), Zuschläge und
   Aufhebungen der letzten 30 Tage, aufgeschlüsselt nach Branche.

Ausgabe: ``web/data/marktpuls.json`` (aggregiert, keine Einzelverfahren, < 50 KB).

--------------------------------------------------------------------------------
Die vier Entscheidungen, die hier drinstecken — alle an echten Daten gemessen:

**(1) Zähleinheit ist das Verfahren, nicht die Bekanntmachung.**
Im Bestand bildet sich ein Verfahren auf drei verschiedene Arten ab, je nach
Schema-Generation:
  * `legacy` (TED_EXPORT, bis 2023): Korrekturen sind ein eigener Notice-Typ
    (`notice_kind='corrigendum'`, F20_2014) — fallen also schon durch den Typfilter.
    Die Klammer über CN/CAN/Korrektur ist der Rückverweis `ref_publication_number`.
  * `eforms` (ab 2023): **eine Korrektur ist erneut ein `ContractNotice`** und trägt
    `notice_kind='cn'`. Gemessen DE 2025: 17.552 von 87.862 eForms-CN (20 %) sind
    Änderungsbekanntmachungen. Wer sie mitzählt, überzeichnet den Markt um ein Fünftel.
    Erkennungsmerkmal ist das Attribut `…EformsExtension.Changes.ChangedNoticeIdentifier`
    (bzw. `…Change.ChangedNoticeIdentifier`). `ref_publication_number` ist hier praktisch
    leer (DE 2025: 0 Zeilen) — die Rückverweis-Klammer trägt ab eForms also NICHT mehr.
    Dafür trägt `ContractFolderID` (BT-04 Verfahrenskennung) zu 100 % der eForms-CN.
  * nationale Quellen (`doe`, `simap`, `atverg`): weder Rückverweis noch verlässliche
    Verfahrenskennung (DÖE: `ContractFolderID` nur zu 9 %) — dort ist die Notice das
    Verfahren.
Daraus der Verfahrensschlüssel als Wasserfall: ContractFolderID → Wurzel der
Rückverweis-Kette → publication_number. Gruppiert wird über ihn, gezählt wird die
*früheste* qualifizierende Veröffentlichung der Gruppe.

**(2) Quellen-Onset ist ein Ingest-Artefakt, kein Marktsignal** (Briefing §6 sinngemäss).
Gemessen: DÖE liefert erst ab 2023 (+125k Notices/Jahr in DE), simap.ch erst ab 2024
(+14k/Jahr in CH). Eine 5-Jahres-Kurve über alle Quellen zeigte einen Sprung, der die
Aufnahme einer Quelle abbildet, nicht den Markt. Für die **Zeitreihe** wird deshalb je
Land nur die Quellenfamilie verwendet, die über das *ganze* Fenster durchgehend liefert
(faktisch überall TED). Welche Quellen ausgeschlossen wurden, steht im JSON
(`coverage.<land>.quellen_ausgeschlossen`) und gehört in die Anzeige.
Für den **Stichtags**-Teil (aktuelle Lage) gilt das nicht — dort zählt alles, was da ist,
mit Quellen-Dedup aus der zentralen Firewall (`gold/<C>/notice_duplicates`).

**(3) Länder-parametrisiert, nicht DE-verdrahtet.** `--laender DE,AT,CH` (Default: was
unter `data/silver/` liegt). Je Land wird die Abdeckung ausgewiesen; wo das Fenster nicht
vollständig belegt ist oder die Fallzahl unter `MIN_FAELLE` liegt, steht das als
`belastbar: false` im JSON, statt still mitgemittelt zu werden.

**(4) Herkunft ausweisen.** Die laufenden Verfahren stützen sich auf die **echte**
`submission_deadline` aus der Bekanntmachung (`frist_basis: "echt"`). Verfahren ohne
veröffentlichte Frist werden separat als `ohne_frist` gezählt, nie stillschweigend
über eine geschätzte Frist in die Kennzahl gerechnet (die Schätzung aus
`gold/*/lead_deadline.parquet` existiert nur für DE vollständig — sie hier zu benutzen
hiesse, DE und CH/AT mit verschiedenen Massstäben zu messen).

--------------------------------------------------------------------------------
DER JAHRES-LAYER — vier weitere Entscheidungen, ebenfalls gemessen:

**(5) Eine Reihe je Quelle, nie eine Summenkurve.** Die Zeitreihe des Saison-Teils wirft
Quellen mit späterem Beginn *heraus* (Entscheidung 2 oben) — richtig für einen
Monatsdurchschnitt, aber im Jahres-Layer wäre es Datenverlust. Hier bekommt jede Quelle
statt dessen eine **eigene Reihe ab ihrem Beginn**. Regel, nicht Sonderfall je Land:

    Eine nationale Quelle wird mit TED zusammengeführt, wenn sie über das ganze
    Fenster durchgehend liefert. Sonst: eigene Reihe ab ihrem Beginn. Nie addieren.

Gemessen ergibt das (Achse 2004–2025): DE = TED + DÖE ab 2023, CH = TED + simap ab 2024,
AT = TED + atverg ab 2019. Über das kurze 5-Jahres-Fenster liefert atverg durchgehend und
wird dort zusammengeführt — dieselbe Quelle, andere Achse, andere Antwort. Deshalb steht
die Begründung je Reihe im JSON (`grund`), statt im Kopf des Lesers rekonstruiert zu werden.
`serie` sagt, zu welcher Linie eine Quelle gehört; `quelle` bleibt immer einzeln
ausgewiesen. Damit **ist** die Quellen-Zusammensetzung je Jahr die Datenstruktur selbst —
es braucht keinen zweiten, ableitbaren Block daneben.

**(6) Brüche markieren, nicht glätten.** Ein Knick über 22 Jahre ist häufiger eine
Regeländerung als ein Marktereignis. Markiert wird beides, aber getrennt gekennzeichnet:
  * `art: "gemessen"` — aus unserem eigenen Bestand abgeleitet und damit nachprüfbar:
    `schema_wechsel` (die vorherrschende `schema_gen` wechselt), `quelle_start`,
    `land_start` (nur am Aggregat), `teiljahr`.
  * `art: "kuratiert"` — äusseres Wissen, das in keinen Daten steht. Kleine Tabelle
    `REGEL_BRUECHE`, jeder Eintrag trägt einen `beleg`. Sie ist **bewusst kurz**: die
    EU-Schwellenwerte werden alle zwei Jahre neu festgesetzt (2004, 2006, … 2026) — elf
    Marken machen die Markierung wertlos, statt sie zu schärfen.

**(7) Teiljahre bleiben stehen, sie werden nur gekennzeichnet.** Gemessen: CH-TED beginnt
2016 mit nur **5 belegten Monaten** (Aug–Dez, 1.843 Verfahren), 2017 sind es 4.406 — wer
das Teiljahr als Jahreswert zeichnet, liest daraus +139 % Marktwachstum. Ebenso simap 2024
(6 Monate). Weggeworfen wird nichts (Projekt-Konvention „markieren statt filtern"), aber
jede Reihe führt `teiljahre: [{jahr, monate}]`, und das laufende Jahr fehlt ganz —
die Achse endet beim letzten *vollen* Jahr.

**(8) Die Historie ist ein Schalter, kein Default.** `--ab-jahr 2004` verlängert die Achse;
ohne ihn deckt der Jahres-Layer dasselbe 5-Jahres-Fenster wie die Saison ab. Grund:
`build_marktpuls.py` läuft im Tageslauf (`scripts/daily_leads.sh`) und darf dort nicht
minutenlang werden. Der Saison-Teil bleibt **immer** auf den 5 vollen Jahren — ein
Saisonindex über 22 Jahre mit vier Schema-Generationen und wechselnder Meldepflicht
mittelte Regime, die nichts miteinander zu tun haben.

--------------------------------------------------------------------------------
Aufruf::

    python3 scripts/build_marktpuls.py [--laender DE,AT,CH] [--jahre 5] [--ab-jahr 2004]
                                       [--out web/data/marktpuls.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

# Das Projektverzeichnis MUSS selbst auf den Pfad — `python3 scripts/x.py` legt nur
# `scripts/` auf sys.path, nie die Wurzel. Ohne diese Zeilen fand `from govisor …`
# das Paket nur, wenn der Aufrufer zufaellig PYTHONPATH gesetzt hatte; im Tageslauf
# unter launchd ist die Umgebung leer und der Schritt starb am 2026-08-15 lautlos
# (abgefangen durch das `||` im Shell-Skript — marktpuls.json blieb still veraltet).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from govisor import db as _db  # noqa: E402

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
SILVER = ROOT / "data" / "silver"
GOLD = ROOT / "data" / "gold"

# --- Fachliche Konstanten -------------------------------------------------------
FENSTER_JAHRE = 5           # Briefing §3.1: letzte 5 vollständige Jahre
MIN_FAELLE = 200            # Briefing §3.4: Mindestfallzahl je Land×Branche-Kombination
LAGE_TAGE = 30              # Briefing §4.1: Zuschläge/Aufhebungen der letzten 30 Tage
AUSREISSER_PCT = 25.0       # Briefing §7: ab welcher Abweichung ein Monat hervorgehoben wird
# --- Wann ein Monat im Befundsatz BENANNT werden darf ---------------------------
# Früher entschied allein `AUSREISSER_PCT` über einen Fenster-Durchschnitt. Das war aus zwei
# Gründen untauglich für eine öffentliche Anzeige, beide gemessen:
#   * **Kipppunkt.** 9 von 27 auswertbaren Kombinationen lagen weniger als 3 pp von der
#     Schwelle entfernt, die Standardansicht `gesamt|alle` bei 0,2 pp. Der Satz wäre zwischen
#     „gleichmässig verteilt" und „Januarloch" gesprungen, sobald sich die Daten minimal bewegen.
#   * **Reihenfolge-Fehler.** Geprüft wurde erst das Hoch, dann das Tief — sobald irgendein
#     Monat über der Schwelle lag, wurde er gemeldet, auch wenn das Tief doppelt so stark war
#     (DE/Energie meldete „Juli +31 %", während der Januar bei −39 % lag).
# Ersetzt durch eine Aussage, die nicht kippen kann: **wie oft lag der Monat über 22 Jahre
# hinweg in derselben Richtung?** Gemessen `gesamt|alle`: Januar 22 von 22 Jahren darunter,
# Juli 22 von 22 darüber — während Feb/Apr/Mai/Sep/Okt in 55–59 % der Jahre die Richtung
# wechseln, also Rauschen sind. Beide Kriterien müssen erfüllt sein: Richtung UND Ausmass.
STABIL_ANTEIL = 0.8         # in mind. 80 % der Jahre dieselbe Richtung
STABIL_MIN_PCT = 10.0       # und im Mittel mind. so weit vom Jahresmittel entfernt
                            # (der Dezember hält die Richtung zu 82 %, aber nur mit +3,9 % —
                            #  verlässlich und trotzdem bedeutungslos, deshalb beide Hürden)
# Dritte Hürde: genug Masse für eine MONATS-Aussage. `MIN_FAELLE` (200) gilt für den ganzen
# Block über fünf Jahre — das sind 3,3 Verfahren im Monat und trägt keine Monatsaussage.
# Gemessen CH/Medizin: Ø 7 Verfahren/Monat, „verlässlich in 8 von 10 Jahren" bei einer
# Spanne von −70 bis +100 %. Bei Ø 30 verschiebt eine einzelne Vergabe den Index um 3 pp,
# bei Ø 50 um 2 pp — darunter misst man Zufall, nicht Saison.
STABIL_MIN_PRO_MONAT = 50
GESAMT = "gesamt"           # Schlüssel des Länder-Aggregats
ALLE = "alle"               # Schlüssel des Branchen-Aggregats

# Die Bekanntmachungsarten, die ein *bietbares* Verfahren eröffnen. `pin` nur mit Frist
# (Briefing §2.1: „Vorinformationen ohne Frist zählen nicht als Ausschreibung").
TENDER_KINDS = ("cn", "pin")

# Quellenfamilie je schema_gen. Alle TED-Schema-Generationen sind EINE Quelle (der
# Formatwechsel legacy→eforms ist kein Quellenwechsel); die nationalen Portale sind eigene.
QUELLE = {
    "legacy": "ted", "eforms": "ted", "text": "ted", "ojs": "ted",
    "doe": "doe", "simap": "simap", "atverg": "atverg",
}

# Branche identisch zu scripts/export_web_leads.py (dim_cpv.branche → ui_branche) —
# Briefing §9-4: die Zahlen müssen zur Lead-Liste passen.
BRANCHE_SQL = """CASE b.branche
  WHEN 'IT' THEN 'it' WHEN 'Elektro' THEN 'it' WHEN 'Messtechnik' THEN 'it'
  WHEN 'Bau' THEN 'bau' WHEN 'Installation' THEN 'bau' WHEN 'Immobilien' THEN 'bau'
    WHEN 'Ingenieur/Architektur' THEN 'bau' WHEN 'Wartung' THEN 'bau'
  WHEN 'Medizin' THEN 'medizin' WHEN 'Gesundheit' THEN 'medizin'
  WHEN 'Sicherheit' THEN 'sicherheit'
  WHEN 'Energie' THEN 'energie' WHEN 'Versorgung' THEN 'energie' WHEN 'Wasser' THEN 'energie'
    WHEN 'Umwelt/Reinigung' THEN 'energie' WHEN 'Chemie' THEN 'energie' WHEN 'Rohstoffe' THEN 'energie'
  ELSE 'beratung' END"""
BRANCHEN = ("bau", "it", "beratung", "medizin", "sicherheit", "energie")

# --- Jahres-Layer ---------------------------------------------------------------
# Frühestes zulässiges `--ab-jahr`. Der Bestand beginnt 2004-01 (CLAUDE.md); alles davor
# wäre eine leere Achse. Zugleich der Filter gegen kaputte Jahreswerte: AT/atverg führt
# 127 Zeilen mit `year = 1` — die fallen über `jahr >= ab_jahr` heraus, statt die Achse
# bis zum Jahr 1 zu ziehen.
FRUEHESTES_JAHR = 2004
# Ab wie vielen belegten Monaten ein Jahr als vollständig gilt. Zwölf, weil alles andere
# eine Ermessensgrenze wäre: ein Jahr ist voll oder es ist es nicht.
VOLLE_MONATE = 12
# Unterhalb dieser Zahl gilt ein Jahr einer Quelle als Vorlauf, nicht als Betrieb.
# Gemessen an AT/atverg: 2009–2018 stehen 1–20 Verfahren je Jahr (Streuzeilen aus einem
# Nachtrag), ab 2019 sind es 6.578 mit 12 belegten Monaten. Ohne diese Schwelle stünde der
# Serienbeginn von atverg auf 2009 und die Reihe bestünde zehn Jahre lang aus Rauschen.
MIN_JAHR_VERFAHREN = 100

# --- Single-Bid-Layer ------------------------------------------------------------
# Verfahrensarten, bei denen ein einziger Bieter **kein Befund, sondern die Bauart** ist:
# hier wurde kein Wettbewerb gesucht. Gemessen über 2010–2026 (Anteil Single-Bid):
#   negotiated_no_call 79,4 % · Verhandlungsverf. ohne vorherige Bek. 72,4 % · Direktvergabe 61,2 %
# Bewusst NICHT dabei, obwohl der Name es nahelegt: `Direktvergabe mit vorheriger
# Bekanntmachung` liegt bei 18,6 % — dort wurde sehr wohl veröffentlicht und geboten.
# Wer nach dem Namen filtert statt nach der gemessenen Quote, wirft diese 5.644 Vergaben
# fälschlich weg. Der ungefilterte Wert bleibt als `quote_alle` daneben stehen.
OHNE_WETTBEWERB = (
    "negotiated_no_call",
    "Verhandlungsverfahren ohne vorheriger Bekanntmachung",
    "Direktvergabe",
)
# Eine Serie wird für ein Jahr nur gezeichnet, wenn sie genug Masse UND genug Abdeckung hat.
# Gemessen 2010: 53 von 21.010 Zuschlägen trugen eine Bieterzahl (0,3 %) — die daraus
# gerechneten „5,7 %" wären eine Zahl über 53 Fälle, gezeichnet wie ein Jahreswert.
BIETER_MIN_JAHR = 300
BIETER_MIN_ABDECKUNG = 40.0

# Bruchstellen, die in KEINEM Datensatz stehen — äusseres Wissen, deshalb `art: kuratiert`
# und jeder Eintrag mit `beleg`. Bewusst kurz gehalten (s. Entscheidung 6 im Modulkopf):
# die EU-Schwellenwerte werden alle zwei Jahre neu festgesetzt, elf Marken auf einer Achse
# markieren nichts mehr. Wer eine Zeile ergänzt, ergänzt den Beleg mit.
# `laender = "*"` gilt für alle, sonst eine Liste.
REGEL_BRUECHE = (
    {"jahr": 2006, "code": "eu_standardformulare", "laender": "*",
     "beleg": "Verordnung (EG) Nr. 1564/2005. Erste einheitlichen EU-Standardformulare, "
              "anwendbar ab 01.02.2006"},
    {"jahr": 2016, "code": "eu_vergaberichtlinien_2014", "laender": "*",
     "beleg": "Richtlinien 2014/24/EU und 2014/25/EU, Umsetzungsfrist 18.04.2016 (in DE das "
              "Vergaberechtsmodernisierungsgesetz, GWB/VgV/SektVO/KonzVgV); neue "
              "Standardformulare nach Durchführungsverordnung (EU) 2015/1986"},
    {"jahr": 2024, "code": "eforms_pflicht", "laender": "*",
     "beleg": "Verordnung (EU) 2019/1780 (eForms) i. d. F. der Verordnung (EU) 2022/2303. "
              "Übergang 2023, verbindliches TED-Format ab 2024"},
)


# --- Hilfsfunktionen ------------------------------------------------------------
def _glob(country: str, table: str) -> str:
    return str(SILVER / country / table / "**" / "*.parquet")


def _hat_tabelle(country: str, table: str) -> bool:
    d = SILVER / country / table
    return d.is_dir() and any(d.rglob("*.parquet"))


def verfuegbare_laender() -> list[str]:
    if not SILVER.is_dir():
        return []
    return sorted(p.name for p in SILVER.iterdir()
                  if p.is_dir() and _hat_tabelle(p.name, "notices"))


def _wurzeln(con: duckdb.DuckDBPyConnection, country: str) -> list[tuple[str, str]]:
    """Rückverweis-Kette bis zur Wurzel auflösen (wie ``gold.build_procedures``).

    Hier bewusst nachgebaut statt ``data/gold/DE/procedures.parquet`` gelesen: die
    Tabelle existiert nur für DE, und der Marktpuls soll für jedes Land gleich rechnen.
    """
    rows = con.execute(f"""
        SELECT publication_number, ref_publication_number
        FROM '{_glob(country, "notices")}'
        WHERE publication_number IS NOT NULL AND ref_publication_number IS NOT NULL
    """).fetchall()
    if not rows:
        return []
    ref = dict(rows)

    def root(pn: str) -> str:
        seen: set[str] = set()
        while True:
            parent = ref.get(pn)
            if not parent or parent in seen:
                return pn
            seen.add(pn)
            pn = parent

    return [(pn, root(pn)) for pn in ref]


def _dedup_ids(country: str) -> list[str]:
    """notice_ids, die als Quellen-Dublette fallen — aus der zentralen Dubletten-Firewall.

    Bis 2026-08-13 kamen sie aus zwei quellenspezifischen Skripten (`atverg_dedup.parquet`,
    `ted_dedup.parquet`). Die sind abgeloest: `govisor/dedupe.py` prueft ALLE Quellen eines
    Landes in einem Durchlauf, und mit `--alle-arten` deckt es auch Zuschlaege ab — die
    Veroeffentlichungs-Sicht, die genau hier gebraucht wird. Marktpuls zaehlt Publikationen
    je Jahr; ohne Zuschlaege waeren AT/CH in den Jahresschichten doppelt gezaehlt.

    Genommen wird nur die staerkste Belegstufe (`kaeufer_und_titel`: identische Vergabestelle
    UND Titel-Enthaltung >= 0,8, nach Zahlen-, Geschwister- und Stufen-Sperre). Die
    schwaecheren Stufen stehen in der Tabelle, sind aber fuer eine Zaehlung zu unsicher.

    Fehlt die Datei, wird nichts ausgeschlossen — die Reihen rauschen dann sichtbar, statt
    still falsch zu sein. Das ist die richtige Ausfallrichtung.
    """
    dup = GOLD / country / "notice_duplicates.parquet"
    if not dup.exists():
        return []
    con = _db.connect()
    out = [r[0] for r in con.execute(
        f"SELECT DISTINCT duplicate_id FROM '{dup}' WHERE beleg = 'kaeufer_und_titel'"
    ).fetchall()]
    con.close()
    return out


def _in_list(col: str, werte: list[str]) -> str:
    """SQL-Bedingung ohne Parameterbindung — Werte sind ausschliesslich Notice-IDs aus
    unserem eigenen Bestand, trotzdem wird jedes Hochkomma verdoppelt."""
    if not werte:
        return "FALSE"
    lit = ",".join("'" + w.replace("'", "''") + "'" for w in werte)
    return f"{col} IN ({lit})"


# --- Kern: Verfahrenstabelle je Land --------------------------------------------
def verfahren_tabelle(con: duckdb.DuckDBPyConnection, country: str, ab_jahr: int) -> None:
    """Legt TEMP TABLE ``v_<country>`` an: ein Verfahren = eine Zeile.

    Spalten: land, jahr, monat, branche, quelle, verfahren_key, frist, hat_frist.
    Enthält nur *eröffnende* Bekanntmachungen (cn / pin-mit-Frist), ohne Korrekturen.
    """
    n = _glob(country, "notices")
    a = _glob(country, "attributes")
    dim_cpv = GOLD / "DE" / "dim_cpv.parquet"      # reine Dimensionstabelle (CPV-Division)

    # Die beiden gesuchten Pfade sind eForms-Konstrukte und können vor der ersten
    # eForms-Bekanntmachung des Landes gar nicht vorkommen (gemessen DE: `ContractFolderID`
    # und `ChangedNoticeIdentifier` existieren ausschliesslich ab 2023). Der Attribut-Scan
    # wird deshalb auf diese Jahre gepinnt statt auf `ab_jahr` — sonst würde `--ab-jahr 2004`
    # ~20 Jahre Attribute lesen, in denen definitionsgemäss nichts zu finden ist.
    # Abgeleitet statt eingetragen, damit es in jedem Land gilt (EU-weit-Grundsatz).
    attr_ab = con.execute(
        f"SELECT min(year) FROM '{n}' WHERE schema_gen = 'eforms'").fetchone()[0]
    attr_ab = max(ab_jahr, attr_ab) if attr_ab is not None else 9999

    # Änderungsbekanntmachungen (eForms) — als eigene Temp-Tabelle, weil der
    # Attribut-Scan sonst je Abfrage neu läuft.
    con.execute("CREATE OR REPLACE TEMP TABLE _chg (notice_id VARCHAR)")
    if _hat_tabelle(country, "attributes"):
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE _chg AS
            SELECT DISTINCT notice_id FROM '{a}'
            WHERE year >= {attr_ab} AND path LIKE '%ChangedNoticeIdentifier'
        """)
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE _folder AS
            SELECT notice_id, min(value) AS folder FROM '{a}'
            WHERE year >= {attr_ab} AND path LIKE '%.ContractFolderID' AND value IS NOT NULL
            GROUP BY 1
        """)
    else:
        con.execute("CREATE OR REPLACE TEMP TABLE _folder (notice_id VARCHAR, folder VARCHAR)")

    # Rückverweis-Wurzeln (legacy)
    con.execute("CREATE OR REPLACE TEMP TABLE _root (publication_number VARCHAR, root VARCHAR)")
    paare = _wurzeln(con, country)
    if paare:
        con.executemany("INSERT INTO _root VALUES (?, ?)", paare)

    dedup = _dedup_ids(country)
    quelle_case = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in QUELLE.items())

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _notices AS
        SELECT n.notice_id,
               -- Ersatzdatum aus year/month, wo `publication_date` fehlt. Gemessen DE/DÖE
               -- 2023: nur 8.875 von 102.043 `cn` tragen ein publication_date — eine
               -- Forderung darauf warf **93 % der Quelle weg**, lautlos. `year`/`month`
               -- sind belastbar: sie verteilen sich natürlich über alle zwölf Monate (kein
               -- Ingest-Klumpen), und wo beide Angaben vorliegen, stimmen sie zu 98,3 %
               -- überein. Der Monatserste ist die gröbere, aber ehrliche Angabe — die
               -- Alternative war kein genaueres Datum, sondern gar kein Verfahren.
               coalesce(n.publication_date, make_date(n.year, n.month, 1)) AS publication_date,
               (n.publication_date IS NULL) AS datum_aus_jahr_monat,
               n.year AS jahr, n.month AS monat,
               n.submission_deadline AS frist, n.schema_gen,
               (c.notice_id IS NOT NULL) AS ist_aenderung,
               CASE n.schema_gen {quelle_case} ELSE 'sonstige' END AS quelle,
               coalesce({BRANCHE_SQL}, 'beratung') AS branche,
               coalesce(f.folder, r.root, n.publication_number, n.notice_id) AS verfahren_key
        FROM '{n}' n
        LEFT JOIN _folder f ON f.notice_id = n.notice_id
        LEFT JOIN _root r ON r.publication_number = n.publication_number
        LEFT JOIN _chg c ON c.notice_id = n.notice_id
        LEFT JOIN '{dim_cpv}' b ON b.division = substr(n.cpv_main, 1, 2)
        WHERE n.year >= {ab_jahr}
          AND n.notice_kind IN {TENDER_KINDS}
          AND (n.notice_kind <> 'pin' OR n.submission_deadline IS NOT NULL)
          -- Ein Verfahren braucht einen Zeitpunkt — aber `year`/`month` genügen dafür.
          AND (n.publication_date IS NOT NULL OR (n.year IS NOT NULL AND n.month IS NOT NULL))
          AND coalesce(n.publication_date, make_date(n.year, n.month, 1)) <= current_date
                                                          -- Datums-Ausreisser (bis 2033) raus
          AND NOT ({_in_list("n.notice_id", dedup)})
    """)

    # Ein Verfahren = eine Zeile.
    # Zeitpunkt/Branche/Quelle: aus der frühesten **eröffnenden** Bekanntmachung (Änderungen
    # eröffnen nichts). Frist: das **Maximum über alle** Zeilen der Gruppe — genau dafür
    # bleiben die Änderungsbekanntmachungen in der Gruppe, denn eine Fristverlängerung steht
    # ausschliesslich in ihnen. Wer sie vorher wegwirft, zeigt abgelaufene Verfahren als offen.
    # Gruppen ohne eröffnende Zeile (Änderung, deren Original vor `ab_jahr` liegt) fallen raus.
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE v_{country} AS
        SELECT * FROM (
            SELECT '{country}' AS land, verfahren_key,
                   min_by(jahr, publication_date) FILTER (WHERE NOT ist_aenderung) AS jahr,
                   min_by(monat, publication_date) FILTER (WHERE NOT ist_aenderung) AS monat,
                   min(publication_date) FILTER (WHERE NOT ist_aenderung) AS pub,
                   min_by(branche, publication_date) FILTER (WHERE NOT ist_aenderung) AS branche,
                   min_by(quelle, publication_date) FILTER (WHERE NOT ist_aenderung) AS quelle,
                   -- Nur für die Bruch-Erkennung des Jahres-Layers: die Schema-Generation
                   -- der eröffnenden Bekanntmachung. `quelle` fasst legacy/text/eforms/ojs
                   -- bewusst zu „ted" zusammen (ein Formatwechsel ist kein Quellenwechsel) —
                   -- genau dieser Wechsel ist hier aber die zu markierende Bruchstelle.
                   min_by(schema_gen, publication_date) FILTER (WHERE NOT ist_aenderung) AS schema_gen,
                   max(frist) AS frist,
                   -- Herkunfts-Kennzeichnung (Projekt-Konvention): steht der Zeitpunkt
                   -- dieses Verfahrens auf einem echten Veröffentlichungsdatum oder nur auf
                   -- year/month? Wird als Anteil in `coverage` ausgewiesen, damit die
                   -- gröbere Angabe sichtbar bleibt statt sich unter die exakten zu mischen.
                   bool_and(datum_aus_jahr_monat) FILTER (WHERE NOT ist_aenderung)
                     AS datum_aus_jahr_monat,
                   count(*) FILTER (WHERE ist_aenderung) AS n_aenderungen,
                   count(*) AS n_notices
            FROM _notices GROUP BY verfahren_key
        ) WHERE pub IS NOT NULL
    """)


# --- Teil 1: Saisonalität -------------------------------------------------------
def quellen_im_fenster(con, country: str, jahre: list[int]) -> tuple[list[str], list[dict]]:
    """Quellenfamilien, die über das GANZE Fenster liefern — der Rest fliegt aus der Zeitreihe."""
    rows = con.execute(f"""
        SELECT quelle, count(DISTINCT jahr) AS j, count(*) AS n, min(jahr) AS von, max(jahr) AS bis
        FROM v_{country} WHERE jahr BETWEEN {jahre[0]} AND {jahre[-1]}
        GROUP BY 1 ORDER BY 3 DESC
    """).fetchall()
    drin, raus = [], []
    for q, j, n, von, bis in rows:
        if j == len(jahre):
            drin.append(q)
        else:
            raus.append({"quelle": q, "verfahren": n, "von": von, "bis": bis,
                         "grund": "liefert erst ab %d — Quellen-Onset, kein Marktsignal" % von})
    return drin, raus


def saison_block(con, wo: str, jahre: list[int], stab: dict[int, dict] | None = None,
                 naiv_mitfuehren: bool = False) -> dict:
    """Monatswerte + Befund für eine Land×Branche-Kombination.

    ``avg`` = Ø absolute Verfahren je Kalendermonat (Briefing §3.1).
    ``pct`` = Abweichung vom Jahresmittel. Berechnet als **Saisonindex**: erst je Jahr
    normiert (Monat / Monatsmittel des Jahres), dann über die Jahre gemittelt. Der
    naive Weg (Ø-Zahl / Ø-Jahresmittel) gewichtet grosse Jahre stärker und reagiert auf
    Niveauverschiebungen im Fenster; der Index tut das nicht. Beide Werte liegen im JSON
    (`pct` = Index, `pct_naiv`), damit die Differenz prüfbar bleibt.
    """
    rows = con.execute(f"""
        WITH je_jahr_monat AS (
            SELECT jahr, monat, count(*) AS n FROM _saison WHERE {wo} GROUP BY 1, 2
        ), voll AS (
            SELECT j.jahr, m.monat, coalesce(x.n, 0) AS n
            FROM (SELECT unnest({jahre}) AS jahr) j
            CROSS JOIN (SELECT unnest([1,2,3,4,5,6,7,8,9,10,11,12]) AS monat) m
            LEFT JOIN je_jahr_monat x ON x.jahr = j.jahr AND x.monat = m.monat
        ), jm AS (
            SELECT jahr, avg(n) AS mittel FROM voll GROUP BY 1
        )
        SELECT v.monat, avg(v.n) AS avg_n,
               avg(CASE WHEN jm.mittel > 0 THEN v.n / jm.mittel END) AS index_
        FROM voll v JOIN jm ON jm.jahr = v.jahr
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    monate = [{"m": int(m), "avg": round(a, 1)} for m, a, _ in rows]
    total = sum(r[1] for r in rows) * len(jahre)
    jahresmittel = sum(r[1] for r in rows) / 12 if rows else 0.0
    stab = stab or {}
    for eintrag, (_, a, idx) in zip(monate, rows):
        eintrag["pct"] = round(((idx or 1.0) - 1.0) * 100, 1)
        # `pct_naiv` ist das Prüffeld zum Saisonindex (s. Docstring) und wird nirgends
        # gerendert. In 35 Blöcken × 12 Monaten kostet es ~4 KB des 50-KB-Budgets für eine
        # Information, die genau einmal gebraucht wird: am Gesamtwert, wo die Abweichung
        # zwischen beiden Rechenwegen belegt ist. Deshalb nur dort.
        if naiv_mitfuehren:
            eintrag["pct_naiv"] = round((a / jahresmittel - 1) * 100, 1) if jahresmittel else 0.0
        # Ein Bit je Monat: hielt dieser Monat über die ganze Achse die Richtung? Damit kann
        # die Anzeige die verlässlichen Ausschläge von denen trennen, die jährlich wechseln —
        # ohne dass die vollen Stabilitätsdaten ins JSON müssen (Grössenbudget). Nur gesetzt,
        # wenn wahr: die meisten Monate sind es nicht, und `"stabil":false` zwölfmal je
        # Kombination kostete 6 KB für eine Information, die das Fehlen schon trägt.
        if stab.get(eintrag["m"], {}).get("stabil"):
            eintrag["stabil"] = True
    return {
        "monate": monate,
        "jahresmittel": round(jahresmittel, 1),
        "verfahren_gesamt": int(round(total)),
        # `jahre` stand hier früher je Block — in allen 35 identisch, weil das Fenster für
        # alle dasselbe ist. Es steht jetzt einmal unter `fenster`.
        "befund": befund(monate, stab),
        "genug": int(round(total)) >= MIN_FAELLE,
    }


def monats_stabilitaet(con, achse: list[int]) -> dict[tuple, dict]:
    """Je (land, branche, monat): wie oft lag der Monat über die GANZE Achse in derselben
    Richtung? Ein Scan über ``_saison``, in Python aggregiert.

    Bewusst über die Achse (bis 2004), nicht über das 5-Jahres-Fenster: die Frage lautet
    „war das immer so", und die beantwortet man nicht mit fünf Jahren. Die angezeigten
    Balken bleiben davon unberührt — sie stehen weiter auf dem Fenster.
    """
    rows = con.execute(f"""
        SELECT land, branche, jahr, monat, count(*) AS n FROM _saison
        WHERE jahr BETWEEN {achse[0]} AND {achse[-1]} GROUP BY 1, 2, 3, 4
    """).fetchall()

    # ERST die Mengen addieren, DANN den Index bilden. Andersherum (Index je Land×Branche
    # bilden und die Indizes mitteln) käme für das Aggregat Unsinn heraus: jedes Jahr läge
    # dann vierzehnfach in der Stichprobe, gewichtet nach Kombination statt nach Menge.
    menge: dict[tuple, int] = {}
    for land, branche, jahr, monat, n in rows:
        for lnd in (GESAMT, land):
            for br in (ALLE, branche):
                k = (lnd, br, jahr, monat)
                menge[k] = menge.get(k, 0) + n

    # Jahresmittel je (land, branche, jahr) — über ZWÖLF Monate, nicht über die belegten:
    # ein Monat ohne Verfahren ist eine Null, kein fehlender Wert.
    summe: dict[tuple, int] = {}
    for (lnd, br, jahr, _m), n in menge.items():
        summe[(lnd, br, jahr)] = summe.get((lnd, br, jahr), 0) + n

    roh: dict[tuple, list[float]] = {}
    for (lnd, br, jahr), gesamt_jahr in summe.items():
        mittel = gesamt_jahr / 12.0
        if mittel <= 0:
            continue
        for monat in range(1, 13):
            idx = menge.get((lnd, br, jahr, monat), 0) / mittel
            roh.setdefault((lnd, br, monat), []).append(idx)

    out: dict[tuple, dict] = {}
    for key, werte in roh.items():
        n = len(werte)
        ueber = sum(1 for v in werte if v > 1.0)
        anteil = max(ueber, n - ueber) / n if n else 0.0
        mittel = 100.0 * (sum(werte) / n - 1.0) if n else 0.0
        hoch = ueber >= n - ueber
        # Ø Verfahren dieses Monats über alle Jahre — die Masse-Hürde.
        lnd, br, monat = key
        pro_monat = sum(menge.get((lnd, br, j, monat), 0)
                        for j in range(achse[0], achse[-1] + 1)) / max(1, n)
        # Die Spanne NUR über die Jahre der vorherrschenden Richtung. Sonst behauptet der
        # Satz „lag auf derselben Seite" und zeigt darunter eine Spanne, die beide Seiten
        # umfasst (gemessen CH/Medizin: „8 von 10 Jahren" mit −70 bis +100 %). Die
        # abweichenden Jahre verschwinden dadurch nicht — sie stehen in `jahre_gleich`.
        gleiche = [v for v in werte if (v > 1.0) == hoch] or werte
        out[key] = {
            "jahre": n,
            "gleiche_richtung": max(ueber, n - ueber),
            "richtung": "ueber" if hoch else "unter",
            "lo": round(100.0 * (min(gleiche) - 1.0), 1),
            "hi": round(100.0 * (max(gleiche) - 1.0), 1),
            "mittel": round(mittel, 1),
            "pro_monat": round(pro_monat, 1),
            # Drei Hürden, jede gegen einen gemessenen Fehlschluss: Richtung (sonst Rauschen),
            # Ausmass (Dezember: 82 % treu bei +3,9 %), Masse (CH/Medizin: Ø 7 im Monat).
            "stabil": (n >= 3 and anteil >= STABIL_ANTEIL
                       and abs(mittel) >= STABIL_MIN_PCT
                       and pro_monat >= STABIL_MIN_PRO_MONAT),
        }
    return out


def befund(monate: list[dict], stab: dict[int, dict]) -> dict:
    """Der Ein-Satz-Befund — Briefing §7. Kein vorformulierter Text: hier entstehen nur
    CODE + Zahlen, formuliert wird im Frontend (i18n).

    Benannt wird der **stärkste über die Jahre verlässliche** Ausschlag. Zwei Fehler der
    ersten Fassung sind damit erledigt (beide gemessen, s. `STABIL_ANTEIL` oben):
    die Reihenfolge Hoch-vor-Tief, die schwächere Effekte melden konnte, und die harte
    Schwelle, an der die Aussage kippte.
    """
    if not monate:
        return {"typ": "keine_daten"}
    hoch = max(monate, key=lambda x: x["pct"])
    tief = min(monate, key=lambda x: x["pct"])

    # Die Achse entscheidet, WELCHE Monate benannt werden dürfen (Verlässlichkeit über 22
    # Jahre). Das angezeigte Fenster entscheidet, WELCHER davon genannt wird — sonst nennt
    # der Satz einen anderen Monat als den, dessen Balken im Bild heraussticht. Gemessen an
    # DE/Energie: über die Achse führt der Juli, im Fenster liegt der Januar bei −39 %.
    def taugt(m: dict) -> bool:
        s = stab.get(m["m"])
        if not s or not s["stabil"]:
            return False
        # Die Verlässlichkeit muss STÜTZEN, was das Diagramm zeigt. Ein Monat, der über die
        # Achse überwiegend oben liegt, im gezeigten Fenster aber unten, belegt den Satz
        # nicht — er widerspricht ihm. Gemessen CH/IT: Befund „tief", Spanne +0 bis +140 %.
        return (m["pct"] > 0) == (s["richtung"] == "ueber")

    kandidaten = [m for m in monate if taugt(m)]
    if kandidaten:
        stark = max(kandidaten, key=lambda m: abs(m["pct"]))
        s = stab[stark["m"]]
        return {
            "typ": "tief" if stark["pct"] < 0 else "spitze",
            "monat": stark["m"], "pct": stark["pct"], "avg": stark["avg"],
            # Der Beleg, der den Satz trägt: „in 22 von 22 Jahren".
            "jahre": s["jahre"], "jahre_gleich": s["gleiche_richtung"],
            "mittel": s["mittel"], "spanne": [s["lo"], s["hi"]],
        }
    return {"typ": "flach", "monat": hoch["m"], "pct": hoch["pct"], "avg": hoch["avg"],
            "monat_tief": tief["m"], "pct_tief": tief["pct"]}


# --- Teil 2: Jahres-Layer + Historie --------------------------------------------
def _jahres_rohdaten(con, laender: list[str], achse: list[int]) -> dict:
    """Ein Scan über alle ``v_<land>`` — je (land, jahr, quelle, branche) Zahl und Monate.

    Zwei getrennte Auswertungen aus derselben Abfrage, weil sie Verschiedenes messen:
      * ``zahl[(land, branche, quelle, jahr)]`` — der Reihenwert.
      * ``monate[(land, quelle, jahr)]`` — belegte Kalendermonate, aber **nur auf der Ebene
        aller Branchen**. Auf Branchenebene wäre eine unbelegte Monatslücke oft schlicht
        eine dünne Branche, kein unvollständiger Ingest — dieselbe Zahl, andere Bedeutung.
    """
    union = " UNION ALL ".join(f"SELECT * FROM v_{c}" for c in laender)
    rows = con.execute(f"""
        SELECT land, jahr, quelle, branche, count(*) AS n, count(DISTINCT monat) AS monate
        FROM ({union})
        WHERE jahr BETWEEN {achse[0]} AND {achse[-1]}
        GROUP BY 1, 2, 3, 4
    """).fetchall()

    zahl: dict[tuple, int] = {}
    monat_paare: dict[tuple, set] = {}
    for land, jahr, quelle, branche, n, _m in rows:
        for br in (ALLE, branche):
            for lnd in (GESAMT, land):
                zahl[(lnd, br, quelle, jahr)] = zahl.get((lnd, br, quelle, jahr), 0) + n

    # Belegte Monate lassen sich nicht aus den Branchen-Teilsummen addieren (dieselben
    # Monate kämen mehrfach) — dafür ein zweiter, kleiner Scan ohne Branchen-Achse.
    for land, jahr, quelle, monate in con.execute(f"""
        SELECT land, jahr, quelle, count(DISTINCT monat)
        FROM ({union}) WHERE jahr BETWEEN {achse[0]} AND {achse[-1]} GROUP BY 1, 2, 3
    """).fetchall():
        monat_paare[(land, quelle, jahr)] = monate
        vorher = monat_paare.get((GESAMT, quelle, jahr), 0)
        monat_paare[(GESAMT, quelle, jahr)] = max(vorher, monate)

    return {"zahl": zahl, "monate": monat_paare}


def _serien_regel(zahl: dict, monate: dict, land: str, quellen: list[str],
                  achse: list[int]) -> dict[str, dict]:
    """Die Regel aus Entscheidung 5, in Code: welche Quelle bekommt eine eigene Linie?

    TED ist immer die Basis-Reihe. Eine nationale Quelle wird ihr zugeschlagen, wenn sie
    **von Anfang an mitliefert** — also spätestens im ersten Jahr, in dem TED in diesem
    Land liefert, und danach lückenlos. Sonst eigene Reihe ab ihrem eigenen Beginn.

    Damit ist die Antwort achsenabhängig, und das ist richtig: über 2021–2025 liefert
    atverg durchgehend (→ zusammengeführt), über 2004–2025 beginnt es 2019 (→ eigene
    Reihe). Dieselbe Quelle, zwei Fenster, zwei Antworten — deshalb steht der Grund
    maschinenlesbar dabei, statt implizit zu bleiben.
    """
    def betriebsjahre(q: str) -> list[int]:
        """Jahre, in denen die Quelle wirklich *läuft* — nicht Streuzeilen aus Nachträgen."""
        return [j for j in achse if zahl.get((land, ALLE, q, j), 0) >= MIN_JAHR_VERFAHREN]

    basis = betriebsjahre("ted")
    basis_von = basis[0] if basis else achse[0]

    out: dict[str, dict] = {}
    for q in quellen:
        jahre_q = betriebsjahre(q)
        if not jahre_q:
            # Nur Streuzeilen (AT/atverg 2009–2018: 1–20 Verfahren je Jahr). Keine Reihe,
            # aber ausgewiesen — sonst verschwindet der Bestand lautlos.
            roh = sum(zahl.get((land, ALLE, q, j), 0) for j in achse)
            if roh:
                out[q] = {"serie": None, "grund": "vorlauf", "von": None, "verfahren": roh}
            continue
        if q == "ted":
            out[q] = {"serie": "ted", "grund": "basis", "von": jahre_q[0]}
            continue
        lueckenlos = jahre_q == [j for j in achse if j >= jahre_q[0]]
        if jahre_q[0] <= basis_von and lueckenlos:
            out[q] = {"serie": "ted", "grund": "durchgehend", "von": jahre_q[0]}
        else:
            out[q] = {"serie": q, "grund": "beginnt_spaeter", "von": jahre_q[0]}
    return out


def _brueche(con, laender: list[str], land: str, regeln: dict, achse: list[int],
             zahl: dict, monate: dict) -> list[dict]:
    """Bruchstellen einer Achse — gemessene und kuratierte, immer unterscheidbar.

    Ein Knick über 22 Jahre ist häufiger eine Regeländerung als ein Marktereignis. Die
    Markierung nimmt dem Leser die Fehldeutung ab, ohne die Kurve zu glätten.
    """
    b: list[dict] = []

    # (a) gemessen: Schema-Generation wechselt. Nur innerhalb der TED-Familie — ein
    # Formatwechsel bei TED ist ein Bruch, das Hinzukommen einer nationalen Quelle nicht
    # (das ist `quelle_start`).
    mitglieder = laender if land == GESAMT else [land]
    union = " UNION ALL ".join(f"SELECT * FROM v_{c}" for c in mitglieder)
    dominant = con.execute(f"""
        SELECT jahr, arg_max(schema_gen, n) FROM (
            SELECT jahr, schema_gen, count(*) AS n FROM ({union})
            WHERE quelle = 'ted' AND jahr BETWEEN {achse[0]} AND {achse[-1]}
              AND schema_gen IS NOT NULL
            GROUP BY 1, 2
        ) GROUP BY 1 ORDER BY 1
    """).fetchall()
    for (_vj, vs), (nj, ns) in zip(dominant, dominant[1:]):
        if vs != ns:
            b.append({"jahr": nj, "art": "gemessen", "typ": "schema_wechsel",
                      "von": vs, "nach": ns})

    # (b) gemessen: eine Quelle setzt ein. Nur für Quellen mit EIGENER Reihe — eine
    # zusammengeführte Quelle hat definitionsgemäss keinen sichtbaren Einsatzpunkt.
    for q, r in sorted(regeln.items()):
        if r["serie"] == q and q != "ted" and r["von"] and r["von"] > achse[0]:
            b.append({"jahr": r["von"], "art": "gemessen", "typ": "quelle_start", "quelle": q})

    # (c) gemessen, nur am Aggregat: ein Land tritt hinzu. Gemessen CH — der Bestand
    # beginnt dort 2016, nicht der Schweizer Markt. In einer Summenzeile über alle Länder
    # sähe das wie Wachstum aus; genau die Verwechslung, die der Quellen-Onset auch macht.
    if land == GESAMT:
        for c in mitglieder:
            jahre_c = [j for j in achse
                       if sum(zahl.get((c, ALLE, q, j), 0) for q in QUELLE.values()) > 0]
            if jahre_c and jahre_c[0] > achse[0]:
                b.append({"jahr": jahre_c[0], "art": "gemessen", "typ": "land_start", "land": c})

    # (d) kuratiert: Regeländerungen. Stehen in keinem Datensatz, tragen deshalb `beleg`.
    for r in REGEL_BRUECHE:
        if not (achse[0] < r["jahr"] <= achse[-1]):
            continue
        if r["laender"] != "*" and not set(r["laender"]) & set(mitglieder):
            continue
        b.append({"jahr": r["jahr"], "art": "kuratiert", "typ": "regel",
                  "code": r["code"], "beleg": r["beleg"]})

    b.sort(key=lambda x: (x["jahr"], x["typ"]))
    return b


def jahres_layer(con, laender: list[str], achse: list[int], heute: dt.date) -> dict:
    """Teil 2: ein Wert je Kalenderjahr, je Quelle eine eigene Reihe, Brüche markiert."""
    roh = _jahres_rohdaten(con, laender, achse)
    zahl, monate = roh["zahl"], roh["monate"]
    quellen_je_land: dict[str, list[str]] = {}
    for (land, br, q, _j) in zahl:
        if br == ALLE:
            quellen_je_land.setdefault(land, [])
            if q not in quellen_je_land[land]:
                quellen_je_land[land].append(q)

    regeln = {land: _serien_regel(zahl, monate, land, sorted(qs), achse)
              for land, qs in quellen_je_land.items()}

    reihen: dict[str, list[dict]] = {}
    for land in [GESAMT] + laender:
        for br in [ALLE] + list(BRANCHEN):
            zeilen = []
            for q, r in sorted(regeln.get(land, {}).items()):
                if r["serie"] is None or r["von"] is None:
                    continue
                jahre_q = [j for j in achse if j >= r["von"]]
                werte = [zahl.get((land, br, q, j), 0) for j in jahre_q]
                if not any(werte):
                    continue          # Branche, die diese Quelle nie bedient hat
                # Teiljahre: gemessen, nicht gerundet. Die Anzeige entscheidet, ob sie den
                # Punkt gestrichelt zeichnet oder weglässt — die Zahl bleibt hier stehen.
                teil = [{"jahr": j, "monate": monate.get((land, q, j), 0)}
                        for j in jahre_q
                        if 0 < monate.get((land, q, j), 0) < VOLLE_MONATE]
                zeile = {"quelle": q, "serie": r["serie"], "grund": r["grund"],
                         "von": r["von"], "werte": werte}
                if teil:
                    zeile["teiljahre"] = teil
                zeilen.append(zeile)
            if zeilen:
                reihen[f"{land}|{br}"] = zeilen

    return {
        "achse": achse,
        "von": achse[0], "bis": achse[-1],
        # Das laufende Jahr fehlt bewusst: es ist per Definition ein Teiljahr und liest sich
        # als Einbruch. Ausgewiesen, damit die Anzeige das sagen kann statt es zu verschweigen.
        "laufendes_jahr": heute.year,
        "reihen": reihen,
        "brueche": {land: _brueche(con, laender, land, regeln.get(land, {}), achse, zahl, monate)
                    for land in [GESAMT] + laender},
        # Quellen, die im Fenster nur Streuzeilen haben (`grund: vorlauf`) — kein Datenverlust,
        # aber auch keine Reihe. Gemessen AT/atverg 2009–2018: 1–20 Verfahren je Jahr.
        "vorlauf": {land: [{"quelle": q, "verfahren": r["verfahren"]}
                           for q, r in sorted(rs.items()) if r["grund"] == "vorlauf"]
                    for land, rs in regeln.items()
                    if any(r["grund"] == "vorlauf" for r in rs.values())},
    }


# --- Teil 3: Single-Bid (Wettbewerbsdichte) -------------------------------------
def bieter_layer(con, laender: list[str], achse: list[int]) -> dict:
    """Anteil der Zuschläge mit genau **einem** Bieter, je Jahr und Quelle.

    Ein eigener Datenstrang: die Bieterzahl steht in ``silver/<land>/awards`` und damit
    ausschliesslich an **Zuschlägen**. Drei Eigenschaften, die die Anzeige tragen muss —
    alle gemessen, keine davon offensichtlich:

    **(1) Die Kennzahl ist rückblickend, nicht nutzbar für die Suche.** Von den aktuell
    offenen Ausschreibungen trägt **keine einzige** eine Bieterzahl (gemessen: 0). Sie
    entsteht erst mit dem Zuschlag. Wer sie als Chancen-Signal liest, liest sie falsch —
    sie beschreibt Verfahren, auf die niemand mehr bieten kann.

    **(2) Sie sieht nur einen Teil des Marktes.** DÖE meldet **nie** eine Bieterzahl (0
    Zeilen über alle Jahre), also ist der gesamte deutsche Unterschwellenbereich für diese
    Kennzahl unsichtbar. Ab 2023 fällt die Abdeckung deshalb von ~88 % auf ~60 % — nicht
    weil weniger gemeldet wird, sondern weil eine Quelle dazukam, die dieses Feld nicht
    führt. `abdeckung` steht deshalb je Jahr im JSON und gehört in die Anzeige.

    **(3) Quellen-Onset schlägt hier genauso zu wie in der Zeitreihe.** Eine Mischkurve
    über DACH springt 2018→2019 von 20 % auf 27 % — das ist der atverg-Start (konstant
    ~50 % Single-Bid), kein Marktereignis. Deshalb auch hier: **eine Reihe je Land×Quelle,
    nie eine Summe.** Sauber getrennt zeigt DE/TED einen Anstieg von 10,6 % (2011) auf
    27,2 % (2022) und einen Rückgang auf 21,3 % (2025).
    """
    lst = ",".join("'" + p.replace("'", "''") + "'" for p in OHNE_WETTBEWERB)
    teile = []
    for c in laender:
        n, a = _glob(c, "notices"), _glob(c, "awards")
        if not _hat_tabelle(c, "awards"):
            continue
        quelle_case = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in QUELLE.items())
        teile.append(f"""
            SELECT '{c}' AS land,
                   CASE x.schema_gen {quelle_case} ELSE 'sonstige' END AS quelle,
                   x.year AS jahr,
                   coalesce({BRANCHE_SQL}, 'beratung') AS branche,
                   (aw.mx IS NOT NULL) AS hat_bieter,
                   (aw.mx = 1) AS single,
                   (x.procedure_type IS NULL OR x.procedure_type NOT IN ({lst})) AS mit_wettbewerb
            FROM '{n}' x
            LEFT JOIN (SELECT notice_id, max(num_tenders) AS mx FROM '{a}'
                       WHERE num_tenders IS NOT NULL GROUP BY 1) aw ON aw.notice_id = x.notice_id
            LEFT JOIN '{GOLD / "DE" / "dim_cpv.parquet"}' b ON b.division = substr(x.cpv_main, 1, 2)
            WHERE x.notice_kind = 'can' AND x.year BETWEEN {achse[0]} AND {achse[-1]}
        """)
    if not teile:
        return {"achse": achse, "reihen": {}, "abdeckung": {}}
    con.execute("CREATE OR REPLACE TEMP TABLE _bieter AS " + " UNION ALL ".join(teile))

    rows = con.execute("""
        SELECT land, quelle, jahr, branche,
               count(*) AS cans,
               count(*) FILTER (WHERE hat_bieter) AS mit,
               count(*) FILTER (WHERE single) AS sb,
               count(*) FILTER (WHERE hat_bieter AND mit_wettbewerb) AS mit_w,
               count(*) FILTER (WHERE single AND mit_wettbewerb) AS sb_w
        FROM _bieter GROUP BY 1, 2, 3, 4
    """).fetchall()

    # Aufsummieren auf die Anzeige-Ebenen. Die QUELLE bleibt getrennt (Entscheidung wie im
    # Jahres-Layer); Land und Branche werden zu `gesamt`/`alle` verdichtet.
    agg: dict[tuple, list[int]] = {}
    for land, quelle, jahr, branche, cans, mit, sb, mit_w, sb_w in rows:
        for br in (ALLE, branche):
            for lnd in ([land] if land == GESAMT else [GESAMT, land]):
                k = (lnd, br, quelle, jahr)
                v = agg.setdefault(k, [0, 0, 0, 0, 0])
                v[0] += cans; v[1] += mit; v[2] += sb; v[3] += mit_w; v[4] += sb_w

    reihen: dict[str, list[dict]] = {}
    for land in [GESAMT] + laender:
        for br in [ALLE] + list(BRANCHEN):
            zeilen = []
            quellen = sorted({q for (l, b, q, _j) in agg if l == land and b == br})
            for q in quellen:
                jahre_q = [j for j in achse
                           if (v := agg.get((land, br, q, j)))
                           and v[3] >= BIETER_MIN_JAHR
                           and 100.0 * v[1] / max(1, v[0]) >= BIETER_MIN_ABDECKUNG]
                if len(jahre_q) < 2:
                    continue                 # eine einzelne Jahresmarke ist keine Reihe
                von = jahre_q[0]
                spanne = [j for j in achse if von <= j <= jahre_q[-1]]
                hol = lambda j, i: (agg[(land, br, q, j)][i] if agg.get((land, br, q, j)) else 0)
                # Gespeichert werden die beiden ZÄHLER, nicht der Anteil. Der Prozentwert
                # wird in der Anzeige daraus gerechnet. Zwei Gründe: eine Quelle der
                # Wahrheit statt Prozent und Basis nebeneinander (die auseinanderlaufen
                # können), und — der eigentliche Anlass — ein Anteil ohne seine Grundmenge
                # ist nicht einzuordnen. „20 %" heisst in DE 7.047 von 35.062 Zuschlägen;
                # ohne die zweite Zahl weiss niemand, ob das viel ist.
                zeile = {
                    "quelle": q, "von": von,
                    # Basis: Zuschläge mit Bieterzahl, OHNE die Verfahrensarten, die per
                    # Bauart nur einen Bieter haben.
                    "n": [hol(j, 3) for j in spanne],
                    "sb": [hol(j, 4) for j in spanne],
                }
                if br == ALLE:
                    # Der ungefilterte Gegenwert nur auf der Branchen-Gesamtebene — je
                    # Branche wäre das die doppelte Datenmenge für dieselbe Aussage.
                    zeile["n_alle"] = [hol(j, 1) for j in spanne]
                    zeile["sb_alle"] = [hol(j, 2) for j in spanne]
                zeilen.append(zeile)
            if zeilen:
                reihen[f"{land}|{br}"] = zeilen

    # Abdeckung je Land und Jahr — der Anteil der Zuschläge, der überhaupt eine Bieterzahl
    # trägt. Ohne diese Zeile liest sich „30 %" als Aussage über den ganzen Markt.
    abdeckung: dict[str, list[dict]] = {}
    for land in [GESAMT] + laender:
        werte = []
        for j in achse:
            cans = sum(v[0] for (l, b, _q, jj), v in agg.items()
                       if l == land and b == ALLE and jj == j)
            mit = sum(v[1] for (l, b, _q, jj), v in agg.items()
                      if l == land and b == ALLE and jj == j)
            if cans:
                werte.append({"jahr": j, "pct": round(100.0 * mit / cans, 1), "cans": cans})
        if werte:
            abdeckung[land] = werte

    # Die zentrale Einschränkung der Kennzahl — GEMESSEN, nicht behauptet: wie viele der
    # aktuell offenen Ausschreibungen tragen eine Bieterzahl? Erwartet 0 (sie entsteht erst
    # mit dem Zuschlag), aber genau solche „ist doch klar"-Zahlen gehören nachgerechnet.
    # Steht die Null hier fest verdrahtet, merkt niemand, wenn eine Quelle es doch meldet.
    offen = 0
    for c in laender:
        if not _hat_tabelle(c, "awards"):
            continue
        offen += con.execute(f"""
            SELECT count(DISTINCT x.notice_id)
            FROM '{_glob(c, "notices")}' x
            JOIN (SELECT DISTINCT notice_id FROM '{_glob(c, "awards")}'
                  WHERE num_tenders IS NOT NULL) a ON a.notice_id = x.notice_id
            WHERE x.notice_kind IN {TENDER_KINDS} AND x.submission_deadline >= current_date
        """).fetchone()[0]

    return {
        "achse": achse, "von": achse[0], "bis": achse[-1],
        "reihen": reihen, "abdeckung": abdeckung,
        "ohne_wettbewerb": list(OHNE_WETTBEWERB),
        "offene_mit_bieterzahl": offen,
    }


# --- Teil 4: Aktuelle Lage ------------------------------------------------------
def lage_block(con, laender: list[str], heute: dt.date) -> dict:
    """Stichtags-Kennzahlen. Anders als die Zeitreihe zählt hier JEDE Quelle mit —
    ein Stichtag kennt keinen Onset-Sprung."""
    union = " UNION ALL ".join(f"SELECT * FROM v_{c}" for c in laender)
    con.execute(f"CREATE OR REPLACE TEMP TABLE _lage AS {union}")

    def zaehl(wo: str) -> int:
        return con.execute(f"SELECT count(*) FROM _lage WHERE {wo}").fetchone()[0]

    je_land, je_branche = {}, {}
    for c in laender + [GESAMT]:
        wo_land = "TRUE" if c == GESAMT else f"land = '{c}'"
        frisch = zaehl(f"{wo_land} AND pub >= current_date - 90")
        mit_frist = zaehl(f"{wo_land} AND pub >= current_date - 90 AND frist IS NOT NULL")
        je_land[c] = {
            "laufend": zaehl(f"{wo_land} AND frist >= current_date"),
            "ohne_frist": frisch - mit_frist,
            # Herkunfts-Kennzeichnung (Projekt-Konvention): die Kennzahl steht ausschliesslich
            # auf der echten `submission_deadline`. `frist_abdeckung` sagt, für welchen Anteil
            # der frischen Verfahren überhaupt eine Frist veröffentlicht ist — sinkt sie (AT:
            # atverg meldet oft keine), ist `laufend` eine Untergrenze, keine Vollzählung.
            "frist_basis": "echt",
            "frist_abdeckung": round(100.0 * mit_frist / frisch, 1) if frisch else 0.0,
        }
        je_branche[c] = [{"key": b, "n": zaehl(f"{wo_land} AND branche = '{b}' AND frist >= current_date")}
                         for b in BRANCHEN]
        je_branche[c].sort(key=lambda x: -x["n"])

    # Zuschläge / Aufhebungen der letzten 30 Tage — je Land aus Silber, ohne Verfahrens-
    # Klammer (ein CAN IST der Abschluss; die Klammer würde Mehrlos-Zuschläge verschlucken).
    zuschlag, aufhebung = {}, {}
    for c in laender:
        n, aw = _glob(c, "notices"), _glob(c, "awards")
        hat_aw = _hat_tabelle(c, "awards")
        gewinner = (f"(SELECT DISTINCT notice_id FROM '{aw}' WHERE winner_name IS NOT NULL)"
                    if hat_aw else "(SELECT NULL::VARCHAR AS notice_id WHERE FALSE)")
        z, a = con.execute(f"""
            SELECT count(*) FILTER (WHERE g.notice_id IS NOT NULL),
                   count(*) FILTER (WHERE g.notice_id IS NULL)
            FROM '{n}' x LEFT JOIN {gewinner} g ON g.notice_id = x.notice_id
            WHERE x.notice_kind = 'can'
              AND x.publication_date BETWEEN current_date - {LAGE_TAGE} AND current_date
        """).fetchone()
        zuschlag[c], aufhebung[c] = z, a
    zuschlag[GESAMT] = sum(zuschlag.values())
    aufhebung[GESAMT] = sum(aufhebung.values())

    return {
        "stand": heute.isoformat(),
        "fenster_tage": LAGE_TAGE,
        "je_land": {c: {**je_land[c], "zuschlag_30d": zuschlag[c], "aufhebung_30d": aufhebung[c]}
                    for c in je_land},
        "je_branche": je_branche,
    }


# --- Orchestrierung -------------------------------------------------------------
def bauen(laender: list[str], n_jahre: int, heute: dt.date, ab_jahr: int | None = None) -> dict:
    letztes_volles = heute.year - 1
    jahre = list(range(letztes_volles - n_jahre + 1, letztes_volles + 1))
    # Achse des Jahres-Layers. Ohne `--ab-jahr` deckt sie dasselbe Fenster wie die Saison ab
    # (Entscheidung 8: die Historie kostet Laufzeit und gehört nicht per Default in den
    # Tageslauf). Der Saison-Teil bleibt in JEDEM Fall auf `jahre`.
    achse_von = min(jahre[0], max(FRUEHESTES_JAHR, ab_jahr)) if ab_jahr else jahre[0]
    achse = list(range(achse_von, letztes_volles + 1))
    con = _db.connect()
    con.execute("SET threads=4")

    coverage: dict[str, dict] = {}
    saison_quellen: dict[str, list[str]] = {}
    for c in laender:
        verfahren_tabelle(con, c, achse[0])
        drin, raus = quellen_im_fenster(con, c, jahre)
        saison_quellen[c] = drin
        gesamt, im_fenster = con.execute(f"""
            SELECT count(*), count(*) FILTER (WHERE jahr BETWEEN {jahre[0]} AND {jahre[-1]}
                   AND quelle IN ({",".join("'" + q + "'" for q in drin) or "''"}))
            FROM v_{c}
        """).fetchone()
        max_pub, bestand_von, n_grob = con.execute(
            f"SELECT max(pub), min(jahr), count(*) FILTER (WHERE datum_aus_jahr_monat) "
            f"FROM v_{c}").fetchone()
        coverage[c] = {
            # `verfahren_gesamt` zählt den geladenen Bereich, und der hängt jetzt an
            # `--ab-jahr`. `bestand_von` sagt, ab wann dieses Land überhaupt im Bestand ist
            # (gemessen CH: 2016) — ohne das läse sich die Zahl als Landesgeschichte.
            "verfahren_gesamt": gesamt,
            "bestand_von": bestand_von,
            # Anteil der Verfahren, deren Zeitpunkt nur auf year/month steht (kein echtes
            # `publication_date`). Gemessen DE ~57 % — praktisch die ganze DÖE-Menge.
            "datum_nur_monat_pct": round(100.0 * n_grob / gesamt, 1) if gesamt else 0.0,
            "verfahren_im_fenster": im_fenster,
            "quellen_zeitreihe": drin,
            "quellen_ausgeschlossen": raus,
            "letzte_veroeffentlichung": max_pub.isoformat() if max_pub else None,
            "belastbar": im_fenster >= MIN_FAELLE and bool(drin),
        }

    # Länder OHNE einen einzigen Fall im Fenster fliegen ganz raus — nicht als „nicht
    # belastbar" markiert, sondern gar nicht erst ausgewiesen. Gemessen stand „EU: 0
    # Verfahren  ⚠ nicht belastbar" in der Ausgabe; eine Kategorie mit null Fällen ist keine
    # Aussage über einen dünnen Markt, sondern eine leere Zeile.
    #
    # Sie war zudem die Ursache des zweiten Fehlers: der EU-Topf brachte „ted" als
    # AUSGESCHLOSSENE Quelle ins Aggregat ein, während TED für DE/AT/CH die tragende Quelle
    # ist. In der Gesamtzeile stand deshalb „Quellen atverg+ted, ausgeschlossen: … ted" —
    # dieselbe Quelle gleichzeitig drin und draußen.
    leer = [c for c in laender if coverage[c]["verfahren_im_fenster"] == 0]
    for c in leer:
        print(f"  {c}: 0 Verfahren im Fenster — nicht ausgewiesen (leere Kategorie, "
              f"keine Aussage über den Markt)")
        laender.remove(c)
        coverage.pop(c, None)
        saison_quellen.pop(c, None)

    # Aggregat-Zeile: dieselbe Struktur wie ein Land, damit die Anzeige nicht zwei Fälle
    # kennen muss. Ein dünnes Land wird MITGEZÄHLT (kein Datenverlust), aber namentlich in
    # `nicht_belastbar` ausgewiesen — genau die Forderung „nicht still mitgemittelt".
    drin_agg = sorted({q for c in coverage.values() for q in c["quellen_zeitreihe"]})
    # Ausgeschlossen zählt am Aggregat nur, was NIRGENDS in die Zeitreihe eingeht. Sonst
    # stünde „TED erst ab 2023" da, nur weil der dünne EU-Topf erst 2023 anfängt — obwohl
    # TED die tragende Quelle von DE/AT/CH über das ganze Fenster ist.
    raus_agg: dict[str, dict] = {}
    for c in coverage.values():
        for q in c["quellen_ausgeschlossen"]:
            if q["quelle"] in drin_agg:
                continue
            vorher = raus_agg.get(q["quelle"])
            if vorher is None or q["von"] < vorher["von"]:
                raus_agg[q["quelle"]] = dict(q)
            elif vorher:
                vorher["verfahren"] += q["verfahren"]
    coverage[GESAMT] = {
        "verfahren_gesamt": sum(c["verfahren_gesamt"] for c in coverage.values()),
        "bestand_von": min((c["bestand_von"] for c in coverage.values()
                            if c["bestand_von"] is not None), default=None),
        "datum_nur_monat_pct": round(
            100.0 * sum(c["datum_nur_monat_pct"] / 100.0 * c["verfahren_gesamt"]
                        for c in coverage.values())
            / max(1, sum(c["verfahren_gesamt"] for c in coverage.values())), 1),
        "verfahren_im_fenster": sum(c["verfahren_im_fenster"] for c in coverage.values()),
        "quellen_zeitreihe": drin_agg,
        "quellen_ausgeschlossen": sorted(raus_agg.values(), key=lambda q: -q["verfahren"]),
        "letzte_veroeffentlichung": max(
            (c["letzte_veroeffentlichung"] for c in coverage.values() if c["letzte_veroeffentlichung"]),
            default=None),
        "belastbar": sum(c["verfahren_im_fenster"] for c in coverage.values()) >= MIN_FAELLE,
        "nicht_belastbar": [c for c in laender if not coverage[c]["belastbar"]],
        "mitglieder": laender,
    }

    # Saison-Grundmenge: nur durchgehende Quellen, nur volle Jahre.
    teile = [f"SELECT * FROM v_{c} WHERE quelle IN ({','.join(chr(39)+q+chr(39) for q in saison_quellen[c])})"
             for c in laender if saison_quellen[c]]
    con.execute(f"CREATE OR REPLACE TEMP TABLE _saison AS {' UNION ALL '.join(teile)}"
                if teile else "CREATE OR REPLACE TEMP TABLE _saison AS SELECT * FROM v_%s WHERE FALSE" % laender[0])

    # Richtungstreue je Monat über die GANZE Achse — ein Scan für alle Kombinationen.
    stabilitaet = monats_stabilitaet(con, achse)

    saison: dict[str, dict] = {}
    for land in [GESAMT] + laender:
        wo_land = "TRUE" if land == GESAMT else f"land = '{land}'"
        for br in [ALLE] + list(BRANCHEN):
            wo = wo_land if br == ALLE else f"{wo_land} AND branche = '{br}'"
            st = {m: stabilitaet[(land, br, m)] for m in range(1, 13)
                  if (land, br, m) in stabilitaet}
            saison[f"{land}|{br}"] = saison_block(
                con, wo, jahre, st, naiv_mitfuehren=(land == GESAMT and br == ALLE))

    jahre_layer = jahres_layer(con, laender, achse, heute)
    bieter = bieter_layer(con, laender, achse)
    lage = lage_block(con, laender, heute)
    con.close()

    return {
        # 3 = Single-Bid-Layer (`bieter`); Befund steht jetzt auf Richtungstreue statt
        #     auf einer Schwelle und trägt seinen Beleg; `saison.*.jahre` und die
        #     durchgängigen `pct_naiv` sind entfallen (beide ungenutzt, 5 KB).
        # 2 = Jahres-Layer dazugekommen (`jahre`), `coverage.*.bestand_von` neu.
        # Die Anzeige muss mit einer Datei ohne `jahre` weiter zurechtkommen (Stand 1),
        # sonst bricht sie am ersten Deploy, bei dem Skript und Frontend nicht Schritt halten.
        "schema": 3,
        "erzeugt": dt.datetime.now().isoformat(timespec="seconds"),
        "stand": heute.isoformat(),
        "laender": laender,
        "gesamt_key": GESAMT,
        "branchen": list(BRANCHEN),
        "fenster": {"von": jahre[0], "bis": jahre[-1], "jahre": len(jahre)},
        "min_faelle": MIN_FAELLE,
        "coverage": coverage,
        "saison": saison,
        "jahre": jahre_layer,
        "bieter": bieter,
        "lage": lage,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--laender", default=None,
                   help="Komma-Liste, z. B. DE,AT,CH (Default: alles unter data/silver/)")
    p.add_argument("--jahre", type=int, default=FENSTER_JAHRE)
    p.add_argument("--ab-jahr", type=int, default=None, dest="ab_jahr",
                   help=f"Historie: Achse des Jahres-Layers ab diesem Jahr (frühestens "
                        f"{FRUEHESTES_JAHR}). Ohne Angabe deckt der Jahres-Layer dasselbe "
                        f"Fenster ab wie die Saison — die Historie kostet Laufzeit und "
                        f"gehört nicht per Default in den Tageslauf.")
    p.add_argument("--out", default=str(ROOT / "web" / "data" / "marktpuls.json"))
    p.add_argument("--stichtag", default=None, help="ISO-Datum (Test/Reproduktion)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    laender = ([x.strip().upper() for x in args.laender.split(",") if x.strip()]
               if args.laender else verfuegbare_laender())
    laender = [c for c in laender if _hat_tabelle(c, "notices")]
    if not laender:
        print("Keine Länder mit Silber-notices gefunden.", file=sys.stderr)
        return 1
    heute = dt.date.fromisoformat(args.stichtag) if args.stichtag else dt.date.today()

    daten = bauen(laender, args.jahre, heute, args.ab_jahr)
    text = json.dumps(daten, ensure_ascii=False, separators=(",", ":"))

    print(f"Länder: {', '.join(laender)} | Fenster {daten['fenster']['von']}–{daten['fenster']['bis']}")
    for c, cov in daten["coverage"].items():
        raus = ", ".join(q["quelle"] for q in cov["quellen_ausgeschlossen"]) or "–"
        print(f"  {c}: {cov['verfahren_im_fenster']:>8,} Verfahren im Fenster "
              f"(Quellen {'+'.join(cov['quellen_zeitreihe'])}, ausgeschlossen: {raus})"
              f"{'' if cov['belastbar'] else '  ⚠ nicht belastbar'}")
    g = daten["saison"][f"{GESAMT}|{ALLE}"]
    print(f"  Jahresmittel {g['jahresmittel']:,.0f}/Monat, Befund {g['befund']}")
    print("  " + "  ".join(f"{m['m']:>2}:{m['pct']:+.0f}%" for m in g["monate"]))

    j = daten["jahre"]
    print(f"\nJahres-Layer {j['von']}–{j['bis']} ({len(j['achse'])} Jahre, "
          f"{j['laufendes_jahr']} als laufendes Jahr ausgelassen)")
    for land in [GESAMT] + laender:
        for z in j["reihen"].get(f"{land}|{ALLE}", []):
            teil = "".join(f" ⚠{t['jahr']}={t['monate']}Mon" for t in z.get("teiljahre", []))
            print(f"  {land:>7} {z['quelle']:<7} → Serie '{z['serie']}' ({z['grund']}), "
                  f"ab {z['von']}: {z['werte'][0]:,} … {z['werte'][-1]:,}{teil}")
        for v in j["vorlauf"].get(land, []):
            print(f"  {land:>7} {v['quelle']:<7} → keine Reihe (Vorlauf, "
                  f"{v['verfahren']:,} Verfahren unter der Betriebsschwelle)")
    for land in [GESAMT] + laender:
        for b in j["brueche"].get(land, []):
            rest = {k: v for k, v in b.items()
                    if k not in ("jahr", "art", "typ", "beleg")}
            print(f"  {land:>7} Bruch {b['jahr']} [{b['art']}] {b['typ']}"
                  f"{' ' + str(rest) if rest else ''}")

    print(f"\n  Lage: {daten['lage']['je_land'][GESAMT]}")
    print(f"  JSON {len(text)/1024:.1f} KB")

    if args.dry_run:
        return 0
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
