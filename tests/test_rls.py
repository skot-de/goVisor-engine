"""Row-Level-Security: was eine angemeldete Person lesen darf.

Die Tabellen liegen in Supabase, der Schutz ist RLS. Ein Fehler hier ist nicht sichtbar —
er faellt erst auf, wenn jemand fremde Daten sieht.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONEN = sorted((ROOT / "supabase").glob("*.sql"))

# Tabellen, deren Inhalt bewusst fuer alle Angemeldeten lesbar ist. JEDE braucht einen Grund.
OFFEN_MIT_GRUND = {
    "doc_requirement_types":
        "Vokabular der Anforderungsarten (§6a) — eine Nachschlagetabelle ohne Nutzerbezug, "
        "wie eine CPV-Liste. Sie zu verbergen schuetzt nichts und bricht jede Anzeige.",
}


# ⚠ `for <op>` IST OPTIONAL — und fehlt es, gilt die Policy fuer ALLE Operationen.
# Die erste Fassung dieses Musters verlangte es und sah damit 18 von 34 Policies. Sie meldete
# trotzdem „sauber": ein Waechter, der die Haelfte nicht liest, findet in der anderen Haelfte
# eben nichts. Genau deshalb prueft `test_der_waechter_sieht_alle_policies` unten die ZAHL.
_POLICY = re.compile(
    r'create policy\s+"?([A-Za-z0-9_]+)"?\s+on\s+([\w.]+)'
    r'(?:\s+as\s+\w+)?(?:\s+for\s+(\w+))?(?:\s+to\s+[\w,\s]+)?([^;]*);', re.I | re.S)


def _policies() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Die GELTENDEN Policies: `(tabelle, name)` → `(datei, operation, bedingung)`.

    ⚠ DIE REIHENFOLGE IST DER GANZE WITZ. Migrationen laufen nacheinander, und ein spaeteres
    `drop policy … / create policy …` ersetzt ein frueheres. Wer alle Dateien gleichzeitig
    liest, sieht abgeloeste Regeln als geltend — beim Bauen dieses Tests genau passiert: die
    Messung meldete drei `using (true)`, von denen zwei seit 0019 nicht mehr gelten.
    """
    geltend: dict[tuple[str, str], tuple[str, str, str]] = {}
    for f in MIGRATIONEN:                      # sortiert = Anwendungsreihenfolge
        for m in _POLICY.finditer(f.read_text(encoding="utf-8")):
            name, tab = m.group(1), m.group(2).removeprefix("public.")
            op = (m.group(3) or "all").lower()
            geltend[(tab, name)] = (f.name, op, " ".join(m.group(4).split()))
    return geltend


def test_der_waechter_sieht_alle_policies():
    """⚠ EIN MUSTER, DAS DIE HAELFTE UEBERSIEHT, MELDET SAUBERKEIT.

    Die erste Fassung von `_POLICY` verlangte eine `for`-Klausel. Die ist aber optional —
    ohne sie gilt die Policy fuer ALLE Operationen, und genau so sind hier neun geschrieben
    (`alerts_rw_own`, `contracts_rw_own`, `declarations_rw_own` …). Der Waechter sah 18 von
    34 und meldete „sauber"; in der Haelfte, die er las, war ja nichts.

    Deshalb prueft er jetzt seine eigene Ausbeute gegen die schlichte Zahl der
    `create policy`-Vorkommen. Ein Parser, der nicht nachzaehlt, was er gefunden hat, ist
    ein Parser, dem man nicht glauben darf.
    """
    roh = sum(len(re.findall(r"create policy", f.read_text(encoding="utf-8"), re.I))
              for f in MIGRATIONEN)
    # `drop policy` + `create policy` derselben Kennung zaehlt roh doppelt; der Bestand ist
    # deshalb kleiner oder gleich. Deutlich weniger heisst: das Muster greift nicht.
    gefunden = len(_policies())
    assert gefunden >= roh - 4, (
        f"Das Muster findet nur {gefunden} von {roh} `create policy`-Vorkommen. "
        f"Eine Schreibweise wird nicht erkannt — und in dem, was nicht gelesen wird, "
        f"findet der Waechter nie etwas.")


def test_jede_tabelle_hat_rls_eingeschaltet():
    """Ohne `enable row level security` ist eine Policy Zierrat — es liest jeder alles."""
    tabellen, mit_rls = set(), set()
    for f in MIGRATIONEN:
        t = f.read_text(encoding="utf-8")
        tabellen |= {m.group(1) for m in re.finditer(
            r"create table(?: if not exists)?\s+(?:public\.)?(\w+)", t, re.I)}
        mit_rls |= {m.group(1) for m in re.finditer(
            r"alter table\s+(?:public\.)?(\w+)\s+enable row level security", t, re.I)}
    ohne = sorted(tabellen - mit_rls)
    assert not ohne, f"Tabellen ohne RLS: {ohne}"


def test_keine_lesepolicy_steht_ohne_grund_auf_true():
    """⚠ GEFUNDEN AM 2026-09-06.

    `0006_doc_analysis.sql` setzt §12.2 sorgfaeltig um: `doc_packages` ist auf
    `visibility = 'shared'` begrenzt, `doc_files` erbt das ueber einen `exists`-Verweis. Die
    CHECKLISTE aber — genau der Inhalt, den §12.2 schuetzen soll — stand auf `using (true)`.
    Jeder Angemeldete haette jede Checkliste lesen koennen, auch die eines `private`-Pakets.
    Der Kern-Risikofall lautet: „im selben Lead sitzen konkurrierende Bieter". Die Tuer am
    Paket war zu, das Fenster daneben offen.

    Ohne Wirkung, weil keine der fuenf Tabellen aus 0006 von einer Zeile Code beruehrt wird
    — und genau deshalb jetzt behoben (0019), solange es nichts kostet.
    """
    offen = [(tab, name, datei, bed) for (tab, name), (datei, op, bed) in _policies().items()
             if op.lower() == "select"
             and re.search(r"using\s*\(\s*true\s*\)", bed, re.I)
             and tab not in OFFEN_MIT_GRUND]
    assert not offen, ("Lesepolicies ohne Einschraenkung:\n  "
                       + "\n  ".join(f"{t}.{n} ({d})" for t, n, d, _ in offen))


def test_jede_offene_tabelle_nennt_ihren_grund():
    """Eine Ausnahme ohne Begruendung ist ein Schweigen, kein Befund."""
    for tab, grund in OFFEN_MIT_GRUND.items():
        assert len(grund) > 40, f"{tab} steht ohne belastbare Begruendung in der Liste"


def test_keine_ausnahme_fuer_eine_tabelle_die_es_nicht_gibt():
    """Toter Ballast verdeckt, dass die Liste niemand mehr liest."""
    vorhanden = set()
    for f in MIGRATIONEN:
        vorhanden |= {m.group(1) for m in re.finditer(
            r"create table(?: if not exists)?\s+(?:public\.)?(\w+)",
            f.read_text(encoding="utf-8"), re.I)}
    tot = [t for t in OFFEN_MIT_GRUND if t not in vorhanden]
    assert not tot, f"Ausnahmen fuer Tabellen, die es nicht gibt: {tot}"
