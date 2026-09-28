"""Hält die Zuordnung Abrufer → (Manifest-Datei, Schlüsselfeld) ehrlich.

WARUM ES DIESE DATEI GIBT (2026-09-20). Es gab zwei Konventionen, die zufällig meistens
übereinstimmten: den Kurznamen, unter dem `scripts/rueckstau.py` einen Abrufer führt, und
den Namen, unter dem der Abrufer sein Manifest SCHREIBT. Bei drei von dreizehn liefen sie
auseinander:

    simap_docs        sucht _manifest_simap_docs.parquet   → geschrieben wird _manifest_simap
    vergabeportal_at  sucht _manifest_vergabeportal_at     → geschrieben wird _manifest_vergabeportal
    cosinex           Datei da, aber `frueher()` ohne id_feld="notice_id" gerufen

Gemerkt hat es niemand, weil `frueher()` auf alle drei Lagen mit demselben leeren Ergebnis
antwortete wie auf „noch nichts versucht". Folge: jeder längst gelernte Ausgang zählte
weiter in den Rückstau, und der Dokumenten-Arbeiter wählte danach aus, wer drankommt —
simap_docs stand mit 1.566 gemeldeten und 3 echten Aufgaben dauerhaft auf Platz eins.

Zwei Sorten Test:
1. **Gegen die echte Platte.** Für jeden Abrufer, dessen Manifest existiert, muss der
   Nachschlag etwas finden. Genau das hätte den Fehler am ersten Tag gemeldet.
2. **Synthetisch.** Dass `frueher()` laut wird, statt leer zu antworten — sonst ist der
   Wächter selbst wieder stumm.
"""
import importlib.util
import pathlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

from govisor.docfetch_queue import (  # noqa: E402
    KENNUNG, ManifestFehler, _pfad, frueher, kennung,
)

_spec = importlib.util.spec_from_file_location("rs", ROOT / "scripts" / "rueckstau.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


# ── 1. Gegen die echte Datenlage ────────────────────────────────────────────

@pytest.mark.parametrize("kurz", sorted(rs.abrufer()))
def test_jeder_abrufer_findet_sein_manifest(kurz):
    """Existiert das Manifest, muss der Nachschlag es auch lesen können.

    Ein leeres Ergebnis bei vorhandener Datei ist genau der Fehler, der dreizehn Tage
    unsichtbar war — nicht „noch nichts versucht", sondern „falsch nachgeschlagen".
    """
    name, id_feld = kennung(kurz)
    ort = rs._manifest_ort(kurz)
    p = _pfad(ort, name)
    if not p.exists():
        pytest.skip(f"{kurz}: noch kein Manifest ({p.name}) — nie gelaufen, kein Befund")
    stand = frueher(ort, name, id_feld=id_feld)
    assert stand, (
        f"{kurz}: {p.name} existiert, der Nachschlag liefert aber NICHTS. Dann zählt jeder "
        f"bereits gelernte Ausgang wieder in den Rückstau. Eintrag in "
        f"docfetch_queue.KENNUNG prüfen.")


def test_kennung_deckt_jeden_abweichenden_abrufer_ab():
    """Die Tabelle darf keine Einträge für Abrufer führen, die es nicht mehr gibt."""
    bekannt = set(rs.abrufer())
    verwaist = sorted(set(KENNUNG) - bekannt)
    assert not verwaist, f"KENNUNG führt Abrufer, die es nicht mehr gibt: {verwaist}"


# ── 2. Synthetisch: wird der Nachschlag wirklich laut? ──────────────────────

def _manifest(tmp_path, name: str, id_feld: str, ids: list[str]) -> pathlib.Path:
    p = _pfad(tmp_path, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({id_feld: ids, "status": ["gated"] * len(ids)}), p)
    return p


def test_falsches_schluesselfeld_wird_laut_statt_leer(tmp_path):
    """Der eigentliche Fehler vom 20.09.: Datei da, Spalte anders, Antwort leer."""
    _manifest(tmp_path, "probe", "notice_id", ["a", "b"])
    with pytest.raises(ManifestFehler) as e:
        frueher(tmp_path, "probe")            # Vorgabe lead_id — die Spalte gibt es nicht
    assert "notice_id" in str(e.value), "die Meldung muss die vorhandenen Spalten nennen"


def test_mit_richtigem_schluesselfeld_liest_er_normal(tmp_path):
    _manifest(tmp_path, "probe", "notice_id", ["a", "b"])
    stand = frueher(tmp_path, "probe", id_feld="notice_id")
    assert set(stand) == {"a", "b"}


def test_fehlende_datei_bleibt_still_aber_streng_warnt(tmp_path, capsys):
    """Beim ersten Lauf eines Abrufers ist eine fehlende Datei normal — dann kein Lärm.

    Für eine Auswertung, die über ALLE Abrufer zählt, ist sie fast immer ein Namensdreher;
    die setzt `streng=True` und bekommt einen Hinweis.
    """
    assert frueher(tmp_path, "gibtsnicht") == {}
    assert capsys.readouterr().err == ""
    assert frueher(tmp_path, "gibtsnicht", streng=True) == {}
    assert "kein Manifest" in capsys.readouterr().err


def test_rueckstand_schluckt_einen_manifestfehler_nicht(tmp_path, monkeypatch):
    """`except Exception: pass` hatte den Defekt zugedeckt — das darf nicht zurückkommen."""
    quelle = (ROOT / "scripts" / "rueckstau.py").read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(z for z in quelle.splitlines()
                               if not z.lstrip().startswith("#"))
    assert "except ManifestFehler:" in ohne_kommentar and "raise" in ohne_kommentar, (
        "rueckstand() muss ManifestFehler durchfallen lassen, sonst ist der Wächter stumm")


# ── 3. Die Gegenrichtung — und sie ist die wichtigere ───────────────────────
#
# ⚠ Test 1 hat eine Lücke, und ich bin am 2026-09-20 hineingelaufen: er überspringt, wenn
# die gesuchte Datei nicht existiert. Genau das ist aber der Namensdreher — `rueckstand()`
# suchte `_manifest_simap_docs.parquet`, fand nichts, und „nichts gefunden" sah aus wie
# „dieser Abrufer lief noch nie". Ein Test, der bei Abwesenheit schweigt, kann Abwesenheit
# nicht prüfen.
#
# Die Gegenrichtung schliesst das: JEDE Manifest-Datei, die auf der Platte liegt, muss von
# genau einem Abrufer beansprucht werden. Eine herrenlose Datei ist entweder ein Dreher
# oder der Rest eines gelöschten Abrufers — beides will man sehen.

def _manifeste_auf_der_platte() -> set[pathlib.Path]:
    return set((ROOT / "data" / "docs").glob("*/_manifest*.parquet"))


def test_jede_manifest_datei_gehoert_einem_abrufer():
    da = _manifeste_auf_der_platte()
    if not da:
        pytest.skip("keine Manifeste auf der Platte")
    beansprucht = set()
    for kurz in rs.abrufer():
        name, _ = kennung(kurz)
        beansprucht.add(_pfad(rs._manifest_ort(kurz), name))
    herrenlos = sorted(p.relative_to(ROOT).as_posix() for p in da - beansprucht)
    assert not herrenlos, (
        "Diese Manifeste beansprucht kein Abrufer — entweder ein Namensdreher zwischen "
        "Kurzname und Manifest-Name (dann zaehlt jeder gelernte Ausgang wieder in den "
        f"Rueckstau), oder der Rest eines geloeschten Abrufers: {herrenlos}")
