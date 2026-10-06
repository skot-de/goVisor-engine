# Cleanup-Bericht: gebaut und nicht eingebunden

**Stand:** 2026-10-06 · **Erzeugt von** `python3 scripts/pruefe_leichen.py` (die Zahlen) ·
**Urteil und Risiko** von Hand. ⚠ Jede Zahl hier traegt dieses Datum; wer sie aendert, zieht
das Datum mit.

**Nichts ist geloescht.** Entscheidung Sven, 2026-10-06: erst ein Bericht, Loeschen spaeter.
Jede Zeile unten ist eine Vorlage zur Entscheidung, keine ausgefuehrte Aenderung.

**Warum es diesen Bericht gibt:** „gebaut, aber nicht verdrahtet" ist laut `CLAUDE.md` die
haeufigste Fehlerklasse des Projekts. Dagegen stehen 15 Sonden — die aber Komponenten, Seiten,
Routen, einzelne Symbole, `app/` und nicht eingetragene Dauerdienste **nicht** sehen. Genau
diese Luecke messt `pruefe_leichen.py` mit fuenf neuen Spuren: **32 Befunde.**

---

## ⚠ Wie belegt ist welche Aussage? Drei Stufen

Dieses Papier mischt sonst dreierlei, und das ist der Fehler, den die Vertriebsunterlagen am
2026-10-05 teuer gelehrt haben: eine Zahl, die man nachrechnen kann, liest sich genauso wie
eine, die jemand behauptet hat. Deshalb hier ausdruecklich:

| Stufe | heisst | gilt fuer |
|---|---|---|
| **⭘ nachrechenbar** | `python3 scripts/pruefe_leichen.py` erzeugt es jedes Mal neu | alle **32 Befunde** der fuenf Spuren, dazu die Zweiglage, die Ausnahme-Alter und die Groessen unter `web/data` |
| **◐ von Hand nachgemessen** | ich habe es selbst gegen das laufende System geprueft | die Arbeiter-Kette (`pgrep`, launchd, kein Abnehmer der Tabelle), der plist-Unterschied, `web/data` = 5,2 GB, die 51 Dateien Unterschied zu `web/grounding-page` |
| **○ aus einer Erkundung, von mir NICHT nachgeprueft** | eine Hilfs-Sitzung hat es gemeldet; es steht hier, weil es wichtig ist, aber es ist kein Beleg | **alles im Abschnitt „`govisor/` + `scripts/`" ausser den Spur-Befunden**, also: „alle 50 `build_*` verdrahtet", die 8 vergessenen Daueraufrufe, die 4 Sonden in keiner Liste, die 5 CLI-Unterbefehle, die 24 Skripte mit festem `gold/DE`, dass die Spalten der drei Streamlit-Apps stimmen. Dazu im Frontend-Teil: die 8 Merkmalsschalter, die fehlende Blackout-Ausnahme, die sieben nicht dokumentierten Schalter, die Aussage von `feature-inventory-vergabestelle.md`. |

⚠ **Warum das keine Formsache ist:** von 11 Symbol-Funden derselben Erkundung waren beim
Nachpruefen **zwei falsch** (`betragCents` laeuft als Namensraum-Import, `loadClaim` wird
dynamisch geholt) — 18 %. Wer die ○-Zeilen als Arbeitsauftrag nimmt, prueft sie vorher nach.

### ✅ Die drei Blindstellen sind geschlossen (2026-10-06, nach dem kritischen Durchgang)

Sie standen hier als offene Luecken und sind es nicht mehr. **22 → 32 Befunde**, und zwei der
drei Schliessungen haben echte Funde zurueckgeholt, die vorher stillschweigend ausfielen.

| war blind | jetzt | Ertrag |
|---|---|---|
| **Stilblaetter** — Spur 1 las nur `.ts/.tsx/.js/.mjs` | liest auch `.css` unter `web/components`, Verweis ueber den Dateinamen | **+2**: `SiteHeader.module.css`, `SiteFooter.module.css` (je 16 Z, Initialcommit). Gegenprobe: `marktpuls.css` und `trefferguete.css` haben je einen Verweis und werden korrekt **nicht** gemeldet. |
| **Pruefskript galt als Aufrufer** | Produktaufrufer und Pruefwerk zaehlen getrennt (`ist_pruefwerk`) | **+1**: `api/org/zuordnung` (119 Z) wird **nur** von `web/scripts/test_zuordnung.mjs` gerufen. ⚠ Der Fund fiel zuerst trotzdem durch, weil der **Zweigvergleich** dasselbe Pruefskript auf `main` mitlas — die lokale Pruefung trennte, der Zweigvergleich nicht. *Eine Ausnahme ist nur so scharf wie ihre unscharfste Haelfte.* |
| **7 von 84 Modulen pauschal uebersprungen** (Namensraum-Import) | Aliasname wird an das Modul gebunden, nur das wirklich abgerufene Glied gilt als benutzt | **+1 und genauer**: `betragCents` bleibt draussen (laeuft als `P.betragCents`), `loadClaim` aus demselben Modul erscheint. Keine 84 Module mehr im Blindflug. |

