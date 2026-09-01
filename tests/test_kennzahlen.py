"""Das Kennzahlen-Verzeichnis und die Ketten, die daran hängen.

⚠ Der Fehler, gegen den diese Datei steht: `docsignals` erkannte fünfzehn Signale, das
Parquet trug fünfzehn, der Export schrieb sieben, der API-Typ kannte sieben, der Renderer
zeigte sieben. Sechs Kennzahlen waren gebaut, gemessen, gespeichert und wurden nie gezeigt.
Keine Zeile Code war falsch; es war dreimal dieselbe Liste, von Hand geführt.
"""
from __future__ import annotations

import re
from pathlib import Path

from govisor import kennzahlen as kz

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"


def test_jede_kennzahl_nennt_ihre_bezugsgroesse():
    """Der Dataclass-Wächter greift schon beim Import; hier steht er noch einmal als
    ausdrückliche Zusage, damit `keine` eine ENTSCHEIDUNG bleibt und kein Vergessen."""
    for k in kz.ALLE:
        assert k.bezug in kz.BEZUEGE
        if k.bezug != "keine":
            assert k.wogegen, f"{k.schluessel} hat einen Bezug ohne Vergleichswert"


def test_schluessel_sind_eindeutig():
    s = [k.schluessel for k in kz.ALLE]
    assert len(s) == len(set(s)), "doppelter Schlüssel im Verzeichnis"


def test_der_export_zaehlt_keine_spalten_mehr_auf():
    """⚠ Die Stelle, an der die sechs Felder verlorengingen."""
    quelle = (WURZEL / "scripts" / "export_doc_signals.py").read_text(encoding="utf-8")
    # ⚠ Den Docstring MIT ausschneiden, nicht nur die `#`-Zeilen. Er nennt die alte Liste,
    # um vor ihr zu warnen — ein Test über den Rohtext hinge an der eigenen Begründung.
    # Dieselbe Falle ist heute dreimal zugeschlagen.
    ohne_doc = re.sub(r'^"""(?:.|\n)*?"""', "", quelle, count=1)
    code = "\n".join(z for z in ohne_doc.splitlines() if not z.lstrip().startswith("#"))
    assert "kennzahlen.DOC_SIGNALE" in code
    assert "guarantee_required, binding_days" not in code, "wieder eine getippte Spaltenliste"


def test_der_export_laeuft_wirklich_durch():
    """⚠ Ein Test, der nur den Import prüft, hätte den Fehler NICHT gefunden. Beim Ausbau des
    Verzeichnisses wurde `quelle` von der Spalte zur Datei; der Export las weiter `quelle`
    und baute `SELECT notice_id, doc_signals.parquet, doc_signals.parquet, …`. Die
    Textprüfung darunter war grün, das Skript kaputt. Deshalb hier die echte Rechnung."""
    quelle = (WURZEL / "scripts" / "export_doc_signals.py").read_text(encoding="utf-8")
    assert "kennzahlen.spalten(felder)" in quelle, "baut die Spaltenliste wieder selbst"
    assert "k.quelle ==" not in quelle, "vergleicht wieder gegen die Datei statt die Spalte"
    # Die Spaltenliste muss gegen das echte Parquet binden.
    src = WURZEL / "data" / "docs" / "DE" / "doc_signals.parquet"
    if not src.exists():
        return
    import duckdb
    spalten = ", ".join(kz.spalten(kz.DOC_SIGNALE))
    duckdb.connect().execute(
        f"select notice_id, {spalten} from read_parquet('{src.as_posix()}') limit 1").fetchall()


def test_das_parquet_traegt_keine_unbekannte_spalte():
    """Ein neues Signal in `docsignals` soll AUFFALLEN, nicht liegenbleiben. Läuft nur, wenn
    das Parquet da ist — sonst ist nichts zu prüfen."""
    src = WURZEL / "data" / "docs" / "DE" / "doc_signals.parquet"
    if not src.exists():
        return
    import duckdb
    spalten = {c[0] for c in duckdb.connect().execute(
        f"describe select * from read_parquet('{src.as_posix()}') limit 1").fetchall()}
    # `notice_id` ist der Schlüssel, `evidence` der Belegtext je Signal — beides sind keine
    # eigenen Kennzahlen und stehen deshalb bewusst nicht im Verzeichnis.
    ohne = spalten - {"notice_id", "evidence"} - set(kz.spalten(kz.DOC_SIGNALE))
    assert not ohne, (
        f"Signale im Parquet, aber nicht im Verzeichnis: {sorted(ohne)}. "
        "Eintragen, sonst kommen sie nie im Frontend an.")


