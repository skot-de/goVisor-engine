"""Riegel, die erst am Tag des Starts scharf werden — und genau dann falsch stehen könnten.

Beide Befunde hier stammen aus derselben Beobachtung: ein Stub, der noch nichts tut, ist
harmlos, solange er *sagt*, dass er nichts tut. Gefährlich wird er in dem Moment, in dem
eine Umgebungsvariable ihn scharf schaltet, ohne dass jemand den Code dahinter geschrieben
hat.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRIPE = ROOT / "web" / "lib" / "stripe.ts"
TOR = ROOT / "web" / "lib" / "identityGate.ts"


def test_zahlstub_meldet_keinen_erfolg_ohne_umsetzung():
    """Ein Schlüssel in der Umgebung darf keine Zahlung bestätigen.

    ⚠ SO STAND ES: `if (!KEY) return {ok:false}; … return {ok:true, stub:false};` — dazwischen
    nur ein TODO. Solange kein Schlüssel gesetzt war, stimmte das. Der Tag, an dem jemand
    `STRIPE_SECRET_KEY` setzt (also der Tag des Starts), war damit auch der Tag, an dem
    `chargeSubscription` „Zahlung erfolgreich" meldet, ohne dass Geld fliesst — ohne Fehler,
    ohne Protokolleintrag. Ein Schlüssel in der Umgebung ist eben keine Aussage darüber, ob
    der Code, der ihn benutzt, geschrieben wurde.
    """
    q = STRIPE.read_text(encoding="utf-8")
    assert re.search(r"const\s+UMGESETZT\s*=\s*(true|false)", q), (
        "stripe.ts fuehrt keinen `UMGESETZT`-Schalter mehr — dann haengt das Scharfschalten "
        "wieder allein an der Umgebungsvariablen.")
    assert re.search(r"stripeEnabled\s*=\s*UMGESETZT\s*&&", q), (
        "`stripeEnabled` leitet sich nicht mehr aus `UMGESETZT` ab. Ein gesetzter Schluessel "
        "wuerde die Anbindung fuer scharf halten, obwohl sie leer ist.")
    assert "pruefeStand" in q, "der laute Abbruch bei Schluessel-ohne-Umsetzung fehlt"

    # Kein Erfolgs-Rueckgabewert, der ohne Umsetzung erreichbar waere.
    for treffer in re.findall(r"return\s*\{[^}]*ok:\s*true[^}]*\}", q):
        assert "stub: true" in treffer, (
            f"Erfolgsmeldung im Stub gefunden: {treffer!r}. Solange `UMGESETZT` false ist, "
            "darf keine Funktion Erfolg melden.")


def test_das_identitaetstor_wird_verdrahtet_bevor_geld_fliesst():
    """Ein fail-closed gebautes Tor, das an nichts haengt, schuetzt nichts.

    `web/lib/identityGate.ts` ist sorgfaeltig gebaut (fail-closed, eigener Sperrtext) und
    wird von KEINER Stelle aufgerufen — gemessen am 2026-09-04. Es ist die Leiche der am
    2026-08-21 gestrichenen Erfolgspraemie: die Sperre hing an der Abrechnung, die Abrechnung
    ist weg. Heute ist das folgenlos, weil nichts nach aussen wirkt und kein Geld fliesst.

    Der Tag, an dem beides wieder gilt, ist derselbe: der Start. Deshalb steht dieser Test
    hier und nicht als Notiz — er wird genau dann rot, wenn das Tor gebraucht wird.
    """
    if not TOR.exists():
        return                      # bewusst entfernt ist eine gueltige Antwort
    if not re.search(r"const\s+UMGESETZT\s*=\s*true", STRIPE.read_text(encoding="utf-8")):
        return                      # noch kein Geldfluss — das Tor darf schlafen

    web = ROOT / "web"
    rufer = [p for p in list(web.glob("app/**/*.ts")) + list(web.glob("app/**/*.tsx"))
             + list(web.glob("lib/**/*.ts"))
             if p != TOR and "identityGate" in p.read_text(encoding="utf-8")]
    assert rufer, (
        "Stripe ist scharf (`UMGESETZT = true`), aber `lib/identityGate.ts` ruft niemand auf. "
        "Der Kommentar dort sagt: alles, was nach aussen wirkt oder Geld bewegt, muss darauf "
        "hoeren. Entweder verdrahten oder die Datei loeschen — beides ist ehrlich, ein "
        "ungenutztes Sicherheitstor ist es nicht.")
