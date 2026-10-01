"""Ist jede RPC gegen den oeffentlichen anon-Key dicht?

⚠ DER BEFUND, DER DIESEN TEST AUSGELOEST HAT (2026-10-01, gefunden von Hand in der
Nachbarsitzung). Supabase gewaehrt neuen Funktionen im Schema `public` per
ALTER DEFAULT PRIVILEGES automatisch EXECUTE an `anon` UND `authenticated`. Ein
`revoke all ... from public` entfernt diese EINZEL-Grants **nicht** — `public` ist eine
andere Rolle als `anon`.

Folge: `kauf_gutschreiben` (0027) war mit dem oeffentlichen anon-Key direkt aufrufbar.
`kauf_gutschreiben(<org>, 'seat', 100, 'stripe', '<beliebig>')` haette hundert Sitzplaetze
ohne Zahlung gutgeschrieben. Geschlossen in 0030.

⚠ WARUM ES DIESEN TEST BRAUCHT UND NICHT NUR DEN FIX. Der Fix gilt fuer zwei Funktionen.
Die naechste security-definer-RPC bringt dieselbe Luecke mit, und sie faellt nur auf, wenn
jemand von Hand nachsieht — so wie diesmal. Ein `revoke from public` SIEHT richtig aus, und
genau das ist das Gefaehrliche: die Zeile steht da, sie wirkt nur nicht.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SQL = sorted((WURZEL / "supabase").glob("*.sql"))

# Funktionen, die KEINEN Entzug brauchen, je mit Grund. Ohne Grund ist es kein Ausnahmefall,
# sondern ein Persilschein (dieselbe Regel wie in `pruefe_verdrahtung.py`).
AUSNAHMEN = {
    "touch_updated_at":    "Trigger-Funktion (returns trigger), direkt aufgerufen wirft sie",
    "handle_new_user":     "Trigger-Funktion auf auth.users, direkt aufgerufen wirft sie",
    "pruefe_profil_grenze": "Trigger-Funktion auf profiles, direkt aufgerufen wirft sie",
    "pruefe_seat_grenze":  "Trigger-Funktion auf user_profiles, direkt aufgerufen wirft sie",
    "pruefe_invite_seat":  "Trigger-Funktion auf pending_invites, direkt aufgerufen wirft sie",
}


def _funktionen() -> dict[str, dict]:
    """Name → {datei, returns, rolle_entzogen, rolle_gewaehrt} ueber ALLE Migrationen."""
    alles = "\n".join(p.read_text(encoding="utf-8") for p in SQL)
    aus: dict[str, dict] = {}
    for p in SQL:
        t = p.read_text(encoding="utf-8")
        for m in re.finditer(
                r"create (?:or replace )?function public\.([a-z_]+)\s*\(.*?\)\s*returns\s+(\w+)",
                t, re.S):
            name, rueck = m.group(1), m.group(2).lower()
            aus.setdefault(name, {"datei": p.name, "returns": rueck})
    for name, d in aus.items():
        entzug = re.findall(rf"revoke\s+\w+\s+on function public\.{name}\([^)]*\)\s*from\s+([^;]+);",
                            alles, re.S)
        gewaehrt = re.findall(rf"grant\s+execute\s+on function public\.{name}\([^)]*\)\s*to\s+([^;]+);",
                              alles, re.S)
        d["entzogen"] = {r.strip() for z in entzug for r in z.replace("\n", " ").split(",")}
        d["gewaehrt"] = {r.strip() for z in gewaehrt for r in z.replace("\n", " ").split(",")}
    return aus


# Die Rollen, die Supabase per ALTER DEFAULT PRIVILEGES automatisch bedient.
STANDARDROLLEN = {"public", "anon", "authenticated"}


def test_jede_rpc_entzieht_jede_nicht_gewollte_rolle():
    """⛔ `from public` REICHT NICHT, und ein pauschales „alles entziehen" waere zu streng.

    Die Regel ist: **jede Standardrolle, die nicht ausdruecklich GEWAEHRT ist, muss
    ausdruecklich ENTZOGEN sein.** Das Gewaehren drueckt die Absicht aus, und nur die
    Differenz dazu ist ein unbeabsichtigtes Recht.

    ⚠ Die erste Fassung dieses Tests verlangte den Entzug von `anon` UND `authenticated` fuer
    jede Funktion — und wurde an `merge_profile` rot, die `authenticated` absichtlich hat.
    Ein Waechter, der die Absicht nicht liest, erzwingt die falsche.
    """
    funk = _funktionen()
    assert funk, "keine Funktionen gefunden — stimmt der Pfad supabase/*.sql noch?"
    maengel = []
    for name, d in sorted(funk.items()):
        if name in AUSNAHMEN or d["returns"] == "trigger":
            continue
        gewollt = d["gewaehrt"] & STANDARDROLLEN
        fehlt = STANDARDROLLEN - gewollt - d["entzogen"]
        if fehlt:
            maengel.append(f"{name} ({d['datei']}): Entzug fehlt fuer {sorted(fehlt)}, "
                           f"entzogen {sorted(d['entzogen']) or 'nichts'}, "
                           f"gewaehrt {sorted(d['gewaehrt']) or 'nichts'}")
    assert not maengel, (
        "RPC mit dem Supabase-Standardrecht fuer anon/authenticated:\n  "
        + "\n  ".join(maengel)
        + "\n⚠ `revoke all on function … from public, anon, authenticated;` — `public` allein "
          "entfernt die Einzel-Grants nicht (Befund 2026-10-01, siehe 0030).")


def test_jede_rpc_hat_danach_einen_erlaubten_aufrufer():
    """Entziehen ohne Gewaehren macht die Funktion unaufrufbar — auch fuer den Server.

    Das ist der stille Gegenfehler zum Befund: die Haertung sieht gruen aus, und die
    Bezahlung scheitert in Produktion.
    """
    maengel = [f"{n} ({d['datei']})" for n, d in sorted(_funktionen().items())
               if n not in AUSNAHMEN and d["returns"] != "trigger"
               and d["entzogen"] and not d["gewaehrt"]]
    assert not maengel, ("entzogen, aber niemandem gewaehrt: " + ", ".join(maengel))


def test_jede_ausnahme_ist_begruendet_und_existiert():
    """Eine Ausnahme fuer eine Funktion, die es nicht mehr gibt, ist eine Falle fuer den Naechsten."""
    funk = _funktionen()
    for name, grund in AUSNAHMEN.items():
        assert len(grund) > 20, f"{name} ist nicht begruendet"
        assert name in funk, f"{name} steht in AUSNAHMEN, existiert aber in keiner Migration mehr"


def test_der_waechter_findet_eine_offene_rpc():
    """⚠ SELBSTPROBE — sie muss den Fund ERZWINGEN, nicht nur moeglich machen.

    Geprueft wird mit dem Zustand VOR 0030: nur `from public`. Findet die Regel den nicht,
    prueft sie nichts.
    """
    vorher = {"kauf_gutschreiben": {"datei": "0027", "returns": "void",
                                    "entzogen": {"public"}, "gewaehrt": {"service_role"}}}
    offen = [n for n, d in vorher.items()
             if STANDARDROLLEN - (d["gewaehrt"] & STANDARDROLLEN) - d["entzogen"]]
    assert offen == ["kauf_gutschreiben"], \
        "die Regel haette den Befund vom 2026-10-01 NICHT gefunden"
