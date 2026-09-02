"""Bezifferte Schwellen im Vergleich (Kennzahl 6) — drei Filter, drei Fehlerarten.

Die Übergabe verspricht „198.584 Zahlen, einordenbar gegen Median und Quartil". Einordenbar ist
rund ein Prozent, und der Weg dahin ist der eigentliche Inhalt dieser Kennzahl:

    ohne Einheit          „Median 20" ist 20 mm oder 20 Jahre
    ohne eine Grösse      „mindestens 20 %" — wovon? Steigung, Recyclinganteil, Rabatt
    ohne Standfestigkeit  der Mindestumsatz wächst mit unserer Lesetiefe, nicht mit der Vergabe

Diese Datei hält alle drei fest, dazu die zwei Fallen, die beim Bauen zugeschlagen haben: die
Einheit mit Faktor („Mio. EUR") und das Quartil, das mit dem Median zusammenfällt.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_schwellen.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
DATEI = WURZEL / "web" / "data" / "schwellen.json"


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_sw", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


# ── Filter 1: die Einheit ───────────────────────────────────────────────────────────────

def test_ohne_einheit_kein_vergleich():
    m = _modul()
    assert m._dimension(None) is None and m._dimension("") is None
    assert m._dimension("eur") == "geld" and m._dimension("Jahre") == "jahre"
    assert m._dimension("mm") is None, "eine unbekannte Einheit darf nicht durchrutschen"


def test_faktor_einheiten_fliegen_raus():
    """⚠ DIE TEURE FALLE. „1,5 Mio. EUR" trägt den Multiplikator in der EINHEIT. Wer sie zu
    `geld` zählt, vergleicht 1,5 gegen 1.500.000 — ein Fehler um das Millionenfache. Sie werden
    verworfen und nicht umgerechnet: geraten wäre schlimmer als fehlend."""
    m = _modul()
    for u in ("mio. eur", "Mio EUR", "TEUR", "tsd. euro", "Millionen EUR"):
        assert m._dimension(u) is None, f"{u!r} wurde als Dimension anerkannt"


# ── Filter 2: die Gruppe muss eine Grösse benennen ──────────────────────────────────────

def test_nur_arten_die_eine_groesse_benennen():
    """⚠ Ein Urteil, kein Rechenschritt. `technische_mindestanforderung / prozent` ist über die
    Lesetiefe stabil und trotzdem unvergleichbar: 20 % Steigung gegen 20 % Recyclinganteil."""
    m = _modul()
    for raus in ("technische_mindestanforderung", "frist", "leistung_menge",
                 "einzureichendes_dokument", "zertifikat"):
        assert raus not in m.VERGLEICHBAR, f"{raus} benennt keine einzelne Grösse"
    assert "vertragsstrafe" in m.VERGLEICHBAR
    assert m.VERGLEICHBAR["vertragsstrafe"] == ("prozent",), \
        "in EUR mischt die Vertragsstrafe zwei Skalen (Drift 16,7×)"


def test_versicherungen_nach_schadensart_getrennt():
    """⚠ Der `req_type` reicht hier nicht: die Deckungssummen spreizen sechsfach (allgemein
    500.000, Umweltschäden 3 Mio.). Ein gemeinsamer Median wäre für jede Art falsch."""
    m = _modul()
    assert {"berufshaftpflicht", "haftung"} <= set(m.AUSPRAEGUNGEN)
    assert m._auspraegung("berufshaftpflicht", "", "Personenschäden 2.500.000 Euro", 2.5e6) == "Personenschäden"
    assert m._auspraegung("berufshaftpflicht", "", "Deckungssumme 1 Mio", 1e6) == "allgemein"


def test_kombinierte_deckung_ist_eine_eigene_gruppe():
    """⚠ DIE FALLE, die erst im Beleg auffiel. 28 % aller Belege lauten „Mindestdeckungssumme
    von 3 Mio. EUR für Personen-, Sach- und Vermögensschäden" — EINE Summe für alles. Die
    abgekürzten Glieder tragen das Wort „schäden" nicht, deshalb traf die Schlagwortsuche nur
    „Vermögensschäden" und verglich eine kombinierte Deckung gegen Einzelsummen."""
    m = _modul()
    for zitat in ("3 Mio. € für Personen-, Sach- und Vermögensschäden",
                  "Deckung für Personen-, Sach-/Vermögensschäden",
                  "Personen- und Sachschäden 2.000.000"):
        assert m._auspraegung("haftung", "", zitat, 2e6) == "kombiniert", zitat
    assert m._auspraegung("haftung", "", "Nur Vermögensschäden 1.000.000", 1e6) == "Vermögensschäden"


