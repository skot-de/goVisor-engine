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
            # Der Wert steht NUR da, wenn er belegt ist. Vorher stand die CPV-Median-
            # Imputation dort mit einem Sternchen daneben — technisch gekennzeichnet,
            # praktisch als Zahl gelesen. Eine geschätzte Zahl neben einem echten
            # Vertragstitel liest niemand als Schätzung.
            "vol": eur(v) if vs == "actual" else None,
            "ende": ende.strftime("%m/%Y") if ende and hasattr(ende, "strftime") else None,
            "art": art,
        })
    return zeilen


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
        "id": "transparenz", "staerke": 100,
        "titel": "Das steht öffentlich über euch",
        "zahlen": [
            {"wert": f"{r[0]:,}".replace(",", "."), "label": "Zuschläge benannt"},
            {"wert": f"{r[1]:,}".replace(",", "."), "label": "Vergabestellen"},
            {"wert": f"{r[2]} bis {r[3]}" if r[2] and r[3] else None, "label": "Zeitraum"},
        ],
        # Diese Zeile ist der Grund, warum der Baustein trägt statt zu prahlen.
        "grenze": ("Was hier nicht steht: eure verlorenen Angebote. Öffentlich benannt "
                   "wird nur, wer den Zuschlag bekommt. Angebote werden gezählt, nicht "
                   "namentlich genannt."),
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
    wer = namen[0] if k == 1 else f"von {k} Auftraggebern"
    return {
        "id": "abhaengigkeit", "staerke": 90,
        "titel": "Woher eure Aufträge kommen",
        "zahlen": [{"wert": f"{anteil*100:.0f} %", "label": (f"von {wer}" if k == 1 else wer)},
                   {"wert": str(len(rows)), "label": "Auftraggeber insgesamt"}],
        "namen": namen,
        "grenze": (f"Gezählt über {ges} öffentliche Zuschläge. Aufträge ausserhalb "
                   "öffentlicher Vergabeverfahren sind hier nicht enthalten."),
        "bruecke": {"produkt": "Strategie",
                    "text": "Wo ihr ausserhalb dieser Konzentration anschlussfähig seid"},
    }


def baustein_vertraege(con, ctx):
    """Die konkrete Liste — Svens zweites Ziel („kennt ihr sie so gut wie wir?")."""
    zeilen = _vertragszeilen(con, ctx["id"])
    if not zeilen:
        return None
    n_aus = sum(1 for z in zeilen if z["art"] == "auslauf")
    n_fertig = sum(1 for z in zeilen if z["art"] == "fertigstellung")
    return {
        "id": "vertraege", "staerke": 95,
        "titel": "Eure laufenden Vorhaben, aus öffentlichen Bekanntmachungen",
        "zeilen": zeilen,
        "n_auslauf": n_aus, "n_fertigstellung": n_fertig,
        "grenze": ("Volumen steht nur dort, wo es in der Bekanntmachung beziffert ist. "
                   "Wo es fehlt, lassen wir das Feld leer statt zu schätzen."),
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
        "id": "wettbewerber", "staerke": 85,
        "titel": "Wer euch bisher verdrängt hat",
        "zahlen": [{"wert": Z.clean_name(name), "label": "häufigster Gegner"},
                   {"wert": str(int(row[1])), "label": "belegte Verdrängungen"}],
        "grenze": ("Gezählt werden nur Fälle, in denen ein Nachfolgeauftrag an eine "
                   "andere Firma ging. Verlorene Erstvergaben sind nicht sichtbar."),
        "bruecke": {"produkt": "Strategie",
                    "text": "Der Direktvergleich, Vertrag für Vertrag"},
    }


def baustein_offene_im_feld(con, ctx):
    """Was die Firma NICHT weiss: fremde Ausschreibungen in ihrem Fachgebiet.

    Der stärkste Baustein für den Verkauf, weil er als einziger nichts über den Empfänger
    behauptet, sondern etwas zeigt, das er nicht hat. Die Prämisse der alten Seite lag
    genau andersherum: sie erzählte ihm von seinen eigenen Verträgen — dem, was er besser
    weiss als wir und wo unsere Daten am dünnsten sind.
    """
    LE = f"read_parquet('{G}/lead_export.parquet')"
    div = con.execute(f"""SELECT substr(cpv_code, 1, 2) d, count(*) FROM {LE}
      WHERE incumbent_group_id = ? AND cpv_code IS NOT NULL
      GROUP BY 1 ORDER BY 2 DESC LIMIT 1""", [ctx["id"]]).fetchone()
    if not div:
        return None
    r = con.execute(f"""SELECT count(*), count(DISTINCT buyer_name) FROM {LE}
      WHERE phase = 'open' AND substr(cpv_code, 1, 2) = ?
        AND (incumbent_group_id IS NULL OR incumbent_group_id <> ?)""",
      [div[0], ctx["id"]]).fetchone()
    if not r or not r[0]:
        return None
    return {
        "id": "offene_im_feld", "staerke": 80,
        "titel": "Was gerade offen ist, in eurem Fachgebiet",
        "zahlen": [{"wert": f"{r[0]:,}".replace(",", "."), "label": "offene Ausschreibungen"},
                   {"wert": f"{r[1]:,}".replace(",", "."), "label": "Vergabestellen"}],
        "grenze": ("Alle offenen Verfahren im selben CPV-Bereich, ohne eure eigenen. "
                   "Ob sie zu euch passen, entscheidet das Profil."),
        "bruecke": {"produkt": "Planung", "text": "Die Liste, gefiltert auf euer Profil"},
    }


def baustein_zweitversuche(con, ctx):
    """Chronisch erfolglose Bedarfe im Fachgebiet — das stärkste Einstiegssignal."""
    LE = f"read_parquet('{G}/lead_export.parquet')"
    RS = f"read_parquet('{G}/retender_signal.parquet')"
    div = con.execute(f"""SELECT substr(cpv_code, 1, 2) FROM {LE}
      WHERE incumbent_group_id = ? AND cpv_code IS NOT NULL
      GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", [ctx["id"]]).fetchone()
    if not div:
        return None
    r = con.execute(f"""SELECT count(*), max(fail_years) FROM {RS}
      WHERE still_open AND substr(cpv_class, 1, 2) = ?""", [div[0]]).fetchone()
    if not r or not r[0]:
        return None
    return {
        "id": "zweitversuche", "staerke": 75,
        "titel": "Wo wiederholt niemand geboten hat",
        "zahlen": [{"wert": f"{r[0]:,}".replace(",", "."), "label": "chronische Bedarfe"},
                   {"wert": f"bis {int(r[1])} Jahre", "label": "erfolglos in Folge"}],
        "grenze": ("Bedarfe, die dieselbe Stelle über mehrere Jahre erfolglos "
                   "ausgeschrieben hat. Dort ist der Wettbewerb am dünnsten."),
        "bruecke": {"produkt": "Strategie", "text": "Die Segmente, sortiert nach Chance"},
    }


BAUSTEINE = [baustein_transparenz, baustein_vertraege, baustein_abhaengigkeit,
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

    return {
        "id": identity_id, "name": Z.clean_name(b[0]), "stand": str(now),
        "bausteine": gebaut,
        "belegt": [t["id"] for t in gebaut],
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
