"""Ein Ausfall darf nicht wie ein leeres Ergebnis aussehen.

Der Markenkern lautet „Unbekanntes bleibt sichtbar, statt plausibel erfunden zu werden".
Ein leeres Ergebnis ist aber eine AUSSAGE: „hier gibt es nichts". Kommt dieselbe Antwort
auch dann, wenn der Datenspeicher nicht erreichbar ist, hat das Produkt einen Ausfall in
eine Auskunft verwandelt — genau die Verwechslung, gegen die es antritt.

⚠ SO WAR ES BIS ZUM 2026-09-04. `loadDataFile` gab fuer jeden Fehlschlag `null` zurueck:
Datei nicht da, S3 antwortet 500, Netz weg, Signatur abgelehnt. Fuenf Routen machten daraus
ein leeres Ergebnis mit HTTP 200:

    /api/branchen    jede Branche zeigt 0 Leads
    /api/plz-geo     `json ?? "{}"` — die Umkreissuche findet nichts
    /api/markt       Marktbloecke leer
    /api/strategie   ausdruecklich `{ status: 200 }`
    /api/kalender    keine Fristen, fuer alle Leads

Der Kommentar in `dataSource.ts` fordert die Unterscheidung seit jeher („eine Stoerung, die
man sehen muss"); sie stand nur im `console.error` und erreichte den Aufrufer nie. Ein
Protokoll im Server-Log sieht niemand, der die Seite benutzt.
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
ROUTEN = ("branchen", "plz-geo", "markt", "strategie", "kalender")


def test_die_regel_stimmt():
    """Der Node-Pruefer gegen die ECHTE Funktion, nicht gegen eine Abschrift."""
    skript = WEB / "scripts" / "pruefe-ladegrund.mjs"
    p = subprocess.run(["node", str(skript)], capture_output=True, text=True)
    assert p.returncode == 0, f"die Ladegrund-Regel stimmt nicht:\n{p.stdout}{p.stderr}"


@pytest.mark.parametrize("route", ROUTEN)
def test_route_unterscheidet_ausfall_von_leer(route):
    """Jede dieser Routen muss den Stoerfall eigens beantworten."""
    q = (WEB / "app" / "api" / route / "route.ts").read_text(encoding="utf-8")
    assert "ladeMitGrund" in q, (
        f"/api/{route} laedt ohne Grund — dann kann sie einen Ausfall nicht von einem "
        f"leeren Ergebnis unterscheiden.")
    # ⚠ VOKABELN GENUEGEN NICHT. Der erste Entwurf pruefte nur, ob die Woerter
    # `DATEN_STOERUNG` und `503` irgendwo in der Datei stehen. Die Gegenprobe lief prompt
    # gruen durch, obwohl ich die Bedingung auf `if (false)` gesetzt hatte — die Woerter
    # standen ja noch da. Gesucht ist der ZUSAMMENHANG: eine echte Abfrage auf den Grund,
    # und kurz darauf die 503.
    import re as _re
    stellen = [m.end() for m in _re.finditer(r"grund === DATEN_STOERUNG", q)]
    assert stellen, (
        f"/api/{route} vergleicht nirgends gegen DATEN_STOERUNG. Ein leeres Ergebnis mit "
        f"HTTP 200 ist hier eine Behauptung ueber Daten, die niemand gelesen hat.")
    # Zwei Bauformen sind erlaubt: entweder folgt die 503 direkt, oder die Stelle setzt
    # einen Merker, weil ueber viele Dateien gesammelt wird (so macht es `/api/kalender`).
    # In beiden Faellen muss die Route die 503 ueberhaupt kennen.
    direkt = any("503" in q[i:i + 260] for i in stellen)
    ueber_merker = any("= true" in q[i:i + 120] for i in stellen) and "503" in q
    assert direkt or ueber_merker, (
        f"/api/{route} erkennt die Stoerung, antwortet aber nicht mit 503.")


def test_der_knappe_weg_bleibt_derselbe_weg():
    """`loadDataFile` muss ueber `ladeMitGrund` laufen — sonst driften zwei Ladepfade.

    Zwei getrennte Fassungen waeren die naechste stille Falle: eine mit Grund, eine ohne,
    und die Aufrufer waehlen zufaellig.
    """
    q = (WEB / "lib" / "dataSource.ts").read_text(encoding="utf-8")
    i = q.index("export async function loadDataFile")
    rumpf = q[i:i + 400]
    assert "ladeMitGrund" in rumpf, (
        "`loadDataFile` holt die Datei wieder selbst — dann gibt es zwei Ladepfade, die "
        "auseinanderlaufen koennen.")


def test_branchen_brennt_einen_ausfall_nicht_ein():
    """⚠ Der schwerste Teil des Befunds.

    `/api/branchen` legt den Suchkorpus in einer Modulvariablen ab, die NIE zurueckgesetzt
    wird. War der Speicher beim ersten Aufruf nicht erreichbar, stand dort bis zum naechsten
    Neustart des Prozesses ein LEERER Korpus — und jede Suche bekam „0 Treffer" mit HTTP 200,
    auch lange nachdem der Speicher wieder antwortete. Aus einer voruebergehenden Stoerung
    wurde eine dauerhafte Falschauskunft.
    """
    q = (WEB / "app" / "api" / "branchen" / "route.ts").read_text(encoding="utf-8")
    for name in ("CORPUS", "GEO"):
        i = q.index(f"    {name} = out;")
        davor = q[max(0, i - 300):i]
        assert "throw new DatenStoerung" in davor, (
            f"`{name}` wird auch nach einer Stoerung gesetzt — der leere Korpus bleibt dann "
            f"bis zum Neustart stehen.")
    for merker in ("corpusPromise", "geoPromise"):
        assert f"{merker}.catch(() => {{ {merker} = null; }});" in q, (
            f"`{merker}` behaelt einen fehlgeschlagenen Versuch — dann wirft auch jeder "
            f"spaetere Aufruf dieselbe alte Stoerung, obwohl der Speicher wieder da ist.")
