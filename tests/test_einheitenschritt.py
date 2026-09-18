"""Stellt der Einheiten-Schritt eine Frage, wo es nichts zu fragen gibt?

⚠ WARUM DIESE DATEI EXISTIERT. Schritt 3 des Onboardings fragt „Gehoeren diese Einheiten
zu euch?". Bei EINER Einheit ist das keine Frage, sondern eine Liste mit einem Eintrag,
ueber den in Schritt 2 gerade entschieden wurde.

⚠ DIESE REGEL IST AM 2026-09-18 ZWEIMAL GEKIPPT, und beide Male mit Grund.

Vormittags wurde der Sprung ENTFERNT: der Schritt traegt die Zusage „Mit der Bestaetigung
merken wir uns diese Einheiten als eure Identitaet. {n} Siege fliessen in euer Profil." —
die Stelle, an der aus „wir kennen euch" ein Profil wird.

Nachmittags hat Sven an einem Bildschirm mit genau einer Einheit entschieden: „hat die
seite keinen mehrwert, sondern kostet nur zeit und ein klick". Auch richtig: Schritt 2 hat
gerade „arbeitest du bei {firma}?" gefragt und bestaetigen lassen.

Aufgeloest ist der Widerspruch nicht durch Nachgeben, sondern durch Nachsehen: die Zusage
steht AUCH auf dem Abschlussbildschirm („Siege im Profil"), den der Sprung ansteuert. Sie
kommt also eine Seite spaeter, statt zu verschwinden. Der Einwand von vormittags war
berechtigt und ist erledigt, nicht uebergangen.

⚠ Uebersprungen wird nur bei einer BELEGTEN Einheit. Gemessen: 30.175 von 37.948 Firmen
sparen den Klick, zwei behalten die Warnung, die bei blosser Selbstauskunft dort haengt.

Gemessen am 2026-09-18, zwei Grundmengen — beide richtig, verschiedene Fragen:

    alle DE-Identitaeten (entity_identity.parquet)  304.994 · 96,9 % mit EINER Einheit
    Firmen, die das Onboarding findet (suppliers)    37.948 · 79,5 % mit EINER Einheit

Die zweite ist die einschlaegige: Schritt 3 erreicht nur, wer in Schritt 2 einen Treffer
aus `suppliers.json` bestaetigt hat. ⚠ Ich hatte die erste Zahl als falsch bezeichnet —
sie war es nicht, ich hatte eine andere Grundmenge gemessen.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-einheitenschritt.mjs"


def test_die_sonde_laeuft_gruen():
    """Faehrt die ECHTE Regel `hatEtwasZuEntscheiden` gegen fuenf Faelle.

    ⚠ ZWEI DINGE, DIE SIE FESTHAELT. Erstens: uebersprungen wird nur bei einer BELEGTEN
    Einheit. Ist sie blosse Selbstauskunft, traegt der Schritt eine Warnung („diese
    Zuschlaege zaehlen als eure Historie"), und sie stillschweigend zu uebergehen hiesse,
    eine Zustimmung anzunehmen, die niemand gegeben hat. Zweitens: BEIDE Wege in den
    Bildschirm (normaler Pfad und Token-Pfad) benutzen dieselbe Regel — auf dem
    Token-Pfad stand `anzahl > 1` ohne Belegpruefung, die zwei Regeln waren bereits
    auseinandergelaufen.

    Gegengeprueft am 2026-09-18: rot, wenn (a) der Schritt wieder uebersprungen wird,
    (b) die Scheinfrage zurueckkehrt, (c) der Text verspricht, eine Einheit spaeter zu
    ERGAENZEN — das kann das Produkt nicht, `EntityKorrektur` ersetzt nur die Zuordnung.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Der Schritt entfaellt, wo er nichts fragt — und bleibt, wo er warnt" in r.stdout


def test_die_beleglage_wandert_weiter_ins_profil():
    """Uebersprungen wird die FRAGE, nicht die Erfassung.

    ⚠ `confirmedEntities` muss auch im uebersprungenen Fall gefuellt werden, und zwar mit
    der richtigen Beleglage. Die Plausibilitaetsbremse vom 2026-08-21 haelt fest: der
    BELEG wandert mit ins Profil, nicht nur der Name — sonst ist nach dem Speichern nicht
    mehr unterscheidbar, welcher Teil des Bestands belegt ist und welcher blosse
    Selbstauskunft.
    """
    seite = (WURZEL / "web" / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    i = seite.index("confirmedEntities:")
    block = seite[i:i + 400]
    assert "beleg:" in block, "confirmedEntities traegt die Beleglage nicht mehr"
    assert "kennung" in block and "selbstauskunft" in block, (
        "die beiden Beleg-Auspraegungen fehlen — der Unterschied waere nach dem Speichern weg")
    # `aktiv` wird in `ladeMitglieder` gesetzt, also VOR dem Sprung — auch im
    # uebersprungenen Fall steht die Auswahl bereit.
    lade = seite[seite.index("const ladeMitglieder"):]
    assert "setAktiv(" in lade[:lade.index("\n  }, [")], (
        "`aktiv` wird nicht mehr beim Laden gesetzt — im uebersprungenen Fall waere es leer")


# ── Die Zeile zum Nachschärfen ─────────────────────────────────────────────────────────

SEITE = WURZEL / "web" / "app" / "onboarding" / "page.tsx"


def _ohne_kommentar_tsx(s: str) -> str:
    """`//` und `/* */` raus — sonst prueft der Test die Begruendung (F13)."""
    raus, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                raus.append(" ")
                i += 1
            continue
        if s[i] == "/" and i + 1 < n and s[i + 1] == "*":
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                raus.append("\n" if s[i] == "\n" else " ")
                i += 1
            raus.append("  ")
            i += 2
            continue
        raus.append(s[i])
        i += 1
    return "".join(raus)


def test_die_zeile_steht_unter_dem_knopf():
    """⚠ DIE REIHENFOLGE IST DIE ANFORDERUNG, nicht das Beiwerk.

    Sven wollte einen Hinweis aufs Nachschaerfen. Ein Kasten DARUEBER konkurriert mit dem
    einen Versprechen, auf das vier Schritte hingearbeitet haben — und „ihr koennt noch
    verfeinern" liest sich direkt nach dem Fertigwerden wie „du bist noch nicht fertig".
    Wer die Zeile nach oben zieht, hat den Kasten zurueck, den sie ersetzt.
    """
    code = _ohne_kommentar_tsx(SEITE.read_text(encoding="utf-8"))
    i_knopf = code.index('onClick={fertigstellen}')
    i_zeile = code.index('className="sum-schaerfe"')
    assert i_knopf < i_zeile, (
        "Die Schaerfe-Zeile steht VOR dem Knopf zum Weitergehen. Sie soll ihn begleiten, "
        "nicht ihm die Aufmerksamkeit nehmen.")


def test_die_zeile_nennt_eine_zahl_statt_einer_behauptung():
    """„Optimiert eure Suchergebnisse" ist eine Behauptung ohne Beleg. Die Zeile nennt,
    wie viele der GESTELLTEN Nachweisfragen eine Antwort tragen — und wo es nichts zu
    zaehlen gibt, sagt sie das, statt eine Zahl zu erfinden."""
    code = _ohne_kommentar_tsx(SEITE.read_text(encoding="utf-8"))
    block = code[code.index('className="sum-schaerfe"'):]
    block = block[:block.index("</p>")]
    assert "nachweisStand" in block, "die Zeile rechnet nicht mehr, sie behauptet"
    assert "{n} von {m}" in block or "{ n:" in block, "in der Zeile steht keine Zahl mehr"
    assert "/unternehmen" in block, "der Link aufs Eignungsprofil fehlt"


def test_gestellte_ja_nein_fragen_gelten_als_beantwortet():
    """⚠ Bei einer GESTELLTEN Ja/Nein-Frage ist `false` ein „nein", keine Luecke. Sie als
    offen zu zaehlen wuerde die Zahl kleiner zeigen, als sie ist — und dem Nutzer eine
    Aufgabe andichten, die er schon erledigt hat.

    Das ist dieselbe Unterscheidung, die `gefragt` ueberhaupt erst noetig gemacht hat: aus
    einer NICHT gestellten Frage ein „nein" zu machen legt ihm Worte in den Mund.
    """
    code = _ohne_kommentar_tsx(SEITE.read_text(encoding="utf-8"))
    i = code.index("const nachweisStand")
    block = code[i:code.index("})();", i)]
    assert "beziffert" in block, "die Unterscheidung zwischen bezifferten und Ja/Nein-Feldern fehlt"
    for feld in ("haftpflicht", "referenzen", "umsatz"):
        assert feld in block, f"das bezifferte Feld {feld!r} wird nicht mehr geprueft"
    assert "pq" not in block.replace("checkAngaben?.", ""), (
        "eine Ja/Nein-Frage wird als bezifferte Luecke gezaehlt")
