# Technik-Ticket: Inkrementelles `build_entities`

> **⚠ ÜBERHOLT (2026-07-22, bei der Umsetzung):** Beim Implementieren zeigte das
> Profiling, dass der Flaschenhals **nicht** die Auflösung war, sondern **`_write`**
> — es fügte 3,7M party_entity-Zeilen **row-by-row per `executemany`** ein (336 s).
> Behoben durch **vektorisiertes Arrow-Bulk-Insert** (alle 7 Builder profitieren) +
> **in-run-Memoisierung** von `resolve_supplier` (84 % Wiederholungen). Ergebnis:
> `build_entities` **443 s → 20 s (~22×), bit-identisch** (Golden-Hashes geprüft), **ohne**
> die unten skizzierte Per-Monat-Cache-Komplexität. Das Ticket bleibt als Analyse/
> Lehrstück stehen; sein Ziel ist erreicht (build_entities ist kein Bottleneck mehr).
> Die Kern-Disziplin (Bit-Identität via Golden-Test, HR-mtime-Denken) hat sich bewährt.

**Status:** Überholt — Ziel einfacher erreicht (s. o.)
**Ursprünglicher Entwurf (2026-07-22)**
**Typ:** Backend-Performance (kein Produkt-Feature)
**Motivation:** `build_entities` = **443 s ≈ 74 %** des Gold-Rebuilds (profiliert). Es
löst bei **jedem** Lauf alle ~1,8M Parteien neu auf, obwohl beim täglichen Refresh nur
~2 Monate Silber neu sind. Der HR-Index ist bereits gecacht (22×); dies ist der große Rest.

---

## Kern-Erkenntnis (aus dem Code)

`build_entities` besteht aus **zwei Schichten** mit sehr unterschiedlichem Charakter:

