"""Was die Seite über sich selbst sagt — und die eine Angabe, die bewusst fehlt.

Für einen Abrufer, ob Suchmaschine oder Sprachmodell, zählt, was ohne JavaScript im HTML
steht. Die Signale dafür sind billig zu bauen und still zu verlieren: ein Umbau am Layout,
und `canonical` oder die Strukturdaten sind weg, ohne dass irgendetwas bricht. Niemand
merkt es, bis die Seite Monate später nicht auftaucht.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
LAYOUT = WEB / "app" / "layout.tsx"

# Die Seiten, die ein Fremder ohne Konto sieht. Nur sie sind überhaupt indizierbar —
# alles hinter dem Anmelde-Tor gehört in keine Sitemap und braucht kein hreflang.
OEFFENTLICH = [
    WEB / "components" / "Landing.tsx",
    WEB / "app" / "start" / "page.tsx",
    WEB / "app" / "login" / "page.tsx",
]


def test_die_maschinen_signale_stehen_noch_im_layout():
    """Fünf Angaben, jede einzeln verlierbar."""
    s = LAYOUT.read_text(encoding="utf-8")
    for name, muster in (
        ("metadataBase", r"metadataBase:\s*new URL"),
        ("canonical", r"alternates:\s*\{\s*canonical"),
        ("Open Graph", r"openGraph:\s*\{"),
        ("Twitter-Karte", r"twitter:\s*\{"),
        ("Strukturdaten", r'type="application/ld\+json"'),
    ):
        assert re.search(muster, s), f"{name} ist aus dem Layout verschwunden"


def test_robots_und_sitemap_gibt_es_und_sie_sind_erreichbar():
    """Eine robots.txt hinter dem Anmelde-Tor ist keine.

    ⚠ Genau das war sie am 2026-08-30, wenige Minuten nach dem Anlegen: `GET /robots.txt`
    beantwortete die Middleware mit `/login?weiter=%2Frobots.txt`. Aufgefallen ist es nur,
    weil ich sie danach wirklich abgerufen habe statt anzunehmen, dass sie ausgeliefert wird.
    """
    assert (WEB / "app" / "robots.ts").exists(), "robots.ts fehlt"
    assert (WEB / "app" / "sitemap.ts").exists(), "sitemap.ts fehlt"

    mw = (WEB / "middleware.ts").read_text(encoding="utf-8")
    for pfad in ('"/robots.txt"', '"/sitemap.xml"'):
        assert pfad in mw, f"{pfad} steht nicht mehr in der Ausnahmeliste — ein Crawler " \
                           f"bekommt dort wieder eine Umleitung auf /login"

    # Und durch die Baustellen-Sperre: eine schwarze HTML-Seite als Antwort auf robots.txt
    # liest kein Crawler als Regelwerk, er faellt auf „alles erlaubt" zurueck.
    vorhang = mw[mw.index("if (BLACKOUT)"):mw.index("return blackPage();")]
    for pfad in ("/robots.txt", "/sitemap.xml"):
        assert pfad in vorhang, f"{pfad} kommt nicht mehr durch die Baustellen-Sperre"


def _uebersetzbare_stellen() -> dict[str, int]:
    """Wie viele Textstellen der öffentlichen Seiten über den Katalog laufen."""
    aus = {}
    for p in OEFFENTLICH:
        s = p.read_text(encoding="utf-8") if p.exists() else ""
        aus[p.name] = len(re.findall(r'\bt[k]?\(\s*["`]', s))
    return aus


def test_hreflang_fehlt_solange_es_nichts_zu_verlinken_gibt():
    """Die eine Angabe, die bewusst NICHT da ist — und der Wächter über ihrer Begründung.

    Die Anwendung spricht drei Sprachen, aber nur hinter der Anmeldung: die öffentlichen
    Seiten tragen ihren Text fest verdrahtet auf Deutsch im JSX. Gemessen am 2026-08-30:
    40 deutsche Textstellen, keine einzige im Katalog, kein einziger `t()`-Aufruf.

    Es gibt also keine englische oder französische Startseite, auf die ein `hreflang` zeigen
    könnte. Wer Sprach-Routen anlegt, ohne vorher die Texte übersetzbar zu machen, liefert
    unter `/en` und `/fr` denselben deutschen Inhalt aus — `hreflang` wäre dann eine
    Falschangabe, und drei URLs mit gleichem Text sind schlechter als eine saubere.

    ⚠ DIESER TEST BEWACHT KEINEN ZUSTAND, SONDERN EINE BEGRÜNDUNG. Sobald die öffentlichen
    Seiten übersetzbar werden, ist der Grund weg — und dann soll auffallen, dass `hreflang`
    fehlt, statt dass die Auslassung als Entscheidung weiterlebt, die niemand mehr kennt.
    """
    stellen = _uebersetzbare_stellen()
    layout = LAYOUT.read_text(encoding="utf-8")
    hat_hreflang = re.search(r"alternates:[^}]*languages", layout, re.S) is not None

    if sum(stellen.values()) == 0:
        assert not hat_hreflang, (
            "hreflang ist gesetzt, obwohl die oeffentlichen Seiten nur Deutsch koennen — "
            "die Angabe zeigt dann auf Inhalte, die es nicht gibt")
        return

    assert hat_hreflang, (
        "Die oeffentlichen Seiten sind jetzt uebersetzbar:\n  "
        + "\n  ".join(f"{n}: {k} t()-Aufrufe" for n, k in stellen.items() if k)
        + "\nDamit entfaellt der Grund, aus dem `alternates.languages` im Layout fehlt.\n"
          "Jetzt gehoeren Sprach-Routen (/en, /fr) und hreflang dazu — sonst sind die\n"
          "uebersetzten Fassungen von aussen weiterhin unauffindbar.")


def test_die_startseite_bleibt_eine_server_komponente():
    """Die eine Seite, deren Text ein Abrufer wirklich liest.

    ⚠ HIER STAND EIN TEST MIT FALSCHER PRAEMISSE. Er verlangte von allen drei oeffentlichen
    Seiten, dass sie keine Client-Komponenten sind — mit der Begruendung, deren Text stehe
    sonst nicht im HTML. Das stimmt in Next so nicht: Client-Komponenten werden beim ersten
    Aufruf ebenfalls server-gerendert. Nachgemessen am laufenden Server: `/start` liefert
    506, `/login` 706 Zeichen Fliesstext, obwohl beide `"use client"` tragen. Der Test war
    rot, und zwar zu Unrecht.

    Was bleibt, ist die enge, belastbare Aussage: die STARTSEITE ist die einzige Seite mit
    Inhalt, den jemand lesen soll (6.301 Zeichen, gemessen am 2026-08-30). Als
    Server-Komponente haengt ihr Text an nichts, was erst im Browser passiert — kein
    `useEffect`, kein Nachladen, keine Bedingung, die auf dem Server anders ausfaellt.
    `/start` und `/login` sind Formulare; dass sie im Client leben, ist richtig so.
    """
    landing = WEB / "components" / "Landing.tsx"
    kopf = landing.read_text(encoding="utf-8")[:200]
    assert '"use client"' not in kopf and "'use client'" not in kopf, (
        "Landing.tsx ist eine Client-Komponente geworden. Das muss nicht heissen, dass der "
        "Text verschwindet — aber er haengt dann an dem, was im Browser passiert, und genau "
        "das laesst sich von hier aus nicht mehr pruefen.")
