"""Kennzahlen-Verzeichnis: was eine Zahl ist, wo sie erscheint, wogegen sie auffällt.

WARUM ES DIESE DATEI GIBT. Am 2026-09-01 hat sich herausgestellt, dass `docsignals` fünfzehn
Anforderungs-Signale erkennt, `doc_signals.parquet` alle fünfzehn trägt, und **sieben davon
je im Frontend ankamen**. Verloren gingen sie an handgetippten Spaltenlisten: eine im Export
der Signale, eine im Lead-Export, eine im API-Typ, eine im Renderer. Viermal dieselbe Liste,
viermal pflegbar, viermal vergessbar. Betroffen waren `binding_until` (5.747 Sätze),
`penalty_pct` (4.066), `site_visit` (3.723), `site_visit_mandatory` (3.723),
`presentation_required` (3.576) und `skonto_pct` (393).

⚠ DIE BEZUGSGRÖSSE IST DIE KATEGORIE. Nicht „Marktdaten gegen Firmendaten", nicht „wichtig
gegen unwichtig" — beides wäre eine Meinung. **Wogegen verglichen wird** ist eine Eigenschaft
der Kennzahl, und sie entscheidet zugleich über die Darstellung: nur was einen Bezug hat,
kann auffällig werden und eine Leiste bekommen.

    markt    gegen den Branchen- oder Gesamtwert
    vorwert  gegen den eigenen Stand von vorher (braucht Historie, die es noch nicht gibt)
    profil   gegen eine Schwelle im Firmenprofil
    keine    beschreibend oder Datenlage; bleibt sichtbar, aber in der Detailebene

`keine` ist eine ENTSCHEIDUNG, kein Platzhalter: eine Zahl ohne Vergleichswert kann nie
auffallen und gehört dauerhaft nach unten. Das ist keine Abwertung, sondern die Entlastung —
gut ein Viertel des Bestands fällt darunter und muss nie um Aufmerksamkeit konkurrieren.

ZWEI GENAUIGKEITSSTUFEN, und der Unterschied ist wichtig.
`spalte` trägt den EXAKTEN Namen dort, wo die Zahl entsteht. Den gibt es nur, wo eine
einzelne Spalte sie liefert (Dokument-Signale, Vergabestellen-Kacheln); dort hängen Export,
API-Typ und Renderer daran, und `tests/test_kennzahlen.py` hält die drei zusammen.
Alles andere nennt nur `quelle` — die Datei oder Funktion, in der es entsteht. Eine Zahl, die
im Browser aus dem Profil gerechnet wird, HAT keine Quellspalte, und so zu tun als hätte sie
eine wäre schlimmer als die Lücke.

⚠ VOLLSTÄNDIG HEISST: alles, was ein Nutzer sieht. Stand 2026-09-01 sind das **135
Kennzahl-Plätze über elf Flächen** — Plätze, nicht Metriken: dieselbe Zahl kann auf zwei
Bildschirmen stehen und dort verschiedene Bezüge haben. Wer eine neue baut, trägt sie ein;
sonst ist sie in der nächsten Zählung wieder ein Fund.

Die Verteilung sagt mehr als die Summe:

    markt    58   die grösste Gruppe und die meiste offene Arbeit
    keine    39   beschreibend; kann nie auffallen, gehört dauerhaft nach unten
    profil   23   vergleicht gegen ein Feld, das wir schon haben
    vorwert  15   braucht Historie je Nutzer, die es noch nicht gibt

Nur 19 der 135 tragen eine exakte Quellspalte. Das ist keine Schwäche des Verzeichnisses,
sondern die Lage: die meisten Zahlen entstehen in einer Rechnung, nicht in einer Spalte.
"""
from __future__ import annotations

from dataclasses import dataclass

BEZUEGE = frozenset({"markt", "vorwert", "profil", "keine"})


@dataclass(frozen=True)
class Kennzahl:
    """Eine Zahl, die im Frontend erscheint."""

    schluessel: str
    label: str
    bezug: str
    wogegen: str = ""
    flaeche: str = ""
    quelle: str = ""
    spalte: str = ""
    einheit: str = ""

    def __post_init__(self) -> None:
        if self.bezug not in BEZUEGE:
            raise ValueError(f"{self.schluessel}: unbekannter Bezug {self.bezug!r}")
        # ⚠ Ein Bezug ohne benannten Vergleichswert ist eine unerfüllte Zusage: die Anzeige
        # verspricht eine Einordnung, und niemand kann sagen, wogegen.
        if self.bezug != "keine" and not self.wogegen:
            raise ValueError(f"{self.schluessel}: Bezug {self.bezug!r} ohne Vergleichswert")


def _k(schluessel: str, label: str, bezug: str, wogegen: str = "") -> Kennzahl:
    """Kurzform für die Inventarzeilen — Fläche und Quelle setzt `_mit` darunter."""
    return Kennzahl(schluessel, label, bezug, wogegen)


