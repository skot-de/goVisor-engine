"""Der Tageslauf — Zahlen im Skript gegen das, was die Protokolle wirklich sagen.

Ein Sicherheitsabstand, der aus einer Messung stammt, altert mit der Messung. `daily_leads.sh`
reserviert Zeit für die Auswertung („Ernte") und begründet das mit einer ausgezählten Tabelle.
Am 2026-08-30 war die Tabelle über einen Monat alt, zählte 7 der inzwischen 10 Schritte, und
die Reserve lag mit dem **0,91-fachen** der gemessenen Erntezeit unter dem, was sie decken
sollte — sie war gar keine Reserve mehr.

⚠ Aufgefallen ist das nicht im Betrieb. Die Läufe blieben mit 87 bis 184 Minuten weit unter
der 8-Stunden-Grenze, die Reserve wurde also nie geprüft. Sie hätte beim ersten langen Abruf
gegriffen — und genau dann versagt. Diese Sorte Fehler meldet sich erst im Ernstfall.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUF = ROOT / "scripts" / "daily_leads.sh"
LOGS = ROOT / "data" / "logs"

# Wie viel Luft die Reserve über dem gemessenen schlimmsten Fall haben muss. Das Skript
# begründet sie mit „dem Doppelten"; der Test verlangt 1,5× — er soll melden, wenn der
# Abstand schmilzt, nicht schon beim ersten Ausreisser rot werden.
MINDEST_FAKTOR = 1.5
# Wie viele Läufe angesehen werden. Zu wenige, und ein einzelner kurzer Lauf redet die
# Ernte klein; zu viele, und längst behobene Ausreisser halten die Zahl künstlich hoch.
LAEUFE = 8


def _erntesc_hritte() -> list[str]:
    """Die Schritte hinter der Marke „AB HIER: AUSWERTUNG" — das, was die Reserve deckt.

    Aus dem Skript gelesen, nicht abgeschrieben: genau daran ist die alte Tabelle
    gescheitert (sie kannte `Dokument-Dubletten` nicht, 18 min).
    """
    zeilen = LAUF.read_text(encoding="utf-8").splitlines()
    # ⚠ AUF DIE TRENNZEILE ANKERN, nicht auf den Wortlaut. Die Begruendung der Reserve
    # ZITIERT die Marke im Kommentar — ein `"AB HIER: AUSWERTUNG" in z` findet deshalb
    # zuerst den Kommentar, und der steht 600 Zeilen VOR der Stelle. Der Test maass damit
    # den halben Nachtlauf als Ernte und meldete 179 statt 99 min. Ein Waechter, der die
    # falsche Menge misst, ist schlimmer als keiner: seine Zahl sieht benutzbar aus.
    marke = [i for i, z in enumerate(zeilen) if z.startswith("# ══ AB HIER: AUSWERTUNG")]
    assert len(marke) == 1, f"Marke nicht eindeutig: {len(marke)} Treffer"
    # Nur Schritte auf oberster Ebene (`step "…"` ohne Einrueckung) — eingerueckte stehen
    # in Bedingungen und Schleifen und laufen nicht zwingend.
    return [m.group(1) for z in zeilen[marke[0]:]
            if (m := re.match(r'step "(.+)"$', z))]


def _ernte_minuten() -> list[float]:
    """Erntezeit je Lauf, aus den Protokollen ausgezählt."""
    schritte = _erntesc_hritte()
    aus = []
    for log in sorted(LOGS.glob("daily-*.log"), reverse=True)[:LAEUFE]:
        text = log.read_text(encoding="utf-8", errors="replace")
        s = sum(int(m.group(1))
                for name in schritte
                if (m := re.search(rf"⏱ {re.escape(name)} — (\d+)s", text)))
        if s:
            aus.append(s / 60)
    return aus


def test_die_erntesc_hritte_werden_ueberhaupt_gefunden():
    """Ohne diesen Test wäre der Wächter darunter geräuschlos wirkungslos.

    Findet die Marke oder das `step "…"`-Muster nicht mehr, käme eine leere Liste heraus —
    und eine leere Liste besteht jede Schwellenprüfung. Genau so verschwindet ein Test,
    ohne dass jemand ihn löscht.
    """
    schritte = _erntesc_hritte()
    assert len(schritte) >= 8, f"nur {len(schritte)} Erntesc hritte erkannt: {schritte}"
    assert "Frontend-Daten exportieren (web/data)" in schritte, \
        "der Frontend-Export liegt nicht mehr in der Ernte — stimmt die Marke noch?"


@pytest.mark.skipif(not LOGS.exists() or not list(LOGS.glob("daily-*.log")),
                    reason="keine Tageslauf-Protokolle (frische Arbeitskopie)")
def test_ernte_reserve_deckt_die_gemessene_ernte():
    """Die reservierte Zeit muss über der wirklich gebrauchten liegen — mit Abstand.

    Der Sinn der Reserve: bevor ein Abrufschritt startet, prüft der Lauf, ob danach noch
    genug Zeit bis zur Gesamtgrenze bleibt, um aus den Daten das Produkt zu machen. Ist sie
    zu klein, wird der Lauf mitten in der Auswertung abgeschnitten — also genau dann, wenn
    er sich gerade gelohnt hätte, weil der Abruf viel gebracht hat.
    """
    quelle = LAUF.read_text(encoding="utf-8")
    m = re.search(r"ERNTE_RESERVE=\$\{GOVISOR_ERNTE_RESERVE:-(\d+)\}", quelle)
    assert m, "ERNTE_RESERVE steht nicht mehr in der erwarteten Form im Skript"
    reserve = int(m.group(1)) / 60

    gemessen = _ernte_minuten()
    assert gemessen, "keine Erntezeiten in den Protokollen gefunden — Format geaendert?"
    schlimmster = max(gemessen)

    assert reserve >= schlimmster * MINDEST_FAKTOR, (
        f"Die Ernte-Reserve deckt die Wirklichkeit nicht mehr:\n"
        f"  reserviert          {reserve:.0f} min\n"
        f"  gemessen (schlimmster von {len(gemessen)} Laeufen)  {schlimmster:.0f} min\n"
        f"  Faktor              {reserve / schlimmster:.2f}×  (verlangt: {MINDEST_FAKTOR}×)\n"
        f"  Werte: {', '.join(f'{x:.0f}' for x in sorted(gemessen))}\n"
        f"Entweder die Reserve erhoehen oder einen Erntesc hritt guenstiger machen.")
