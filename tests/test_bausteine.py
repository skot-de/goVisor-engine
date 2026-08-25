"""Bausteinbibliothek ↔ Supabase (Ticket #23 §9/§12.3).

Ohne Netz und ohne Node: geprüft werden die Zusicherungen, die man einer TypeScript-Datei
nicht ansieht, wenn man sie nur überfliegt — und die teuer sind, wenn sie fallen.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUTE = (ROOT / "web" / "app" / "api" / "blocks" / "route.ts").read_text(encoding="utf-8")
KRYPTO = (ROOT / "web" / "lib" / "blockCrypto.ts").read_text(encoding="utf-8")
LIB = (ROOT / "web" / "components" / "explorer" / "BausteinLibrary.tsx").read_text(encoding="utf-8")
SCHEMA = (ROOT / "supabase" / "0006_doc_analysis.sql").read_text(encoding="utf-8")


# ── Der Inhalt darf die Datenbank nie im Klartext erreichen ────────────────────────────────

def test_inhalt_geht_nur_verschluesselt_in_die_spalte():
    """⚠ Die Spalte heisst `content_encrypted`. Ein Klartext darin fiele niemandem auf."""
    assert "verschluessele(" in ROUTE
    # Kein Satz, der `content` roh in die Tabelle schreibt.
    assert not re.search(r"content_encrypted:\s*b\.content", ROUTE)
    assert not re.search(r"\bcontent:\s*b\.content", ROUTE)


def test_ohne_schluessel_wird_nichts_gespeichert():
    """Ein stiller Rückfall auf Klartext wäre der schlimmste Ausgang: er sieht aus wie Erfolg."""
    assert "KeinSchluessel" in KRYPTO and "KeinSchluessel" in ROUTE
    assert "503" in ROUTE, "fehlender Schlüssel muss als Störung antworten, nicht als Erfolg"


def test_schluessellaenge_wird_geprueft():
    """Ein zu kurzer Schlüssel aus der Umgebung darf nicht durchrutschen."""
    assert "!== 32" in KRYPTO


def test_jeder_baustein_bekommt_einen_eigenen_datenschluessel():
    """Das „Envelope": Hauptschlüssel tauschbar, ohne einen Baustein neu zu verschlüsseln."""
    assert KRYPTO.count("randomBytes(32)") >= 1     # Datenschlüssel je Satz
    assert "aes-256-gcm" in KRYPTO                  # authentifiziert, nicht nur verschlüsselt
    assert "getAuthTag" in KRYPTO and "setAuthTag" in KRYPTO


def test_kopf_und_laengenpruefung_passen_zusammen():
    """1 + 12 + 32 + 16 + 12 + 16 = 89. Wer eine Zahl ändert, muss beide ändern."""
    assert "daten.length < 89" in KRYPTO
    assert "subarray(89)" in KRYPTO


# ── bytea reist als Hex ────────────────────────────────────────────────────────────────────

def test_bytea_wird_als_hex_uebergeben():
    """⚠ Ein Buffer landete als `{"0":72,…}` in der Spalte — und fiele erst beim nächsten
    Entschlüsseln auf, also lange nach dem Schreiben."""
    assert 'toString("hex")' in ROUTE and '\\\\x' in ROUTE


# ── Archivieren statt Löschen ──────────────────────────────────────────────────────────────

def test_geloescht_wird_nicht_sondern_archiviert():
    """So steht es im Schema (§9.2) — ein Baustein kann in einem alten Angebot stecken."""
    assert "archived: true" in ROUTE
    assert ".delete()" not in ROUTE
    assert "archived" in SCHEMA


def test_archivierte_tauchen_nicht_wieder_auf():
    assert 'eq("archived", false)' in ROUTE


# ── Lokal-first bleibt lokal-first ─────────────────────────────────────────────────────────

def test_bibliothek_zeigt_zuerst_den_browser_stand():
    """⚠ Erst laden, dann anzeigen, hiesse: die Bibliothek ist beim Aufruf kurz leer — und
    eine leere Bausteinbibliothek liest sich wie Datenverlust."""
    i_lokal = LIB.index("const lokal = load();")
    i_fetch = LIB.index('fetch("/api/blocks")')
    assert i_lokal < i_fetch


