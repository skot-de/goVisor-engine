#!/usr/bin/env python3
"""Einen gefallenen Blocker im Dokument-Manifest freigeben.

    python3 scripts/entsperren.py --quelle cosinex --blocker parser [--probe]

**Wozu.** `docfetch_queue` parkt Vorgänge, bei denen weder „gibt es nicht" noch „vielleicht
morgen" zutrifft: die Unterlagen existieren, uns fehlt ein Zugang, eine Zusage oder eine
Fähigkeit. Solche Sätze laufen NICHT über eine Frist wieder auf — sonst würde jede Woche
sinnlos bei fremden Portalen angeklopft. Sie warten, bis der benannte Blocker fällt.

Fällt er, muss es jemand sagen. Genau dafür ist dieses Skript da. Erster Anlass am
2026-08-22: der rib-Parser holt jetzt die Bekanntmachung, wenn es keine Vergabeunterlagen
gibt — damit ist der Blocker `parser` für 94 Vorgänge erledigt.

⚠ ES LÖSCHT DIE SÄTZE, statt sie auf „offen" zu setzen. Das ist Absicht: ein Vorgang ohne
Manifest-Eintrag IST der Zustand „noch nie versucht", und den kann die Auswahl bereits.
Verloren geht dabei nur die Notiz des letzten Fehlschlags.

⚠ SCHREIBT IN `data/` — vorher `scripts/laeuft_was.sh`. Ein Abrufer, der dasselbe Manifest
fortschreibt, überschreibt die Freigabe mit dem Stand, den er beim Start gelesen hat.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor.docfetch_queue import BLOCKIERT, entsperre, frueher  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quelle", default="cosinex", help="Abrufer, z. B. cosinex, netserver")
    ap.add_argument("--blocker", required=True,
                    help=f"einer von: {', '.join(sorted(set(BLOCKIERT.values())))}")
    ap.add_argument("--land", default="DE")
    ap.add_argument("--probe", action="store_true", help="nur zählen, nichts ändern")
    a = ap.parse_args()

    if a.blocker not in set(BLOCKIERT.values()):
        print(f"  ✖ Unbekannter Blocker: {a.blocker}", file=sys.stderr)
        return 2

    wurzel = ROOT / "data" / "docs" / a.land
    id_feld = "notice_id" if a.quelle == "cosinex" else "lead_id"
    stand = frueher(wurzel, a.quelle, id_feld=id_feld)
    betroffen = [k for k, v in stand.items()
                 if BLOCKIERT.get(str(v.get("status") or "").lower()) == a.blocker]
    print(f"  {a.quelle}/{a.land}: {len(betroffen):,} Satz/Sätze mit Blocker „{a.blocker}\"")
    if a.probe:
        for k in betroffen[:5]:
            print(f"    {k}  ({stand[k].get('status')})")
        print("  (Probe — nichts geändert)")
        return 0

    frei = entsperre(wurzel, a.quelle, a.blocker)
    print(f"  {frei:,} freigegeben — der nächste Lauf versucht sie erneut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