def _mit(gruppe: tuple[Kennzahl, ...], flaeche: str, quelle: str) -> tuple[Kennzahl, ...]:
    from dataclasses import replace
    return tuple(replace(k, flaeche=flaeche, quelle=quelle) for k in gruppe)


# ── Anforderungen aus den Vergabeunterlagen ──────────────────────────────────────────────
# Quelle: govisor/docsignals.py → data/docs/<L>/doc_signals.parquet → web/data/doc-signals.json
# ⚠ Die EINZIGE Gruppe mit exakten Quellspalten, an denen drei Stellen im Code hängen.
# Reihenfolge = Anzeigereihenfolge im Anforderungs-Block.
#
# ⚠ `evidence` STAND HIER ZUERST NICHT, mit der Begründung „Belegtext, keine eigene
# Kennzahl". Als Kennzahl stimmt das, als Entscheidung war es falsch: damit hatte der Beleg
# GAR KEINEN Ort, an dem jemand merkt, dass er unverdrahtet ist — genau die Lücke, gegen die
# dieses Verzeichnis antritt. Die Übergabe der Parallelsitzung hat ihn am selben Tag als
# „gebaut, aber nicht verdrahtet" gelistet. Er steht jetzt drin, mit `bezug="keine"`, weil er
# nichts vergleicht, sondern belegt.
def _s(schluessel: str, spalte: str, label: str, einheit: str, bezug: str, wogegen: str = "") -> Kennzahl:
    return Kennzahl(schluessel, label, bezug, wogegen, "unterlagen",
                    "doc_signals.parquet", spalte, einheit)


DOC_SIGNALE: tuple[Kennzahl, ...] = (
    _s("guarantee", "guarantee_required", "Sicherheit / Bürgschaft", "ja/nein",
       "profil", "euer Bürgschaftsrahmen"),
    _s("bindingDays", "binding_days", "Bindefrist", "Tage",
       "markt", "übliche Bindefrist im Regelwerk"),
    # ⚠ Das Datum ist NICHT dieselbe Kennzahl wie die Dauer. „90 Tage" sagt, wie lange ihr
    # gebunden seid; „bis 14.11." sagt, ob es in eure Auslastung passt. Im Bestand ist das
    # Datum ausserdem vierzigmal häufiger ablesbar (5.747 gegen 150 Sätze).
    _s("bindingUntil", "binding_until", "Bindefrist bis", "Datum", "keine"),
    _s("eligibility", "eligibility_count", "Eignungsnachweise", "Anzahl",
       "profil", "was ihr hinterlegt habt"),
    _s("certificates", "certificates", "Geforderte Zertifikate", "Liste",
       "profil", "eure Zertifikate"),
    _s("variants", "variants_allowed", "Nebenangebote", "ja/nein", "keine"),
    _s("framework", "framework", "Rahmenvereinbarung", "ja/nein", "keine"),
    _s("weights", "award_weights", "Zuschlagsgewichte", "Prozent",
       "markt", "übliche Gewichtung im Feld"),
    _s("siteVisit", "site_visit", "Ortstermin", "ja/nein", "keine"),
    # ⚠ Mehr als eine Anzeige: ist der Termin PFLICHT und liegt er ausserhalb eurer Regionen,
    # ist das ein Zulassungsgrund und steht als Blocker in `matchLead`. 3.723 Vorgänge mit
    # erkanntem Termin, davon 108 verpflichtend.
    _s("siteVisitMandatory", "site_visit_mandatory", "Ortstermin verpflichtend", "ja/nein",
       "profil", "eure Regionen"),
    _s("presentationRequired", "presentation_required", "Präsentation gefordert", "ja/nein",
       "profil", "habt ihr die Leute dafür"),
    _s("penaltyPct", "penalty_pct", "Vertragsstrafe", "Prozent",
       "markt", "übliche Vertragsstrafe im Feld"),
    _s("skontoPct", "skonto_pct", "Skonto", "Prozent", "markt", "übliches Skonto im Feld"),
    # Der Beleg zur Behauptung: je Signal das Zitat aus dem Dokument (Median 88 Zeichen).
    # Deckung 9.409 von 9.788 Vorgängen mit Volltext = 96 %. Er vergleicht nichts, er
    # belegt — deshalb `keine`, und deshalb gehört er nach unten und nicht in eine Leiste.
    _s("evidence", "evidence", "Beleg aus dem Dokument", "Zitat", "keine"),
)

# ── Vergabestellen-Kacheln (Anbieter-Sicht) ──────────────────────────────────────────────
# Der Vergleichswert ist überall derselbe: der Median über die Vergabestellen derselben
# Branche, gerechnet in `StrategieView.marktLage`.
_BRANCHE = "Median der Vergabestellen derselben Branche"
VERGABESTELLEN: tuple[Kennzahl, ...] = tuple(
    Kennzahl(s, lab, "markt", _BRANCHE, "strategie", "strategie.json", s, einh)
    for s, lab, einh in (
        ("vergabenJahr", "Vergaben pro Jahr", "Anzahl"),
        ("neuAnteil", "Neue Anbieter (36 Mon.)", "Prozent"),
        ("bieterMedian", "Ø Bieter je Vergabe", "Anzahl"),
        ("kmu", "Zuschläge an KMU", "Prozent"),
        ("preis", "Nur über den Preis entschieden", "Prozent"),
        ("wechsel", "Wechsel bei Nachfolgevergaben", "Prozent"),
    )
)

