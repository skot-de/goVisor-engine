"""Gedächtnis für die Unterlagen-Warteschlangen — damit ein Lauf vorankommt.

**Warum es das gibt (gemessen 2026-08-14).** Alle vier Unterlagen-Fetcher wählten ihre
Kandidaten nach demselben Muster: nimm die offenen Leads, sortiere nach Frist, überspringe
die, für die schon eine ZIP-Datei liegt. Das klingt richtig und ist es fast — bis auf einen
Fall, der in der Praxis der häufigste ist: **ein Vorgang, der keine Unterlagen hergibt,
hinterlässt keine Datei.** Er steht deshalb beim nächsten Lauf wieder ganz vorn. Und beim
übernächsten. Für immer.

Gemessen sah das so aus:

    aumass          2 von 2 Versuchen  „ohne_unterlagen (Ex Ante Bekanntmachung)"
    staatsanzeiger  3 von 3 Versuchen  „frameset"
    healyhudson    40 von 40 Versuchen  0 geladen, davon 30× „kein_downloadbereich"

Das las sich wie drei kaputte Fetcher. Es war ein Fehler, dreimal. Die Fetcher meldeten
ihren Ausgang sauber — nur hörte ihnen niemand zu: das Manifest wurde bei jedem Lauf
**überschrieben** statt fortgeschrieben, und die Kandidatenwahl las es nie.

**Zwei Sorten Fehlschlag, zwei Antworten.** Sie zu vermengen wäre der nächste Fehler:

    DAUERHAFT   Der Vorgang gibt strukturell nichts her. Eine Ex-Ante-Bekanntmachung
                kündigt eine beabsichtigte Direktvergabe an — es GIBT keine Unterlagen,
                heute nicht und in drei Wochen nicht. Ein Portal, das anonyme Abrufe aufs
                Dashboard umleitet, tut das nicht zufällig. Nie wieder versuchen.

    VORÜBERGEHEND  Eine Vorgangsseite ohne Dateien kann morgen welche haben (Unterlagen
                werden oft nach der Bekanntmachung nachgereicht). Ein Netzfehler ist ein
                Netzfehler. Hier wäre „nie wieder" ein echter Datenverlust — also eine
                Sperrfrist statt eines Ausschlusses.

**Markieren statt löschen**, wie überall im Projekt: nichts wird aus der Warteschlange
entfernt. Der Grund steht im Manifest und ist abfragbar; die Auswahl überspringt nur.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

# ── EIN VOKABULAR ─────────────────────────────────────────────────────────────────────────
#
# Warum das hier steht und nicht in jedem Abrufer: die Warteschlange verzweigt über die
# EXAKTE Zeichenkette. Zwei Schreibweisen für dieselbe Sache sind deshalb kein
# Schönheitsfehler, sondern ein Fehler in der Entscheidung. Gemessen am 2026-08-15 lagen
# `fehler` (2×) und `error` (1×) nebeneinander in den Manifesten — dieselbe Aussage, und
# nur eine davon hätte eine Regel je erreichen können.
#
# `normalisiere()` läuft beim Schreiben UND beim Lesen. Deshalb heilen sich Altbestände
# von selbst; niemand muss eine Migration fahren, damit die Sperrlogik greift.
ALIASE = {
    "error": "fehler",
    "empty": "leer",
    "ohne_dokumente": "leer",
    "gate": "gated",
}


def normalisiere(status: str | None) -> str | None:
    """Schreibweise auf die kanonische Form bringen (siehe ALIASE)."""
    if status is None:
        return None
    return ALIASE.get(status, status)


# Der Vorgang gibt strukturell nichts her — erneutes Abrufen kostet nur Zeit und fremde
# Last. Wer hier etwas ergänzt, sollte begründen können, warum es sich NIE ändern kann.
DAUERHAFT = frozenset({
    "ohne_unterlagen",      # Ex-Ante-Bekanntmachung: es gibt keine Unterlagen
    "kein_downloadbereich",  # Portal leitet anonyme Abrufe aufs Dashboard um
    "frameset",             # Inhalts-Frame bleibt ohne Sitzung leer
    "abgelaufen",           # Frist vorbei — das Portal nimmt die Unterlagen herunter
})

# ── DRITTE KLASSE: blockiert ──────────────────────────────────────────────────────────────
#
# Weder „gibt es nicht" noch „vielleicht morgen". Die Unterlagen EXISTIEREN, wir kommen nur
# nicht heran — es fehlt ein Zugang, eine Zusage oder eine Fähigkeit auf unserer Seite.
#
# Warum das eine eigene Klasse braucht (gemessen 2026-08-15): `gated` ist mit **389 Leads**
# der grösste Blockade-Topf überhaupt. Als „vorübergehend" behandelt kostet er jede Woche
# 389 sinnlose Abrufe bei fremden Portalen. Als „dauerhaft" markiert wäre er an dem Tag
# verloren, an dem ein Konto existiert — und niemand würde daran denken.
#
# Ein blockierter Vorgang läuft deshalb NICHT über eine Frist wieder auf, sondern erst,
# wenn der benannte Blocker fällt: entweder der Abrufer meldet ihn beim Aufruf als gelöst
# (`filtere(..., frei={"konto"})`) oder jemand räumt ihn von Hand (`entsperre`).
BLOCKIERT = {
    "gated":                "konto",   # cosinex: Teilnahmeantrag/Login nötig
    "gesperrt":             "konto",
    "abgewiesen":           "konto",
    "nicht_angemeldet":     "konto",
    "kein_zugriff":         "konto",
    "kein_token":           "konto",
    "interesse_noetig":     "interesse",   # simap: Interesse muss bekundet werden
    "interesse_abgelehnt":  "interesse",
    "nur_cockpit":          "portal",  # Portal gibt anonym nur die Oberfläche her
    "nur_einzeldateien":    "portal",  # kein Sammel-ZIP; Einzelabruf noch nicht gebaut
    "zu_gross":             "groesse",  # über der Grössengrenze DIESES Laufs
}

# Kann sich ändern. Nicht bei jedem Lauf erneut probieren, aber auch nicht aufgeben.
SPERRE_TAGE = 7

# Kein Fehlschlag — hier ist nichts nachzuholen.
#   downloaded  ZIP liegt
#   exists      lag schon vor diesem Lauf
#   probe       Trockenlauf-Vermerk
#   nur_liste   das IST das Ergebnis: die Abrufer für subreport und vergabeportal.at
#               sammeln Dateilisten, sie laden nichts herunter. Als Fehlschlag gewertet
#               liefe jeder erfasste Vorgang für immer in der Warteschlange mit.
KEIN_FEHLSCHLAG = frozenset({"downloaded", "exists", "probe", "nur_liste"})

# Historische Dateinamen. `docfetch.py` (cosinex) schreibt seit jeher `_manifest.parquet`
# ohne Quellenkürzel — 3.416 Zeilen Vorgeschichte. Statt sie umzubenennen (ein Schreibzugriff
# auf `data/`, der einen laufenden Index stören könnte) zeigt der Pfad einfach dorthin,
# solange die Datei existiert. Neue Quellen bekommen den einheitlichen Namen.
_ALT_DATEI = {"cosinex": "_manifest.parquet"}


def _pfad(out_root: Path, name: str) -> Path:
    alt = _ALT_DATEI.get(name)
    if alt and (out_root / alt).exists():
        return out_root / alt
    return out_root / f"_manifest_{name}.parquet"


def frueher(out_root: Path, name: str, id_feld: str = "lead_id") -> dict[str, dict]:
    """Letzter bekannter Ausgang je Kennung. Leeres Ergebnis, wenn es kein Manifest gibt.

    `id_feld` gibt es, weil `docfetch.py` seine Sätze über `notice_id` führt und die übrigen
    Abrufer über `lead_id`. Eine Doppelspalte nur zur Vereinheitlichung wäre schlechter: sie
    könnte auseinanderlaufen, und dann wüsste niemand, welche gilt.

    Bewusst fehlertolerant: ein unlesbares Manifest darf einen Lauf nicht verhindern. Der
    schlimmste Fall ist, dass wieder von vorn probiert wird — der Zustand von gestern.
    """
    p = _pfad(out_root, name)
    if not p.exists():
        return {}
    try:
        import duckdb
        con = duckdb.connect()
        spalten = {r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')").fetchall()}
        # Manifeste von vor dem 2026-08-14 kennen `versucht_am` nicht. Statt sie zu
        # verwerfen (und damit die gemessenen Fehlschlaege), gilt dann das Datum der
        # Datei — fuer die Sperrfrist genau genug, und die DAUERHAFT-Faelle brauchen es
        # ohnehin nicht.
        if "versucht_am" in spalten:
            wann_sql = "coalesce(versucht_am, DATE '1970-01-01')"
        else:
            import datetime as _dt
            stand = _dt.date.fromtimestamp(p.stat().st_mtime)
            wann_sql = f"DATE '{stand.isoformat()}'"
        if id_feld not in spalten:
            return {}
        rows = con.execute(
            f"""SELECT {id_feld}, arg_max(status, {wann_sql}) AS status,
                       max({wann_sql}) AS wann
                FROM read_parquet('{p.as_posix()}') GROUP BY {id_feld}""").fetchall()
    except Exception:                                     # noqa: BLE001
        return {}
    return {r[0]: {"status": normalisiere(r[1]), "wann": r[2]} for r in rows}


def ueberspringen(vorher: dict, heute: dt.date | None = None,
                  frei: frozenset[str] | set[str] = frozenset()) -> str | None:
    """Soll dieser Kandidat übersprungen werden? Gibt den Grund zurück, sonst None.

    `frei` nennt die Blocker, die der Aufrufer als gelöst meldet — etwa `{"konto"}`, wenn
    für dieses Portal inzwischen Zugangsdaten hinterlegt sind. Nur der Abrufer selbst weiss
    das; die Warteschlange darf es nicht raten.
    """
    if not vorher:
        return None
    status = normalisiere(vorher.get("status"))
    if status in KEIN_FEHLSCHLAG:
        return None
    if status in DAUERHAFT:
        return status
    blocker = BLOCKIERT.get(status)
    if blocker:
        if blocker in frei:
            return None                 # Zugang da → nochmal versuchen, ohne Frist
        return f"{status} (blockiert: {blocker})"
    wann = vorher.get("wann")
    if not wann:
        return None
    heute = heute or dt.date.today()
    if isinstance(wann, dt.datetime):
        wann = wann.date()
    if (heute - wann).days < SPERRE_TAGE:
        return f"{status} (Sperre bis {wann + dt.timedelta(days=SPERRE_TAGE)})"
    return None


def filtere(offen: list, vorher: dict[str, dict], lead_id=lambda x: x[0],
            frei: frozenset[str] | set[str] = frozenset()) -> tuple[list, dict]:
    """Kandidatenliste → (was zu holen ist, {grund: anzahl}).

    `lead_id` holt die Kennung aus einem Eintrag; die Fetcher führen unterschiedliche
    Tupel-Formen, deshalb wird der Zugriff hereingereicht statt eine Form zu erzwingen.
    """
    bleibt, gruende = [], {}
    for eintrag in offen:
        grund = ueberspringen(vorher.get(lead_id(eintrag)) or {}, frei=frei)
        if grund:
            schluessel = grund.split(" (")[0]
            gruende[schluessel] = gruende.get(schluessel, 0) + 1
        else:
            bleibt.append(eintrag)
    return bleibt, gruende


def entsperre(out_root: Path, name: str, blocker: str) -> int:
    """Alle Sätze eines Blockers aus dem Manifest nehmen — der nächste Lauf probiert sie neu.

    Der Weg von Hand, wenn ein Blocker fällt, ohne dass ein Abrufer es merken kann: die
    Grössengrenze wird angehoben, ein Portal öffnet seinen Download, ein Konto entsteht.
    Gibt die Zahl der wieder freigegebenen Sätze zurück.

    Bewusst LÖSCHEND und nicht „Status auf offen setzen": ein Satz ohne Manifest-Eintrag ist
    exakt der Zustand „noch nie versucht", und den kann die Auswahl bereits.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    p = _pfad(out_root, name)
    if not p.exists():
        return 0
    try:
        zeilen = pq.read_table(p).to_pylist()
    except Exception:                                     # noqa: BLE001
        return 0
    bleibt = [z for z in zeilen
              if BLOCKIERT.get(normalisiere(z.get("status"))) != blocker]
    frei = len(zeilen) - len(bleibt)
    if frei:
        tmp = p.with_suffix(".part")
        pq.write_table(pa.Table.from_pylist(bleibt), tmp, compression="zstd")
        tmp.replace(p)
    return frei