# ── Kennzahl 7: Tagessatz und Obergrenze sind zwei Zahlen ───────────────────────────────

def test_vertragsstrafe_trennt_tagessatz_und_obergrenze():
    """⚠ 0,20 % je Werktag gegen 5 % insgesamt — Verhältnis 1:25. Die Übergabe sagt „fast alle
    bei 5 %" und meint die Obergrenze; ein gemeinsamer Median wäre für beide falsch."""
    m = _modul()
    assert m._auspraegung("vertragsstrafe", "", "0,2 % je werktag des verzugs", 0.2) == "Tagessatz"
    assert m._auspraegung("vertragsstrafe", "", "insgesamt höchstens 5 % der auftragssumme", 5.0) == "Obergrenze"


def test_die_sperre_faengt_saetze_mit_beiden_zahlen():
    """⚠ NICHT SCHMUCK. „0,2 % je Werktag, insgesamt höchstens 5 %" nennt beide Zahlen in einem
    Satz. Ohne Sperre landet der Tagessatz in der Obergrenzen-Gruppe und zerlegt deren Median.
    329 solche Belege fallen lieber ganz raus."""
    m = _modul()
    assert m._auspraegung("vertragsstrafe", "", "0,2 % je Werktag, insgesamt höchstens 5 %", 0.2) is None


def test_der_beleg_ersetzt_die_einheit_nur_mit_band():
    """⚠ Bei der Vertragsstrafe fehlt die Einheit in 81 % der Fälle; ohne Beleg wären 216 statt
    4.796 Werte vergleichbar. Aber unter den Werten stecken auch Eurobeträge — was ausserhalb
    des Bandes liegt, wird verworfen und NICHT umgerechnet."""
    m = _modul()
    assert m.AUSPRAEGUNGEN["vertragsstrafe"]["einheitOptional"] is True
    assert m.AUSPRAEGUNGEN["berufshaftpflicht"]["einheitOptional"] is False, \
        "bei Geldbetraegen darf der Beleg die Einheit nicht ersetzen"
    assert m._auspraegung("vertragsstrafe", "", "insgesamt höchstens 25.000", 25000.0) is None
    for regel in m.AUSPRAEGUNGEN["vertragsstrafe"]["regeln"]:
        assert regel["band"], "eine Regel ohne Band lässt Eurobeträge als Prozent durch"


def test_das_einheitenfeld_ist_selbst_beleg():
    """⚠ DER FUND, der erst in der laufenden App auftauchte. Bei der Vertragsstrafe ist `unit`
    Fliesstext: „der Auftragssumme je angefangenen Werktag", „€ je Vorfall", „pro Woche". Die
    erste Fassung verwarf alle 2.123 solchen Zeilen, weil sie keine bekannte Einheit fand."""
    m = _modul()
    assert m._auspraegung("vertragsstrafe", "der Auftragssumme je angefangenen Werktag", "", 0.1) == "Tagessatz"
    cfg = m.AUSPRAEGUNGEN["vertragsstrafe"]
    assert m._dimension_aus_beleg(cfg, m._belegtext("des Auftragswertes", "")) == "prozent"
    assert m._dimension_aus_beleg(cfg, m._belegtext("€ je Vorfall", "")) == "geld", \
        "eine Geldstrafe je Vorfall darf nicht als Prozentsatz gelesen werden"


def test_einheitenfeld_schlaegt_das_geteilte_zitat():
    """⚠ DER FUND AUS DER LAUFENDEN APP. Geschwisterzeilen teilen sich den Belegsatz: „0,1 %
    der Auftragssumme je angefangenen Werktag" und „10 % der Auftragssumme" haben für BEIDE
    denselben Satz. Wer den gemeinsamen Text zuerst liest, bekommt bei genau den Vorgängen
    keine Zuordnung, die beide Zahlen nennen."""
    m = _modul()
    geteilt = "wird die leistungszeit überschritten, 0,1 % je werktag, insgesamt höchstens 10 %"
    assert m._auspraegung("vertragsstrafe", "der Auftragssumme je angefangenen Werktag",
                          geteilt, 0.1) == "Tagessatz"
    # ⚠ Die stumme Schwesterzeile bleibt unbestimmt — das ist richtig, nicht schade.
    assert m._auspraegung("vertragsstrafe", "der Auftragssumme", geteilt, 10.0) is None


