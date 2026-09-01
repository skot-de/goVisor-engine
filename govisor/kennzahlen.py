"""Kennzahlen-Verzeichnis: was eine Zahl ist, woher sie kommt, wogegen sie auffällt.

WARUM ES DIESE DATEI GIBT. Am 2026-09-01 hat sich herausgestellt, dass `docsignals` fünfzehn
Anforderungs-Signale aus den Vergabeunterlagen erkennt, `doc_signals.parquet` alle fünfzehn
trägt, und **sieben davon je im Frontend ankommen**. Verlorengegangen sind sie an einer
einzigen Stelle: `export_doc_signals.py` zählte seine Spalten von Hand auf. Dieselbe Liste
stand danach ein zweites Mal im API-Typ und ein drittes Mal im Renderer. Dreimal pflegbar,
dreimal vergessbar.

Betroffen waren `binding_until` (5.747 Sätze), `penalty_pct` (4.066), `site_visit` (3.723),
`site_visit_mandatory` (3.723), `presentation_required` (3.576) und `skonto_pct` (393). Sie
wurden gebaut, gemessen, gespeichert und nie gezeigt.

WAS HIER STEHT UND WAS NICHT. Dies ist kein zweiter Ort für Zahlen, sondern der Ort für ihre
EIGENSCHAFTEN: wie sie heisst, woher sie kommt, in welcher Einheit sie steht und — das ist
der Kern — **wogegen sie verglichen wird**. Ohne Bezugsgrösse kann eine Zahl nie auffallen;
sie ist dann Hintergrund, und das ist eine Einordnung, keine Abwertung.

⚠ DIE BEZUGSGRÖSSE IST DIE KATEGORIE. Nicht „Marktdaten" gegen „Firmendaten" und nicht
„wichtig" gegen „unwichtig" — beides wäre eine Meinung. Wogegen verglichen wird, ist eine
Eigenschaft der Kennzahl und entscheidet zugleich über die Darstellung: nur was einen Bezug
hat, bekommt eine Leiste.

    markt    gegen den Branchen- oder Gesamtwert
    vorwert  gegen den eigenen Stand von vorher (braucht Historie, die es noch nicht gibt)
    profil   gegen eine Schwelle im Firmenprofil
    keine    beschreibend oder Datenlage; bleibt sichtbar, aber in der Detailebene

⚠ VOLLSTÄNDIG IST NUR, WAS HIER STEHT. Das Verzeichnis deckt heute die Dokument-Signale und
die Vergabestellen-Kacheln ab. Die übrigen Kennzahlen des Frontends sind erfasst, aber noch
nicht eingetragen (Stand 2026-09-01: 127 gezählt, davon 21 hier). Wer eine neue Kennzahl
baut, trägt sie ein; `tests/test_kennzahlen.py` hält fest, dass keine ohne Bezugsgrösse
durchgeht und dass der Export nichts fallen lässt.
"""
from __future__ import annotations

from dataclasses import dataclass

BEZUEGE = frozenset({"markt", "vorwert", "profil", "keine"})


@dataclass(frozen=True)
class Kennzahl:
    """Eine Zahl, die im Frontend erscheint.

    `quelle`  Spaltenname dort, wo sie entsteht (Parquet, Gold-Tabelle).
    `schluessel`  Name, unter dem sie im Frontend ankommt. Weicht bewusst ab, wo der
              technische Name im Produkt nichts zu suchen hat (`guarantee_required` →
              `guarantee`).
    `bezug`   siehe oben. `keine` ist eine gültige Antwort, kein Platzhalter.
    `wogegen` in Worten, was der Vergleichswert IST. Leer nur bei `bezug="keine"`.
    """

    schluessel: str
    quelle: str
    label: str
    einheit: str
    bezug: str
    wogegen: str = ""

    def __post_init__(self) -> None:
        if self.bezug not in BEZUEGE:
            raise ValueError(f"{self.schluessel}: unbekannter Bezug {self.bezug!r}")
        if self.bezug != "keine" and not self.wogegen:
            raise ValueError(f"{self.schluessel}: Bezug {self.bezug!r} ohne Vergleichswert")