# ═════════════════════════════════════════════════════════════════════════════════════════
# ⚠ EINE ZEILE JE KENNZAHL UND FLÄCHE, nicht je Kennzahl. „Vergaben pro Jahr" steht beim
# Käufer im Lead-Detail UND als Kachel in der Strategie; das sind zwei Plätze mit womöglich
# verschiedenem Bezug, und der Leser sucht nach Bildschirm, nicht nach Metrik. Was hier NICHT
# stehen darf, ist dieselbe Kennzahl zweimal auf DEMSELBEN Bildschirm — elf solche Zeilen
# sind beim Aufbau entstanden und wieder raus.
#
# ⚠ Und nicht blind entdoppeln: „Vergaben pro Jahr (Anbieter)" ist die Zahl einer FIRMA, nicht
# einer Vergabestelle, und „Rahmenvereinbarung (Name)" ist eine Tabellenspalte, nicht das
# Ja/Nein-Signal aus den Unterlagen. Ein Abgleich über den Namen hätte beide gelöscht.
# ═════════════════════════════════════════════════════════════════════════════════════════
# Das Inventar: alles, was ein Nutzer sonst noch sieht. Gezählt am 2026-09-01 aus dem
# Quelltext, Fläche für Fläche.
# ═════════════════════════════════════════════════════════════════════════════════════════

# ── Lead-Liste ────────────────────────────────────────────────────────────────────────────
# Die Spalten der Trefferliste.
# Quelle: explorerCore.COLS
_LISTE: tuple[Kennzahl, ...] = (
    _k("empfehlung", "Empfehlung", "profil", "Relevanz und Blocker aus matchLead"),
    _k("relevanz", "Relevanz", "profil", "Feld, Region, Volumen gegen euer Profil"),
    _k("passung0Bis100", "Passung 0 bis 100", "profil", "dieselbe Rechnung, feiner aufgelöst"),
    _k("chanceVerdraengbarkeit", "Chance (Verdrängbarkeit)", "markt", "Verdrängbarkeit im Branchenmittel"),
    _k("aufwand", "Aufwand", "markt", "üblicher Aufwand im selben Feld"),
    _k("konkurrenzBieterzahl", "Konkurrenz (Bieterzahl)", "markt", "Ø Bieter je Vergabe im Feld"),
    _k("volumen", "Volumen", "profil", "volMin und volMax"),
    _k("wettbewerbErstmalsAusgeschrieben", "Wettbewerb (erstmals ausgeschrieben)", "keine"),
    _k("amtsinhaber", "Amtsinhaber", "keine"),
    _k("netzwerkWieVieleSuchenPartner", "Netzwerk (wie viele suchen Partner)", "keine"),
)

# ── Lead-Detail ───────────────────────────────────────────────────────────────────────────
# Uebersicht, Anforderungen, Kaeufer, Markt.
# Quelle: api/lead-detail
_LEAD_DETAIL: tuple[Kennzahl, ...] = (
    _k("vergabenImSegment", "Vergaben im Segment", "markt", "Segmentgrösse gegen alle Segmente"),
    _k("chancenScore", "Chancen-Score", "markt", "Perzentil über alle Segmente"),
    _k("chronischErfolgloseBedarfe", "Chronisch erfolglose Bedarfe", "markt", "Anteil im Feld"),
    _k("erfolgloseAusschreibungen", "Erfolglose Ausschreibungen", "markt", "Aufhebungsquote im Feld"),
    _k("nurEinBieter", "Nur ein Bieter", "markt", "Einzelbieter-Quote im Feld"),
    _k("vergabenGesamtKaeufer", "Vergaben gesamt (Käufer)", "keine"),
    _k("vergabenProJahrKaeufer", "Vergaben pro Jahr (Käufer)", "markt", "Median aller Vergabestellen"),
    _k("bekanntmachungBisZuschlag", "Bekanntmachung bis Zuschlag", "markt", "Median der Entscheidungsdauer"),
    _k("typischerAuftragswertMedian", "Typischer Auftragswert (Median)", "profil", "eure Wertspanne"),
    _k("bekanntesVolumen", "Bekanntes Volumen", "keine"),
    _k("vergabenMitNurEinemBieterKaeufer", "Vergaben mit nur einem Bieter (Käufer)", "markt", "Marktüblich in der Branche"),
    _k("bieterJeAusschreibungKaeufer", "Bieter je Ausschreibung (Käufer)", "markt", "Marktüblich in der Branche"),
    _k("verschiedeneGewinnerKaeufer", "Verschiedene Gewinner (Käufer)", "markt", "Konzentration marktüblich"),
    _k("anzahlZuschlagskriterien", "Anzahl Zuschlagskriterien", "markt", "üblich im Feld"),
    _k("ampelEinschaetzungAusDenUnterlagen", "Ampel-Einschätzung aus den Unterlagen", "profil", "eure Nachweise gegen die Anforderungen"),
    _k("bieterChecklisteErfuellungsgrad", "Bieter-Checkliste, Erfüllungsgrad", "profil", "abgehakt gegen gefordert"),
    _k("fristInTagen", "Frist in Tagen", "keine"),
    _k("vertragsende", "Vertragsende", "keine"),
    _k("amtsinhaberSeitJahren", "Amtsinhaber seit Jahren", "markt", "übliche Verweildauer im Feld"),
    _k("amtsinhaberZyklen", "Amtsinhaber-Zyklen", "markt", "übliche Zyklenzahl"),
    _k("erfolgloseVersucheDiesesBedarfs", "Erfolglose Versuche dieses Bedarfs", "markt", "Anteil chronischer Bedarfe im Feld"),
    _k("anzahlLose", "Anzahl Lose", "keine"),
    _k("aufwandstreiberListe", "Aufwandstreiber (Liste)", "keine"),
)

