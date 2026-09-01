"""Aktivierung D: Vergabestelle beobachten, ohne eine Vorhersage zu behaupten.

⚠ Das Übergabepapier schlägt vor: „Diese Stelle schreibt etwa alle vier Jahre aus. Sollen wir
euch erinnern?" Am 2026-09-01 nachgemessen ist das nicht belegbar: `contract_succession`
liefert für JEDE grosse Vergabestelle einen Median-Abstand von 1,0 Jahren, und das ist eine
Eigenschaft des Nachfolge-Modells, kein Vertragszyklus. Weder `buyer_loyalty` noch
`retender_signal` tragen eine Zykluslänge.
"""
from __future__ import annotations

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"
BW = (WEB / "lib" / "supabase" / "buyerWatch.ts").read_text(encoding="utf-8")
ALERTS = (WEB / "app" / "api" / "alerts" / "route.ts").read_text(encoding="utf-8")
SHELL = (WEB / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
CORE = (WEB / "lib" / "explorerCore.js").read_text(encoding="utf-8")


def _ohne_kommentar(text: str) -> str:
    """⚠ Kommentare raus, sonst schlägt der Test an der BEGRÜNDUNG an: sie zitiert den Satz
    aus dem Papier, um zu erklären, warum wir ihn nicht benutzen. Diese Falle ist heute zum
    vierten Mal zugeschlagen."""
    raus, im_block = [], False
    for z in text.splitlines():
        t = z.strip()
        if t.startswith("/*"):
            im_block = True
        if im_block:
            if "*/" in t:
                im_block = False
            continue
        if t.startswith("//") or t.startswith("*"):
            continue
        raus.append(z)
    return "\n".join(raus)


def test_keine_zyklus_behauptung():
    """⚠ Der Kern. Eine erfundene Jahreszahl wäre genau die Sorte Behauptung, gegen die
    dieses Produkt antritt. Geprüft wird der ANGEZEIGTE Text, nicht die Erklärung daneben."""
    for datei in (BW, CORE):
        code = _ohne_kommentar(datei)
        assert "alle vier Jahre" not in code
        assert "schreibt etwa alle" not in code


def test_die_beobachtung_wird_zugestellt():
    """⚠ Ein Schalter ohne Zustellung wäre „gebaut, nicht verdrahtet" — die Fehlerklasse,
    gegen die in diesem Projekt der halbe Tag draufgeht."""
    assert "user_buyer_watch" in ALERTS
    assert '"buyer_neu"' in ALERTS or "buyer_neu" in ALERTS


def test_der_posteingang_laeuft_nicht_ueber():
    """⚠ Wer DB Netz beobachtet, bekäme beim ersten Klick hunderte Meldungen und fände danach
    seine Fristen nicht mehr. Ein Posteingang, der überläuft, ist so nutzlos wie ein leerer."""
    stelle = ALERTS[ALERTS.index("if (stellen?.length)"):]
    stelle = stelle[:stelle.index("const { data, error }")]
    assert "proStelle" in stelle and ">= 10" in stelle


def test_der_kaeufer_steht_in_der_schlanken_datei():
    """⚠ Der einzige andere Weg zum Käufernamen wären die sieben vollen Lead-Dateien, 110 MB.
    Genau davon ist `leads-fristen.json` die Abkehr."""
    exp = (WURZEL / "scripts" / "export_web_leads.py").read_text(encoding="utf-8")
    block = exp[exp.index("def _frist_zeile"):exp.index("def export_branche")]
    assert '"buyer":' in block
    assert 'buyer?: string | null' in (WEB / "lib" / "alerts.ts").read_text(encoding="utf-8")


def test_der_schalter_springt_erst_nach_dem_speichern():
    """⚠ Ein Schalter, der sofort umschaltet und still nichts speichert, ist schlimmer als
    keiner: der Nutzer glaubt, er bekommt Bescheid, und hört nie wieder etwas."""
    stelle = SHELL[SHELL.index('case "buyerwatch"'):]
    stelle = stelle[:stelle.index("break;\n      }")]
    assert "if (neu === null) return;" in stelle
    assert stelle.index("toggleBuyerWatch") < stelle.index('aria-pressed", String(neu)')


def test_ein_fehlschlag_erreicht_die_oberflaeche():
    """`null` heisst „nicht gespeichert" und darf nicht wie „aus" aussehen."""
    assert "Promise<boolean | null>" in BW
    assert "return error ? null : true;" in BW
