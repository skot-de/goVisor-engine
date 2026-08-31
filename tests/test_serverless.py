"""Welche Routen brauchen eine Python-Laufzeit — und wissen sie das selbst?

`docs/cloud-azure.md` beschreibt die Grundform des Umzugs so: „die Anwendung kennt die
Datenfabrik nicht. Sie liest NUR fertige JSONs." Für die Datenrouten stimmt das. Für elf
Routen stimmt es nicht: sie starten `python3` aus dem Repository.

Auf einem Deployment gibt es weder den Interpreter noch das Repository. Ohne Riegel wird
daraus ein **Exec-Fehler**, der wie ein Codefehler aussieht — genau das ist am 2026-08-22
bei `/api/firma` passiert und steht dort als Kommentar:

    „aus einem Datenproblem wurde ein Exec-Fehler, der wie ein Codefehler aussieht"

`/api/firma` macht seither vor, wie es geht: erst die vorberechnete Datei, und in Produktion
NIE Python, sondern eine Antwort, die sagt was fehlt. Vier Routen haben diesen Riegel,
sieben nicht.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "web" / "app" / "api"

# Was heute Python startet, mit dem Stand vom 2026-08-31. Der Wert sagt, ob die Route in
# Produktion einen Riegel hat — sie also NICHT versucht, `python3` zu starten.
#
# ⚠ Diese Liste ist kein Freibrief, sondern ein Zählwerk. Sie steht hier, damit eine
# ZWÖLFTE Route auffällt, bevor sie im Umzug übersehen wird — und damit sichtbar bleibt,
# welche sieben noch offen sind.
BEKANNT: dict[str, bool] = {
    "firma": True,                       # liest zuerst die vorberechnete Datei, Vorbild
    "intern/firmen": True,
    "intern/landing": True,
    "intern/outreach": True,
    "lead-docs": False,                  # Upload; laut eigenem Kommentar bewusst lokal
    "lead/datei": False,
    "lead/dokumente": False,
    "unternehmen/bilanz": False,
    "unternehmen/vorbefuellung": False,
    "draft-check": False,
    "blocks-import": False,
}


def _python_routen() -> dict[str, bool]:
    """(Route → hat sie einen Produktions-Riegel?) für alles, was `child_process` ruft."""
    aus = {}
    for f in sorted(API.rglob("route.ts")):
        quelle = f.read_text(encoding="utf-8")
        if "child_process" not in quelle:
            continue
        name = f.parent.relative_to(API).as_posix()
        aus[name] = 'NODE_ENV === "production"' in quelle
    return aus


def test_keine_neue_route_startet_unbemerkt_python():
    """Eine zwölfte Route soll auffallen, bevor sie im Umzug übersehen wird."""
    ist = _python_routen()
    neu = sorted(set(ist) - set(BEKANNT))
    weg = sorted(set(BEKANNT) - set(ist))
    assert not neu, (
        f"Neue Route(n) mit Python-Aufruf: {neu}\n"
        f"Entweder einen Produktions-Riegel einbauen (Vorbild: app/api/firma/route.ts) "
        f"oder hier eintragen — und dann in `docs/cloud-azure.md` mitzaehlen.")
    assert not weg, (
        f"Diese Route(n) rufen kein Python mehr: {weg}\n"
        f"Schoen — hier und in `docs/cloud-azure.md` austragen, sonst bleibt die Liste "
        f"laenger als das Problem.")


def test_der_riegel_steht_da_wo_er_verzeichnet_ist():
    """Wer als abgesichert gilt, muss es auch sein.

    ⚠ Die gefährlichere Richtung ist die zweite: eine Route, die den Riegel VERLIERT,
    verhält sich lokal unverändert. Der Unterschied zeigt sich erst auf dem Deployment,
    und dort als Fehler, der nach etwas ganz anderem aussieht.
    """
    ist = _python_routen()
    falsch = {name: (soll, ist[name]) for name, soll in BEKANNT.items()
              if name in ist and soll != ist[name]}
    assert not falsch, "\n".join(
        f"{n}: verzeichnet als {'mit' if s else 'ohne'} Riegel, "
        f"tatsaechlich {'mit' if i else 'ohne'}" for n, (s, i) in falsch.items())


def test_das_umzugsdokument_nennt_die_richtige_zahl():
    """Die Zahl im Dokument muss der Wirklichkeit folgen, nicht dem Gedaechtnis.

    Hier stand über Wochen `/firma` als DER eine nicht-serverless-fähige Fall — und
    ausgerechnet der war inzwischen gelöst. Wer nach dem Dokument plant, budgetiert eine
    Route und findet elf.
    """
    doc = (ROOT / "docs" / "cloud-azure.md").read_text(encoding="utf-8")
    ist = _python_routen()
    ohne_riegel = sum(1 for v in ist.values() if not v)

    # ⚠ ZIFFER ODER WORT. Das Dokument schreibt „elf" und „Sieben", nicht „11" und „7" — ein
    # Test, der nur Ziffern sucht, zwingt den Text in seine Form. Der Text ist fuer Menschen
    # da, der Test hat sich danach zu richten.
    def steht_da(n: int) -> bool:
        woerter = {1: "ein", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs",
                   7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf",
                   13: "dreizehn", 14: "vierzehn", 15: "fünfzehn"}
        if re.search(rf"\b{n}\b", doc):
            return True
        wort = woerter.get(n)
        return bool(wort) and re.search(rf"\b{wort}\b", doc, re.I) is not None

    assert steht_da(len(ist)), (
        f"`docs/cloud-azure.md` nennt nicht mehr die aktuelle Zahl: "
        f"{len(ist)} Routen rufen Python")
    assert steht_da(ohne_riegel), (
        f"`docs/cloud-azure.md` nennt nicht mehr die Zahl der ungesicherten Routen: "
        f"{ohne_riegel} ohne Produktions-Riegel")