**Neu ausgenommen, mit Grund statt durch eine schwaechere Regel:** `/api/kauf/webhook`
(Stripe ruft von aussen; derzeit 503-Stub, weil `lib/stripe.ts:32` die Konstante
`UMGESETZT=false` traegt), `/api/alerts/run` (Vercel-Cron) und `/api/health`. Ein Webhook ohne
internen Aufrufer ist kein Defekt, sondern die Bauart — die Regel aufzuweichen haette dagegen
die echten Funde wieder durchfallen lassen.

---

## ⛔ Zwei Funde, die das Produkt betreffen

### 1. Ein Dauerdienst, den niemand startet — und die Oberflaeche wartet auf ihn

`scripts/antwort_arbeiter.py` (250 Z) erklaert mit `--takt 30` ausdruecklich Dauerbetrieb.

| gepruefter Punkt | Ergebnis |
|---|---|
| laufender Prozess (`pgrep -fl antwort_arbeiter`) | **keiner** |
| Eintrag in `~/Library/LaunchAgents` | **keiner** — eingetragen sind `daily`, `analyse`, `dokumente`, `waechter` |
| Aufruf im Tageslauf oder Waechterlauf | **keiner** |
| anderer Abnehmer der Tabelle `user_antwortauftrag` | **keiner im ganzen Repo** |

Dabei legt `web/components/explorer/Antwortvorschlaege.tsx:90` Auftraege ab und fragt in
Zeile 63 nach Ergebnissen. **Die Antworten entstehen nie.** Kein Test schlaegt an: Arbeiter,
Route und Komponente sind jeder fuer sich korrekt.

⚠ Das ist die Funktion, die am 2026-10-05 um `insDokument()` erweitert wurde (Fragebogen →
belegte Antworten → Dokument). In diesem Zustand kann Phase 3 nichts erzeugen.
**Empfehlung:** Dienst eintragen, nicht Code loeschen — der Baustein ist nicht ueberfluessig,
er ist unangeschlossen.

### 2. Der Betrieb ist aus einem frischen Checkout nicht herstellbar

| Dienst | plist im Repo | laeuft |
|---|---|---|
| `de.skot.govisor.daily` | ja — zeigt auf `C09_govisor/scripts/daily_leads.sh` | **`C09_govisor-nachtlauf/scripts/daily_leads.sh`** |
| `eu.govisor.analyse` | **nein** | ja |
| `eu.govisor.dokumente` | **nein** | ja |
| `eu.govisor.waechter` | **nein** | ja |

⛔ **Wer `deploy/de.skot.govisor.daily.plist` nachinstalliert, dreht die Lehre vom 2026-10-05
zurueck** — dass der Nachtlauf einen eigenen Baum hat, fest auf `main`, damit „was nicht auf
main liegt, laeuft nicht" gilt. Die Datei im Repo beschreibt den Zustand von vorher.
**Empfehlung:** die vier plists in `deploy/` auf den tatsaechlichen Stand bringen. Kein
Loeschkandidat, ein Dokumentationsfehler mit Rueckfallrisiko.

---

## `web/` — Frontend

### Seiten, auf die nichts verlinkt (3) und eine Route ohne Produktaufrufer

| Seite | dahinter | Befund |
|---|---|---|
| `/authority` | `VergabeblickView` **577 Z** + `vergabeblick.css` | Die **ganze Vergabestellen-Rolle** haengt an einer uneingelinkten URL. ⚠ `docs/feature-inventory-vergabestelle.md:104` fuehrt einen Rollen-Umschalter `/leads ↔ /authority` als „✅" — den gibt es im Code nicht. |
| `/marktpuls` | `Marktpuls.tsx` **1103 Z** + `marktpuls.css` | Der Dateikopf sagt es selbst: „Vorschau-/Referenz-Einbau, der eigentliche Einbauort ist noch offen". `Landing.tsx:422` hat nur einen Fliesstext-Teaser. |
| `/intern/claims` | `InternClaims.tsx` 130 Z | **Abgeloest**: `app/intern/konten/page.tsx:36` holt `/api/intern/claims` selbst und hat eigenes `claim()`-Handling. Die Admin-Navigation listet claims nicht. |