# ── Strategie ─────────────────────────────────────────────────────────────────────────────
# Zehn Bereiche, die dichteste Flaeche des Produkts.
# Quelle: export_strategie.py
_STRATEGIE: tuple[Kennzahl, ...] = (
    _k("auslaufendeVertraege", "Auslaufende Verträge", "vorwert", "Stand der Vorwoche"),
    _k("volumenBelegtPipeline", "Volumen belegt (Pipeline)", "keine"),
    _k("volumenGeschaetzt", "Volumen geschätzt", "keine"),
    _k("ohneWertangabe", "Ohne Wertangabe", "keine"),
    _k("anzahlVertraegeInDerPipeline", "Anzahl Verträge in der Pipeline", "vorwert", "Stand der Vorwoche"),
    _k("rahmenOhneErneutenWettbewerb", "Rahmen ohne erneuten Wettbewerb", "markt", "Anteil marktüblich"),
    _k("groessteEinzelpostenAusschreibung", "Grösste Einzelposten: Ausschreibung", "keine"),
    _k("groessteEinzelpostenVergabestelle", "Grösste Einzelposten: Vergabestelle", "keine"),
    _k("groessteEinzelpostenWert", "Grösste Einzelposten: Wert", "profil", "eure Alleingrenze"),
    _k("groessteEinzelpostenVertragsende", "Grösste Einzelposten: Vertragsende", "keine"),
    _k("offenheitEinstufung", "Offenheit (Einstufung)", "markt", "abgeleitet aus den drei Zeilen darüber"),
    _k("wechselEinstufung", "Wechsel (Einstufung)", "markt", "abgeleitet"),
    _k("derStaerksteAnbieterHaelt", "Der stärkste Anbieter hält", "markt", "Konzentration marktüblich"),
    _k("zuschlaegeJeVergabestelleAnteil", "Zuschläge je Vergabestelle, Anteil", "markt", "Spalte „vs. Markt\" steht schon daneben"),
    _k("vergabenJeCpv36Mon", "Vergaben je CPV (36 Mon.)", "markt", "Feldgrösse gegen alle Felder"),
    _k("trend12MonateFeld", "Trend 12 Monate (Feld)", "vorwert", "Vorjahresfenster"),
    _k("buergschaftsquoteImFeld", "Bürgschaftsquote im Feld", "profil", "euer Rahmen"),
    _k("naeheNachbarfeld", "Nähe (Nachbarfeld)", "keine"),
    _k("gemeinsameAnbieterNachbarfeld", "Gemeinsame Anbieter (Nachbarfeld)", "markt", "Überlappung marktüblich"),
    _k("einstiegsfreundlichFeld", "Einstiegsfreundlich (Feld)", "markt", "abgeleitet aus Bieterzahl und Neuzugängen"),
    _k("bieterImFeldEinstiegsfenster", "Bieter im Feld (Einstiegsfenster)", "markt", "marktüblich"),
    _k("wertEinstiegsfenster", "Wert (Einstiegsfenster)", "profil", "eure Wertspanne"),
    _k("fristEinstiegsfenster", "Frist (Einstiegsfenster)", "keine"),
    _k("belegtGesperrtBindung", "Belegt gesperrt (Bindung)", "markt", "Anteil gesperrten Volumens marktüblich"),
    _k("gelisteteNamentlichBekannt", "Gelistete namentlich bekannt (%)", "keine"),
    _k("gelisteteUnbekannt", "Gelistete unbekannt", "keine"),
    _k("volumenBelegtBindung", "Volumen belegt (Bindung)", "keine"),
    _k("rahmenvereinbarungName", "Rahmenvereinbarung (Name)", "keine"),
    _k("gelistetJaNein", "Gelistet (ja/nein)", "keine"),
    _k("wertRahmen", "Wert (Rahmen)", "profil", "eure Wertspanne"),
    _k("laeuftAusRahmen", "Läuft aus (Rahmen)", "keine"),
    _k("fensterAbNaechsterEinstieg", "Fenster ab (nächster Einstieg)", "vorwert", "ist ein Fenster seit letzter Woche aufgegangen?"),
    _k("werHoltWasZuschlaegeJeAnbieter", "Wer holt was (Zuschläge je Anbieter)", "markt", "Marktanteil"),
    _k("werHaeltWasVerteidigung", "Wer hält was (Verteidigung)", "markt", "marktübliche Verteidigungsquote"),
    _k("fachgebietAnbieter", "Fachgebiet (Anbieter)", "keine"),
    _k("vergabenProJahrAnbieter", "Vergaben pro Jahr (Anbieter)", "markt", "Median der Anbieter im Feld"),
    _k("eigeneZuschlaege36Mon", "Eigene Zuschläge (36 Mon.)", "vorwert", "Vorjahresfenster"),
    _k("eigeneVergabestellenAnzahl", "Eigene Vergabestellen (Anzahl)", "markt", "Streuung marktüblich"),
    _k("regelwerkAusschreibungenDarunter", "Regelwerk: Ausschreibungen darunter", "profil", "euer bevorzugter Rahmen"),
    _k("regelwerkVolumenBelegt", "Regelwerk: Volumen belegt", "profil", "eure Wertspanne"),
    _k("nachweisGefordertInNVergaben", "Nachweis: gefordert in n Vergaben", "profil", "habt ihr ihn?"),
    _k("vergabenIn36MonatenBereichskopf", "Vergaben in 36 Monaten (Bereichskopf)", "markt", "Feldgrösse"),
    _k("verschiedeneAnbieterBereichskopf", "Verschiedene Anbieter (Bereichskopf)", "markt", "Wettbewerbsdichte marktüblich"),
    _k("duennGemessenAusNVergaben", "Dünn, gemessen aus n Vergaben", "keine"),
)

