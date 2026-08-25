"""Ein zu grosser Upsert-Stapel darf den Tageslauf nicht abreissen.

**Der Fall.** Ist der Stapel zu gross, endet er auf zwei Arten — und sie sehen völlig
verschieden aus:

  * die Datenbank bricht ab      → HTTP 400 mit `57014` im Antworttext
  * curl gibt vorher auf         → **HTTP 000, ohne Antworttext**

Der Halbierungs-Zweig kannte nur den ersten Fall. Der zweite riss den ganzen Lauf ab —
gemessen am 2026-08-15 UND 2026-08-16, beide Male endete der Tageslauf „MIT Fehler beim
Supabase-Upload". Ein Timeout heisst „zu viel auf einmal", nicht „geht nicht", und das gilt
unabhängig davon, wer zuerst aufgibt.

Geprüft wird OHNE Netz: `subprocess.run` wird ersetzt. Ein Test, der dafür in die echte
Datenbank schreibt, wäre langsam, abhängig von deren Tagesform — und würde beim Prüfen
genau das tun, was er prüfen soll.
"""
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent


def _quelle() -> str:
    return (ROOT / "scripts" / "export_supabase.py").read_text(encoding="utf-8")


def test_zeitueberschreitung_von_curl_gilt_als_mengenproblem():
    """`000` und der curl-Ausstieg 28 muessen denselben Zweig nehmen wie `57014`."""
    s = _quelle()
    assert 'code == "000" or out.returncode == 28' in s, \
        "curl-Zeitueberschreitung wird nicht erkannt"
    m = re.search(r'if \("57014" in body or (\w+)\) and len\(buf\) > 1:', s)
    assert m, "der Halbierungs-Zweig deckt die Zeitueberschreitung nicht ab"
    assert m.group(1) == "zeitueberschreitung"


def test_fehlermeldung_nennt_die_ursache():
    """Im Log stand nur „HTTP 000: 000". Das sagt nicht, ob es die Zeitgrenze, ein
    Netzfehler oder ein Zertifikat war — und genau diese Unterscheidung braucht man beim
    naechsten Mal, wenn niemand danebensitzt."""
    s = _quelle()
    assert "curl-Ausstieg {out.returncode}" in s
    assert "out.stderr" in s, "curls eigene Meldung gehoert in den Fehlertext"


def test_kein_scheintest_fuer_das_verhalten():
    """BEWUSST KEIN Verhaltenstest hier — und das ist die ehrliche Variante.

    Der Halbierungs-Zweig steckt in einer inneren `flush()` von `push()`, die Parquet liest
    und curl aufruft. Ihn echt durchzuspielen hiesse, beides nachzubauen; ein Test, der
    dabei mehr Attrappe als Pruefung ist, gibt Sicherheit, die er nicht hat. Mein erster
    Anlauf tat genau das — er „bestand", indem er sich selbst uebersprang.

    Die beiden Tests darueber nageln die Bedingung fest, auf die es ankommt. Der echte
    Beweis kommt aus dem naechsten Tageslauf: steht dort „Zeitgrenze (curl) bei N Zeilen —
    halbiert erneut" statt „HTTP 000", greift die Korrektur.
    """
    s = _quelle()
    assert 'woher = "curl" if zeitueberschreitung else "Datenbank"' in s, \
        "die Meldung muss sagen, WER aufgegeben hat — sonst ist der Beweis nicht lesbar"
