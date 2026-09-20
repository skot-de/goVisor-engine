"""Die Lücken-Hinweise im Tagesbriefing sind Einladungen, keine Mängelliste.

⚠ Der Fehler, gegen den diese Datei steht: alle Hinweise führten auf `/unternehmen` — eine
Seite, auf der man die Hälfte davon gar nicht ändern kann. Ein Hinweis, der ins falsche
Zimmer zeigt, ist keine Einladung, sondern eine Sackgasse.
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
DP = (WEB / "components" / "explorer" / "DetailPanel.tsx").read_text(encoding="utf-8")
SHELL = (WEB / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
TG = (WEB / "components" / "explorer" / "Trefferguete.tsx").read_text(encoding="utf-8")


def _luecken() -> str:
    return DP[DP.index("const luecken = ["):DP.index("].filter((x) => x.n > 0)")]


def test_jede_luecke_nennt_ihr_ziel():
    """Ohne Ziel landet ein Hinweis wieder auf der Sammelseite."""
    block = _luecken()
    keys = re.findall(r'\{ key: "(\w+)"', block)
    ziele = re.findall(r'ziel: "(\w+)"', block)
    assert len(keys) == len(ziele) == 5, f"{len(keys)} Lücken, {len(ziele)} Ziele"
    assert set(ziele) <= {"trefferguete", "profil"}


def test_die_zwei_mit_eingabefeld_gehen_dorthin():
    """⚠ Bürgschaftsrahmen und Alleingrenze sind die EINZIGEN zwei, die man direkt füllen
    kann — `BetragInput` in der Treffergüte. Sie aufs Eignungsprofil zu schicken hiesse, den
    Nutzer an dem Feld vorbeizuführen, das er sucht."""
    block = _luecken()
    for key in ("buerg", "allein"):
        stelle = block[block.index(f'key: "{key}"'):]
        assert 'ziel: "trefferguete"' in stelle[:120], f"{key} zeigt nicht auf die Treffergüte"
    assert "BetragInput" in TG and "buergschaft" in TG and "maxAlleine" in TG


def test_die_shell_kennt_das_ziel():
    """⚠ Ein Ziel, das die Shell nicht kennt, fällt still durch: `onGoto` tut dann nichts,
    und der Klick sieht aus wie ein kaputter Knopf."""
    assert 'ziel === "trefferguete"' in SHELL
    stelle = SHELL[SHELL.index('ziel === "trefferguete"'):]
    assert 'setStratSektion("trefferguete")' in stelle[:200]


def test_jeder_hinweis_sagt_was_der_klick_tut():
    """Ein Hinweis, der nur benennt, was fehlt, ist eine Mängelmeldung. Eine Einladung sagt,
    was danach passiert."""
    block = _luecken()
    # ⚠ Seit dem 2026-09-20 traegt die Bitte die Zahl selbst („Nehmt die Region auf, 1.204
    # liegen ausserhalb"), weil auf der Kachel nur EINE Zeile Platz hat. Beim Umbau war sie
    # kurzzeitig ein reiner Befund ohne Aufforderung — dieser Test hat es gemeldet.
    texte = re.findall(r'bitte: \(n: string\) => t\("([^"]+)"', block)
    assert len(texte) == 5
    # ⚠ HIER STAND EINE WORTLISTE (Tragt|Sagt|nehmt|Passt|gehört), und sie ist am
    # 2026-09-20 an „Nehmt" gescheitert — dasselbe Wort, nur am Satzanfang gross. Eine
    # Liste prueft, welche Verben mir damals eingefallen sind, nicht die Regel. Die Regel
    # ist: jede Bitte FAENGT mit einer Aufforderung in der Ihr-Form an, und die endet im
    # Deutschen auf -t (Tragt, Sagt, Nehmt, Passt, Ergaenzt, Hinterlegt).
    for txt in texte:
        erstes = txt.split(",")[0].split()[0]
        assert re.fullmatch(r"[A-ZÄÖÜ][a-zäöüß]+t", erstes), (
            f"faengt nicht mit einer Aufforderung an: {txt[:60]}")


def test_kein_gedankenstrich_in_der_kachel():
    """Sven-Vorgabe. Die Kachel trug bis zum 2026-09-01 einen zwischen Titel und Text."""
    for txt in re.findall(r'bitte: \(n: string\) => t\("([^"]+)"', _luecken()):
        assert "—" not in txt and "–" not in txt, txt


def test_genau_eine_bitte():
    """⚠ Fünf Bitten auf einem Bildschirm sind keine Einladung mehr, sondern eine
    Mängelliste. Bis zum 2026-09-20 waren es drei; seit dem Umbau auf Kacheln ist es genau
    EINE, und zwar die mit der größten Wirkung. Schließt man sie, rückt die nächste nach.

    ⚠ Die Sortierung ist dabei der eigentliche Anspruch, nicht die Eins: ohne sie zeigt die
    Kachel irgendeine Lücke, und „die größte" wäre eine Behauptung."""
    assert "b.luecken[0].text" in DP, "die Kachel zeigt nicht mehr die erste Lücke"
    assert "b.luecken.slice" not in DP, "es werden wieder mehrere Bitten gezeigt"
    assert "sort((a, z) => z.n - a.n)" in DP