def test_anmelden_verliert_keine_bausteine():
    """Was nur im Browser lag, muss beim ersten Abgleich hochwandern."""
    assert "nurLokal" in LIB and "merkmal" in LIB


def test_abgleich_erkennt_denselben_baustein_ohne_zeitstempel():
    """Sonst stünde derselbe Text nach dem Abgleich zweimal da."""
    i = LIB.index("const merkmal =")
    zeile = LIB[i:LIB.index("\n", i)]
    assert "theme" in zeile and "content" in zeile
    assert "saved_at" not in zeile and "Date" not in zeile


# ── Firmenfreigabe: persönlich, mit ausdrücklicher Freigabe ────────────────────────────────

MIG = (ROOT / "supabase" / "0016_bausteine_firmenebene.sql").read_text(encoding="utf-8")


def ohne_kommentare(quelle: str, zeichen: str) -> str:
    """Zeilenkommentare weg. Ein Blockkommentar (`/* … */`) beginnt in diesen Dateien
    immer am Zeilenanfang mit `/*` oder ` *`, deshalb reicht die Zeilenbetrachtung."""
    aus = []
    for z in quelle.splitlines():
        s = z.strip()
        if s.startswith(zeichen) or s.startswith("/*") or s.startswith("*"):
            continue
        aus.append(z.split(zeichen)[0] if zeichen in z else z)
    return "\n".join(aus)


def test_freigabe_haengt_am_belegten_anspruch_nicht_am_profilfeld():
    """⚠ Der Kern der Sache, und die Stelle, an der es kippen würde.

    `user_profiles.identity_id` ist eine SELBSTAUSKUNFT — `saveIdentityCorrection` lässt
    jeden Nutzer sie frei setzen. Eine Freigabe, die nur darauf schaut, wäre eine offene
    Tür: wer den Namen einer fremden Firma einträgt, läse deren Bausteine. Am
    2026-08-25 gegen die laufende Datenbank geprüft (Transaktion mit Rollback):
    ohne Anspruch 0 Treffer, mit blosser Selbstauskunft 0, mit belegtem Anspruch 1.
    """
    assert "identity_claims" in MIG
    assert "'belegt'" in MIG and "'geprueft'" in MIG
    # ⚠ Geprüft wird der CODE, nicht der Text: beide Dateien erwähnen `user_profiles` in
    # einem Kommentar, der genau erklärt, warum sie es NICHT benutzen. Ein Test, der die
    # blosse Zeichenkette verbietet, verbietet die Begründung mit.
    regeln = ohne_kommentare(MIG[MIG.index("create policy"):], "--")
    assert "user_profiles" not in regeln, "die Regel darf nicht am Profilfeld hängen"
    code = ohne_kommentare(ROUTE, "//")
    assert "identity_claims" in code and "user_profiles" not in code


def test_lesen_geht_weiter_als_schreiben():
    """Kolleginnen dürfen einen freigegebenen Baustein LESEN, nicht ändern oder archivieren
    — sonst nimmt jemand anderes einem Menschen seinen Text weg."""
    for befehl in ("for select", "for insert", "for update", "for delete"):
        assert befehl in MIG, f"{befehl} fehlt — eine FOR-ALL-Regel wäre zu weit"
    i = MIG.index("for delete")
    assert "auth.uid() = profile_id" in MIG[i:i + 200]
    assert "identity_claims" not in MIG[i:i + 200], "Löschen darf NIE fremde Bausteine treffen"


def test_freigegeben_ohne_firma_ist_unmoeglich():
    """Ein freigegebener Baustein ohne Firma wäre für niemanden sichtbar und sähe trotzdem
    freigegeben aus — ein Zustand, den man gar nicht erst zulassen sollte."""
    assert "ptb_firma_braucht_identity" in MIG


def test_zuruecknehmen_loescht_die_firma():
    """Sonst bliebe ein privater Baustein mit Firmenvermerk stehen — sieht aus wie ein Rest."""
    assert re.search(r"identity_id:\s*nachFirma\s*\?\s*firma\s*:\s*null", ROUTE)


def test_ansicht_bietet_fremden_bausteinen_kein_archivieren_an():
    """Ein Knopf, den die Regel ohnehin verweigert, ist schlimmer als keiner."""
    assert "b.eigen === false" in LIB


