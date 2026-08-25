#!/usr/bin/env python3
"""Outreach-Landing-Generator → web/data/outreach.json

Je Zielfirma eine token-adressierte Auswertung. Vorberechnet und statisch abgelegt, damit
`/t/<token>` serverless-fähig und öffentlich bleibt (kein Python im Deploy).

WAS DIE SEITE ERREICHEN SOLL (Sven, 2026-08-16), in dieser Reihenfolge:
  1. „Wir kennen euch." — und zwar belegt, mit Angabe, WELCHER Teil sichtbar ist.
  2. „Kennt ihr eure Aufträge so gut wie wir?" — die konkrete Liste.
  3. Brücke zu den Produkten: Strategie, Unternehmen, Planung.

WARUM BAUSTEINE STATT EINES FESTEN AUFBAUS
------------------------------------------
Die erste Fassung hatte einen festen Aufbau mit Fallbacks. Das ging schief, weil ein
Fallback unter einer Behauptungs-Überschrift steht und dadurch selbst zur Behauptung wird.
Gemessen am 2026-08-16:

  * „Ihr Hauptwettbewerber" — nur **3,1 %** aller Identitäten haben überhaupt eine
    Head-to-head-Historie. Bei 96,9 % zeigte die Seite den grössten Anbieter im CPV-Feld,
    überschrieben mit „Ihr Hauptwettbewerber". Bei Klostermann: **null** belegte
    Niederlagen, angezeigt wurde LEONHARD WEISS.
  * „N Verträge laufen aus" — nur **19,3 %** der endenden Verträge sind Rahmen- oder
    Wiederholungsverträge, laufen also im Wortsinn aus und werden neu vergeben. 43,3 %
    sind Bauleistungen: die werden FERTIG. Bei Klostermann waren alle 14 Bauleistungen.
  * „über 3,4 Mio €" — davon **98,4 % geschätzt**, verteilt auf zwei verschiedene Zahlen
    (CPV-Median-Imputation). Echt belegt: 53.320 €.
  * Die „14 Verträge" enthielten **5 Dubletten** (ein Titel 5×, einer 2×). Real: 9.

Jeder Baustein prüft deshalb SELBST, ob er belegt ist, und gibt sonst `None` zurück. Der
Generator nimmt, was diese Firma hergibt, sortiert nach Stärke. Eine Seite mit drei
belegten Bausteinen ist besser als eine mit sechs, von denen vier geraten sind — der
Empfänger ist der eine Mensch, der seine eigenen Aufträge besser kennt als wir.

Aufruf:
  python3 scripts/export_outreach.py --name Klostermann [--ort Hamm]
  python3 scripts/export_outreach.py --id solo:hr:R2404_HRB6313
Token = sha1(identity_id)[:10] (deterministisch; Sven steuert, wer den Link bekommt).
"""
import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import zielliste as Z  # noqa: E402

G = str(ROOT / "data/gold/DE")
OUT = ROOT / "web" / "data" / "outreach.json"

# Vertragsarten, die im Wortsinn AUSLAUFEN und neu vergeben werden. Alles andere endet
# auch, aber ohne Nachfolge — ein fertiggestelltes Brückenbauwerk wird nicht neu
# ausgeschrieben. Dieselbe Unterscheidung trifft `gold._kind_sql` beim Bauen des
# Nachfolge-Modells: nicht-Rahmen-Bau gilt dort als nicht ketten-würdig. Die Landing-Seite
# hat diese Regel bisher ignoriert und ein Bauende als Vertragsablauf verkauft.
ARTEN_MIT_NACHFOLGE = ("framework", "recurring")
ARTEN_FERTIGSTELLUNG = ("one_off_works", "works_other")

# Ab wann ist Auftraggeber-Konzentration eine Abhängigkeit und nicht Zufall? Unter fünf
# Zuschlägen ist jeder Prozentsatz Rauschen (bei 2 von 2 wären es 100 %).
# Die Schwelle steigt mit der Zahl der Auftraggeber — s. baustein_abhaengigkeit.
ABHAENGIG_SCHWELLE = {1: 0.60, 2: 0.80, 3: 0.90}
ABHAENGIG_AB_ZUSCHLAEGEN = 5

# Bis zu wie vielen Treffern zeigen wir die Vorgaenge selbst statt nur ihrer Anzahl?
# Darueber liest sie niemand mehr, darunter ist die Liste der bessere Beleg.
CHANCEN_ZEIGEN_BIS = 12

# ── VORBELEGUNG FUER DEN WARMEN ONBOARDING-WEG ──────────────────────────────────────
# `dim_cpv.branche` kennt 34 Werte, das Onboarding sechs Knoepfe. Diese Tabelle uebersetzt
# — bewusst als Zuordnung und nicht als Rateregel: was hier nicht steht, bleibt leer, und
# der Nutzer waehlt selbst. Eine falsch vorbelegte Branche ist schlimmer als eine leere,
# weil sie stillschweigend die Relevanz-Sortierung praegt.
BRANCHE_AUS_DIMCPV = {
    "IT": "it", "Druck/Medien": "it",
    "Bau": "bau", "Installation": "bau", "Elektro": "bau", "Immobilien": "bau",
    "Medizin": "medizin", "Gesundheit": "medizin",
    "Beratung": "beratung", "Ingenieur/Architektur": "beratung",
    "Verwaltung": "beratung", "Bildung": "beratung", "Forschung": "beratung",
    "Sicherheit": "sicherheit",
    "Energie": "energie", "Wasser": "energie", "Versorgung": "energie",
    "Umwelt/Reinigung": "energie",
}



def zahl(n) -> str:
    """Tausendertrenner für EINE Zahl.

    ⚠ Nicht auf ganze Sätze anwenden. Genau das ist am 2026-08-17 passiert: ein
    ``f"…{n:,}…".replace(",", ".")`` über einem mehrteiligen Satz machte aus jedem Komma
    im Fliesstext einen Punkt — „von 108 Vergabestellen. mit denen ihr noch nie gearbeitet
    habt." Der Trick gilt der Zahl, nicht der Sprache drumherum.
    """
    return f"{int(n):,}".replace(",", ".")


def token_of(identity_id):
    return hashlib.sha1(identity_id.encode()).hexdigest()[:10]


def eur(v):
    if v is None:
        return None
    v = float(v)
    if v >= 1e6:
        return f"{v/1e6:.1f}".replace(".", ",") + " Mio €"
    return f"{int(round(v)):,}".replace(",", ".") + " €"


def target_ids(con, args):
    if args.id:
        return [args.id]
    Z.build_population(con, adhoc={"name": args.name, "plz": args.plz, "ort": args.ort})
    return [r[0] for r in con.execute("SELECT identity_id FROM pop").fetchall()]


# ─────────────────────────────────────────────────────────────────────────────────────
#  Bausteine
#
#  Vertrag: jeder bekommt (con, ctx) und liefert ein dict oder None. `None` heisst
#  „für diese Firma nicht belegt" und ist ein vollwertiges Ergebnis, kein Fehler.
#  Jeder Baustein trägt `bruecke` — den Produktbereich, in den er führt. Ohne die
#  wäre die Seite eine nette Auswertung ohne Anschluss.
# ─────────────────────────────────────────────────────────────────────────────────────