**Empfehlung:** `/intern/claims` samt Zweitling loeschen (nachweislich abgeloest). `/authority`
und `/marktpuls` **nicht** loeschen — das sind 1.680 Zeilen gebaute Funktion, die nur keinen
Einstieg hat. Entweder verlinken oder bewusst als ruhend kennzeichnen; und die Feature-Liste
korrigieren, die ein nicht existierendes Merkmal als fertig fuehrt.

### Komponenten ohne Importeur (3) und zwei Stilblaetter ohne Komponente

`components/Band.tsx` (23 Z, redundanter Zwilling von `bandMeter()` in `explorerCore.js:3867`;
das CSS `.band` ist live, aber ueber den HTML-String, nicht ueber diese Komponente) ·
`components/Brand.tsx` (19 Z, auch kein `.brandcell` im CSS mehr) ·
`components/unternehmen/UnternehmenTabs.tsx` (23 Z — ihr Dateikopf behauptet, sie stehe „in der
Bereichsleiste des Rahmens"; sie steht nirgends).

Dazu zwei **Stilblaetter ohne jede Komponente** — jetzt ⭘ nachrechenbar, nicht mehr nur aus der
Erkundung: `SiteHeader.module.css` und `SiteFooter.module.css` (je 16 Z, aus dem Initialcommit
`cc29725`; die Namen `SiteHeader`/`SiteFooter` kommen im Repo nicht vor).

⚠ **Nicht gemeldet und nicht anzufassen:** `components/MessHinweis.tsx` (66 Z) ruht
absichtlich, im Dateikopf begruendet (Datenschutzseite fehlt), `tests/test_telemetrie.py:241`
haelt die Bedingung. So sieht ein richtig gekennzeichneter ruhender Baustein aus.

### Exporte ohne Benutzer (16, Symbolebene)

`docAnalysis.ts → analyseIndex` (duenner Mantel um `analyseIndexMitGrund()`, das die Route
direkt nimmt) · `docAnalysis.ts → hatDichte` · `frageSuche.ts → BEISPIELFRAGEN` ·
**`labels.js → setLang`** · `oeffentlich.ts → _resetIndexCache` (Test-Helfer, den kein Test
ruft) · `supabase/buyerWatch.ts → loadBuyerWatch` · `supabase/declarations.ts →
removeDeclaration` · `supabase/leadStatus.ts → WfStatus` · `supabase/unternehmen.ts →
loadStammdaten`.

Dazu **sechs Prototyp-Reste im groessten Modul**, `explorerCore.js` (3.899 Z): `hasToken`,
`toggleToken`, `NETZ_FREI_MAX`, `REGIONS`, `getState`, `getProfile`.

⛔ **Diese sechs fehlten in der ersten Fassung dieses Berichts, und der Grund ist ein Fehler
der Spur gewesen:** sie zaehlte die Ausfuhrliste `export {…}` als interne Benutzung. Ein Name,
der genau zweimal vorkommt — Definition und Ausfuhr — galt damit als „intern gerufen".
`NETZ_FREI_MAX` steht in Zeile 1176 und 3869, und das war die ganze Begruendung fuer sein
Verschwinden. **Ein Fund, der nicht erscheint, ist schlimmer als einer, der falsch ist:
niemand sucht nach ihm.** Gefunden beim kritischen Durchgehen am selben Tag, nicht durch eine
Pruefung — auch das gehoert dazu.

Bei `buyerWatch` und `claims` ist das Muster auffaellig: die **schreibende** Haelfte wird
dynamisch geladen, die **lesende** nie. **Empfehlung:** einzeln pruefen, ob die Lesefunktion
fehlt oder ueberfluessig ist — das ist kein Loeschlauf, sondern je Fall eine Frage.

### Nicht aus dieser Spur, aber beim Messen gefunden

- ⭘ **`api/org/zuordnung/route.ts`** (119 Z, GET/POST/DELETE) hat **keinen Aufrufer im
  Produktcode**, nur `web/scripts/test_zuordnung.mjs`. Die Oberflaeche, mit der owner/admin
  Profile zuweist (Preismodell §7.1), existiert nicht. *(Steht jetzt in Spur 2, nicht mehr nur
  in dieser Aufzaehlung.)*
- **Acht Merkmalsschalter stehen nirgends auf `1`.** Zwei mit Folgen: `EMAIL_API_KEY` fehlt,
  deshalb bricht `/api/alerts/run` ab — **der Vercel-Cron laeuft taeglich 06:00 ins Leere**.
  Und `/ausschreibung/*` ist per `OEFFENTLICHE_SEITEN=1` offen, hat aber **keine
  Blackout-Ausnahme**: der Akquisekanal ist in Produktion trotzdem schwarz
  (`middleware.ts:95-99` sagt das ausdruecklich).
- **`docs/laender/11-betrieb.md:352` nennt sieben wirksame Schalter nicht** — die Liste, die
  der Betreiber beim Go-live abarbeitet, ist unvollstaendig.

---

## `govisor/` + `scripts/`

**Gute Nachricht zuerst:** alle **50** `build_*`-Erzeuger in `gold.py` sind verdrahtet, ueber
`cli.py:411-519` (DE) und die `KETTE` in `build_dach_gold.py:43-120` (AT/CH/LU). Die
historische Fehlerklasse ist dort geschlossen.

- **`scripts/succession_kpis.py`** (95 Z) schreibt dieselben vier Dateien wie
  `gold.build_succession_kpis` (`head_to_head`, `market_switch_rate`, `buyer_loyalty`,
  `contractor_loss`) — **mit anderer Definition und ohne Aufrufer.** Ein Handlauf
  ueberschreibt den Nachtstand. **Empfehlung: loeschen**, der Erzeuger in `gold.py` ist der
  verdrahtete.
- **8 Skripte sehen nach vergessenem Daueraufruf aus**, u. a. `refresh.py` (279 Z, eigene
  nicht installierte plist, einziger geplanter Weg zu `ingest_month`), `monatslauf.py` (102 Z,
  nennt eine Kadenz, null Referenzen), `zielliste.py` (412 Z, Erzeuger von
  `data/zielliste.csv`, das `/api/intern/zielliste` liest — die Datei ist **59 Tage alt**),
  `analyse_batch.py` (112 Z, halber LLM-Preis, ungenutzt waehrend das Guthaben leer war).
- **4 Sonden stehen in KEINER der zwei Aufruflisten** (`pruefe_ueberblick` 276 Z,
  `pruefe_unterlagen` 288 Z, `pruefe_marken_optik` 215 Z, `pruefe_entity_dubletten` 462 Z).
  ⚠ Der Waechter dafuer bildet die **Differenz** von Tageslauf und Waechterlauf — eine Sonde,
  die aus **beiden** faellt, ist fuer ihn unsichtbar. Vorbild: `pruefe_waechter.py` begruendet
  seine Abwesenheit im Dateikopf.

  ⛔ **UND SEIT HEUTE IST ES EINE FUENFTE: `pruefe_leichen.py` SELBST.** Nachgemessen beim
  Abnehmen: die neue Sonde steht in keiner der beiden Listen, und `test_waechterlauf.py` ist
  **gruen** — genau der Beweis fuer die Luecke, die der Absatz darueber beschreibt. Das ist
  vorerst Absicht (dies ist ein Bericht, kein Waechter: Rueckgabe 0 bei Befunden), aber es ist
  kein Zustand, den man vergisst. **Bedingung fuer den Umzug in den Waechterlauf:** die 22
  Befunde sind abgearbeitet oder als `RUHEND` begruendet, dann laeuft sie mit `--streng` mit.
  Bis dahin steht sie hier, damit sie nicht derselbe Fall wird, den sie meldet.
- **5 CLI-Unterbefehle ruft niemand automatisch** (`ingest`, `silver`, `review`, `sources`,
  `verify`). `verify` ist begruendet abgeloest (`pruefe_gold_integritaet.py:6`), die anderen
  vier nicht.
- **`app/` (3 Streamlit-Apps, 883 Z) kommt in keiner Pruefung vor.** Die Spalten stimmen
  (statisch gegen das Parquet-Schema geprueft), aber Sonde 3 kann sie nicht sehen: sie baut
  ihre Pruefmenge nur aus den Namen, die `daily_leads.sh` und die zwei Arbeiter nennen.
  **Dieselbe Blindstelle trifft 24 weitere Skripte mit festem `gold/DE`** — darunter
  `export_outreach.py` (1031 Z), das **produktiv** per `spawn` aus einer Web-Route startet.

---

## Billig und risikofrei

- **5 `claude/*`-Zweige** (5 bis 8 Wochen alt) sind in `main` enthalten → loeschbar.
  ⚠ **Vier Zweige sind NICHT in `main`** und muessen bleiben: `pipeline/entity-wachen`,
  `web/grounding-page`, `web/ticket17-landingpages`, `claude/distracted-lichterman-183f62`.
- **2 Ausnahmen parken seit 42 Tagen** (`pruefe_verdrahtung.py:738` und `:745`):
  `firma-index.json` (2,6 MB) und `doc-listing-index.json` werden gebaut, ausgeliefert und von
  niemandem gelesen. Die Trennung `BEWUSST_…` / `OFFEN_…` ist gut gedacht, aber **nichts liess
  einen OFFEN-Eintrag altern** — anders als `pruefe_bibel.py`, das ein Kapitel nach 30 Tagen
  Stillstand fehlschlagen laesst. Spur 5 schliesst das jetzt.
- **`web/data` = 5,2 GB**, hochgeladen nach S3/R2 (`scripts/upload_web_data.py`), kostet also
  Geld: `vorgang-archiv` 1,6 G · `doc-text` 1,1 G · `doc-analysis` 696 M ·
  `doc-analysis.json` 628 M (vom Upload ausgenommen) · `vorgang-kennung` 379 M · `lv` 259 M.

---

## ⛔ Wie dieser Bericht gemessen wurde — und warum das wichtig ist

**Gegen die Vereinigung der lebenden Zweige, nicht gegen einen.** Ein Toter-Code-Scan auf
EINEM Zweig sieht Verdrahtung nicht, die auf einem anderen liegt: `web/grounding-page` ist
2 h alt und unterscheidet sich in `web/` allein um **51 Dateien**. Wer auf `main` scannt, haelt
fuer tot, was dort gerade eingebunden wurde — und der naechste Merge bringt es stumm zurueck
oder bricht. `pruefe_leichen.py` prueft jeden Kandidaten gegen alle Zweige mit Commit
< 30 Tage; ein Treffer auf irgendeinem heisst „lebt".

**Vier Fehlalarme mussten beim Bau ausgeraeumt werden.** Sie stehen als Kommentar im Skript
und als Test in `tests/test_leichen.py`, weil jeder von ihnen die Spur unbrauchbar gemacht
haette:

| Falle | Wirkung |
|---|---|
| eigene Prosa gemessen | `--takt` im Docstring machte die Spur zu ihrem eigenen Befund — **zweimal** in derselben Datei |
| `.next` mitgelesen | das Build-Erzeugnis listet JEDE Route → Spur 2 fand **nie** etwas. Der teuerste Fehler ist der, der nie anschlaegt. |
| Anfuehrungszeichen davor verlangt | `/auth/passwort` galt als tot, wird aber per `?next=/auth/passwort` erreicht — **loeschen haette das Passwort-Zuruecksetzen getoetet** |
| Namensraum-Import | `preise.ts → betragCents` galt als tot, laeuft als `P.betragCents` aus `await import(…)` |
| Ausfuhrliste als Benutzung | `export {…}` liess **sechs** tote Exporte von `explorerCore.js` verschwinden — gefunden erst beim kritischen Nachgehen |
| Test nagelte den Stand fest | der Selbsttest verlangte, dass `Band.tsx` gemeldet wird — wer dem Bericht folgt und es loescht, haette einen roten Test geerbt, der nach einem Sondendefekt aussieht. Jetzt prueft er auf **Stimmigkeit**: ist die Ursache weg, wird uebersprungen. |

⚠ Und eine Verschaerfung, die FALSCH gewesen waere: „Schleife + `sleep` = Dienst". Gemessen hat
`miss_eu_groesse.py` fuenf `sleep`-Aufrufe (Ratenbremse einer Blaetterschleife), der echte
Dienst `antwort_arbeiter.py` genau einen. Das Signal zeigt in die verkehrte Richtung. Die
Erkennung leitet sich deshalb aus der Quelle ab: ein Dienst **erklaert** seinen Dauerbetrieb
(Takt-Argument in Python, `while true` in der Shell).

**Rueckgabe 0, auch bei Befunden** — das ist ein Bericht, kein Betriebsfehler. Mit `--streng`
gibt es 1; so kann die Spur in den Waechterlauf, sobald die 22 abgearbeitet sind und jeder neue
ein echter Rueckschritt ist.