def test_fehlgeschlagene_freigabe_wird_zurueckgedreht():
    """⚠ Ein Schalter, der umgelegt bleibt und nichts bewirkt hat, ist eine Lüge über den
    Zustand — schlimmer als eine Fehlermeldung."""
    i = LIB.index("async function freigabe")
    block = LIB[i:LIB.index("function removeBlock")]
    assert block.count("zurueck") >= 2, "beide Fehlerwege müssen zurückdrehen"


def test_null_getroffene_zeilen_sind_kein_erfolg():
    """⚠ Der Fehler, den erst der Durchlauf zeigte.

    Trifft die RLS-Regel keine Zeile — weil der Baustein jemand anderem gehört —, liefert
    PostgREST KEINEN Fehler, sondern null Zeilen. Ohne Prüfung meldete die Route `ok`.
    Am 2026-08-25 gemessen: Nutzer B bekam „ok" für das Archivieren eines fremden
    Bausteins, der danach unverändert dastand (`archived = f`). Die Daten waren sicher,
    die Antwort war eine Lüge — und die ist schlimmer, weil niemand nachsieht.
    """
    code = ohne_kommentare(ROUTE, "//")
    for stelle in ("archived: true", "sichtbarkeit: nachFirma"):
        i = code.index(stelle)
        rest = code[i:i + 700]
        assert ".select(" in rest, f"{stelle}: ohne select bleibt der Treffer ungeprüft"
        assert "data?.length" in rest, f"{stelle}: die Trefferzahl wird nicht geprüft"
        assert "403" in rest, f"{stelle}: null Treffer muss abgelehnt werden, nicht bejaht"


# ── Verwendungshistorie (§9.3) ─────────────────────────────────────────────────────────────

SHELL = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")


def test_verwendung_wird_aus_derselben_gefilterten_liste_zugeordnet():
    """⚠ Der Fehler, der beim Bauen fast durchgerutscht wäre.

    Ein erster Entwurf las die `lead_id` über denselben Index aus der UNGEFILTERTEN Liste.
    Sobald ein Baustein wegfällt (zu kurz), hängt die Verwendung am falschen — und das
    fällt nie beim Schreiben auf, sondern erst, wenn jemand die Historie auswertet.
    Am 2026-08-25 im Durchlauf mit drei Bausteinen geprüft, einer davon zu kurz:
    LEAD-B → referenzen, LEAD-C → nachhaltigkeit, LEAD-A verschwunden statt verrutscht.
    """
    code = ohne_kommentare(ROUTE, "//")
    assert "brauchbar" in code
    i = code.index("const verwendungen")
    assert "brauchbar[i]" in code[i:i + 300], "die Zuordnung muss aus der gefilterten Liste kommen"
    assert "roh[i]" not in code, "über die ungefilterte Liste verrutscht die Zuordnung"


def test_fehlende_historie_nimmt_den_baustein_nicht_mit():
    """Eine verlorene Zeile Statistik ist kein Grund, einem Menschen seinen Text wegzunehmen."""
    code = ohne_kommentare(ROUTE, "//")
    # ⚠ Die EINFUEGENDE Stelle, nicht die erste: seit dem Verwendungszähler steht
    # `profile_block_usage(count)` schon oben im `select` der Leseabfrage.
    i = code.index('from("profile_block_usage")')
    rest = code[i:i + 400]
    assert "historie" in rest
    # Kein Abbruch mit Fehlerstatus, nur ein Vermerk in der Antwort.
    assert "status: 500" not in rest


def test_ohne_vorgang_kein_verwendungsvermerk():
    """Ein Baustein ohne Herkunft ist besser als einer mit falscher."""
    code = ohne_kommentare(ROUTE, "//")
    i = code.index("const verwendungen")
    assert 'typeof v.lead_id === "string"' in code[i:i + 400]


def test_checkliste_speichert_lokal_bevor_sie_den_server_fragt():
    """⚠ Umgekehrt hinge der Knopf am Netz — und wer nicht angemeldet ist, verlöre den
    Baustein ganz. Der Server ist die Schicht darüber, nicht die Bedingung."""
    i = SHELL.index("function bausteinUebernehmen")
    block = SHELL[i:i + 1400]
    assert block.index("localStorage.setItem") < block.index('fetch("/api/blocks"')