# ── Regionen ──────────────────────────────────────────────────────────────────────────────
# Geografische Verteilung.
# Quelle: export_strategie.py
_REGIONEN: tuple[Kennzahl, ...] = (
    _k("medianDerKreise", "Median der Kreise", "markt", "steht schon als Bezug daneben"),
    _k("vergabenJeKreis", "Vergaben je Kreis", "markt", "Median der Kreise"),
    _k("vergabenInEurenRegionen", "Vergaben in euren Regionen", "profil", "regions aus dem Profil"),
    _k("vergabenAusserhalbEurerRegionen", "Vergaben ausserhalb eurer Regionen", "profil", "regions"),
    _k("volumenJeKreis", "Volumen je Kreis", "markt", "Median der Kreise"),
    _k("kreiseOhneAmtlichenKontext", "Kreise ohne amtlichen Kontext", "keine"),
    _k("veraenderungJeKreis", "Veränderung je Kreis", "vorwert", "Vorjahresfenster"),
    _k("kreisnameUndZuordnung", "Kreisname und Zuordnung", "keine"),
)

# ── Vergabeblick (Kaeufersicht) ───────────────────────────────────────────────────────────
# ⚠ Die einzige Flaeche mit einem normativen Ziel: mehr Bieter ist dort besser.
# Nur hier ist eine Ampelfarbe berechtigt.
# Quelle: export_strategie.py
_VERGABEBLICK: tuple[Kennzahl, ...] = (
    _k("vergaben36Mon", "Vergaben (36 Mon.)", "markt", "„Marktüblich\" steht daneben"),
    _k("kmuAnteil", "KMU-Anteil", "markt", "„Marktüblich in Ihrer Branche\""),
    _k("reinUeberPreis", "Rein über Preis", "markt", "„Marktüblich\""),
    _k("wechselquote", "Wechselquote", "markt", "„Marktüblich\""),
    _k("neuzugaengeProJahr", "Neuzugänge pro Jahr", "markt", "„Marktüblich\""),
    _k("basisAusNLosenDuennBeiNFaellen", "Basis: aus n Losen, dünn bei n Fällen", "keine"),
)

# ── Firmenprofil ──────────────────────────────────────────────────────────────────────────
# Bilanz einer Firma.
# Quelle: export_firma_profiles.py
_FIRMENPROFIL: tuple[Kennzahl, ...] = (
    _k("zuschlaege36Monate", "Zuschläge 36 Monate", "markt", "Median der Anbieter im Feld"),
    _k("volumenGesamt", "Volumen gesamt", "keine"),
    _k("medianAuftragswert", "Median-Auftragswert", "markt", "Median im Feld"),
    _k("verteidigungsquote", "Verteidigungsquote", "markt", "„Markt n %\" steht daneben"),
    _k("laeuftAusIn18Monaten", "Läuft aus in ≤ 18 Monaten", "vorwert", "Stand der Vorwoche"),
)