def _vertragszeilen(con, identity_id, limit=8):
    """Endende Verträge, entdoppelt und nach Art getrennt.

    Zwei Reparaturen gegenüber der Vorfassung:
    (1) `DISTINCT` auf Titel+Vergabestelle+Ende. Die Losstruktur erzeugt echte Mehrfach-
        Zeilen desselben Vorhabens — „Erweiterung ESTW Eidelstedt" stand 5× untereinander.
    (2) `art` je Zeile statt einer pauschalen Überschrift „läuft aus".
    """
    LE = f"read_parquet('{G}/lead_export.parquet')"
    rows = con.execute(f"""
      SELECT DISTINCT ON (title, buyer_name, contract_end)
             title, buyer_name, value_eur, value_source, contract_end,
             months_to_expiry, contract_kind
      FROM {LE}
      WHERE incumbent_group_id = ? AND months_to_expiry BETWEEN 0 AND 24
      ORDER BY title, buyer_name, contract_end, months_to_expiry
    """, [identity_id]).fetchall()
    rows.sort(key=lambda r: (r[5] is None, r[5]))

    zeilen = []
    for t, b, v, vs, ende, mte, kind in rows[:limit]:
        art = ("auslauf" if kind in ARTEN_MIT_NACHFOLGE
               else "fertigstellung" if kind in ARTEN_FERTIGSTELLUNG else "unklar")
        zeilen.append({
            "titel": t, "buyer": b,
            # Schätzwerte stehen wieder da, aber als Schätzung ERKENNBAR („ca."), nicht
            # als nackte Zahl mit einem Sternchen daneben.
            #
            # Erst ganz weggelassen, weil die Vorfassung 14x dieselbe CPV-Median-Zahl
            # zeigte und in der Überschrift zu „3,4 Mio €" aufsummierte. Sven beim
            # Ansehen: „nun stehen gar keine volumen mehr da" — zu Recht. Das Problem
            # war nie das Schätzen, sondern dass die Schätzung wie eine Tatsache aussah
            # und in eine Summe einging. Beides ist behoben: die Zahl trägt „ca.", und
            # summiert wird sie nirgends.
            "vol": eur(v) if vs == "actual" else None,
            "_roh": v, "_quelle": vs,
            "ende": ende.strftime("%m/%Y") if ende and hasattr(ende, "strftime") else None,
            "art": art,
        })
    return zeilen


# ─────────────────────────────────────────────────────────────────────────────────────
#  DER ZUSCHNITT — eine Stelle, an der aus der Historie einer Firma wird, wie sich der
#  Markt auf sie verengen laesst.
#
#  WARUM ES DAS GEBEN MUSS (Sven, 2026-08-17): „ich kann und werde nicht bei jedem kunden
#  dabei sein und vorher gucken was er sehen wuerde. wir muessen da ein muster schaffen,
#  das immer funktioniert."
#
#  Der Fehler, der das ausgeloest hat, ist lehrreich: die Seite empfahl H. Klostermann
#  (Fernmelde- und Stromleitungen fuer DB Netz) 171 Ausschreibungen von „anderen
#  Auftraggebern". Dahinter standen Schulbau Hamburg, Stadt Wuppertal und das
#  Gebaeudemanagement Hannover — Gebaeudeelektrik. Die CPV-Klasse stimmte (4531
#  „Installation von elektrischen Leitungen"), die Arbeit nicht. Ein Geschaeftsfuehrer
#  liest so eine Liste und weiss in fuenf Sekunden, dass wir sein Geschaeft nicht
#  verstanden haben. Das ist schlechter als gar nicht zu schreiben.
#
#  Gefunden wurde der Fehler NUR, weil jemand die Namen gelesen hat. Genau das soll hier
#  nie wieder noetig sein. Drei Regeln setzen das um:
#
#    1. EINE Quelle fuer die Verengung. Jeder „fuer euch"-Baustein fragt hier, statt sich
#       seine Filter selbst zusammenzubauen. Sonst verengt einer nach CPV, der naechste
#       nach Region, und die Seite widerspricht sich.
#    2. Jede Stufe traegt IHR EIGENES Etikett. Vorher standen die Etiketten als feste
#       Zeichenketten in der Oberflaeche („in eurem Fach", „wo ihr baut"), waehrend die
#       Filter bedingt waren — faellt eine Stufe aus, log das Etikett.
#    3. Eine Stufe kommt nur in die Kette, wenn sie WIRKLICH einschraenkt. Eine Stufe, die
#       nichts wegnimmt, taeuscht Praezision vor, die es nicht gibt.
# ─────────────────────────────────────────────────────────────────────────────────────

# Sammelbecken-Taetigkeiten. `general_public` allein traegt 17.665 Firmen — als Filter
# verengt das nichts und behauptet trotzdem eine Passung. Solche Werte sind KEINE Stufe.
AKTIVITAET_UNSPEZIFISCH = {"general_public", "other", None, ""}
# Ab welchem Anteil der typisierten Auftraggeber gilt eine Taetigkeit als praegend?
# Gemessen: 79 % der Firmen mit >=3 typisierten erreichen 60 %, 46 % erreichen 80 %.
AKTIVITAET_SCHWELLE = 0.60
AKTIVITAET_MIN_BELEGE = 3