def test_beide_checklisten_knoepfe_gehen_denselben_weg():
    """`saveblock` (§7.1) und `clkombi` (§7) taten dasselbe zweimal — eine Änderung an
    einer Stelle hätte die andere stehen lassen."""
    assert SHELL.count("bausteinUebernehmen(") == 3      # 1 Definition + 2 Aufrufe
    assert "govisor.blocks" not in SHELL[SHELL.index("case \"clkombi\""):]


# ── Vorhandenen Baustein in einen Vorgang übernehmen ───────────────────────────────────────

CORE = (ROOT / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
PANEL = (ROOT / "web" / "components" / "explorer" / "DetailPanel.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "explorer.css").read_text(encoding="utf-8")


def test_knopf_steht_neben_dem_bestehenden():
    """Beide Wege gehören in dieselbe Zeile: einen Baustein anlegen und einen holen."""
    i = CORE.index("data-clnutzen")
    assert "data-clkombi" in CORE[i:i + 400], "die zwei Knöpfe gehören zusammen"


def test_neue_aktionen_sind_verdrahtet():
    """⚠ Unsere häufigste Fehlerklasse: gebaut, aber nicht verdrahtet.

    `DetailPanel` reicht nur Aktionen weiter, die in seiner Liste stehen. Fehlt eine, ist
    der Knopf da, sieht richtig aus und tut nichts — und alle Tests bleiben grün.
    """
    for a in ("clnutzen", "clpick"):
        assert f'"{a}"' in PANEL, f"{a} wird nicht weitergereicht"
        assert f'case "{a}"' in SHELL, f"{a} wird nicht behandelt"


def test_auswahlkasten_hat_seine_klassen():
    """Ohne die Regeln stünde die Auswahl als unformatierte Liste im Text."""
    for klasse in ("cl-bib", "cl-bib-z", "cl-bib-h", "cl-bib-t", "cl-bib-x", "cl-hist"):
        assert f".{klasse}" in CSS, f"{klasse} fehlt im Stylesheet"
        assert klasse in SHELL or klasse in CORE, f"{klasse} wird nirgends gesetzt"


def test_fremder_text_geht_nicht_ueber_innerhtml():
    """⚠ Ein Baustein enthält Text, den ein Mensch geschrieben hat — nie als HTML deuten."""
    # Geprüft wird der Code, nicht der Kommentar, der genau diese Regel begründet.
    code = ohne_kommentare(SHELL, "//")
    i = code.index('case "clnutzen"')
    block = code[i:code.index('case "clpick"')]
    assert "textContent = b.content" in block
    # Der Inhalt selbst darf nie über innerHTML gehen — nur das Gerüst drumherum.
    for zeile in block.splitlines():
        if "innerHTML" in zeile:
            assert "b.content" not in zeile, f"Inhalt als HTML: {zeile.strip()[:70]}"


def test_uebernehmen_setzt_den_text_auch_ohne_anmeldung():
    """⚠ Der Vermerk ist die Kür, das Einsetzen die Pflicht. Wer nicht angemeldet ist, soll
    den Baustein trotzdem im Feld haben."""
    i = SHELL.index('case "clpick"')
    block = SHELL[i:i + 1400]
    assert block.index("ta.value = b.content") < block.index('fetch("/api/blocks/usage"')
    assert "if (b.id && activeId)" in block, "ohne Kennung wird nichts vermerkt, aber eingesetzt"


def test_liste_wird_nicht_bei_jedem_klick_neu_geholt():
    """Wer eine Checkliste durchgeht, tippt den Knopf mehrfach."""
    assert "bibliothekRef" in SHELL and "if (bibliothekRef.current) return" in SHELL


def test_leere_themenauswahl_zeigt_trotzdem_den_bestand():
    """⚠ Eine leere Liste erklärt nicht, ob die Bibliothek leer ist oder nur zu diesem Thema
    nichts hat — und das sind zwei sehr verschiedene Lagen."""
    i = SHELL.index('case "clnutzen"')
    block = SHELL[i:SHELL.index('case "clpick"')]
    assert "...passend, ...rest" in block.replace(" ", "").replace("\n", "") or \
           "[...passend, ...rest]" in block
