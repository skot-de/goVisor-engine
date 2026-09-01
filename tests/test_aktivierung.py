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
    texte = re.findall(r'text: t\("([^"]+)"\)', block)
    assert len(texte) == 5
    for txt in texte:
        assert re.search(r"\b(Tragt|Sagt|nehmt|Passt|gehört)\b", txt), f"ohne Aufforderung: {txt[:60]}"


def test_kein_gedankenstrich_in_der_kachel():
    """Sven-Vorgabe. Die Kachel trug bis zum 2026-09-01 einen zwischen Titel und Text."""
    stelle = DP[DP.index("b.luecken.slice(0, 3)"):]
    stelle = stelle[:stelle.index("))}")]
    assert "—" not in stelle and "–" not in stelle


def test_hoechstens_drei_bitten():
    """⚠ Fünf Bitten auf einem Bildschirm sind keine Einladung mehr, sondern eine
    Mängelliste. Sortiert wird nach betroffener Anzahl, die drei mit der größten Wirkung
    gewinnen."""
    assert "b.luecken.slice(0, 3)" in DP
    assert "sort((a, z) => z.n - a.n)" in DP