def test_pro_woche_ist_kein_tagessatz():
    """⚠ 134 Zeilen sagen „pro Woche", 44 „pro Überschreitungsfall" — eigene Bezugsgrössen.
    Ein Wochensatz von 0,5 % neben Tagessätzen von 0,2 % wäre ein Fehlalarm."""
    m = _modul()
    for t in ("0,5 % pro woche", "1 % pro überschreitungsfall", "0,3 % je vorfall"):
        assert m._auspraegung("vertragsstrafe", "", t, 0.5) is None, t


def test_unvergleichbares_faellt_raus_statt_in_eine_restgruppe():
    """Bei der Vertragsstrafe ist `sonst` bewusst None: ein Beleg, der weder Tagessatz noch
    Obergrenze sagt, gehört in keine der beiden Gruppen. 4.026 Zeilen fallen so heraus."""
    m = _modul()
    assert m.AUSPRAEGUNGEN["vertragsstrafe"]["sonst"] is None
    assert m._auspraegung("vertragsstrafe", "", "Vertragsstrafe wird vereinbart", 5.0) is None


# ── Filter 3: misst die Zahl den Vorgang oder uns? ──────────────────────────────────────

def test_driftpruefung_laeuft_bei_jedem_lauf():
    """⚠ SIE DARF KEIN EINGEFRORENES URTEIL SEIN. Eine Liste „diese Gruppen sind stabil" wäre in
    drei Monaten falsch, ohne dass es jemand merkt. Der Export rechnet sie jedes Mal neu."""
    baum = ast.parse(QUELLE)
    fn = next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == "main")
    rumpf = "\n".join(ast.get_source_segment(QUELLE, k) or "" for k in fn.body[1:])
    assert "MAX_DRIFT" in rumpf and "n_parsed_files" in rumpf, "die Driftprüfung fehlt im Lauf"
    assert "verworfen" in rumpf, "was rausfliegt, wird nicht gemeldet"


def test_drift_schwelle_bleibt_streng():
    m = _modul()
    assert m.MAX_DRIFT <= 1.5, "eine lockere Schwelle lässt genau die Gruppen durch, die uns messen"
    assert m.MIND_BAND >= 20 and m.MIND_GRUPPE >= 60


def test_verworfene_gruppen_stehen_nicht_in_der_ausgabe():
    """Der Mindestumsatz ist der Fall, an dem die naheliegende Erklärung falsch war: nicht
    „grosse Vergaben verlangen mehr" (Korrelation mit dem Auftragswert 0,24), sondern unsere
    Lesetiefe. Er darf nicht wieder auftauchen."""
    if not DATEI.exists():
        return
    g = json.loads(DATEI.read_text(encoding="utf-8"))["gruppen"]
    arten = {k.split("|")[1] for k in g}
    assert "mindestumsatz" not in arten and "referenz_mindestwert" not in arten


# ── Anzeige ─────────────────────────────────────────────────────────────────────────────

def test_regeln_kommen_aus_der_datei():
    """⚠ Zwei gepflegte Einheitenlisten wären zwei Listen, die auseinanderlaufen — dieselbe
    Fehlerform wie die handgetippte Spaltenliste bei den Doc-Signalen. Der Renderer liest die
    Regeln aus der Datei, statt eigene zu führen."""
    b = _block("schwellenTreffer")
    assert "S.einheiten" in b and "S.auspraegungen" in b
    for wort in ("'eur'", '"eur"', "personenschäden"):
        assert wort not in b.lower(), f"eigene Liste im Frontend: {wort}"