| Schicht | Was | Kosten | Abhängigkeit |
|---|---|---|---|
| **A — Auflösung** | pro Partei: `resolve_supplier(name, national_id, plz, hr_index)` → stabile `entity_id` + Record | **443 s** (1,8M Aufrufe) | **rein pro Partei** (deterministisch, kein Cross-Notice) |
| **B — Konsolidierung** | `_consolidate_by_national_id` + Aliase über die **gesamte** Entity-Menge | ~Sekunden (323k Entities) | **global** (Set-abhängig: PLZ-Belege, „genau 1 ID-Entity je Name") |

**Schicht A ist deterministisch pro Notice → cachebar.** Schicht B ist global, aber
billig → **immer voll laufen lassen**, wodurch die „0 Fehl-Merges"-Garantie unangetastet bleibt.

---

## Ziel

Beim Refresh nur die **geänderten Monate** neu auflösen (Schicht A), den Rest aus dem
Cache nehmen, dann Schicht B global über die Union rechnen. Erwartung: **443 s → ~30 s**
(nur laufender + voriger Monat werden neu aufgelöst).

**Nicht-Ziel:** Verhalten ändern. Der Output muss **bit-identisch** zum Voll-Rebuild sein.

---

## Design

### Neuer Zwischenstand: `party_resolved` (Cache, pro Monat partitioniert)

Persistiere die **rohe (vor-konsolidierte)** Auflösung je Partei:

```
party_resolved/year=YYYY/MM.parquet:
  notice_id, role, seq, raw_entity_id,
  canonical_name, national_id, method, confidence, norm, plz
```

Deterministisch aus (Partei-Feldern + HR-Index). Ersetzt die In-Memory-`entity_of`/
`links`/`plz_of`-Berechnung als **materialisierten, monatsweise cachebaren** Stand.

### Ablauf `build_entities` (neu)

```
1. Bestimme geänderte Monate (Silber-mtime > party_resolved-mtime ODER HR-Index neuer).
   - HR-Index geändert  -> ALLE Monate neu (Auflösung könnte kippen).  [selten]
   - sonst              -> nur die geänderten Monate.
2. Für jeden zu erneuernden Monat: notice_parties -> resolve_supplier -> party_resolved/…
   (unveränderte Monate: Cache behalten).
3. Schicht B (global, billig):
   a. Union aller party_resolved laden -> entity_of (distinct raw_entity_id + Record),
      plz_of (PLZ-Mengen je raw_entity_id).
   b. merge_map, flagged = _consolidate_by_national_id(entity_of, plz_of)
      merge_map.update(_load_entity_aliases(...))
   c. links = party_resolved mit merge_map.get(raw_entity_id, raw_entity_id)
4. Schreibe entities.parquet + party_entity.parquet + entity_merge_candidates.parquet
   aus EINEM konsistenten Stand (wie heute) -> kein neues Waisen-Risiko.
```

### Cache-Invalidierung

- **Silber-Monat neu** (mtime) → dieser Monat neu auflösen.
- **HR-Index-Quelle neu** (dieselbe mtime-Logik wie der HR-Cache) → **alle** Monate neu,
  weil sich Auflösungen ändern könnten. Selten (Register-Update), aber Pflicht.
- Ein `party_resolved`-Manifest (`{month: hr_source_mtime}`) macht die HR-Abhängigkeit explizit.

---

## Sicherheit / Invarianten

1. **Bit-Identität:** inkrementeller Output == Voll-Rebuild-Output (Entities, party_entity,
   merges, flagged). **Regressionstest ist Pflicht** (s. Testplan).
2. **Set-Abhängigkeit von Schicht B ist abgedeckt:** eine neue PLZ oder neue ID-Entity aus
   einem geänderten Monat kann eine Merge-Entscheidung kippen — deshalb läuft **B immer voll
   über die Union**, nie inkrementell. Genau das bewahrt die Konsolidierungs-Korrektheit.
3. **Kein neues Waisen-Risiko:** entities + party_entity werden weiter aus einem In-Memory-
   Stand geschrieben; die bestehende Fail-Fast-FK-Prüfung nach `build_entities` bleibt.
4. **HR-Determinismus:** Schicht A ist nur dann cachebar, solange `resolve_supplier` eine
   reine Funktion bleibt. Falls je Cross-Notice-Signal einzieht (z. B. Häufigkeits-basierte
   Kanonik), bricht die Annahme — dann Cache invalidieren. Als Invariante dokumentieren.

---

## Umsetzungsschritte

1. `build_party_resolved(cfg, country, months=None)` — Schicht A, monatsweise, schreibt
   `party_resolved/…`. `months=None` = alle fehlenden/veralteten.
2. `build_entities` umbauen: Schicht A über den Cache beziehen, Schicht B unverändert.
3. Manifest für HR-Quell-mtime; bei Änderung Voll-Invalidierung.
4. CLI/`refresh.py`: die geänderten Monate an `build_party_resolved` durchreichen (die
   Refresh-Logik kennt sie bereits — `fresh`).
5. Regressionstest + FK-Check + Voll-vs-Inkrementell-Vergleich.

## Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Schicht-A-Determinismus bricht (künftig Cross-Notice-Signal) | als Invariante dokumentiert; Regressionstest fängt Divergenz |
| HR-Update unbemerkt → veraltete Auflösung | mtime-Manifest erzwingt Voll-Reresolve |
| Cache korrupt/teilweise | fehlender/älterer Monat → automatisch neu aufgelöst (idempotent) |
| Merge-Entscheidung kippt durch neue Daten | Schicht B läuft immer voll → korrekt per Konstruktion |

## Akzeptanzkriterien

1. Voll-Rebuild und inkrementeller Rebuild auf **denselben** Daten erzeugen **identische**
   `entities`, `party_entity`, `entity_merge_candidates` (Zeilen-Set-Gleichheit).
2. HR-Index-Änderung löst nachweislich Voll-Reresolve aus.
3. Täglicher Refresh (nur laufender+voriger Monat neu): `build_entities` **< 60 s** (statt 443).
4. FK-Integrität nach jedem Lauf sauber (bestehender Check).
5. Bestehende Entity-Tests bleiben grün.

## Testplan

- **Golden-Test:** aktuellen Voll-Output einfrieren → inkrementell (1 Monat „ändern" durch
  Touch) → Set-Gleichheit der drei Tabellen assert.
- **HR-Invalidierung:** HR-Quelle touchen → alle Monate müssen neu aufgelöst werden.
- **Idempotenz:** zweimal inkrementell ohne Änderung → keine Neuauflösung, identischer Output.

## Aufwand / Reihenfolge

Mittel (~1–2 Tage sorgfältig). **Voraussetzung ist nichts** — der HR-Cache (bereits gebaut)
und die `fresh`-Monatsliste im Refresh sind die Bausteine. Lohnt sich, sobald der tägliche
Job produktiv läuft; bis dahin ist der Voll-Rebuild (~10 Min) tragbar.

Siehe auch: [`ingest-betrieb.md`], [`v1-gap-analysis.md`].