def schreibe(out_root: Path, name: str, saetze: list[dict], id_feld: str = "lead_id") -> int:
    """Manifest FORTSCHREIBEN statt überschreiben. Gibt die Gesamtzahl der Zeilen zurück.

    Das alte Verhalten (`write_table` auf die Ergebnisse des aktuellen Laufs) warf mit
    jedem Lauf die gesamte Vorgeschichte weg. Damit war nicht nur die Warteschlange blind,
    sondern auch jede spätere Frage nach dem Verlauf unbeantwortbar.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    if not saetze:
        return 0
    heute = dt.date.today()
    # Normalisiert wird beim SCHREIBEN, nicht erst beim Lesen: sonst stünde die abweichende
    # Schreibweise dauerhaft in der Datei und jede Auswertung daneben müsste sie kennen.
    neu = [{**s, "status": normalisiere(s.get("status")),
            "versucht_am": s.get("versucht_am") or heute} for s in saetze]
    p = _pfad(out_root, name)
    alt: list[dict] = []
    if p.exists():
        try:
            alt = pq.read_table(p).to_pylist()
        except Exception:                                 # noqa: BLE001
            alt = []          # unlesbares Altmanifest kostet Historie, nicht den Lauf

    # Je Kennung nur der jüngste Satz — sonst wächst die Datei mit jedem Lauf ohne Nutzen.
    je_id: dict[str, dict] = {}
    for s in alt + neu:
        lid = s.get(id_feld)
        if lid is None:
            continue
        vorhanden = je_id.get(lid)
        if vorhanden is None or _wann(s) >= _wann(vorhanden):
            je_id[lid] = s

    zeilen = list(je_id.values())
    felder = sorted({k for z in zeilen for k in z})
    zeilen = [{k: z.get(k) for k in felder} for z in zeilen]
    out_root.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part")
    pq.write_table(pa.Table.from_pylist(zeilen), tmp, compression="zstd")
    tmp.replace(p)
    return len(zeilen)


def _wann(s: dict) -> dt.date:
    w = s.get("versucht_am")
    if isinstance(w, dt.datetime):
        return w.date()
    return w if isinstance(w, dt.date) else dt.date(1970, 1, 1)


def bericht(gruende: dict[str, int]) -> str:
    """Eine Zeile für die Ausgabe. Leer, wenn nichts übersprungen wurde.

    Übersprungenes wird BENANNT — ein Lauf, der still 200 Kandidaten auslässt und „3
    versucht" meldet, führt in die Irre.
    """
    if not gruende:
        return ""
    teile = ", ".join(f"{k}={v}" for k, v in sorted(gruende.items()))
    # „bekannter Ausgang" statt „früher gescheitert": seit es die Klasse `BLOCKIERT` gibt,
    # ist der häufigste Grund kein Fehlschlag, sondern ein fehlender Zugang. Die alte
    # Formulierung hätte 389 wartende Vorgänge als kaputt dargestellt.
    return f"  übersprungen (bekannter Ausgang): {teile}"
