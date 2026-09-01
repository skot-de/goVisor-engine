"""Das Länderversprechen der Oberfläche darf nicht hinter den Daten zurückbleiben.

⚠ Der Fehler, gegen den diese Datei steht, war KEIN Tippfehler: das Onboarding versprach
„jede öffentliche Vergabe in Deutschland", während ein Drittel der Leads aus Österreich und
der Schweiz kam. Der Satz war stehengeblieben, weil niemand einen Fliesstext anfasst, wenn
eine Datenquelle dazukommt. Genau die Altlast, die der EU-weit-Grundsatz meint.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
STAATEN = (WEB / "lib" / "staaten.ts").read_text(encoding="utf-8")


def _codes() -> set[str]:
    block = re.search(r"export const STAATEN[^=]*=\s*\[(.*?)\];", STAATEN, re.S).group(1)
    return set(re.findall(r'\["([A-Z]{2})"', block))


def test_jedes_gefuehrte_land_hat_eine_dativform():
    """⚠ „in der Schweiz", nicht „in Schweiz". Fehlt die Form, fällt der Satz auf den Code
    zurück und es steht „jede öffentliche Vergabe in CH" auf der Seite."""
    block = re.search(r"export const LAND_IN[^=]*=\s*\{(.*?)\};", STAATEN, re.S).group(1)
    dativ = set(re.findall(r"([A-Z]{2}):", block))
    assert _codes() <= dativ, f"ohne Dativform: {_codes() - dativ}"


def test_die_liste_steht_nur_an_einer_stelle():
    """Zwei Listen heisst: ein neues Land wird an einer von beiden vergessen. Genau so war
    es (FilterPanel + Marktpuls)."""
    for datei in ("components/explorer/FilterPanel.tsx", "components/Marktpuls.tsx",
                  "app/onboarding/page.tsx"):
        text = (WEB / datei).read_text(encoding="utf-8")
        ohne_kommentar = "\n".join(z for z in text.splitlines() if not z.lstrip().startswith(("//", "*", "/*")))
        assert not re.search(r'const (STAATEN|LAND_IN)\s*[:=]', ohne_kommentar), \
            f"{datei} führt wieder eine eigene Länderliste"


def test_das_versprechen_nennt_kein_land_hart():
    """Der Satz trägt `{laender}`, nicht „Deutschland" — sonst altert er wieder."""
    text = (WEB / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    assert "öffentliche Vergabe in {laender}" in text
    assert "öffentliche Vergabe in Deutschland" not in text


def test_der_platzhalter_ueberlebt_jede_uebersetzung():
    """⚠ Ohne `{laender}` in der Übersetzung verschwindet die Länderliste stumm — der Satz
    liest sich weiter richtig und behauptet nichts mehr."""
    for katalog in ("flat.en.json", "flat.fr.json"):
        d = json.loads((WEB / "lib" / "i18n" / "messages" / katalog).read_text(encoding="utf-8"))
        treffer = [v for k, v in d.items() if "{laender}" in k]
        assert treffer, f"{katalog} kennt den Satz nicht"
        for v in treffer:
            assert "{laender}" in v, f"{katalog}: Platzhalter fehlt in der Übersetzung"


def test_laendernamen_sind_uebersetzt():
    """Die Namen gehen einzeln durch `t()`. Fehlt einer im Katalog, steht mitten im
    englischen Satz ein deutsches Land."""
    block = re.search(r"export const LAND_IN[^=]*=\s*\{(.*?)\};", STAATEN, re.S).group(1)
    namen = set(re.findall(r':\s*"([^"]+)"', block)) | {"und"}
    for katalog in ("flat.en.json", "flat.fr.json"):
        d = json.loads((WEB / "lib" / "i18n" / "messages" / katalog).read_text(encoding="utf-8"))
        fehlt = {n for n in namen if n not in d}
        assert not fehlt, f"{katalog}: {fehlt}"


def test_nicht_an_der_definition_uebersetzen():
    """Falle 1 der i18n-Mechanik: Modul-Konstanten werden beim Import ausgewertet — durch
    `t()` gingen sie mit der Sprache des ersten Ladens und blieben dort stehen."""
    roh = re.search(r"export const STAATEN.*?export function", STAATEN, re.S).group(0)
    # ⚠ Ohne Kommentar-Strich schlägt der Test an der BEGRÜNDUNG an, die `t()` erwähnt —
    # dieselbe Falle wie bei den Sicherheits-Wächtern: ein Test, der Text prüft statt Code.
    code = "\n".join(z for z in roh.splitlines() if not z.lstrip().startswith(("//", "*", "/*")))
    assert "t(" not in code.replace("Record<", ""), "Länder werden an der Definition übersetzt"