def zuschnitt(con, ctx):
    """Wie sich der offene Markt auf DIESE Firma verengen lässt. Gecacht im Kontext."""
    if "zuschnitt" in ctx:
        return ctx["zuschnitt"]
    LE = f"read_parquet('{G}/lead_export.parquet')"
    CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
    iid = ctx["id"]

    div = con.execute(f"""SELECT substr(cpv_code,1,2) FROM {LE}
      WHERE incumbent_group_id = ? AND cpv_code IS NOT NULL
      GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", [iid]).fetchone()
    klassen = [r[0] for r in con.execute(f"""SELECT DISTINCT substr(cpv_code,1,4) FROM {LE}
      WHERE incumbent_group_id = ? AND cpv_code IS NOT NULL""", [iid]).fetchall()]
    # Leistungsort, NICHT Sitz der Vergabestelle — s. baustein_offene_im_feld.
    laender = [r[0] for r in con.execute(f"""SELECT DISTINCT substr(market_nuts3,1,3) FROM {LE}
      WHERE incumbent_group_id = ? AND market_nuts3 IS NOT NULL""", [iid]).fetchall()]

    # Praegende Taetigkeit der Auftraggeber. Das ist die Achse, die „Bahnbau" von
    # „Schulverkabelung" trennt, wo die CPV-Klasse beide gleich nennt.
    akt_rows = con.execute(f"""SELECT buyer_activity, count(*) FROM {LE}
      WHERE incumbent_group_id = ? AND buyer_activity IS NOT NULL
      GROUP BY 1 ORDER BY 2 DESC""", [iid]).fetchall()
    typisiert = sum(n for _, n in akt_rows)
    aktivitaet = None
    if typisiert >= AKTIVITAET_MIN_BELEGE:
        top, k = akt_rows[0]
        if k / typisiert >= AKTIVITAET_SCHWELLE and top not in AKTIVITAET_UNSPEZIFISCH:
            aktivitaet = top

    stufen = []
    if div:
        stufen.append({"sql": "substr(cpv_code,1,2) = ?", "par": [div[0]],
                       "label": "sagt der Markt", "art": "division"})
    if klassen:
        namen = [r[0] for r in con.execute(
            f"SELECT label FROM {CL} WHERE substr(cpv_code,1,4) IN "
            f"({','.join('?' * len(klassen))}) AND substr(cpv_code,5,4) = '0000'",
            klassen).fetchall() if r[0]]
        stufen.append({"sql": f"substr(cpv_code,1,4) IN ({','.join('?' * len(klassen))})",
                       "par": list(klassen), "label": "in eurem Fach", "art": "klasse",
                       "hinweis": ", ".join(n[:44] for n in namen[:3]) or None})
    if aktivitaet:
        stufen.append({"sql": "buyer_activity = ?", "par": [aktivitaet],
                       "label": AKTIVITAET_LABEL.get(aktivitaet, "bei euren Auftraggebern"),
                       "art": "aktivitaet"})
    # Bundesweit taetige Firmen bekommen keine Regionsstufe vorgegaukelt.
    if laender and len(laender) < 14:
        stufen.append({"sql": f"substr(market_nuts3,1,3) IN ({','.join('?' * len(laender))})",
                       "par": list(laender), "label": "wo ihr arbeitet", "art": "region"})

    ctx["zuschnitt"] = {"stufen": stufen, "aktivitaet": aktivitaet,
                        "typisiert": typisiert, "klassen": klassen, "division": div[0] if div else None}
    return ctx["zuschnitt"]


# Etiketten fuer die Taetigkeitsstufe. Die eForms-Codes sind fuer den Empfaenger
# unlesbar; „bei Verkehrsbetrieben" ist der Satz, der einen Bahnbauer erreicht.
AKTIVITAET_LABEL = {
    "transport": "bei Verkehrsbetrieben",
    "health": "im Gesundheitswesen",
    "education": "bei Bildungsträgern",
    "environment": "bei Umwelt und Entsorgung",
    "housing": "bei Wohnungs- und Stadtentwicklung",
    "economic_affairs": "in der Wirtschaftsförderung",
    "social_protection": "bei sozialen Trägern",
    "recreation_culture": "bei Kultur und Freizeit",
    "public_order": "bei Sicherheit und Ordnung",
    "defence": "im Verteidigungsbereich",
    "energy": "bei Energieversorgern",
    "water": "bei Wasserversorgern",
    "postal": "bei Postdiensten",
}


def kette_bauen(con, zs, ctx, zusatz_sql="", zusatz_par=None):
    """Stufen nacheinander anwenden und nur behalten, was wirklich einschränkt.

    Gibt die Kette (fürs Anzeigen) und die volle Bedingung (fürs Weiterrechnen) zurück.
    Eine Stufe ohne Wirkung fliegt raus — samt ihrem Etikett. Das ist der Grund, warum
    Etikett und Filter hier zusammen entstehen und nicht an zwei Orten gepflegt werden.
    """
    LE = f"read_parquet('{G}/lead_export.parquet')"
    fremd = "(incumbent_group_id IS NULL OR incumbent_group_id <> ?)"
    bed, par, kette = [], [], []
    vorher = None
    for st in zs["stufen"]:
        p = bed + [st["sql"]], par + st["par"]
        alle = " AND ".join(p[0])
        n = con.execute(
            f"SELECT count(*) FROM {LE} WHERE phase='open' AND {alle} AND {fremd}"
            + (f" AND {zusatz_sql}" if zusatz_sql else ""),
            p[1] + [ctx["id"]] + (zusatz_par or [])).fetchone()[0]
        if vorher is not None and n >= vorher:
            continue                       # nimmt nichts weg → kein Glied, kein Etikett
        bed, par = p[0], p[1]
        glied = {"n": n, "label": st["label"], "art": st["art"]}
        if st.get("hinweis"):
            glied["hinweis"] = st["hinweis"]
        kette.append(glied)
        vorher = n
    return kette, (" AND ".join(bed) if bed else "1=1"), par


def baustein_transparenz(con, ctx):
    """„Wir kennen euch" — und ehrlich dazu, welcher Teil von euch sichtbar ist.

    Das ist der Kern von Svens erstem Ziel. Die Aussage trägt nur, wenn sie die Grenze
    mitliefert: öffentlich benannt werden **Gewinner**. Gemessen an `notice_parties`
    kennen wir 1.233.126 Gewinner namentlich und keinen einzigen unterlegenen Bieter —
    Angebote werden nur gezählt. Wer das verschweigt, behauptet ein vollständiges Bild.
    """
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    SN = f"read_parquet('{G}/../../silver/DE/notices/*/*.parquet')"
    # Die Vergabestelle steht NICHT in `notices` (dort gibt es nur `buyer_countries`),
    # sondern als eigene Zeile in `party_entity` mit role='buyer'. Der erste Anlauf las
    # `n.buyer_name` und flog auf die Nase — der Baustein-Wächter hat den Fehler
    # aufgefangen, die Seite kam ohne diesen Block heraus. Genau dafür ist er da.
    r = con.execute(f"""
      WITH meine AS (
        SELECT DISTINCT p.notice_id FROM {PE} p
        JOIN {EI} ei ON ei.entity_id = p.entity_id
        WHERE p.role = 'winner' AND ei.identity_id = ?
      )
      SELECT (SELECT count(*) FROM meine),
             (SELECT count(DISTINCT b.entity_id) FROM {PE} b
              WHERE b.role = 'buyer' AND b.notice_id IN (SELECT notice_id FROM meine)),
             (SELECT min(year(n.publication_date)) FROM {SN} n
              WHERE n.notice_id IN (SELECT notice_id FROM meine)),
             (SELECT max(year(n.publication_date)) FROM {SN} n
              WHERE n.notice_id IN (SELECT notice_id FROM meine))
    """, [ctx["id"]]).fetchone()
    if not r or not r[0]:
        return None
    return {
        "id": "transparenz", "staerke": 60, "gruppe": "ueber_euch", "form": "kpi",
        # Sven: „'507 zuschläge bekannt' aha, warum nicht: '507 gewonnene Ausschreibungen
        # zwischen 2010 und 2026.'" Die Beschriftung sagt jetzt den ganzen Satz. Das
        # Telegramm sparte drei Wörter und kostete die Aussage.
        "kern": f"Wir kennen {r[0]:,}".replace(",", ".") +
                f" Ausschreibungen, die ihr zwischen {r[2]} und {r[3]} gewonnen habt.",
        "titel": "Das steht öffentlich über euch",
        "zahlen": [
            {"wert": f"{r[0]:,}".replace(",", "."),
             "label": f"gewonnene Ausschreibungen zwischen {r[2]} und {r[3]}"},
            {"wert": f"{r[1]:,}".replace(",", "."), "label": "verschiedene Auftraggeber"},
        ],
        # Diese Zeile ist der Grund, warum der Baustein trägt statt zu prahlen.
        "grenze": ("Eure verlorenen Angebote stehen hier nicht. Öffentlich genannt wird "
                   "nur, wer gewinnt."),
        "bruecke": {"produkt": "Unternehmen",
                    "text": "Das vollständige Profil, mit euren Korrekturen"},
    }


def baustein_abhaengigkeit(con, ctx):
    """Konzentration auf einen Auftraggeber. Nur, wenn sie ausgeprägt UND belegt ist."""
    # WICHTIG: dieselbe Grundgesamtheit wie `baustein_transparenz` — alle Zuschläge aus
    # `party_entity`, nicht die Teilmenge aus `lead_export`, in der die Firma Amtsinhaber
    # ist. Der erste Anlauf zählte über `lead_export` und meldete „1 Auftraggeber
    # insgesamt", während zwei Blöcke höher „6 Vergabestellen" stand. Zwei richtige
    # Zahlen zu zwei verschiedenen Fragen, direkt untereinander — für den Leser schlicht
    # ein Widerspruch, und er hat keine Möglichkeit, das aufzulösen.
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    rows = con.execute(f"""
      WITH meine AS (
        SELECT DISTINCT p.notice_id FROM {PE} p
        JOIN {EI} ei ON ei.entity_id = p.entity_id
        WHERE p.role = 'winner' AND ei.identity_id = ?
      )
      SELECT arg_max(e.canonical_name, e.confidence) nm, count(DISTINCT b.notice_id) n
      FROM {PE} b
      JOIN {EN} e ON e.entity_id = b.entity_id
      WHERE b.role = 'buyer' AND b.notice_id IN (SELECT notice_id FROM meine)
      GROUP BY b.entity_id ORDER BY 2 DESC
    """, [ctx["id"]]).fetchall()
    rows = [(nm, n) for nm, n in rows if nm]
    if not rows:
        return None
    # Nenner ist die Zahl der VERGABEN, nicht die Summe der Käuferzeilen: eine Vergabe
    # kann mehrere Käufer tragen (gemeinsame Beschaffung). Summierte Zeilen ergäben
    # einen Nenner grösser als die Grundgesamtheit und damit zu kleine Anteile.
    ges = con.execute(f"""
      SELECT count(DISTINCT p.notice_id) FROM {PE} p
      JOIN {EI} ei ON ei.entity_id = p.entity_id
      WHERE p.role = 'winner' AND ei.identity_id = ?""", [ctx["id"]]).fetchone()[0]
    if ges < ABHAENGIG_AB_ZUSCHLAEGEN:
        return None

    # Wie WENIGE Auftraggeber reichen für den Löwenanteil? Nicht „der grösste", sondern
    # die kleinste Gruppe, die die Schwelle erreicht.
    #
    # Grund, an einem echten Fall gelernt: Klostermann bekommt 50,1 % von DB Netz und
    # 48,9 % von DB Station&Service — zusammen 99 % von zwei Bahn-Gesellschaften. Eine
    # Prüfung auf den grössten EINZELNEN Auftraggeber sah 50 %, blieb unter der Schwelle
    # und liess den Block ausfallen, obwohl die Abhängigkeit kaum grösser sein könnte.
    #
    # Was hier bewusst NICHT passiert: die beiden zu einem „Konzern Deutsche Bahn"
    # zusammenfassen. `entity_identity` kennt sie als zwei Identitäten
    # (HRB50879 und HRB87691); sie über den Namensstamm zu verschmelzen wäre genau der
    # Automatismus, den das Projekt nach gemessenen 24 % Fehl-Merges verworfen hat.
    # Also wird gezählt, nicht gruppiert — „zwei Auftraggeber" ist belegbar,
    # „ein Konzern" wäre geraten.
    # Die Schwelle wächst mit der Zahl der Auftraggeber. „Drei Auftraggeber stellen 60 %"
    # ist bei den meisten Firmen der Normalfall und damit keine Aussage; „ein Auftraggeber
    # stellt 60 %" ist eine. Ohne diese Staffelung würde der Block fast immer feuern und
    # wäre wieder das, was er ersetzen soll: eine Überschrift ohne Befund.
    kumuliert, treffer = 0, None
    for i, (_, n) in enumerate(rows[:3], start=1):
        kumuliert += n
        anteil = min(kumuliert / ges, 1.0)
        if anteil >= ABHAENGIG_SCHWELLE.get(i, 1.1):
            treffer = (i, anteil)
            break
    if not treffer:
        return None
    k, anteil = treffer

    namen = [nm for nm, _ in rows[:k]]
    # Fuer `baustein_andere_auftraggeber`: der Kontext wird zwischen den Bausteinen
    # geteilt, und dieser hier hat die Namen ohnehin berechnet. Sie ein zweites Mal zu
    # ermitteln hiesse, die Schwellenlogik oben zu verdoppeln — und beim naechsten
    # Feinschliff wuerden beide Stellen auseinanderlaufen.
    ctx["dominante"] = namen

    # DIE FOLGE, NICHT NUR DER BEFUND.
    #
    # „99 % kommen von zwei Auftraggebern" ist eine Beobachtung, die ein Vertriebsleiter
    # laengst kennt. Was fehlt, ist der Satz danach: was passiert, wenn einer wegfaellt.
    # Erst der macht aus einer Zahl einen Grund zu handeln. Der Anteil des GROESSTEN
    # Einzelnen ist dabei die ehrliche Groesse — er beziffert den Ausfall, den ein
    # einziger Auftraggeber ausloesen kann.
    groesster = rows[0][1] / ges
    folge = (f"Fällt der grösste aus, fehlen {groesster*100:.0f} % eures "
             "öffentlichen Geschäfts.")
    # (Hier stand ein `wer`, das den groessten Auftraggeber benannt haette — gebaut,
    # nie in einen Text eingesetzt. Der Name des Auftraggebers im Aufhaenger waere eine
    # Produktentscheidung, keine Aufraeumarbeit; deshalb nur die tote Zeile entfernt.)
    return {
        "id": "abhaengigkeit", "staerke": 95, "gruppe": "ueber_euch", "form": "kpi",
        "kern": (f"{anteil*100:.0f} % eurer Aufträge kommen von einem einzigen Auftraggeber."
                 if k == 1 else
                 f"{anteil*100:.0f} % eurer Aufträge kommen von zwei Auftraggebern."
                 if k == 2 else
                 f"{anteil*100:.0f} % eurer Aufträge kommen von {k} Auftraggebern."),
        "folge": folge,
        "anteil": round(anteil, 3),
        "titel": "Woher eure Aufträge kommen",
        # Die zweite Zahl war „Auftraggeber insgesamt" und stand damit ein zweites Mal
        # auf der Seite — sie steht schon im Transparenz-Baustein. Eine Kachel, die
        # etwas wiederholt, kostet Aufmerksamkeit und gibt nichts zurück.
        "zahlen": [{"wert": f"{anteil*100:.0f} %",
                    "label": (f"eurer Aufträge kommen von {namen[0]}" if k == 1
                              else f"eurer Aufträge kommen von {k} Auftraggebern")}],
        "namen": namen,
        "grenze": (f"Gezählt über {ges} öffentliche Zuschläge. Was ihr ausserhalb "
                   "öffentlicher Vergaben macht, sehen wir nicht."),
        "bruecke": {"produkt": "Strategie",
                    "text": "Wo ihr ausserhalb dieser Konzentration anschlussfähig seid"},
    }


def baustein_vertraege(con, ctx):
    """Die konkrete Liste — Svens zweites Ziel („kennt ihr sie so gut wie wir?")."""
    zeilen = _vertragszeilen(con, ctx["id"])
    if not zeilen:
        return None

    # NUR BELEGTE ZEILEN. Sven: „die qualität der daten ist so naja. wir sollten nur die
    # aufträge anzeigen, wo wir auch eine hohe qualität an informationen haben. ich vermute
    # die werden wissen, wann ihre aufträge enden und welche gerade laufen."
    #
    # Genau das ist der Punkt: der Empfaenger kennt seine eigenen Vertraege. Eine Liste,
    # die er ueberpruefen kann, ist kein Beleg fuer unsere Faehigkeit, sondern eine
    # Einladung, unsere Luecken zu finden. Gemessen bei Klostermann: Enddatum bei ALLEN
    # zehn echt (`timing_source=actual`, im Bestand 15.754 von 15.762), Wert nur bei zwei.
    #
    # Die Tabelle traegt deshalb nicht mehr die Aussage, sondern belegt sie — und zwar mit
    # den Zeilen, die vollstaendig sind. Der Rest wird gezaehlt, nicht gezeigt.
    belegt = [z for z in zeilen if z["vol"] and z["ende"]]
    verschwiegen = len(zeilen) - len(belegt)

    # UNTER DREI ZEILEN GAR KEINE TABELLE. Bei Klostermann ueberlebt genau eine den
    # Filter — eine Tabelle mit einer Zeile ist schwaecher als keine: sie sieht aus, als
    # waere das alles, was wir haben, und lenkt von der Aussage ab, die traegt.
    #
    # Sven: „es ist dann eher ein wow effekt zu sagen '507 aufträge gesamt', '99 % von
    # zwei auftraggebern', daraus ableiten: wir erkennen muster, die euch helfen bessere
    # entscheidungen zu treffen." Genau so: das Muster ist die Nachricht, die Liste
    # hoechstens ihr Beleg. Traegt der Beleg nicht, faellt er weg — nicht die Nachricht.
    if len(belegt) < 3:
        verschwiegen = len(zeilen)
        belegt = []
        vergleich = None
    n_aus = sum(1 for z in zeilen if z["art"] == "auslauf")
    n_fertig = sum(1 for z in zeilen if z["art"] == "fertigstellung")

    # EIN Satz über die Mischung, statt „wird fertig" achtmal untereinander.
    # Sven: „die wissen doch woran sie gerade arbeiten?" — stimmt. Dass ein Bauvorhaben
    # fertig wird, ist für den Empfänger keine Nachricht. Interessant ist erst die
    # Bilanz darüber: ob aus diesem Bestand überhaupt etwas zurückkommt.
    if n_aus and not n_fertig:
        befund = f"Alle {n_aus} werden neu ausgeschrieben, wenn sie auslaufen."
    elif n_fertig and not n_aus:
        befund = (f"Keines dieser {n_fertig} Vorhaben kommt als Neuvergabe zurück, es sind "
                  "einmalige Bauleistungen. Nachschub muss von woanders kommen.")
    elif n_aus:
        befund = (f"{n_aus} davon werden neu ausgeschrieben, {n_fertig} sind einmalige "
                  "Bauleistungen und kommen nicht zurück.")
    else:
        befund = None

    # Ein Schätzwert je Zeile NUR, wenn die Schätzungen sich überhaupt unterscheiden.
    #
    # Bei Klostermann trugen alle acht dieselbe Zahl (250.114 €): der CPV-Median. Acht
    # gleiche „ca."-Beträge untereinander behaupten, jedes Vorhaben sei ungefähr gleich
    # groß, und das ist schlechter als gar keine Angabe. Wo die Schätzung für alle
    # dieselbe ist, ist sie keine Aussage über den einzelnen Vertrag, sondern über das
    # Fachgebiet. Also steht sie EINMAL unter der Tabelle und heisst, was sie ist.
    geschaetzte = {z["_roh"] for z in zeilen if z["_quelle"] != "actual" and z["_roh"]}
    vergleich = None
    # Der Vergleichswert erklaert eine LEERE Spalte in der Tabelle. Ohne Tabelle erklaert
    # er nichts und steht als vierte Fussnote unter einer Karte, die schon zwei hat.
    if len(geschaetzte) == 1:
        vergleich = ("Für die übrigen ist kein Volumen veröffentlicht. Vergleichbare "
                     f"Vergaben in diesem CPV-Bereich liegen bei rund {eur(geschaetzte.pop())}.")
    elif len(geschaetzte) > 1:
        for z in zeilen:
            if not z["vol"] and z["_roh"]:
                z["vol"] = "ca. " + eur(z["_roh"])
    for z in zeilen:
        z.pop("_roh", None); z.pop("_quelle", None)

    return {
        "id": "vertraege", "staerke": 100, "gruppe": "ueber_euch", "form": "karte",
        "vergleich": vergleich,
        "titel": ("Eure laufenden Vorhaben" if belegt else
                  "Was aus euren laufenden Vorhaben zurückkommt"),
        "zeilen": belegt,
        # Den Satz baut der Generator, nicht die Oberflaeche: nur hier ist bekannt, ob
        # ueberhaupt Zeilen stehen. „8 WEITERE Vorhaben" waere falsch, wenn keine erste
        # dasteht — und genau solche Kleinigkeiten liest ein Empfaenger als Schlamperei.
        "verschwiegen_text": (
            None if not verschwiegen else
            (f"Zu euren {verschwiegen} laufenden Vorhaben fehlen uns einzelne Angaben, "
             "deshalb listen wir sie hier nicht auf. Lieber weniger als ungenau."
             if not belegt else
             f"{verschwiegen} weitere zeigen wir nicht, weil uns dort Angaben fehlen.")),
        "befund": befund,
        # KOPFSATZ ≠ KARTENSATZ.
        #
        # Beide standen auf `befund`, und seit `vertraege` den Seitenkopf fuehrt, stand
        # derselbe Satz wortgleich zweimal untereinander auf dem Bildschirm. Genau das
        # hatte die vorige Fassung schon einmal getan (Kernbefund und Kachel sagten beide
        # „99 % von zwei Auftraggebern"), und es kostet zweimal Aufmerksamkeit fuer eine
        # Aussage.
        #
        # Der Kopf traegt die kuerzeste Form des Lochs: eine Zahl und die Folge. Die
        # Begruendung („es sind einmalige Bauleistungen") steht in der Karte, wo die
        # Vorhaben aufgelistet sind und der Satz belegt werden kann.
        "kern": (f"{n_fertig} eurer laufenden Vorhaben enden, ohne dass eines davon neu "
                 "ausgeschrieben wird." if n_fertig and not n_aus else
                 f"{n_aus + n_fertig} eurer laufenden Vorhaben enden, nur {n_aus} davon "
                 "werden neu ausgeschrieben." if n_aus and n_fertig else None),
        "n_auslauf": n_aus, "n_fertigstellung": n_fertig,
        # Diese Zeile stand einmal auf „wo es fehlt, lassen wir das Feld leer statt zu
        # schätzen" — direkt unter der Vergleichszeile, die genau das tut. Zwei Sätze,
        # die sich widersprechen, und der Leser hat keine Möglichkeit zu entscheiden,
        # welcher gilt. Die Grenze dieses Bausteins ist eine andere: der Ausschnitt.
        "grenze": ("Nur was öffentlich bekanntgemacht wurde. Aufträge ausserhalb "
                   "öffentlicher Vergabeverfahren und Nachträge fehlen hier."),
        "bruecke": {"produkt": "Planung",
                    "text": "Fristen und Termine als Kalender, mit Erinnerung"},
    }


def baustein_wettbewerber(con, ctx):
    """NUR bei belegter Head-to-head-Historie. Kein Fallback mehr.

    Der frühere Fallback („grösster Anbieter im CPV-Feld") lieferte bei 96,9 % der Firmen
    einen Namen, der diese Firma nie verdrängt hatte. Lieber kein Block als ein geratener.
    """
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    HH = f"read_parquet('{G}/head_to_head.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    row = con.execute(f"""
      WITH mine AS (SELECT entity_id FROM {EI} WHERE identity_id = ?)
      SELECT wi.identity_id, sum(h.displacements) disp
      FROM {HH} h JOIN {EI} wi ON wi.entity_id = h.winner_entity
      WHERE h.loser_entity IN (SELECT entity_id FROM mine) AND wi.identity_id <> ?
      GROUP BY 1 ORDER BY 2 DESC LIMIT 1
    """, [ctx["id"], ctx["id"]]).fetchone()
    if not row:
        return None
    name = con.execute(f"""SELECT arg_max(e.canonical_name, e.confidence)
      FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id WHERE ei.identity_id = ?""",
      [row[0]]).fetchone()[0]
    if not name:
        return None
    return {
        "id": "wettbewerber", "staerke": 85, "gruppe": "ueber_euch", "form": "kpi",
        "kern": f"{Z.clean_name(name)} hat euch {int(row[1])}-mal verdrängt.",
        "titel": "Wer euch bisher verdrängt hat",
        "zahlen": [{"wert": Z.clean_name(name), "label": "häufigster Gegner"},
                   {"wert": str(int(row[1])), "label": "belegte Verdrängungen"}],
        "grenze": ("Gezählt werden nur Fälle, in denen ein Nachfolgeauftrag an eine "
                   "andere Firma ging. Verlorene Erstvergaben sind nicht sichtbar."),
        "bruecke": {"produkt": "Strategie",
                    "text": "Der Direktvergleich, Vertrag für Vertrag"},
    }


def baustein_offene_im_feld(con, ctx):
    """Was die Firma NICHT weiss: fremde Ausschreibungen, schrittweise auf sie zugeschnitten.

    **Warum ein Trichter und nicht eine Zahl.** „8.080 offene Ausschreibungen in eurem
    Fachgebiet" ist die ganze CPV-Division 45, also jede Bauausschreibung Deutschlands.
    Sven: „schön und gut, aber wie viele genau für klostermann?"

    Die Stufen kommen aus `zuschnitt()` — EINER Stelle für alle Bausteine. Welche Stufen
    es gibt und wie sie heissen, entscheidet dort die Datenlage der Firma; hier wird nur
    noch gezählt und angezeigt. Vorher baute dieser Baustein seine Filter selbst, und der
    Nachbar-Baustein baute andere.

    Die letzte Stufe bleibt bewusst OFFEN: wie viele wirklich passen, hängt an Eignung,
    Kapazität und Zuschnitt, und das steht in keinem öffentlichen Datensatz.
    """
    LE = f"read_parquet('{G}/lead_export.parquet')"
    zs = zuschnitt(con, ctx)
    if not zs["stufen"]:
        return None
    kette, bed, par = kette_bauen(con, zs, ctx)
    if not kette or not kette[-1]["n"]:
        return None
    breit, eng = kette[0]["n"], kette[-1]["n"]

    stellen = con.execute(f"""SELECT count(DISTINCT buyer_name) FROM {LE}
      WHERE phase='open' AND {bed} AND (incumbent_group_id IS NULL OR incumbent_group_id <> ?)""",
      par + [ctx["id"]]).fetchone()[0]

    return {
        "id": "offene_im_feld", "staerke": 80, "gruppe": "fuer_euch", "form": "kpi",
        "kern": f"{zahl(eng)} offene Ausschreibungen passen zu dem, was ihr macht.",
        "titel": "Was gerade offen ist, in eurem Fachgebiet",
        "zahlen": [{"wert": zahl(eng),
                    "label": "offene Ausschreibungen passen zu dem, was ihr macht"},
                   {"wert": zahl(stellen),
                    "label": "Vergabestellen schreiben dort aus"}],
        "trichter": kette,
        # Sven: „den trichter sollten wir als kette zeigen". Der Satz steht ÜBER der
        # Kette, damit sie gelesen wird und nicht nur angesehen.
        "kette": (f"{zahl(breit)} Ausschreibungen sagt der Markt. Wir sagen {zahl(eng)}, "
                  "und mit eurem Profil werden es noch weniger, die wirklich zu euch passen."),
        "grenze": ("Eingegrenzt über eure eigenen Zuschläge. Ob eine Ausschreibung wirklich "
                   "passt, hängt an Eignung und Kapazität, und das steht in keiner "
                   "Bekanntmachung."),
        "bruecke": {"produkt": "Planung", "text": "Die Liste, gefiltert auf euer Profil"},
    }


def baustein_andere_auftraggeber(con, ctx):
    """Offene Ausschreibungen von Auftraggebern AUSSERHALB der Konzentration.

    **Warum es diesen Baustein gibt.** Die Seite diagnostizierte „99 % eurer Aufträge
    kommen von zwei Auftraggebern" und lieferte danach eine Liste, in der dieselben zwei
    wieder drinsteckten. Wer Klumpenrisiko feststellt, muss zeigen, wo der Ersatz liegt.

    **Warum er nur mit Tätigkeitsstufe feuert.** Der erste Anlauf verengte nur über CPV
    und Region und empfahl einem Bahnbauer Schulverkabelung — die CPV-Klasse „Installation
    von elektrischen Leitungen" umfasst beides. Ohne die Achse `buyer_activity` ist
    „andere Auftraggeber" keine Empfehlung, sondern eine Liste, und dieser Baustein
    verspricht ausdrücklich Passung. Fehlt die Achse, faellt er aus. Das ist die richtige
    Antwort: lieber ein Baustein weniger als eine Empfehlung, die den Empfänger verliert.

    Abgegrenzt wird über den Namen der Vergabestelle, weil `lead_export` keine
    `buyer_entity` führt. Das ist gröber und irrt zu unseren Ungunsten (Schreibvarianten
    zählen getrennt) — bei einer Verkaufsaussage die richtige Richtung.
    """
    dominante = ctx.get("dominante")
    zs = zuschnitt(con, ctx)
    if not dominante or not zs["aktivitaet"]:
        return None
    LE = f"read_parquet('{G}/lead_export.parquet')"
    ph = ",".join("?" * len(dominante))
    kette, bed, par = kette_bauen(con, zs, ctx)
    if not kette:
        return None
    gesamt = kette[-1]["n"]

    r = con.execute(f"""SELECT count(*), count(DISTINCT buyer_name) FROM {LE}
      WHERE phase='open' AND {bed}
        AND (incumbent_group_id IS NULL OR incumbent_group_id <> ?)
        AND (buyer_name IS NULL OR buyer_name NOT IN ({ph}))""",
      par + [ctx["id"]] + dominante).fetchone()
    if not r or not r[0] or not gesamt:
        return None
    n, stellen = r
    wo = AKTIVITAET_LABEL.get(zs["aktivitaet"], "in eurem Bereich")

    # WENIGE TREFFER? DANN DIE SACHE STATT DER ANZAHL.
    #
    # Sven am 2026-08-17: „ich finde es gar nicht schlimm, wenn wenige übrig bleiben. das
    # funktioniert aber nur wenn die qualität da ist. wenn es 6 wirkliche treffer sind,
    # nehme ich die lieber als 35 potenzielle, die womöglich passen könnten."
    #
    # Genau deshalb: eine Kachel mit „6" ist eine Behauptung, sechs Zeilen mit Auftraggeber,
    # Titel und Frist sind der Beleg. Bei Klostermann steht dort „DB Energie, HH 110kV-
    # Einspeisung Eidelstedt" — und Eidelstedt ist der Ort, an dem die Firma GERADE baut.
    # Diese eine Zeile beweist die Passung besser als jede Zahl.
    #
    # Oberhalb der Grenze kippt es: dreissig Zeilen liest niemand, dort trägt die Zahl.
    zeilen = []
    if n <= CHANCEN_ZEIGEN_BIS:
        for b_, t_, d_, v_, vs_ in con.execute(f"""SELECT DISTINCT ON (title, buyer_name)
            buyer_name, title, deadline_date, value_eur, value_source
          FROM {LE} WHERE phase='open' AND {bed}
            AND (incumbent_group_id IS NULL OR incumbent_group_id <> ?)
            AND (buyer_name IS NULL OR buyer_name NOT IN ({ph}))
          ORDER BY title, buyer_name, deadline_date""",
          par + [ctx["id"]] + dominante).fetchall():
            zeilen.append({
                "titel": t_, "buyer": b_,
                "vol": eur(v_) if vs_ == "actual" else None,
                # Die Frist ist hier die tragende Spalte, nicht das Vertragsende: sie sagt,
                # ob man ueberhaupt noch bieten kann.
                "ende": d_.strftime("%d.%m.%Y") if d_ and hasattr(d_, "strftime") else None,
                # Rohdatum MIT, damit die Oberflaeche „noch N Tage" beim ANZEIGEN rechnet.
                # Hier zu rechnen hiesse, die Zahl einzufrieren: `outreach.json` entsteht
                # einmal und liegt danach im Deploy. Eine Woche spaeter staende „in 2 Tagen"
                # ueber einer laengst abgelaufenen Frist — schlimmer als keine Angabe.
                "endeISO": d_.isoformat() if d_ and hasattr(d_, "isoformat") else None,
                "_sort": d_.isoformat() if d_ and hasattr(d_, "isoformat") else "9999",
                "art": "unklar",
            })
        # ⚠ Nach dem ROHEN Datum sortieren, nicht nach der deutschen Schreibweise.
        # Lexikalisch steht „01.09.2026" vor „19.08.2026" — die Frist, die in zwei Tagen
        # ablaeuft, rutschte damit ans Ende der Liste. Bei einer Liste, deren ganzer Zweck
        # die Dringlichkeit ist, ist das der schlimmstmoegliche Fehler.
        zeilen.sort(key=lambda z: z["_sort"])
        for z in zeilen:
            z.pop("_sort", None)

    beispiele = [x[0] for x in con.execute(f"""SELECT buyer_name FROM {LE}
      WHERE phase='open' AND {bed}
        AND (incumbent_group_id IS NULL OR incumbent_group_id <> ?)
        AND (buyer_name IS NULL OR buyer_name NOT IN ({ph})) AND buyer_name IS NOT NULL
      GROUP BY 1 ORDER BY count(*) DESC LIMIT 4""",
      par + [ctx["id"]] + dominante).fetchall()]

    return {
        "id": "andere_auftraggeber", "staerke": 88, "gruppe": "fuer_euch",
        # Karte statt Kachel, sobald wir die Vorgaenge selbst zeigen koennen.
        "form": "karte" if zeilen else "kpi",
        "zeilen": zeilen,
        "kern": (f"{zahl(n)} offene Ausschreibungen {wo} kommen nicht von euren "
                 "bisherigen Auftraggebern."),
        "titel": f"Wo eure Aufträge herkommen könnten, {wo}",
        "zahlen": [{"wert": zahl(n), "label": f"offene Ausschreibungen {wo}, ohne eure bisherigen"},
                   {"wert": zahl(stellen), "label": "verschiedene Vergabestellen dahinter"}],
        # Namen statt Zahlen: „BVG, Kölner Verkehrs-Betriebe, SSB Stuttgart" beweist die
        # Passung in einer Zeile, wo eine Zahl sie nur behauptet.
        "namen": beispiele,
        "grenze": (f"Von {zahl(gesamt)} offenen Ausschreibungen in eurem Zuschnitt. "
                   "Abgegrenzt über den Namen der Vergabestelle, Schreibvarianten desselben "
                   "Hauses zählen also getrennt."),
        "bruecke": {"produkt": "Strategie",
                    "text": "Wo ihr ausserhalb dieser Konzentration anschlussfähig seid"},
    }


def baustein_zweitversuche(con, ctx):
    """Chronisch erfolglose Bedarfe — eingegrenzt auf das, was die Firma wirklich baut.

    **Die Zahl stand vorher ungefiltert da.** Gefiltert wurde nur auf die CPV-DIVISION,
    also „Bau" insgesamt, bundesweit: 1.419. Direkt daneben stand ein mühsam auf Fach und
    Region verengter Trichter mit 200. Als Leser kann man die grosse Zahl nicht einordnen
    und liest sie im Zweifel klein — neben einer sauber hergeleiteten wirkt eine
    ungefilterte wie ein Blender.

    Gemessen: über die eigenen CPV-KLASSEN sind es 173 statt 1.419. Eine weitere Stufe
    über die Region bringt nichts (173 bleibt 173) und wird deshalb NICHT gezeigt — eine
    Stufe, die nichts wegnimmt, täuscht Präzision vor, die es nicht gibt.
    """
    LE = f"read_parquet('{G}/lead_export.parquet')"
    RS = f"read_parquet('{G}/retender_signal.parquet')"
    div = con.execute(f"""SELECT substr(cpv_code, 1, 2) FROM {LE}
      WHERE incumbent_group_id = ? AND cpv_code IS NOT NULL
      GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", [ctx["id"]]).fetchone()
    if not div:
        return None
    klassen = [r[0] for r in con.execute(f"""SELECT DISTINCT substr(cpv_code, 1, 4) FROM {LE}
      WHERE incumbent_group_id = ? AND cpv_code IS NOT NULL""", [ctx["id"]]).fetchall()]

    breit = con.execute(f"""SELECT count(*) FROM {RS}
      WHERE still_open AND substr(cpv_class, 1, 2) = ?""", [div[0]]).fetchone()[0]
    if klassen:
        ph = ",".join("?" * len(klassen))
        r = con.execute(f"""SELECT count(*), max(fail_years) FROM {RS}
          WHERE still_open AND substr(cpv_class, 1, 4) IN ({ph})""", klassen).fetchone()
    else:
        r = con.execute(f"""SELECT count(*), max(fail_years) FROM {RS}
          WHERE still_open AND substr(cpv_class, 1, 2) = ?""", [div[0]]).fetchone()
    if not r or not r[0]:
        return None
    n, jahre = r[0], int(r[1] or 0)

    return {
        "id": "zweitversuche", "staerke": 75, "gruppe": "fuer_euch", "form": "kpi",
        "kern": (f"{zahl(n)} Bedarfe in genau eurem Fach werden seit Jahren erfolglos "
                 "ausgeschrieben."),
        "titel": "Wo wiederholt niemand geboten hat",
        "zahlen": [{"wert": zahl(n),
                    "label": "Aufträge in eurem Fach, mehrfach erfolglos ausgeschrieben"},
                   {"wert": f"bis zu {jahre} Jahre", "label": "sucht dieselbe Stelle schon"}],
        "grenze": (f"Eingegrenzt auf eure eigenen CPV-Klassen, aus {zahl(breit)} in der "
                   "ganzen Bauwirtschaft. Dort ist der Wettbewerb am dünnsten, weil kaum "
                   "jemand bietet."),
        "bruecke": {"produkt": "Strategie", "text": "Die Segmente, sortiert nach Chance"},
    }


# WELCHER SATZ IN DEN SEITENKOPF KOMMT — und die Reihenfolge ist eine Verkaufsentscheidung.
#
# Vorher stand `abhaengigkeit` vorn: „99 % eurer Auftraege kommen von zwei Auftraggebern."
# Ein Vertriebsleiter weiss das laengst; es ist eine Beobachtung, kein Grund zu handeln.
#
# `vertraege` sagt dagegen etwas, das er sich NICHT selbst beschaffen kann: dass von seinen
# laufenden Vorhaben keines als Neuvergabe zurueckkommt. Das ist ein Loch in der Pipeline,
# und es ist der Satz, der zum Telefon greifen laesst. Deshalb steht er jetzt vorn — die
# Konzentration folgt als Verschaerfung, nicht als Aufmacher.
#
# `transparenz` (507 gewonnene Ausschreibungen) ist zuletzt gerueckt und in der Staerke
# gefallen: es ist die eigene Zahl des Empfaengers. Sie beweist, dass wir Daten haben, und
# schafft keinen Wert — sie hatte den teuersten Platz der Seite belegt.
KERN_RANG = ["vertraege", "abhaengigkeit", "andere_auftraggeber", "wettbewerber",
             "zweitversuche", "offene_im_feld", "transparenz"]

# Reihenfolge des AUFRUFS, nicht der Anzeige (die macht `staerke`). `andere_auftraggeber`
# muss NACH `abhaengigkeit` laufen: es liest die dominanten Auftraggeber aus dem geteilten
# Kontext, statt die Schwellenlogik ein zweites Mal zu bauen.
BAUSTEINE = [baustein_transparenz, baustein_vertraege, baustein_abhaengigkeit,
             baustein_andere_auftraggeber,
             baustein_wettbewerber, baustein_offene_im_feld, baustein_zweitversuche]


def build_payload(con, identity_id, now):
    b = con.execute("SELECT firmenname FROM base WHERE identity_id = ?", [identity_id]).fetchone()
    if not b:
        return None
    ctx = {"id": identity_id, "now": now}

    gebaut = []
    for f in BAUSTEINE:
        try:
            teil = f(con, ctx)
        except Exception as e:                       # ein kaputter Baustein darf nicht
            print(f"  ! {f.__name__}: {e}", file=sys.stderr)   # die ganze Seite kosten
            teil = None
        if teil:
            gebaut.append(teil)
    if not gebaut:
        return None
    gebaut.sort(key=lambda t: -t["staerke"])

    # Vorbelegung fuer den warmen Weg: Branche und Regionen aus der eigenen Historie.
    # Beides ist im Onboarding aenderbar — es ist ein Vorschlag, keine Festlegung.
    CP = f"read_parquet('{G}/dim_cpv.parquet')"
    LE = f"read_parquet('{G}/lead_export.parquet')"
    br = con.execute(f"""SELECT c.branche FROM {LE} l
      JOIN {CP} c ON c.division = substr(l.cpv_code, 1, 2)
      WHERE l.incumbent_group_id = ? GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""",
      [identity_id]).fetchone()
    branche = BRANCHE_AUS_DIMCPV.get(br[0]) if br else None
    # Leistungsorte, nicht Sitz der Vergabestelle — s. baustein_offene_im_feld.
    regionen = [r[0] for r in con.execute(f"""SELECT substr(market_nuts3, 1, 3) FROM {LE}
      WHERE incumbent_group_id = ? AND market_nuts3 IS NOT NULL
      GROUP BY 1 ORDER BY count(*) DESC""", [identity_id]).fetchall()]

    nach_id = {t["id"]: t for t in gebaut}
    kern = next((nach_id[i]["kern"] for i in KERN_RANG
                 if i in nach_id and nach_id[i].get("kern")), None)

    # ── ZUSTELLQUITTUNG ─────────────────────────────────────────────────────────────
    # Wir wissen, an welche Adresse wir diesen Link schicken. Registriert sich jemand mit
    # GENAU dieser Adresse, ist das Postfachkontrolle — ein Beleg, der ohne Firmendomain
    # auskommt. Das hebt gerade die 47 % der Firmen, zu denen wir keine Domain haben
    # (Klostermann ist eine davon).
    #
    # Gespeichert wird der HASH, nicht die Adresse: `outreach.json` ist eine Datei, die
    # im Deploy mitfaehrt, und eine Adressliste darin waere eine Adressliste zu viel.
    # Derselbe Zuschnitt wie bei `suppliers.json` (sha256, 16 Hex) — er schuetzt gegen
    # das ERNTEN, nicht gegen das Nachpruefen einer bereits bekannten Adresse. Mehr
    # braucht es hier auch nicht.
    #
    # ⚠ Der Token ist damit eine Zustellquittung, KEIN Ausweis. Wer ihn weiterleitet,
    # gibt keine Berechtigung weiter — der Empfaenger landet bei „unbestaetigt", und das
    # ist richtig so.
    zustell = con.execute("SELECT email FROM base WHERE identity_id = ?", [identity_id]).fetchone()
    zustell_hash = (hashlib.sha256(zustell[0].strip().lower().encode()).hexdigest()[:16]
                    if zustell and zustell[0] else None)
    _FREEMAIL = {"gmail.com", "gmx.de", "gmx.net", "web.de", "t-online.de", "outlook.com",
                 "hotmail.com", "yahoo.de", "icloud.com", "freenet.de", "aol.com",
                 "googlemail.com", "posteo.de", "mailbox.org", "arcor.de"}
    zustell_dom = None
    if zustell and zustell[0] and "@" in zustell[0]:
        d = zustell[0].strip().lower().split("@")[-1]
        zustell_dom = None if d in _FREEMAIL else d

    return {
        "id": identity_id, "name": Z.clean_name(b[0]),
        # Nur der Hash und das Datum. Die Adresse selbst bleibt in der Zielliste.
        "zustellung": ({"hash": zustell_hash, "am": _dt.date.today().isoformat(),
                        # Die DOMAIN der Zustelladresse — unsere eigene Wahl, nicht aus
                        # fremden Daten geraten. Damit ist auch die Kollegin belegt, die
                        # sich mit `peter@klostermann-hamm.de` registriert, obwohl wir an
                        # `info@…` geschrieben haben. Genau der Fall, der sonst durch das
                        # Raster faellt: Firmen ohne hinterlegte Domain (47 %).
                        # Freemail faellt raus — `gmail.com` belegt keine Firma.
                        "domain": zustell_dom}
                       if zustell_hash else None),
        # TT.MM.JJJJ statt ISO. `str(now)` lieferte 2026-08-16 — korrekt, aber in einem
        # deutschen Vertriebsdokument liest das niemand als Datum, sondern als Kennung.
        "stand": now.strftime("%d.%m.%Y") if hasattr(now, "strftime") else str(now),
        "kern": kern,
        # Sven: „daraus ableiten: wir erkennen muster, die euch helfen bessere
        # entscheidungen zu treffen." Der Satz gehoert ans Ende der HEUTE-Haelfte: er
        # sagt, wozu die Zahlen darueber gut sind, ohne eine weitere Zahl zu behaupten.
        # Vorbelegung. `null` heisst „wir wissen es nicht" und fuehrt im Onboarding zur
        # normalen Auswahl — nicht zu einer geratenen Voreinstellung.
        "vorbelegung": {"branche": branche, "regionen": regionen},
        "muster": ("Aus solchen Mustern leiten wir ab, welche Ausschreibungen zu euch "
                   "passen und welche ihr euch sparen könnt."),
        "bausteine": gebaut,
        "belegt": [t["id"] for t in gebaut],
        # Die Produktbereiche, in die diese Firma konkret fuehrt — entdoppelt, in der
        # Reihenfolge der Baustein-Staerke.
        "bereiche": list(dict.fromkeys(t["bruecke"]["produkt"] for t in gebaut)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name"); ap.add_argument("--plz"); ap.add_argument("--ort"); ap.add_argument("--id")
    a = ap.parse_args()
    if not (a.name or a.plz or a.ort or a.id):
        print("Bitte --name/--plz/--ort oder --id angeben", file=sys.stderr); return 1

    con = duckdb.connect(); con.execute("SET threads=4")
    now = Z.build_population(con, adhoc={"name": None, "plz": None, "ort": None})
    ids = target_ids(con, a)
    if a.id and not con.execute("SELECT 1 FROM base WHERE identity_id=?", [a.id]).fetchone():
        print("Firma nicht in belegten Zuschlägen", file=sys.stderr); return 1

    store = {}
    if OUT.exists():
        try:
            store = json.loads(OUT.read_text())
        except Exception:
            store = {}
    added = []
    for iid in ids:
        p = build_payload(con, iid, now)
        if not p:
            continue
        store[token_of(iid)] = p
        added.append((token_of(iid), p["name"], p["belegt"]))
    OUT.write_text(json.dumps(store, ensure_ascii=False))
    print(f"{len(added)} Landing(s) → {OUT} (gesamt {len(store)})")
    for tok, nm, belegt in added[:20]:
        print(f"  /t/{tok}   {nm}")
        print(f"            belegt: {', '.join(belegt)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