def test_renderer_wendet_die_gelieferten_regeln_an():
    """⚠ Es reicht nicht, dass keine eigene Liste im Frontend steht — es muss die gelieferte
    auch anwenden, und zwar VOLLSTÄNDIG. Fehlt die Sperre, landet „0,2 % je Werktag, insgesamt
    höchstens 5 %" in der Obergrenzen-Gruppe; fehlt das Band, wird ein Eurobetrag als Prozent
    gelesen."""
    b = (_block("schwellenTreffer") + _block("schwellenVergleich")
         + _block("auspraegungVon") + _block("regelTreffer"))
    for teil in ("S.auspraegungen", "r.muster", "r.sperre", "r.band", "cfg.einheitOptional",
                 "cfg.dimension", "cfg.sonst"):
        assert teil in b, f"der Renderer wertet {teil} nicht aus"


def test_die_vertragsstrafe_zeile_sagt_wovon_die_rede_ist():
    """⚠ KENNZAHL 7. „Vertragsstrafe 0,3 %" allein ist zweideutig: je Werktag oder insgesamt?
    Der Unterschied ist der Faktor 25. Das Verzeichnis führt `penaltyPct` seit dem 01.09. mit
    Bezug „markt" — angezeigt wurde der Vergleich nie."""
    stelle = CORE[CORE.index("if(s.penaltyPct!=null)"):]
    stelle = stelle[:stelle.index("rows.push([tk('Vertragsstrafe')") + 400]
    assert "auspraegungVon(" in stelle, "die Zeile sagt weiterhin nicht, welche Zahl das ist"
    assert "schwellenVergleich(" in stelle, "der versprochene Marktbezug fehlt weiterhin"
    assert "je Werktag" in stelle and "insgesamt" in stelle


def test_nur_echt_ueber_dem_oberen_viertel():
    """⚠ Bei zwei Gruppen fällt das Quartil mit dem Median zusammen (Vertragsstrafe 5 %,
    Referenzen 3). Mit `>=` stünde die Einordnung dort genau beim Üblichen."""
    b = _block("schwellenVergleich")
    assert "t.wert > t.gruppe.hoch" in b, "greift auch beim Median"
    assert "wert < " not in b, "eine niedrigere Schwelle ändert keine Entscheidung"


def test_der_vergleich_ist_nicht_fett():
    """Die geforderte Zahl ist die Nachricht, die Einordnung ordnet sie ein. Im `<b>` schriee
    sie lauter als das, worauf sie sich bezieht."""
    stelle = CORE[CORE.index('data-clchk="${it._i}">✓</button>'):]
    stelle = stelle[:stelle.index("</div>")]
    assert "</b>${vgl}" in stelle, "der Vergleich steht im fetten Kopf"


def test_gruppenschluessel_traegt_das_land():
    """⚠ Ohne Land vergliche ein Schweizer Vorgang gegen deutsche Deckungssummen."""
    b = _block("schwellenTreffer")
    assert "${land}|${it.req_type}|${dim}|${art}" in b
    if DATEI.exists():
        g = json.loads(DATEI.read_text(encoding="utf-8"))["gruppen"]
        assert all(len(k.split("|")) == 4 and len(k.split("|")[0]) == 2 for k in g)


def test_die_einheit_wird_nur_bei_voller_zuordnung_ergaenzt():
    """⚠ „Vertragsstrafe 10" neben „üblich 5 %" ist keine Zeile, sondern ein Rätsel: bei 81 %
    der Vertragsstrafen ist das Einheitenfeld leer, die Einheit steckt im Beleg. Ergänzt wird
    sie nur, wenn die volle Zuordnung durchlief — ohne das Plausibilitätsband stünde bei
    „insgesamt höchstens 25.000" ein „25.000 %"."""
    b = _block("schwellenEinheit")
    assert "String(it.unit || '').trim()" in b, "eine vorhandene Einheit darf nicht überschrieben werden"
    assert "schwellenTreffer(it, l)" in b, "die Einheit entsteht ohne die volle Prüfung"
    zeile = CORE[CORE.index('const val = it.value!=null'):]
    zeile = zeile[:zeile.index("\n")]
    assert "schwellenEinheit(it, l)" in zeile and "it.unit?" in zeile


# ── Ausliefergut ────────────────────────────────────────────────────────────────────────

def test_ausgabe_haelt_die_form():
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    assert set(d) == {"gruppen", "einheiten", "auspraegungen"}
    m = _modul()
    for g in d["gruppen"].values():
        assert set(g) == {"n", "median", "hoch", "label"}
        assert g["n"] >= m.MIND_GRUPPE and g["hoch"] >= g["median"]
