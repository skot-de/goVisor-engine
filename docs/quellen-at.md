# Quelle AT — Österreich (Discovery, 2026-07-28)

**Zwei Ebenen, sehr unterschiedlicher Aufwand:**

## 1. Oberschwellig AT → über TED (empfohlen, niedrigster Aufwand)
AT-Vergaben über EU-Schwelle laufen über **TED** — dieselbe Quelle, die goVisor schon hat, nur
DE-gefiltert. Die Pipeline ist **länder-agnostisch**:
- CLI: `python -m govisor.cli ingest --country AT --from YYYY-MM` (der Bulk-Walker `bulk._walk`
  überspringt Fremdländer-Zips, `--country AT` zieht die AT-Notices)
- Parser (`schema`/`normalize`) hat **kein DE-Hardcoding** → AT = eForms/legacy wie DE, kein neuer Parser
- Danach `silver --country AT`, dann Gold. **Gold ist DE-getunt** (Entity-Res/Markt-KPIs) → wie bei CH
  eine schlanke `build_at_gold`-Brücke ODER `gold --country AT`; Export vereint per `union_by_name`,
  `country='AT'` → aktiviert den AT-Zweig des DACH-Länderfilters.

**Aufwand:** klein (Pipeline steht). Hauptkosten: AT-TED-Bulk-Download (mehrere Monate/Jahre) + Gold-Brücke.

## 2. Unterschwellig AT → ANKÖ / USP (gated, später)
- **ANKÖ / vergabeportal.at**: marktführend, 3.000+ Bekanntmachungen/Tag, aber **kommerziell/Login-
  gegated** — keine offene API gefunden (wie die Portallandschaft-Doku für viele Portale warnte).
- **USP** (usp.gv.at), **eVergabe.at**, **e-beschaffung.at**: offizielle Bundes-Suche — noch nicht auf
  offenen Feed geprüft, vermutlich ebenfalls gated.
- Machbarkeit wie beim Bieterfragen-Report: reine Bekanntmachungs-Metadaten oft offen, Unterlagen hinter
  Login. **Keine automatisierte Account-Anlage** (Betriebsgrenze). → eigener, größerer Schritt.

## Empfehlung
**AT zuerst über TED** (oberschwellig, gratis via bestehende Pipeline) — validiert schnell und
schaltet den AT-Filter live. Unterschwellig (ANKÖ/USP) ist der langwierige, gated Teil — separat
bewerten, ggf. nach cosinex (DE unterschwellig, größeres Volumen).

## Quellen
- [ANKÖ Vergabeportal](https://www.ankoe.at/auftragnehmer/ausschreibungen/)
- [TED (habt ihr)](https://ted.europa.eu/) · Bulk per Land, `ingest --country AT`
