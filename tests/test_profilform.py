"""Ein Profil aus der Datenbank ist nicht das, was die Engine erwartet.

⚠ GEMESSEN AM 2026-09-11, beim Vorbereiten einer Vorfuehrung. `loadProfile()` holte den
`profile`-jsonb aus Supabase und gab ihn mit `as Profile` zurueck — einem Typ mit 18
Pflichtfeldern. Der Cast war eine Behauptung, kein Beleg: zurueck kam, was jemand
hineingeschrieben hatte. Ein per Skript gesetztes Profil trug 5 der 18 Felder.

Die Folge war kein Schoenheitsfehler: `matchLead` starb an `p.nachbarFields.includes(...)`
beim ERSTEN Rendern der Lead-Liste. Der Nutzer sah

    Application error: a client-side exception has occurred

und sonst nichts. Keine halbe Seite, kein Hinweis, kein Weg zurueck — und das erst NACH
erfolgreicher Anmeldung, also an der Stelle, an der er dem Produkt schon vertraut hat.

Zwei Ladepfade trugen dieselbe Luecke: `loadProfile()` aus der Datenbank und der Rueckfall
auf `localStorage`. Beide normalisieren jetzt ueber `buildProfile`.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_die_profilform_stimmt():
    """Der Node-Pruefer gegen die ECHTE Engine, nicht gegen eine Abschrift."""
    p = subprocess.run(["node", str(WEB / "scripts" / "pruefe-profilform.mjs")],
                       capture_output=True, text=True)
    assert p.returncode == 0, f"die Profilform stimmt nicht:\n{p.stdout}{p.stderr}"


def test_beide_ladepfade_normalisieren():
    """⚠ ZWEI PFADE, EINE LUECKE — und der zweite faellt leicht hinten runter.

    Geprueft wird der ZUSAMMENHANG im entkommentierten Code, nicht ein Wort: an jeder
    Stelle, die ein Profil in den Zustand gibt, muss `buildProfile` stehen. Ein Test, der
    nur nach dem Wort sucht, faende die Erklaerung daneben (F13).
    """
    def ohne_kommentar(s: str) -> str:
        raus, i, n = [], 0, len(s)
        while i < n:
            if s[i] == "/" and i + 1 < n and s[i + 1] == "/":
                while i < n and s[i] != "\n":
                    raus.append(" ")
                    i += 1
                continue
            if s[i] == "/" and i + 1 < n and s[i + 1] == "*":
                while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                    raus.append("\n" if s[i] == "\n" else " ")
                    i += 1
                raus.append("  ")
                i += 2
                continue
            raus.append(s[i])
            i += 1
        return "".join(raus)

    auth = ohne_kommentar((WEB / "lib" / "supabase" / "auth.ts").read_text(encoding="utf-8"))
    i = auth.index("export async function loadProfile")
    rumpf = auth[i:auth.index("\n}", i)]
    assert "buildProfile(" in rumpf, (
        "loadProfile gibt den Datenbank-Blob wieder ungeprueft zurueck. Fehlt darin ein "
        "Feld, stirbt die Lead-Liste beim ersten Rendern mit einer weissen Seite.")

    shell = ohne_kommentar(
        (WEB / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8"))
    for treffer in ("setRealProfile(JSON.parse(", "setRealProfile(buildProfile("):
        if treffer in shell:
            assert treffer.startswith("setRealProfile(buildProfile"), (
                "der localStorage-Rueckfall setzt das Profil wieder roh — dieselbe Luecke "
                "wie in loadProfile, nur trifft sie ausschliesslich den Nutzer, dessen "
                "Browser ein altes Profil liegen hat.")
