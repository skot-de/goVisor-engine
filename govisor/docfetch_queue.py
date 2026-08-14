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

# Der Vorgang gibt strukturell nichts her — erneutes Abrufen kostet nur Zeit und fremde
# Last. Wer hier etwas ergänzt, sollte begründen können, warum es sich NIE ändern kann.
DAUERHAFT = frozenset({
    "ohne_unterlagen",      # Ex-Ante-Bekanntmachung: es gibt keine Unterlagen
    "kein_downloadbereich",  # Portal leitet anonyme Abrufe aufs Dashboard um
    "frameset",             # Inhalts-Frame bleibt ohne Sitzung leer
})

# Kann sich ändern. Nicht bei jedem Lauf erneut probieren, aber auch nicht aufgeben.
SPERRE_TAGE = 7

# Kein Fehlschlag: `probe` ist der Trockenlauf-Vermerk, `downloaded` der Erfolg.
KEIN_FEHLSCHLAG = frozenset({"downloaded", "probe"})


def _pfad(out_root: Path, name: str) -> Path:
    return out_root / f"_manifest_{name}.parquet"


def frueher(out_root: Path, name: str) -> dict[str, dict]:
    """Letzter bekannter Ausgang je `lead_id`. Leeres Ergebnis, wenn es kein Manifest gibt.

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
        rows = con.execute(
            f"""SELECT lead_id, arg_max(status, {wann_sql}) AS status,
                       max({wann_sql}) AS wann
                FROM read_parquet('{p.as_posix()}') GROUP BY lead_id""").fetchall()
    except Exception:                                     # noqa: BLE001
        return {}
    return {r[0]: {"status": r[1], "wann": r[2]} for r in rows}


def ueberspringen(vorher: dict, heute: dt.date | None = None) -> str | None:
    """Soll dieser Kandidat übersprungen werden? Gibt den Grund zurück, sonst None."""
    if not vorher:
        return None
    status = vorher.get("status")
    if status in KEIN_FEHLSCHLAG:
        return None
    if status in DAUERHAFT:
        return status
    wann = vorher.get("wann")
    if not wann:
        return None
    heute = heute or dt.date.today()
    if isinstance(wann, dt.datetime):
        wann = wann.date()
    if (heute - wann).days < SPERRE_TAGE:
        return f"{status} (Sperre bis {wann + dt.timedelta(days=SPERRE_TAGE)})"
    return None


def filtere(offen: list, vorher: dict[str, dict], lead_id=lambda x: x[0]) -> tuple[list, dict]:
    """Kandidatenliste → (was zu holen ist, {grund: anzahl}).

    `lead_id` holt die Kennung aus einem Eintrag; die Fetcher führen unterschiedliche
    Tupel-Formen, deshalb wird der Zugriff hereingereicht statt eine Form zu erzwingen.
    """
    bleibt, gruende = [], {}
    for eintrag in offen:
        grund = ueberspringen(vorher.get(lead_id(eintrag)) or {})
        if grund:
            schluessel = grund.split(" (")[0]
            gruende[schluessel] = gruende.get(schluessel, 0) + 1
        else:
            bleibt.append(eintrag)
    return bleibt, gruende


def schreibe(out_root: Path, name: str, saetze: list[dict]) -> int:
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
    neu = [{**s, "versucht_am": s.get("versucht_am") or heute} for s in saetze]
    p = _pfad(out_root, name)
    alt: list[dict] = []
    if p.exists():
        try:
            alt = pq.read_table(p).to_pylist()
        except Exception:                                 # noqa: BLE001
            alt = []          # unlesbares Altmanifest kostet Historie, nicht den Lauf

    # Je lead_id nur der jüngste Satz — sonst wächst die Datei mit jedem Lauf ohne Nutzen.
    je_id: dict[str, dict] = {}
    for s in alt + neu:
        lid = s.get("lead_id")
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
    return f"  übersprungen (früher gescheitert): {teile}"