# ── Anforderungen aus den Vergabeunterlagen ──────────────────────────────────────────────
# Quelle: govisor/docsignals.py → data/docs/<L>/doc_signals.parquet → web/data/doc-signals.json
#
# ⚠ Die Reihenfolge ist die Anzeigereihenfolge im Anforderungs-Block. `evidence` steht
# bewusst NICHT hier: es ist der Belegtext je Signal, keine eigene Kennzahl.
DOC_SIGNALE: tuple[Kennzahl, ...] = (
    Kennzahl("guarantee", "guarantee_required", "Sicherheit / Bürgschaft", "ja/nein",
             "profil", "euer Bürgschaftsrahmen"),
    Kennzahl("bindingDays", "binding_days", "Bindefrist", "Tage",
             "markt", "übliche Bindefrist im Regelwerk"),
    # ⚠ Das Datum ist NICHT dieselbe Kennzahl wie die Dauer. „90 Tage" sagt, wie lange ihr
    # gebunden seid; „bis 14.11." sagt, ob es in eure Auslastung passt. Beide werden erhoben.
    Kennzahl("bindingUntil", "binding_until", "Bindefrist bis", "Datum",
             "keine"),
    Kennzahl("eligibility", "eligibility_count", "Eignungsnachweise", "Anzahl",
             "profil", "was ihr hinterlegt habt"),
    Kennzahl("certificates", "certificates", "Geforderte Zertifikate", "Liste",
             "profil", "eure Zertifikate"),
    Kennzahl("variants", "variants_allowed", "Nebenangebote", "ja/nein",
             "keine"),
    Kennzahl("framework", "framework", "Rahmenvereinbarung", "ja/nein",
             "keine"),
    Kennzahl("weights", "award_weights", "Zuschlagsgewichte", "Prozent",
             "markt", "übliche Gewichtung im Feld"),
    # ⚠ Der Ortstermin ist mehr als eine Anzeige. Ist er PFLICHT und liegt der Ort weit
    # ausserhalb eurer Regionen, ist das ein echter Nicht-bieten-Grund und gehoert zu den
    # Blockern, nicht in eine Zeile. Deshalb `profil`.
    Kennzahl("siteVisit", "site_visit", "Ortstermin", "ja/nein",
             "keine"),
    Kennzahl("siteVisitMandatory", "site_visit_mandatory", "Ortstermin verpflichtend", "ja/nein",
             "profil", "eure Regionen"),
    Kennzahl("presentationRequired", "presentation_required", "Präsentation gefordert", "ja/nein",
             "profil", "habt ihr die Leute dafür"),
    Kennzahl("penaltyPct", "penalty_pct", "Vertragsstrafe", "Prozent",
             "markt", "übliche Vertragsstrafe im Feld"),
    Kennzahl("skontoPct", "skonto_pct", "Skonto", "Prozent",
             "markt", "übliches Skonto im Feld"),
)

# ── Vergabestellen-Kacheln (Anbieter-Sicht, Strategie → Vergabestellen) ──────────────────
# Quelle: scripts/export_strategie.py → web/data/strategie.json, Feld `stellen`.
# Der Vergleichswert ist überall derselbe: der Median über die Vergabestellen derselben
# Branche, gerechnet in `StrategieView.marktLage`.
_BRANCHE = "Median der Vergabestellen derselben Branche"
VERGABESTELLEN: tuple[Kennzahl, ...] = (
    Kennzahl("vergabenJahr", "vergabenJahr", "Vergaben pro Jahr", "Anzahl", "markt", _BRANCHE),
    Kennzahl("neuAnteil", "neuAnteil", "Neue Anbieter (36 Mon.)", "Prozent", "markt", _BRANCHE),
    Kennzahl("bieterMedian", "bieterMedian", "Ø Bieter je Vergabe", "Anzahl", "markt", _BRANCHE),
    Kennzahl("kmu", "kmu", "Zuschläge an KMU", "Prozent", "markt", _BRANCHE),
    Kennzahl("preis", "preis", "Nur über den Preis entschieden", "Prozent", "markt", _BRANCHE),
    Kennzahl("wechsel", "wechsel", "Wechsel bei Nachfolgevergaben", "Prozent", "markt", _BRANCHE),
)

ALLE: tuple[Kennzahl, ...] = DOC_SIGNALE + VERGABESTELLEN


def nach_schluessel(gruppe: tuple[Kennzahl, ...] = ALLE) -> dict[str, Kennzahl]:
    return {k.schluessel: k for k in gruppe}


def spalten(gruppe: tuple[Kennzahl, ...]) -> list[str]:
    """Quellspalten der Gruppe — damit ein Export sie nicht von Hand aufzählen muss."""
    return [k.quelle for k in gruppe]