# ── Treffergueete ─────────────────────────────────────────────────────────────────────────
# Wie gut kennt uns das Profil, und was wuerde eine Aenderung bringen.
# Quelle: api/trefferguete
_TREFFERGUETE: tuple[Kennzahl, ...] = (
    _k("trefferquote", "Trefferquote", "vorwert", "eigener Vorwert"),
    _k("volumenGewonnen", "Volumen gewonnen", "vorwert", "eigener Vorwert"),
    _k("wasEureListeJetztAendernWuerde", "Was eure Liste jetzt ändern würde", "profil", "Wirkung einer Profiländerung"),
    _k("profilabdeckung", "Profilabdeckung", "profil", "60 % Mindestabdeckung"),
    _k("wasWirNichtVerbessernKoennen4Gruende", "Was wir nicht verbessern können (4 Gründe)", "keine"),
)

# ── Marktpuls ─────────────────────────────────────────────────────────────────────────────
# Saison und Jahresverlauf.
# Quelle: export_marktpuls.py
_MARKTPULS: tuple[Kennzahl, ...] = (
    _k("laufendeAusschreibungen", "Laufende Ausschreibungen", "vorwert", "Vorwoche"),
    _k("zuschlaegeLetzteNTage", "Zuschläge (letzte n Tage)", "vorwert", "Vorperiode"),
    _k("aufhebungenLetzteNTage", "Aufhebungen (letzte n Tage)", "markt", "Aufhebungsquote marktüblich"),
    _k("frischAberOhneVeroeffentlichteFrist", "Frisch, aber ohne veröffentlichte Frist", "keine"),
    _k("saisonkurve", "Saisonkurve", "vorwert", "Vorjahre 2004 bis 2025"),
    _k("jahresverlauf", "Jahresverlauf", "vorwert", "Vorjahre"),
)

# ── Cockpit ───────────────────────────────────────────────────────────────────────────────
# Merkliste, Pipeline, Ergebnisse.
# Quelle: lokal (Nutzerzustand)
_COCKPIT: tuple[Kennzahl, ...] = (
    _k("merklisteAnzahl", "Merkliste (Anzahl)", "keine"),
    _k("pipelineJeStufe", "Pipeline je Stufe", "vorwert", "Vorwoche"),
    _k("ergebnisseGewonnenVerloren", "Ergebnisse (gewonnen/verloren)", "vorwert", "Vorperiode"),
    _k("abgeleitetGegenBestaetigt", "Abgeleitet gegen bestätigt", "keine"),
)

# ── Eignungs-Check (oeffentlich) ──────────────────────────────────────────────────────────
# Ohne Konto sichtbar. ⚠ Was hier steht, liest ein Fremder als Erstes von uns.
# Quelle: export_landing.py
_EIGNUNGSCHECK: tuple[Kennzahl, ...] = (
    _k("nVonMVerfahrenHaettenGepasst", "n von m Verfahren hätten gepasst", "markt", "m ist die Bezugsgrösse"),
    _k("davonHeuteNochOffen", "Davon heute noch offen", "keine"),
    _k("anforderungBelegtInN", "Anforderung belegt in n %", "markt", "Anteil über die ausgewerteten Unterlagen"),
    _k("wertverteilungInStufen", "Wertverteilung in Stufen", "markt", "Verteilung über den Zuschnitt"),
    _k("grundlageNAusgewerteteUnterlagen", "Grundlage: n ausgewertete Unterlagen", "keine"),
)


# ── Aus der Übergabe „einzigartige Kennzahlen + Aktivierung" (01.09.) ────────────────────
# Kennzahlen, die nur entstehen, weil wir BEIDE Seiten haben: die öffentliche Bekanntmachung
# und die aus den Unterlagen gewonnenen Werte. Wer nur eine hat, kann sie nicht rechnen.
#
# ⚠ SIE STEHEN HIER, OBWOHL DIE MEISTEN NOCH NICHT ANGEZEIGT WERDEN. Das ist der Zweck: eine
# Kennzahl, die niemand fuehrt, wird beim naechsten Zaehlen wieder als Fund entdeckt. Der
# Zustand steht im Kommentar, nicht in einem Feld — ein Feld „fertig ja/nein" wuerde altern,
# ohne dass es jemand merkt.
#
# ⚠ ZEHN VON FUENFZEHN HABEN AM 01.09. KEINE DATENGRUNDLAGE. `doc_checklist`,
# `doc_analysis`, `doc_verworfen` und `document_duplicates` existieren als Dateien NICHT;
# sie sind seit Commit 07bbd26 im Tageslauf verdrahtet und entstehen erstmals in der Nacht
# auf den 02.09. Die Zahlen im Papier stammen aus einer Probefassung im Sitzungs-Scratch.
# ⚠ ZWEI DER FUENFZEHN STEHEN NICHT HIER, weil sie schon LAUFEN. Die „Vertragsstrafe
# beziffert" ist `penaltyPct` (seit 01.09. verdrahtet), und die „Zuschlagsgewichtung aus den
# Unterlagen" — im Papier als staerkster Neuzugang gefuehrt — ist `award_weights` und rendert
# seit jeher mit Balken. Ihnen fehlt keine Anzeige, ihnen fehlt ABDECKUNG: 205 von 1.829
# offenen Vorgaengen mit mehreren Zuschlagskriterien. Sie doppelt einzutragen haette den
# Eindruck erzeugt, da sei noch etwas zu bauen.
_UEBERGABE: tuple[Kennzahl, ...] = (
    _k("fingerabdruckVergabestelle", "Fingerabdruck der Vergabestelle", "markt",
       "wie oft die Stelle etwas verlangt gegen marktweit"),
    _k("formularaufwand", "Formularaufwand", "markt", "Median 22 Pflichtfelder"),
    _k("mengengeruest", "Mengengerüst", "keine"),
    _k("bezifferteSchwellen", "Bezifferte Schwellen als Vergleichsgruppe", "markt",
       "Median und Quartil derselben Anforderungsart"),
    _k("standardtextAnteil", "Standardtext-Anteil", "markt",
       "Median 10 %, oberes Viertel 27 %"),
    _k("fristwiderspruch", "Widerspruch bei der Angebotsfrist", "keine"),
    _k("verlaesslichkeitAuswertung", "Verlässlichkeit je Auswertung", "keine"),
    _k("anforderungsDrift", "Anforderungs-Drift", "vorwert",
       "dieselbe Vergabestelle in der vorigen Runde"),
    _k("wirkungHuerdenBieterzahl", "Wirkung von Hürden auf die Bieterzahl", "markt",
       "Bieterzahl vergleichbarer Vergaben ohne diese Hürde"),
    _k("aufwandJeEuro", "Aufwand je Euro Auftragswert", "markt",
       "Median 0,15 Anforderungen je 1.000 EUR"),
)