def test_der_api_typ_fuehrt_genau_die_schluessel():
    """Die zweite Stelle, an der dieselbe Liste stand."""
    quelle = (WEB / "app" / "api" / "lead-detail" / "route.ts").read_text(encoding="utf-8")
    block = quelle[quelle.index("type DocSignals = {"):]
    block = block[:block.index("};")]
    im_typ = set(re.findall(r"(\w+)\s*:", block))
    erwartet = {k.schluessel for k in kz.DOC_SIGNALE}
    assert erwartet <= im_typ, f"im API-Typ fehlen: {sorted(erwartet - im_typ)}"
    assert im_typ <= erwartet, f"im API-Typ zu viel: {sorted(im_typ - erwartet)}"


def test_der_renderer_zeigt_sie_auch():
    """Die dritte Stelle. ⚠ Ein Feld im Typ, das niemand rendert, ist genau der Zustand von
    vorher, nur eine Ebene höher."""
    code = (WEB / "lib" / "explorerCore.js").read_text(encoding="utf-8")
    block = code[code.index("const anforderungen"):]
    block = block[:block.index("// Leistungsumfang")]
    # `evidence` ausgenommen (kein Feld), `bindingDays`/`guarantee` standen schon drin.
    for k in kz.DOC_SIGNALE:
        assert f"s.{k.schluessel}" in block, f"{k.schluessel} wird nicht angezeigt"


def test_das_inventar_ist_vollstaendig():
    """⚠ „Halbfertig" war Svens Wort dafür, und er hatte recht: ein Verzeichnis, das nur die
    gerade angefassten Kennzahlen führt, ist eine Notiz, kein Verzeichnis. Die Zahl darf
    wachsen; fällt sie, hat jemand etwas gelöscht, ohne es zu merken."""
    assert len(kz.ALLE) >= 135, f"nur noch {len(kz.ALLE)} Kennzahl-Plätze"
    assert len(kz.nach_flaeche()) >= 11, "eine ganze Fläche fehlt"


def test_keine_kennzahl_steht_zweimal_auf_derselben_flaeche():
    """⚠ Elf solche Zeilen sind beim Aufbau entstanden: dieselbe Kachel einmal mit exakter
    Quellspalte und einmal aus dem Inventar. Dieselbe Zahl auf ZWEI Flächen ist dagegen in
    Ordnung und Absicht."""
    import re
    gesehen = set()
    for k in kz.ALLE:
        # ⚠ Die KLAMMER NICHT WEGWERFEN. Sie ist hier die Unterscheidung, nicht Beiwerk:
        # „Volumen belegt (Pipeline)" und „Volumen belegt (Bindung)" sind zwei Zahlen in
        # zwei Bereichen derselben Ansicht, und „Vergaben pro Jahr (Anbieter)" ist die Zahl
        # einer Firma, nicht einer Vergabestelle. Ein Abgleich ohne Klammer meldete sie als
        # Doppelung und hätte beim Aufräumen echte Kennzahlen gelöscht.
        norm = re.sub(r"[^a-zäöüß0-9]", "", k.label.lower())
        paar = (k.flaeche, norm)
        assert paar not in gesehen, f"{k.label} steht zweimal auf {k.flaeche}"
        gesehen.add(paar)


def test_jede_flaeche_nennt_ihre_quelle():
    for k in kz.ALLE:
        assert k.flaeche, f"{k.schluessel} ohne Fläche"
        assert k.quelle, f"{k.schluessel} ohne Quelle"


def test_eine_spalte_gibt_es_nur_wo_es_eine_gibt():
    """⚠ Ein erfundener Spaltenname wäre schlimmer als die Lücke: der Export würde ihn
    auswählen und scheitern, oder schlimmer, still eine falsche Spalte lesen."""
    mit = [k for k in kz.ALLE if k.spalte]
    assert all(k.flaeche in ("unterlagen", "strategie") for k in mit)
    assert len(mit) == len(kz.DOC_SIGNALE) + len(kz.VERGABESTELLEN)


def test_die_bezugsgroessen_stimmen_mit_der_anzeige():
    """Nur was einen Bezug hat, darf eine Leiste bekommen. Umgekehrt: eine Kennzahl mit
    Bezug `markt` und ohne Vergleichswert in der Anzeige ist eine unerfüllte Zusage."""
    stellen = {k.schluessel for k in kz.VERGABESTELLEN}
    code = (WEB / "components" / "explorer" / "StrategieView.tsx").read_text(encoding="utf-8")
    for s in stellen:
        assert f"marktLage(alle" in code and s in code, f"{s} ohne Marktwert in der Ansicht"
