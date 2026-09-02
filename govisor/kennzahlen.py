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
    # ⚠ Die Bezugsgroesse war eine unerfuellte Zusage: „markt" stand hier, angezeigt wurde
    # bis zum 02.09. nur die nackte Zahl. Verglichen wird jetzt je AUSPRAEGUNG (Tagessatz
    # gegen Obergrenze), nicht „im Feld" — die Streuung zwischen den beiden ist 25-fach und
    # damit groesser als jeder Branchenunterschied.
    _s("penaltyPct", "penalty_pct", "Vertragsstrafe", "Prozent",
       "markt", "Median derselben Ausprägung (Tagessatz oder Obergrenze)"),
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
#
# ⚠ NACHTRAG 02.09., UND ER KORRIGIERT DEN ABSATZ DARUEBER. „Laeuft" stimmte fuer die Anzeige
# der ZAHL, nicht fuer die Kennzahl. `penaltyPct` stand mit Bezug „markt" im Verzeichnis und
# rendert `${s.penaltyPct} %` — ohne jeden Vergleichswert. Schlimmer: die Zahl war zweideutig.
# Vertragsstrafen gibt es als TAGESSATZ und als OBERGRENZE, im Verhaeltnis 1:25 (0,20 % je
# Werktag gegen 5 % insgesamt), und 67 % der 4.114 Werte in `penalty_pct` lassen sich ohne
# Beleg keiner der beiden zuordnen. „Vertragsstrafe 0,3 %" konnte also eine milde Obergrenze
# oder ein harter Tagessatz sein, und die Anzeige sagte nicht welches. Beides ist jetzt
# ergaenzt (s. `schwelleVergleich`); die Trennung liefert `export_schwellen.py` als Regel mit.
_UEBERGABE: tuple[Kennzahl, ...] = (
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
# ── Umfang der Formulare (Kennzahl 4, gebaut am 2026-09-02) ─────────────────────────────
# Sie stand als `formularaufwand` unter `geplant`, mit der Bezugsgroesse „markt, Median 22
# Pflichtfelder". Nachgemessen haelt davon nichts, und die drei Gruende sind drei verschiedene
# Fehlerarten — es lohnt sich, sie auseinanderzuhalten:
#
#   1. FALSCHE GROESSE. „Pflicht" ist ein Kennzeichen im PDF, das kaum jemand setzt: 93 % aller
#      31.799 Formulare tragen null Pflichtfelder, auch 92 % derjenigen mit ueber 50 Feldern.
#      Ein 95-Felder-Vergabeformular ohne ein einziges Pflichtfeld gibt es nicht. Die Zahl
#      misst die Formularsoftware.
#   2. FALSCHE EBENE. Die „22" stimmt sogar (gemessen 23), aber je FORMULAR, nicht je Vorgang.
#   3. ⚠ FALSCHER MESSGEGENSTAND, und das ist die teure. Summen je Vorgang wachsen mit der
#      Zahl gelesener Dateien: 2 → 7 → 16 Formulare, 60 → 327 → 606 Felder. Kein Plateau bei
#      irgendeiner Lesetiefe, und auch keins in den 165 Vorgaengen, deren Unterlagen
#      vollstaendig aus EINEM ZIP kamen. Wer das anzeigt, zeigt unsere Abrufquote.
#
# ⚠ DESHALB BEZUG `keine`, OBWOHL EINE SCHWELLE DRINSTECKT. Die 400 Felder stammen aus der
# Marktverteilung (oberste 12 %), aber ein laufender Marktvergleich waere falsch: der
# marktweite Wert stammt aus derselben Untererfassung wie der eigene, und dagegen verglichen
# saehe jeder tief gelesene Vorgang extremer aus als er ist. Die Kennzahl behauptet nur
# Anwesenheit und sagt nie „wenig Aufwand".
# ── ⚠ KORREKTUR ZU DEN DREI BLOCKERN (2026-09-02, nach Nachfrage) ───────────────────────
# Bei `anforderungsDrift`, `wirkungHuerdenBieterzahl` und `aufwandJeEuro` steht unten dreimal
# „was es braeuchte: Aufbewahrung von Dokumenten ueber den Zuschlag hinaus". DAS IST FALSCH,
# und der Irrtum ist lehrreich: aus „die Bestaende ueberschneiden sich nicht" wurde
# stillschweigend „wir werfen etwas weg". Nachgesehen:
#
#   1. DAS MAPPING GIBT ES LAENGST. `award_tender_link` verbindet Zuschlags- und
#      Ausschreibungsbekanntmachung ueber die Veroeffentlichungsnummer (`method =
#      'ref_publication'`), 373.190 Zeilen — ein amtlicher Verweis, keine Schaetzung. Die
#      Dokumente haengen ohnehin an derselben `notice_id`.
#   2. NIEMAND LOESCHT. `web/data/doc-analysis/` waechst (8.104 Dateien = 8.104 Zeilen in
#      `doc_analysis`); kein Skript raeumt dort auf. Die Auszuege bleiben also erhalten.
#   3. ES IST NUR ZU FRUEH. Der Dokumentbestand ist zwei Wochen alt (Auswertungen vom 22.08.
#      bis 02.09.), die Fristen der erfassten Vorgaenge beginnen am 02.09., und zwischen
#      Ausschreibung und Zuschlag liegen im Median 114 Tage (p75 167, p90 273).
#
#      → erste Ueberschneidungen um Januar 2027, p75 Maerz, p90 Juni 2027.
#
# ⚠ DIE EINZIGE ECHTE GEFAHR ist, dass jemand `web/data/doc-analysis/` aufraeumt, weil es
# „alte, abgelaufene Vorgaenge" enthaelt. Genau die sind der Rohstoff. Der Auszug kostet
# 19,6 MB (doc_checklist 18,6 + doc_analysis 1,0) gegen 239 GB Original-PDFs — die PDFs darf
# man wegwerfen, die Auszuege nicht.

# ── ⚠ NEGATIVBEFUND: Aufwand je Euro Auftragswert (geprueft am 2026-09-02) ──────────────
# `aufwandJeEuro` bleibt unter `geplant`, und dieser Fall ist der unangenehmste der drei: die
# Kennzahl BESTEHT JEDE FORMALE PRUEFUNG und sagt trotzdem nichts.
#
#   rechenbar     3.795 Vorgaenge mit Unterlagen und Wert
#   reproduziert  Median 0,153 Anforderungen je 1.000 EUR (das Papier nennt 0,15)
#   stabil        Driftpruefung 0,136 → 0,156 → 0,174 → 0,169 = Faktor 1,28, unter der Schwelle
#
# ⚠ UND DER NENNER IST NIE GELD, DAS JEMAND VEROEFFENTLICHT HAT:
#
#     Vorgaenge mit Unterlagen                              7.968
#     davon mit ECHTEM Wert (`value_source = 'actual'`)          0
#     davon mit Schaetzung                                   3.795
#     verschiedene Werte darin                                 447
#     Schaetzwerte, die die HAELFTE aller Vorgaenge abdecken     14
#
# Dieselbe Disjunktheit wie bei `anforderungsDrift` und `wirkungHuerdenBieterzahl`: echte Werte
# stehen in Zuschlagsbekanntmachungen, Unterlagen gibt es nur bei offenen Verfahren. Der
# Median-Schaetzwert ist in drei von vier Lesetiefe-Klassen DIESELBE ZAHL (379.674 EUR).
#
# Die Kennzahl waere also unsere Extraktion geteilt durch unsere Schaetzung. Beide Haelften
# tragen etwa gleich viel (Korrelation zum Verhaeltnis 0,66 zur Anforderungszahl, -0,69 zum
# Schaetzwert; die Haelften selbst sind mit 0,10 unabhaengig). Was der Nenner an Streuung
# beisteuert, ist die Segmentzuordnung unseres Schaetzers — fuer die halbe Population eine
# 14-stufige Leiter.
#
# ⚠ UND DIE NUETZLICHE HAELFTE GIBT ES SCHON: Anforderungen im Verhaeltnis zum Ueblichen ist
# `_ANFORDERUNGSPROFIL` (Kennzahl 2), je Bereich, gegen den Markt, ohne geldfoermige
# Scheingenauigkeit. Die Streuung des Verhaeltnisses (Faktor 2,8 zwischen den Quartilen) ist
# kaum groesser als die der reinen Anforderungszahl (2,0).
#
# WAS ES BRAEUCHTE: echte Auftragswerte an Vorgaengen, deren Unterlagen wir gelesen haben.
# „80 Anforderungen fuer einen Auftrag ueber 40.000 Euro" waere eine starke Aussage. ⚠ Und das
# kommt VON SELBST — s. „Korrektur zu den drei Blockern" oben: das Mapping gibt es, geloescht
# wird nichts, es ist nur zu frueh. Erste Ueberschneidungen um Januar 2027.

# ── ⚠ NEGATIVBEFUND: Wirkung von Huerden auf die Bieterzahl (geprueft am 2026-09-02) ────
# Der Eintrag `wirkungHuerdenBieterzahl` bleibt unter `geplant`, aber NICHT, weil noch niemand
# hingesehen haette. Es ist nachgemessen, und der Effekt ist nicht da.
#
# Die Datenlage ist besser als beim Nachbarn (Kennzahl 12 des Papiers): 1.114 offene Vorgaenge
# haben Unterlagen UND eine Bieterzahl ueber `lead_predecessor`. ⚠ Aber die Bieterzahl gehoert
# zum VORGAENGER, die Anforderungen zum aktuellen Verfahren — die Verbindung ist der Kaeufer,
# nicht der Vorgang.
#
#   1. Ueber die HUERDENZAHL: kein Signal. Median 4,0 / 3,0 / 4,0 / 4,0 bei 0 / 1-2 / 3-5 / 6+
#      Huerden, Einzelbieteranteil 19 / 16 / 18 / 21 %.
#   2. Je ANFORDERUNGSART sah es zuerst nach etwas aus — und war der Lesetiefe-Effekt eine
#      Ebene hoeher: die scheinbar wirksamen Arten kommen in 70 bis 90 % der Vorgaenge vor, die
#      „ohne"-Gruppe sind duenn gelesene Faelle. Die echten Huerden (Mindestumsatz,
#      Berufshaftpflicht, Zertifikat) standen bei 4,0 gegen 4,0.
#   3. ⚠ INNERHALB EINER WERTKLASSE erschien der Effekt dann doch — und die REPLIKATION hat ihn
#      zerlegt. In 250k-1M sank die Bieterzahl bei vier Huerden (Referenz-Mindestwert 2,0 gegen
#      4,0), in <250k STIEG sie bei allen acht, in >1M ebenso. Keine einzige Huerde zeigt in
#      allen drei Klassen dieselbe Richtung.
#
# ⚠ DER GRUND, warum die kleine Klasse alles umdreht: 1.486 ihrer 1.694 Vorgaenge haben weniger
# als fuenf extrahierte Anforderungen, und deren Median-Bieterzahl ist 1,0 (der Rest: 4,0). Es
# ist immer dieselbe Menge kaum gelesener Vorgaenge, die als „ohne Huerde" gilt.
#
# Der gemeinsame Treiber ist die GROESSE: die Bieterzahl steigt mit der Lesetiefe (3 → 4 → 5 → 5)
# und mit dem Auftragswert (3 → 4 → 5) in derselben Form. Grosse Vergaben haben mehr Dokumente
# UND mehr Bieter.
#
# ⚠ Die Bieterzahl selbst ist NICHT das Problem: 1/2/3/4/5 mit natuerlichem Abfall, die 999
# kommt genau einmal vor. Der Befund steht auf sauberen Daten.
#
# WAS ES BRAUCHTE: Bieterzahlen am SELBEN Vorgang, dessen Unterlagen wir gelesen haben. ⚠ Auch
# das kommt von selbst — s. „Korrektur zu den drei Blockern": es ist nur zu frueh, nicht
# unmoeglich. Erste Ueberschneidungen um Januar 2027.

# ── Aenderungen an den Vergabeunterlagen (gebaut am 2026-09-02) ─────────────────────────
# ⚠ SIE IST NICHT DIE „ANFORDERUNGS-DRIFT", und die bleibt deshalb unter `geplant`. Das Papier
# meint dort „dieselbe Stelle, zwei Runden: verschaerft?" — und das ist mit den heutigen Daten
# NICHT RECHENBAR, strukturell:
#
#     contract_succession × doc_checklist  =  0 Paare
#     Nachfolger mit Unterlagen: 0 · Vorgaenger mit Unterlagen: 0
#
# Unterlagen existieren nur waehrend laufender Angebotsfrist, ein Vorgaenger ist per Definition
# abgeschlossen. ⚠ Die Bestaende sind HEUTE disjunkt, aber nicht dauerhaft: s. „Korrektur zu den
# drei Blockern" oben. Das Mapping gibt es, geloescht wird nichts, der Bestand ist nur zwei
# Wochen alt. Erste Ueberschneidungen um Januar 2027.
#
# Gebaut ist stattdessen die Drift INNERHALB des laufenden Verfahrens: 209 Vorgaenge tragen
# mehrere Fassungen, 93 davon noch offen, und alle 93 haben im letzten Schritt eine Aenderung
# (Median 3 Dateien).
#
# ⚠ DIE FASSUNG STECKT AUCH IM ZIP-NAMEN. Der Pfad lautet
# `Z42-2025-0209_Version 1.zip::Anlage 510-...`; wer nur das Verzeichnis normalisiert, haelt
# jede Datei der neuen Fassung fuer neu — gemessen „56 neu, 54 weg", von denen 47 byte-gleich
# waren. Der dritte Namensartefakt an einem Tag, nach den Lastgaengen und den Katalog-Staenden.
_UNTERLAGENSTAND: tuple[Kennzahl, ...] = (
    Kennzahl("unterlagenAenderung", "Änderungen an den Vergabeunterlagen", "vorwert",
             "die vorige Fassung derselben Unterlagen",
             "lead-detail", "export_unterlagenstand.py", "file", "Dateien"),
)

# ── Bieterfragen und Antworten (gebaut am 2026-09-02) ───────────────────────────────────
# ⚠ SIE STEHT IM PAPIER ALS „EXISTIEREN NICHT UND SIND NICHT ABGREIFBAR" — und zwar unter den
# Aktivierungs-Auslоesern, mit dem Zusatz „staerkstes Ziel ueberhaupt". Die zitierte
# Machbarkeitsstudie (`docs/bieterfragen-feasibility.md`, 27.07.) ist nicht falsch, sondern
# UEBERHOLT: sie durchsuchte die eForms-ATTRIBUTE der Bekanntmachungen (475,3 Mio. Zeilen) und
# fand dort zu Recht nichts. Die Q&A stecken in den UNTERLAGEN.
#
#     Wer eine Machbarkeitsstudie zitiert, prueft, WELCHE Quelle sie untersucht hat.
#
# Gemessen: 257 Vorgaenge mit Fragerunde, 172 mit lesbarem Text, 1.336 verschiedene
# Abschnitte, 71 Vorgaenge noch offen.
#
# ⚠ ABSCHNITTE, KEINE FRAGE-ANTWORT-PAARE. Die Marke („Frage 3:", „Zu Frage 3:") trennt, sie
# ordnet nicht — nur 35 % der Abschnitte enthalten ein Fragezeichen. Eine Tabelle mit den
# Spalten „Frage" und „Antwort" behauptete eine Zuordnung, die die Daten nicht hergeben.
#
# ⚠ ENTDUBLIERT WIRD UEBER DEN TEXT, nicht ueber den Dateinamen: derselbe Katalog liegt als
# Stand 10.08., 13.08. und 20.08. im Paket (gemessen 264 Marken statt 66).
_BIETERFRAGEN: tuple[Kennzahl, ...] = (
    Kennzahl("bieterfragen", "Bieterfragen und Antworten", "keine", "",
             "lead-detail", "export_bieterfragen.py", "n_fragen", "Abschnitte"),
)

# ── Verlaesslichkeit je Auswertung (Kennzahl 10, gebaut am 2026-09-02) ──────────────────
# Die einzige der Reihe, die nicht die Vergabe misst, sondern UNS. Jede Aussage des Modells
# muss sich mit einem Zitat belegen lassen; was das nicht schafft, wird verworfen.
#
# ⚠ SIE BRAUCHT KEINEN EXPORT. `rejected_items` liegt in `lbAnalyse`, die Zahl der behaltenen
# Punkte auch — die Quote entsteht im Renderer. Was fehlte, war nicht die Zahl (sie stand als
# nackter Halbsatz im Haftungshinweis), sondern ihre Bedeutung.
#
# ⚠ EIN HOHER ANTEIL HEISST LUECKENHAFT, NICHT FALSCH. Angezeigt wird nur, was die
# Belegpruefung bestanden hat. Gemessen ueber 8.104 Auswertungen: ab 50 % Verwurf fallen die
# behaltenen Punkte von 59 auf 20, die fehlenden Doktypen steigen von 1 auf 2.
# Verteilung: Median 8 %, p75 17 %, p90 30 %, ueber 50 % nur 2,4 %.
#
# ⚠ FAST ALLES SIND BELEGFEHLER: 3.967 von 4.006 aufgeschluesselten Verwuerfen (99 %)
# scheiterten an der Zitatpruefung, 39 am Schema, 0 am Typ. ⚠ Die Aufschluesselung
# (`rej_schema`/`rej_typ`/`rej_beleg`) gibt es allerdings erst seit dem 02.09. — 916 von 8.104
# Auswertungen. Wer sie auswertet, misst den neuen Bestand, nicht den ganzen.
#
# ⚠ ABSICHTLICH NICHT NACH MODELL GERAHMT, obwohl die Quote 3,2-fach spreizt (gpt-5.6-luna 4 %,
# gemini-2.5-flash 8 %, Llama-3.3-70B 11 %). Das ist der Punkt, an dem die sonst richtige Regel
# „vergleiche im richtigen Rahmen" KIPPT: bei Kennzahlen ueber die Vergabe nimmt ein Rahmen
# fremde Streuung heraus, hier waere er eine Entschuldigung fuer unsere eigene Werkzeugwahl.
# Eine duenne Auswertung ist duenn, egal welches Modell sie erzeugt hat.
#
# ⚠ BEZUG `keine` MIT SCHWELLE, kein angezeigter Vergleichswert. „Ueblich sind 8 %" waere eine
# Aussage ueber unseren Bestand, die den Nutzer nichts angeht — er will wissen, ob er hier
# selbst nachlesen muss. Die Schwelle (30 %, oberstes Zehntel) haelt ein Test gegen den echten
# Bestand nach, damit sie nicht still altert.
_VERLAESSLICHKEIT: tuple[Kennzahl, ...] = (
    Kennzahl("verlaesslichkeitAuswertung", "Verlässlichkeit je Auswertung", "keine", "",
             "lead-detail", "explorerCore (aus lbAnalyse)", "rejected_items", "Anteil"),
)

# ── Widerspruch bei der Angebotsfrist (Kennzahl 9, gebaut am 2026-09-02) ────────────────
# Die einzige der Reihe, bei der ein Fehlalarm eine Angebotsabgabe kosten kann. Gemessen an
# allen Vorgaengen mit beiden Seiten (1.958): 94,5 % stimmen ueberein, 4,1 % nennen in den
# Unterlagen eine FRUEHERE Frist, 1,4 % eine SPAETERE — die Uebergabe nennt 4,2 % und 1,6 %.
#
# ⚠ DREI FILTER, ALLE AN BELEGEN GEPRUEFT: (1) nur was der Beleg eindeutig als Angebotsfrist
# ausweist — `req_type='frist'` mischt Binde-, Zuschlags-, Ausfuehrungs- und Lieferfristen;
# (2) hoechstens 30 Tage Abweichung, denn darueber stehen Seitenkopf-Daten („Seite 26 von
# 653"), Lieferfristen aus der Vertragsphase und Jahresdreher; (3) keine Seitenkoepfe.
#
# ⚠ DIE ±365-TAGE-FAELLE BLEIBEN BEWUSST STUMM. „Die Angebotsfrist endet am 10.09.2027" kann
# ein echter Jahresdreher des Auftraggebers sein — und genau deshalb wird er nicht gemeldet:
# ohne das Dokument zu oeffnen laesst sich sein Tippfehler nicht von unserem Lesefehler
# unterscheiden. Bei einer Frist ist Schweigen billiger als Raten.
#
# ⚠ UND SIE SAGT NICHT, WELCHE SEITE RECHT HAT. Die Abweichungen spitzen auf VIELFACHEN VON
# SIEBEN (51 von 100 sind exakte Wochenvielfache, zufaellig waeren es 14 %): das ist die
# Signatur verlaengerter Fristen. Mal bleibt das alte Dokument liegen, mal traegt das Dokument
# die Verlaengerung und die Bekanntmachung nicht. Die Anzeige nennt beide Daten und den einen
# Satz, der immer stimmt: die fruehere Angabe ist die sichere.
_FRISTWIDERSPRUCH: tuple[Kennzahl, ...] = (
    Kennzahl("fristwiderspruch", "Widerspruch bei der Angebotsfrist", "keine", "",
             "lead-detail", "export_fristwiderspruch.py", "deadline_date", "Tage"),
)

# ── Standardtext-Anteil (Kennzahl 8, gebaut am 2026-09-02) ──────────────────────────────
# Die Uebergabe nennt Median 10 %, oberes Viertel 27 % — und sagt selbst, dass das eine
# Untergrenze ist: sie mass in 600 Vorgaengen. Am vollen Bestand (9.690 Vorgaenge, 1,32 Mio.
# verschiedene Absaetze, 4,2 Mrd. Zeichen) sind es **29 % / 51 %**, gut das Dreifache.
#
# ⚠ JE ABSATZ, NICHT JE DATEI. `document_duplicates` gibt es laengst (4.902 Paare), aber ganze
# Dateien sind nur in 2,1 % der Faelle identisch — ein geaendertes Datum im Kopf genuegt.
#
# ⚠ DIE VERGLEICHSGRUPPE IST DIE TEXTMENGE, und das war nicht die erste Vermutung. Das
# Regelwerk trennt sichtbar (UVgO 42 %, VOB 25 %, Spreizung 1,8×), die Textmenge doppelt so
# stark (klein 41 %, mittel 25 %, gross 10 %, Spreizung 4,1×) — und ihr Muster wiederholt sich
# INNERHALB jedes Regelwerks. Der Grund ist inhaltlich: grosse Pakete tragen ein eigenes
# Leistungsverzeichnis und eigene technische Anlagen, die nirgends sonst stehen.
#
# ⚠ UNTER 50 TSD. ZEICHEN IST DIE ZAHL RAUSCHEN: dort landen 35 % der Vorgaenge bei genau 0 %
# (darueber 3 %). Sie bekommen keinen Wert statt eines schlechten.
#
# ⚠ SIE HAELT DIE DRIFTPRUEFUNG AUS, WEIL SIE EIN VERHAELTNIS IST: 25 % → 34 % → 32 % → 36 %
# ueber die Lesetiefe, nicht monoton, Korrelation 0,13. Absolute Zaehlungen aus denselben
# Dokumenten tun das nicht (Kennzahl 4: 2 → 7 → 16 Formulare).
_STANDARDTEXT: tuple[Kennzahl, ...] = (
    Kennzahl("standardtextAnteil", "Standardtext-Anteil", "markt",
             "Median und oberes Viertel derselben Textmengen-Klasse",
             "lead-detail", "export_standardtext.py", "text", "Prozent"),
)

# ── Bezifferte Schwellen im Vergleich (Kennzahl 6, gebaut am 2026-09-02) ────────────────
# Die Uebergabe verspricht „198.584 Zahlen, einordenbar gegen Median und Quartil derselben
# Anforderungsart". Zahlen gibt es sogar mehr (223.570), einordenbar sind rund 2.500 — ein
# Prozent. Drei Filter liegen dazwischen, und jeder steht fuer eine eigene Fehlerart:
#
#   1. OHNE EINHEIT KEIN VERGLEICH. Bei `technische_mindestanforderung` fehlt sie in 66 % der
#      Faelle, bei `vertragsstrafe` in 81 %, bei `zertifikat` in 97 %. „Median 20" ist 20 mm
#      oder 20 Jahre. ⚠ Und eine Einheit kann einen FAKTOR tragen: „1,5 Mio. EUR" gegen
#      „1.500.000 EUR" verglichen ist ein Fehler um das Millionenfache — solche Schreibweisen
#      werden verworfen, nicht geraten.
#   2. DIE GRUPPE MUSS EINE GROESSE BENENNEN. Ein Urteil, kein Rechenschritt, deshalb als
#      Liste mit Begruendung im Export. Verworfen: `technische_mindestanforderung`
#      („mindestens 20 %" — wovon?), `frist` (Bindefrist und Ausfuehrungsfrist im selben Topf),
#      `leistung_menge` (mischt Tueren und Schrauben, und ist Kennzahl 5).
#      ⚠ Bei den Versicherungen reicht der `req_type` nicht: die Deckungssummen sind nach
#      SCHADENSART gestaffelt und spreizen dabei sechsfach (allgemein 500.000, Umwelt 3 Mio.).
#   3. ⚠ MISST DIE ZAHL DEN VORGANG ODER UNS? Diese Pruefung rechnet der Export bei JEDEM Lauf
#      selbst, statt das Urteil von heute einzufrieren. Durchgefallen sind u. a. der
#      Mindestumsatz (2,5×) und die Vertragsstrafe in EUR (16,7×, gemischte Skala).
#      ⚠ Beim Mindestumsatz war die naheliegende Erklaerung falsch: „tief gelesene Vorgaenge
#      sind grosse Vergaben" — die Schwelle korreliert NICHT mit dem Auftragswert (0,24), und
#      der Anstieg bleibt innerhalb jedes Regelwerks (VgV 480.000 → 1.500.000).
#
# ⚠ SIE HAT KEINE EIGENE ANZEIGE. Die Zahl stand seit jeher in der Checklistenzeile; ergaenzt
# ist nur die Einordnung daneben. Wie bei Kennzahl 5: erst suchen, ob die Zahl schon da ist.
_SCHWELLEN: tuple[Kennzahl, ...] = (
    Kennzahl("schwelleVergleich", "Bezifferte Schwelle gegen ihre Gruppe", "markt",
             "Median und oberes Viertel derselben Anforderungsart, Einheit und Schadensart",
             "lead-detail", "export_schwellen.py", "wert_num", "je Gruppe"),
)

# ── Umfang des Leistungsverzeichnisses (Kennzahl 5, gebaut am 2026-09-02) ───────────────
# Sie stand als `mengengeruest` unter `geplant`: „495.891 LV-Positionen mit Menge und Einheit".
# Diese Zahl LIEGT NIRGENDS — sie wurde beim Parsen gezaehlt und nie gespeichert, `docpipe.py`
# macht aus GAEB-Positionen Text. Was liegt, sind extrahierte `leistung_menge`-Zeilen.
#
# ⚠ UND DIE ZERFALLEN IN ZWEI GRUPPEN, von denen eine unbrauchbar ist:
#     GAEB/LV             3.494 Zeilen · Median 86 · max   6.953 · ueber 5.000:   2
#     Preisblatt/Tabelle  6.327 Zeilen · Median 56 · max 200.010 · ueber 5.000: 263
# Die Spitze der zweiten sind LASTGAENGE — Viertelstundenwerte eines Jahres (35.040 Zeilen),
# keine zu kalkulierenden Positionen. „200.010 Positionen zu bepreisen" waere bei jeder
# Stromausschreibung falsch. GAEB (.x83/.x81/.x86) ist per Format ein Leistungsverzeichnis;
# die Trennung braucht keine Namensliste.
#
# ⚠ SIE DARF EINEN VERGLEICH TRAGEN UND KENNZAHL 4 NICHT — gemessen, nicht gesetzt. Das
# groesste LV je Vorgang ist ueber die Lesetiefe STABIL (69 → 96 → 78) und es gibt genau eins
# je Vorgang; die Formularsummen wachsen monoton mit. Verglichen wird je GEWERK (CPV
# 4-stellig): innerhalb von CPV 45 spreizen die Mediane 5,4-fach (Installation 292, Anstrich
# 54). Unter 40 Vorgaengen im Gewerk steht die Zahl ohne Vergleich.
#
# ⚠ Die beiden messen NICHT dasselbe, obwohl ein VHB 223 ein Feld je LV-Position hat:
# Korrelation -0,02, von 803 grossen LV haben nur 79 auch ein grosses Formular.
_FORMULAR: tuple[Kennzahl, ...] = (
    Kennzahl("formularUmfang", "Umfang der Formulare", "keine", "",
             "lead-detail", "export_umfang.py", "wert_num", "Felder"),
    Kennzahl("lvUmfang", "Umfang des Leistungsverzeichnisses", "markt",
             "Leistungsverzeichnisse desselben Gewerks (CPV 4-stellig, ab 40 Vorgängen)",
             "lead-detail", "export_umfang.py", "wert_num", "Positionen"),
)

# ── Fingerabdruck der Vergabestelle (Kennzahl 3, gebaut am 2026-09-02) ───────────────────
# ⚠ Nur die sieben Anforderungsarten unter 25 % Marktanteil. Dass eine Stelle
# `einzureichendes_dokument` (92 % marktweit) immer verlangt, ist keine Eigenschaft der
# Stelle, sondern des Verfahrens. Und mindestens fuenf Verfahren: „3 von 3" ist rechnerisch
# auffaellig und trotzdem duenn.
_STELLENPROFIL: tuple[Kennzahl, ...] = (
    Kennzahl("fingerabdruckVergabestelle", "Fingerabdruck der Vergabestelle", "markt",
             "Marktanteil derselben Anforderungsart, je Land",
             "lead-detail", "export_stellenprofil.py", "", "Anteil"),
)

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
                              + _ANFORDERUNGSPROFIL + _STELLENPROFIL + _FORMULAR
                              + _SCHWELLEN + _STANDARDTEXT
                              + _FRISTWIDERSPRUCH
                              + _VERLAESSLICHKEIT
                              + _BIETERFRAGEN
                              + _UNTERLAGENSTAND + INVENTAR)


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
