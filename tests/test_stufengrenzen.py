"""Sind Profil- und Sitzgrenze stufenabhaengig (Preismodell v1.9 §7.3)?

Die drei Trigger setzten `profiles_paid`/`seats_paid` bis zum 2026-10-01 UNBEDINGT durch.
Live gelesen: `tier` kam in keiner der drei Funktionen vor. Aufgefallen ist es nicht, weil
alle 13 Organisationen auf `tier='free'` mit `profiles_paid=1` stehen und Free laut §7.3
ohnehin auf eins begrenzt ist — der Trigger tat versehentlich das Richtige.

⚠ GEKIPPT WAERE ES BEIM ERSTEN BEZAHLTEN ABSCHLUSS. Sobald eine Organisation auf `analyse`
geht, haette die Datenbank das zweite Profil und den zweiten Nutzer verweigert, obwohl das
Preismodell beides als unbegrenzt verkauft und die Erweiterung zu 29 € genau dafuer da ist.

Behoben in 0032 und am laufenden System geprueft (Transaktion, danach zurueckgerollt):
    free      zweites Profil  gesperrt      analyse   zweites Profil  erlaubt
    trial     zweites Profil  gesperrt      analyse   zweite Einladung erlaubt
    free      zweite Einladung gesperrt (Sitz vom Inhaber belegt)
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SQL = WURZEL / "supabase" / "0032_grenzen_stufenabhaengig.sql"
FUNKTIONEN = ("pruefe_profil_grenze", "pruefe_seat_grenze", "pruefe_invite_seat")


def _ohne_kommentare(text: str) -> str:
    """⚠ PFLICHT VOR JEDER MUSTERPRUEFUNG. Die Begruendung in 0032 NENNT die verworfene Form
    `tier not in ('free','trial')` — ein Grep ohne dieses Strippen schlaegt an der Erklaerung
    an statt am Code. Dieselbe Lehre steht unter „Waechter messen Prosa statt Code"."""
    return "\n".join(z.split("--")[0] for z in text.splitlines())


def test_alle_drei_grenzen_kennen_die_stufe():
    code = _ohne_kommentare(SQL.read_text(encoding="utf-8"))
    for fn in FUNKTIONEN:
        assert f"function public.{fn}()" in code, f"{fn} wird in 0032 nicht neu definiert"
    # Je Funktion EIN Block: ab der Definition bis zum abschliessenden $$;
    for fn in FUNKTIONEN:
        i = code.index(f"function public.{fn}()")
        rumpf = code[i:code.index("$$;", i)]
        assert "tier" in rumpf, f"{fn} liest die Stufe nicht"
        assert "'analyse'" in rumpf and "'strategie'" in rumpf, \
            f"{fn} nennt die bezahlten Stufen nicht"


def test_die_pruefung_steht_in_der_positiven_form():
    """⛔ `tier not in ('free','trial')` waere die Falle, nicht die Loesung.

    Faende die Abfrage keine Organisation, waere `t` NULL — und `NULL not in (…)` ist NULL,
    der Riegel wuerde uebersprungen und die Grenze griffe NICHT. In der positiven Form
    (`tier in ('analyse','strategie')`) ist NULL ebenfalls nicht wahr und die Grenze greift.
    Jede unbekannte Stufe ist damit begrenzt statt frei.
    """
    code = _ohne_kommentare(SQL.read_text(encoding="utf-8"))
    assert "not in ('free'" not in code.replace(" ", "").replace("notin", "not in"), \
        "die negative Form ist zurueck — bei NULL greift die Grenze dann nicht"
    assert code.count("in ('analyse', 'strategie')") == 3, \
        "nicht alle drei Funktionen pruefen in der positiven Form"


def test_die_grenze_fuer_free_ist_fest_eins_und_nicht_die_abrechnungsmenge():
    """§7.3 sagt „genau 1". `profiles_paid`/`seats_paid` sind seit 0032 ABRECHNUNGSgroessen —
    ein Free-Konto rechnet nichts ab, also darf eine Abrechnungsmenge dort nichts erlauben."""
    code = _ohne_kommentare(SQL.read_text(encoding="utf-8"))
    assert "profiles_paid" not in code.split("comment on column")[0], \
        "die Profilgrenze haengt wieder an der Abrechnungsmenge"
    assert "seats_paid" not in code.split("comment on column")[0], \
        "die Sitzgrenze haengt wieder an der Abrechnungsmenge"
    assert code.count("n >= 1") + code.count("belegt >= 1") == 3


def test_die_umgedeutete_bedeutung_steht_an_der_spalte():
    """`profiles_paid` hiess in 0024 „erlaubte Profile". Das ist seit 0032 falsch, und eine
    Spalte, deren Kommentar das Gegenteil behauptet, ist eine Falle fuer den Naechsten."""
    sql = SQL.read_text(encoding="utf-8")
    assert "comment on column public.organizations.profiles_paid" in sql
    assert "comment on column public.organizations.seats_paid" in sql
    assert "ABGERECHNETE" in sql, "die neue Bedeutung steht nicht am Feld"


def test_der_waechter_findet_die_rueckkehr_der_unbedingten_grenze():
    """⚠ SELBSTPROBE — sie muss den Fund erzwingen. Geprueft wird die Fassung VOR 0032
    (unbedingt, ohne Stufe): findet die Regel die nicht, prueft sie nichts."""
    vorher = """
create or replace function public.pruefe_profil_grenze()
returns trigger language plpgsql as $$
declare n int; grenze int;
begin
  select count(*) into n from public.profiles where org_id = new.org_id;
  select profiles_paid into grenze from public.organizations where id = new.org_id;
  if grenze is not null and n >= grenze then raise exception 'x'; end if;
  return new;
end;
$$;
"""
    rumpf = vorher[vorher.index("function public.pruefe_profil_grenze()"):]
    assert "tier" not in rumpf.split("$$;")[0], "die Selbstprobe prueft die falsche Fassung"
    assert "profiles_paid" in rumpf, "die Selbstprobe prueft die falsche Fassung"
