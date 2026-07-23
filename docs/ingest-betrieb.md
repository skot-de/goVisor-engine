# goVisor — Regelmäßiger Ingest-Betrieb

**Status:** 2026-07-22 (P1)
**Ziel:** TED-Daten frisch halten, damit Alerts (#9) und Win-Detection (#6) zeitnah sind.

---

## Wie TED liefert

TED stellt **nur Monatspakete** bereit (`ted.europa.eu/packages/monthly/YYYY-MM`).
Ein tägliches oder Einzel-Notice-Feed gibt es nicht. Das **laufende Monatspaket wächst
während des Monats** — neue Notizen kommen laufend dazu. „Frisch bleiben" heißt daher:
das laufende (und für spät gemeldete Notizen das **vorige**) Monatspaket regelmäßig neu
ziehen.

**Konsequenz für die Latenz:** Alerts sind so frisch wie der letzte Refresh-Lauf, nicht
„in Echtzeit" (das steht auch in Ticket 09 v2). Ein täglicher Lauf ist die sinnvolle
Obergrenze — häufiger bringt nichts, weil sich das Monatspaket nur langsam füllt.

### ⚠ Freshness-Grenze (gemessen 2026-07-22)

Das **laufende** Monatspaket ist verzögert verfügbar: `packages/monthly/2026-07`
lieferte **404**, `2026-06` **200**. Heißt: bis das laufende Paket erscheint, ist der
Vormonat die frischeste Quelle → **die Timing-Latenz kann bis zu ~einem Monat betragen.**
Der Refresh fängt den 404 sauber ab (verarbeitet den Vormonat weiter), aber die Grenze
ist real.

**Echte Tagesfrische** ginge über TED-**Tagespakete**: `packages/daily/…` existiert
(liefert 400 = falsches ID-Format, nicht 404 = fehlt) — ist im Repo aber **nicht
implementiert** (nur `monthly`). Wenn Alert-Freshness geschäftskritisch wird, ist das
Tagespaket-Ingest der nächste Ausbau (ID-Format recherchieren, Dedup gegen Monatspaket).
Für V1 mit „daily Digest"-Alerts ist die Monatspaket-Latenz vertretbar.

---

## Der Refresh-Lauf

`scripts/refresh.py` macht idempotent und ohne LLM-Kosten:

1. **Ingest** laufender Monat immer (`--force`, wächst); **Vormonat nur bei Änderung**
   — HEAD-Fingerprint (`Content-Length`) gegen `data/cache/ingest_fingerprints.json`;
   unverändert → Re-Download übersprungen (spart ~400 MB + Silber-Rebuild). `evict` spart Platz.
2. **Silber** neu (force) **nur für frisch ingestierte Monate** (nicht alle 270).
3. **Voller Gold-Rebuild** (`python -m govisor.cli gold`) — **~3 Min**. **Keine LLM-/API-
   Kosten** (die Nachfolge-Adjudikation ist separat). Zwei Optimierungen (bit-identisch geprüft):
   - **HR-Index gecacht** (`data/cache/hr_index.parquet`, mtime-invalidiert): 136 s → 6 s (22×).
   - **`build_entities`** war 443 s (Bottleneck: `_write` fügte 3,7M Zeilen row-by-row ein) →
     **20 s** via vektorisiertem Arrow-Bulk-Insert (hilft allen Buildern) + in-run-Memoisierung.
4. **FK-Integrität** — jeder Verstoß = stiller Datenverlust → Exit 1.

Exit 0 = sauber, 1 = Ingest-/Gold-/FK-Fehler (vom Scheduler auswertbar). Robust: fehlt
das laufende Paket noch (Monatsanfang), wird geloggt und weitergemacht.

Manuell:
```
python scripts/refresh.py     # aus dem Repo-Root (Skript ist aber pfad-robust)
```

---

## Täglich planen (macOS launchd)

Der Job ist als Datei bereitgestellt, **aber nicht aktiviert** — bewusst einzuschalten:

```bash
cp scripts/de.govisor.refresh.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/de.govisor.refresh.plist
```

Läuft täglich **06:00**, Logs in `~/Library/Logs/govisor-refresh.log`.

Prüfen / stoppen:
```bash
launchctl list | grep govisor                       # geladen?
launchctl unload ~/Library/LaunchAgents/de.govisor.refresh.plist   # abschalten
tail -f ~/Library/Logs/govisor-refresh.log          # zuschauen
```

**Cron-Alternative** (Linux/Server):
```
0 6 * * *  cd /Pfad/zu/C09_govisor && /usr/bin/python3 scripts/refresh.py >> ~/govisor-refresh.log 2>&1
```

---

## Separat & seltener: LLM-Nachfolge-Adjudikation

`scripts/succession_llm.py` adjudiziert die **Content-Succession-Queue** per LLM
(OpenRouter, kostet Geld — Key in `.secrets/openrouter.key`). Das läuft **nicht** im
täglichen Refresh (der merged nur gecachte Kanten). Empfehlung: **wöchentlich/monatlich**
manuell oder als separater, seltenerer Job — nur wenn genug neue Queue-Einträge da sind.

Der tägliche Refresh nutzt die zuletzt adjudizierten Kanten; neue Leads bekommen ihre
LLM-Nachfolge erst beim nächsten Adjudikations-Lauf. Für Timing-Alerts (Frist/Auslauf)
und Attribution ist das unkritisch — die hängen nicht an der LLM-Adjudikation.

---

## Was der Refresh NICHT tut (bewusst)

- **Kein voller Backfill** — nur laufender + voriger Monat. Historische Lücken schließt
  man einmalig mit `python -m govisor.cli ingest --from YYYY-MM --to YYYY-MM --resume`.
- **Kein inkrementelles Gold** — der Gold-Rebuild ist immer vollständig (Erfahrung: die
  Konsistenz-Garantien wiegen die paar Minuten auf).
- **Keine LLM-Kosten** — s. o.