# ── Was die Aktivierung mitbringt (2026-09-02) ───────────────────────────────────────────
# ⚠ EINE AKTIVIERUNG IST KEINE KENNZAHL. „Habt ihr mitgeboten?" ist eine Frage, „Stelle
# beobachten" ein Schalter, die Bitten um Unterlagen sind Text. Sie gehoeren nicht hierher.
#
# Was hierher gehoert, sind die ZAHLEN, die dabei auf dem Bildschirm landen. Sie sind beim
# Bauen entstanden und waeren beim naechsten Zaehlen wieder als Fund aufgetaucht — genau der
# Zustand, gegen den dieses Verzeichnis angelegt wurde.
#
# ⚠ Die fuenf Luecken-Hinweise vergleichen alle gegen ein PROFILFELD, keiner gegen den Markt.
# Das ist kein Zufall: eine Luecke ist per Definition der Abstand zwischen dem, was ein
# Vorgang verlangt, und dem, was ihr hinterlegt habt.
_AKTIVIERUNG: tuple[Kennzahl, ...] = (
    _k("luecke_buergschaft", "Lücke: Bürgschaftsrahmen fehlt", "profil",
       "euer Bürgschaftsrahmen, falls hinterlegt"),
    _k("luecke_alleingrenze", "Lücke: über eurer Alleingrenze", "profil", "`maxAlleine`"),
    _k("luecke_region", "Lücke: außerhalb eurer Regionen", "profil", "`regions`"),
    _k("luecke_wertspanne", "Lücke: außerhalb eurer Wertspanne", "profil", "`volMin`/`volMax`"),
    _k("luecke_ortstermin", "Lücke: Pflicht-Ortstermin außerhalb des Gebiets", "profil",
       "`regions` gegen den Ortstermin aus den Unterlagen"),
    # Wie viele erwartete Unterlagen bei DIESEM Vorgang fehlen. Kein Marktwert: dass anderswo
    # dieselbe Art fehlt, aendert nichts daran, dass sie hier fehlt.
    _k("fehlende_unterlagen", "Offen: erwartete Unterlagen fehlen", "keine"),
    _k("posteingang_ungelesen", "Ungelesene Hinweise", "keine"),
)

