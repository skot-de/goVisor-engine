"""Impressum und Datenschutzerklärung: erreichbar, vollständig, und nichts erfunden.

Drei Sorten Prüfung, in der Reihenfolge ihrer Tragweite:

1. **Erreichbarkeit.** Eine Anbieterkennung hinter der Coming-Soon-Sperre ist keine. Die
   Pflicht aus § 5 DDG knüpft an die Erreichbarkeit des Angebots, nicht an den Zustand
   der Baustelle. Dasselbe gilt für die Datenschutzerklärung: wer wissen will, was mit
   seinen Daten geschieht, muss das können, BEVOR er sich anmeldet.
2. **Vollständigkeit.** Was das Gesetz verlangt, muss dastehen. Fehlt es, meldet sich der
   Test, bis es da ist.
3. **Keine Erfindungen.** Angaben, die niemand mitgeteilt hat, dürfen nicht als
   Platzhaltertext auf einer Pflichtseite landen. Eine erfundene Registernummer ist
   schlimmer als eine fehlende, weil sie richtig aussieht.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANBIETER = ROOT / "web" / "lib" / "anbieter.ts"
IMPRESSUM = ROOT / "web" / "app" / "impressum" / "page.tsx"
DATENSCHUTZ = ROOT / "web" / "app" / "datenschutz" / "page.tsx"
MIDDLEWARE = ROOT / "web" / "middleware.ts"
SITEMAP = ROOT / "web" / "app" / "sitemap.ts"


def _text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


# ── 1. Erreichbarkeit ─────────────────────────────────────────────────────────────────

def test_pflichtseiten_kommen_durch_beide_tore():
    t = _text(MIDDLEWARE)
    liste = t.split("const RECHTLICHES")[1].split("]")[0]
    for pfad in ("/impressum", "/datenschutz"):
        assert pfad in liste, f"{pfad} steht nicht in RECHTLICHES"
    assert "const DURCH_DIE_SPERRE = [...GROUNDING, ...RECHTLICHES]" in t, (
        "RECHTLICHES ist nicht mit der Sperren-Ausnahme verbunden")
    assert "const OFFEN = [...DURCH_DIE_SPERRE" in t, (
        "Die Pflichtseiten stehen nicht in OFFEN — ein Besucher landete auf /login.")
    # Die Ausnahme muss in der Kette stehen, die `blackPage` verhindert, nicht irgendwo.
    kette = t.split("return blackPage(pfad);")[0].rsplit("if (!unlocked", 1)[-1]
    assert "istGrounding" in kette, "Die Pflichtseiten bekämen die schwarze Seite."


def test_pflichtseiten_stehen_in_der_sitemap():
    t = _text(SITEMAP)
    for pfad in ("/impressum", "/datenschutz"):
        assert pfad in t, f"{pfad} fehlt in der Sitemap"


def test_pflichtseiten_brauchen_kein_javascript():
    """Wer eine Pflichtangabe sucht, soll sie auch ohne Javascript finden."""
    for p in (IMPRESSUM, DATENSCHUTZ):
        t = _text(p)
        assert not t.lstrip().startswith('"use client"'), f"{p.name} ist eine Client-Komponente"
        for haken in ("useState(", "useEffect(", "fetch("):
            assert haken not in t, f"{haken} in {p.name}: das braucht Javascript."


def test_seiten_verweisen_aufeinander():
    """Beide Seiten sind Pflicht, und wer die eine findet, soll die andere finden."""
    assert "/datenschutz" in _text(IMPRESSUM), "Impressum verlinkt die Datenschutzerklärung nicht"
    assert "/impressum" in _text(DATENSCHUTZ), "Datenschutzerklärung verlinkt das Impressum nicht"


# ── 2. Vollständigkeit ────────────────────────────────────────────────────────────────

def test_pflichtangaben_nach_ddg_stehen_da():
    """Firma, Anschrift, Vertretung und Umsatzsteuer-ID sind da."""
    t = _text(ANBIETER)
    for feld, muster in (
        ("Firma", r'firma: "skot UG'),
        ("Strasse", r'strasse: "[^"]+"'),
        ("PLZ", r'plz: "\d{5}"'),
        ("Ort", r'ort: "[^"]+"'),
        ("Vertretung", r'vertreten: "[^"]+"'),
        ("USt-IdNr", r'ustIdNr: "DE\d{9}"'),
    ):
        assert re.search(muster, t), f"Pflichtangabe fehlt oder hat ein anderes Format: {feld}"


def test_impressum_ist_vollstaendig():
    """⚠ FÜR EINE UG IST DIE REGISTEREINTRAGUNG PFLICHT (§ 5 Abs. 1 Nr. 4 DDG).

    Dieser Test ist rot, solange Registergericht, Registernummer oder eine elektronische
    Kontaktmöglichkeit fehlen. Das ist Absicht und kein Rauschen: ohne diese Angaben ist
    die Anbieterkennung unvollständig, und unvollständig ist bei einer Pflichtangabe ein
    Mangel, kein Feinschliff.

    **Behoben wird er mit drei Zeilen** in `web/lib/anbieter.ts`:
    `registergericht`, `registernummer` und `email` setzen. Die Werte stehen im
    Handelsregisterauszug; die Mailadresse entscheidet der Geschäftsführer.
    """
    t = _text(ANBIETER)
    fehlt = []
    for feld in ("registergericht", "registernummer", "email"):
        if re.search(rf'{feld}: null as', t):
            fehlt.append(feld)
    assert not fehlt, (
        "Die Anbieterkennung ist unvollständig, es fehlen: " + ", ".join(fehlt) + ". "
        "Zu setzen in web/lib/anbieter.ts. Solange die Seite nicht öffentlich erreichbar "
        "ist, ist das kein akuter Rechtsverstoß, vor dem Start aber zwingend.")


VERARBEITER = ROOT / "web" / "lib" / "verarbeiter.ts"


def test_drittland_absatz_behauptet_keine_grundlage_die_fehlt():
    """⚠ Der Satz „erfolgt auf Grundlage der Standardvertragsklauseln" ist eine BEHAUPTUNG.

    Er sagt, dass ein Vertrag geschlossen wurde. Liegt er nicht vor, ist er falsch, und
    zwar in genau dem Dokument, mit dem man seine Rechtmässigkeit belegt. Am 2026-10-02
    stand er hier, ohne dass ein einziger AV-Vertrag nachgewiesen war; ich hatte ihn aus
    der üblichen Form übernommen. Aufgefallen ist es erst, als eine Nachbarsitzung
    dieselbe Voraussetzung unabhängig aufschrieb.

    Deshalb haengt der Absatz jetzt am gepflegten Vertragsstand, und dieser Test ist rot,
    solange einer offen ist. **Das ist eine kaufmännische Aufgabe, keine technische**:
    kein Code kann einen Vertrag herbeiführen, er kann nur verhindern, dass man ihn
    vergisst und trotzdem behauptet.
    """
    # ⚠ PRO EINTRAG TRENNEN, nicht ueber die ganze Datei suchen. Der erste Versuch war
    # `name: "…"[\s\S]{0,1400}?avv: "offen"` — nicht gierig, aber ueber Eintragsgrenzen
    # hinweg: „Supabase" fand den `avv: "offen"` des NAECHSTEN Eintrags und wurde gemeldet,
    # waehrend Vercel durchrutschte. Ein Test, der die falschen Namen nennt, ist
    # schlimmer als keiner — man behebt dann das Falsche.
    t = _text(VERARBEITER)
    rumpf = t.split("export const VERARBEITER", 1)[1]
    eintraege = re.split(r"\n  \{", rumpf)
    offen = [re.search(r'name: "([^"]+)"', e).group(1)
             for e in eintraege
             if re.search(r'name: "', e) and re.search(r'^\s*avv: "offen"', e, re.M)]
    assert not offen, (
        "Ohne Auftragsverarbeitungsvertrag darf die Datenschutzerklärung keine "
        "Rechtsgrundlage für die Drittlandübermittlung nennen. Offen: "
        + ", ".join(offen) + ". Stand pflegen in web/lib/verarbeiter.ts, sobald die "
        "Verträge vorliegen.")


def test_die_seite_rendert_den_vertragsstand_statt_ihn_zu_tippen():
    """⚠ Sonst stimmt der Test, und die Seite sagt trotzdem etwas anderes."""
    t = _text(DATENSCHUTZ)
    assert "ohneVertrag()" in t, (
        "Abschnitt 12 haengt nicht am Vertragsstand — dann kann er eine Grundlage "
        "behaupten, die es nicht gibt, ohne dass ein Test es merkt.")
    assert "VERARBEITER.map" in t, "Die Empfängertabelle kommt nicht aus `verarbeiter.ts`"


def test_datenschutz_nennt_die_gemessenen_empfaenger():
    """Die Erklärung muss die Dienstleister nennen, die der Code tatsächlich aufruft."""
    v = _text(VERARBEITER)
    for empfaenger in ("Supabase", "Vercel", "OpenRouter"):
        assert empfaenger in v, f"{empfaenger} fehlt in der Empfängerliste"
    t = _text(DATENSCHUTZ)
    for pflicht in ("Artikel 15 DSGVO", "Artikel 17 DSGVO", "Beschwerde",
                    "Standardvertragsklauseln", "Speicherdauer", "Cookies"):
        assert pflicht in t, f"Abschnitt fehlt: {pflicht}"


def test_datenschutz_beschreibt_den_llm_versand():
    """⚠ Der eingriffsintensivste Vorgang muss dastehen, nicht der harmloseste.

    Hochgeladene Vergabeunterlagen gehen an ein Sprachmodell in den USA
    (`scripts/process_upload.py` ruft `llm.kontext(zweck="upload")`). Eine
    Datenschutzerklärung, die Server-Protokolle erklärt und das verschweigt, beschreibt
    das Falsche ausführlich.
    """
    t = _text(DATENSCHUTZ)
    assert "Sprachmodell" in t and "OpenRouter" in t
    assert "Vergabeunterlagen" in t
    # Der Hinweis auf das, was der Nutzer selbst steuern muss.
    assert "Laden Sie keine Unterlagen hoch" in t, (
        "Der Warnhinweis zu Personendaten in hochgeladenen Unterlagen fehlt.")


def test_behauptungen_ueber_tracking_stimmen_mit_dem_code():
    """⚠ „Wir setzen keine Analysewerkzeuge ein" ist eine prüfbare Aussage.

    Steht sie in der Erklärung, während der Code ein Zählpixel lädt, ist die Erklärung
    falsch. Deshalb wird hier beides verglichen statt nur das eine gelesen.
    """
    t = _text(DATENSCHUTZ)
    assert "keine Reichweitenmessung" in t
    quellen = list((ROOT / "web" / "app").rglob("*.tsx")) + list((ROOT / "web" / "lib").rglob("*.ts"))
    code = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in quellen)
    for werkzeug in ("googletagmanager", "google-analytics", "plausible.io",
                     "matomo", "hotjar", "mixpanel", "segment.com", "facebook.net"):
        # ⚠ KEIN deutsches Schlusszeichen in einem f-String: das ist ein ASCII-"
        # und beendet die Zeichenkette mitten im Satz. Heute zum zweiten Mal zugeschlagen.
        assert werkzeug not in code.lower(), (
            f"Die Datenschutzerklaerung sagt 'keine Reichweitenmessung', der Code laedt "
            f"aber {werkzeug}. Eine der beiden Aussagen ist zu korrigieren.")


# ── 3. Keine Erfindungen ──────────────────────────────────────────────────────────────

def test_keine_platzhalter_auf_den_pflichtseiten():
    """Was fehlt, fehlt sichtbar — es wird nicht durch Blindtext ersetzt."""
    for p in (ANBIETER, IMPRESSUM, DATENSCHUTZ):
        t = _text(p).lower()
        for blind in ("lorem ipsum", "musterstadt", "musterstraße", "max mustermann",
                      "xxx", "tbd", "hrb 00000", "beispiel gmbh"):
            assert blind not in t, f"Platzhalter {blind!r} in {p.name}"


def test_anschrift_kommt_aus_einer_quelle():
    """⚠ Dreimal getippt wäre zweimal falsch, sobald sich etwas ändert."""
    for p in (IMPRESSUM, DATENSCHUTZ):
        t = _text(p)
        assert "@/lib/anbieter" in t, f"{p.name} tippt die Anschrift selbst"
        assert "Elchstr" not in t, (
            f"{p.name} trägt die Straße fest im Text statt sie aus `anbieter.ts` zu holen")
    # Auch die Grounding Page zieht aus derselben Quelle.
    fakten_seite = _text(ROOT / "web" / "app" / "fakten" / "page.tsx")
    assert "@/lib/anbieter" in fakten_seite, (
        "Die Grounding Page baut ihre Organisation nicht aus `anbieter.ts` — dann steht "
        "die Anschrift im JSON-LD anders als im Impressum, und das sind für ein Modell "
        "zwei verschiedene Organisationen.")