# ── Aufwand gegen Zeitfenster (Kennzahl 1, gebaut am 2026-09-02) ─────────────────────────
# Sie stand bis dahin unter `geplant`. Wer eine Kennzahl baut und den Eintrag stehen laesst,
# schickt die naechste Sitzung auf die Suche nach Arbeit, die es nicht mehr gibt — dieselbe
# Alterung, gegen die dieses Verzeichnis angelegt wurde. Ein Waechter haelt es jetzt fest.
#
# ⚠ SIE BRAUCHT BEIDE SEITEN und ist deshalb eine der wenigen, die sonst niemand rechnen
# kann: die Bekanntmachung sagt wann veroeffentlicht und wann Frist, die Unterlagen sagen wie
# viel Arbeit.
#
# ⚠ UND IHRE BEZUGSGROESSE IST DAS REGELWERK, NICHT DER MARKT INSGESAMT. Der Median liegt bei
# 34 Tagen in jeder Aufwandsklasse (Korrelation 0,08) — das sah nach „der Markt gibt dieselbe
# Zeit, egal wie viel Arbeit drinsteckt" aus und ist es nicht: 68 % aller Fenster liegen
# zwischen 28 und 40 Tagen, weil dort die gesetzlichen Mindestfristen liegen. Unterschwellig
# gelten andere: unter den Vorgaengen mit hoechstens 28 Tagen sind 21 % UVgO, im Rest 4 %.
# Ein Vergleichswert, der zwei Rechtsgrundlagen mischt, ist keiner.
# ── Anforderungsprofil (Kennzahl 2, gebaut am 2026-09-02) ────────────────────────────────
# ⚠ Die Uebergabe nennt sie „Strenge als Perzentil je Bereich". Das Wort stimmt fuer die
# Haelfte der Bereiche nicht: `formalitaet` sind ausfuellbare Formulare (Aufwand),
# `leistung` ist Umfang. Huerden sind nur `eignung` und `ausschluss`. Der Eintrag heisst
# deshalb anders als im Papier — und die Anzeige waehlt ihr Wort nach der Art des Bereichs.
_ANFORDERUNGSPROFIL: tuple[Kennzahl, ...] = tuple(
    Kennzahl(f"profil_{b}", lab, "markt",
             "Median und oberstes Zehntel desselben Bereichs, je Land",
             # ⚠ KEIN `spalte`. Der Bereichsname ist ein Spalten-WERT (`doc_checklist.bereich`),
             # kein Spaltenname; das Feld traegt den exakten Namen der Quellspalte, an dem
             # Export, API-Typ und Renderer haengen. Ihn hier zu missbrauchen hiesse, den
             # einen Vertrag aufzuweichen, der das Verzeichnis pruefbar macht — der Waechter
             # hat es sofort gemeldet.
             "lead-detail", "export_anforderungsprofil.py", "", "Anzahl")
    for b, lab in (
        ("eignung", "Anforderungsprofil: Eignungsnachweise"),
        ("ausschluss", "Anforderungsprofil: Ausschlusskriterien"),
        ("formalitaet", "Anforderungsprofil: Formalitäten"),
        ("termin", "Anforderungsprofil: Termine und Fristen"),
        ("leistung", "Anforderungsprofil: Leistungsbeschreibung"),
        ("vertrag", "Anforderungsprofil: Vertragsbedingungen"),
        ("zuschlag", "Anforderungsprofil: Zuschlagskriterien"),
    )
)

_ZEITFENSTER: tuple[Kennzahl, ...] = (
    Kennzahl("aufwandGegenZeitfenster", "Aufwand gegen Zeitfenster", "markt",
             "Median desselben Regelwerks (VgV / VOB/A / UVgO), je Land",
             "lead-detail", "export_fenster.py", "", "Tage"),
)


_FLAECHEN = (
    (_LISTE, "liste", "explorerCore.COLS"),
    (_LEAD_DETAIL, "lead-detail", "api/lead-detail"),
    (_STRATEGIE, "strategie", "export_strategie.py"),
    (_REGIONEN, "regionen", "export_strategie.py"),
    (_VERGABEBLICK, "vergabeblick", "export_strategie.py"),
    (_FIRMENPROFIL, "firmenprofil", "export_firma_profiles.py"),
    (_TREFFERGUETE, "trefferguete", "api/trefferguete"),
    (_MARKTPULS, "marktpuls", "export_marktpuls.py"),
    (_COCKPIT, "cockpit", "lokal (Nutzerzustand)"),
    (_EIGNUNGSCHECK, "eignungscheck", "export_landing.py"),
    # ⚠ Fläche „geplant": noch nirgends angezeigt. Sie steht bewusst in derselben Liste,
    # damit die Zählung ehrlich bleibt und niemand sie zweimal entdeckt.
    (_UEBERGABE, "geplant", "docs/uebergabe-kennzahlen-aktivierung.md"),
    (_AKTIVIERUNG, "aktivierung", "DetailPanel/explorerCore/api-alerts"),
)

INVENTAR: tuple[Kennzahl, ...] = tuple(
    k for gruppe, flaeche, quelle in _FLAECHEN for k in _mit(gruppe, flaeche, quelle)
)

ALLE: tuple[Kennzahl, ...] = (DOC_SIGNALE + VERGABESTELLEN + _ZEITFENSTER
                              + _ANFORDERUNGSPROFIL + INVENTAR)


def nach_flaeche() -> dict[str, tuple[Kennzahl, ...]]:
    raus: dict[str, list[Kennzahl]] = {}
    for k in ALLE:
        raus.setdefault(k.flaeche, []).append(k)
    return {f: tuple(v) for f, v in raus.items()}


def nach_bezug() -> dict[str, tuple[Kennzahl, ...]]:
    raus: dict[str, list[Kennzahl]] = {}
    for k in ALLE:
        raus.setdefault(k.bezug, []).append(k)
    return {b: tuple(v) for b, v in raus.items()}


def spalten(gruppe: tuple[Kennzahl, ...]) -> list[str]:
    """Quellspalten einer Gruppe — damit ein Export sie nicht von Hand aufzählen muss.

    ⚠ Nur sinnvoll für Gruppen mit exakten Spalten (DOC_SIGNALE, VERGABESTELLEN). Eine
    Kennzahl ohne `spalte` fällt heraus, statt einen erfundenen Namen zu liefern.
    """
    return [k.spalte for k in gruppe if k.spalte]
