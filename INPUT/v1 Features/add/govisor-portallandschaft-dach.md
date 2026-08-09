# goVisor — Portallandschaft DACH (Anbindungs-Referenz)

**Version:** 1.0
**Stand:** 2026-07-27
**Zweck:** Übersicht der Vergabeportale in D/A/CH als Grundlage für die schrittweise Anbindung
**Kernprinzip:** Nach **Engine** priorisieren, nicht nach Domain — die hunderte Portale laufen auf wenigen Software-Plattformen

---

## 0. Die entscheidende Erkenntnis vorweg

Martin Ha spricht von „über 200 Portalen". Das stimmt als Zahl der Domains — aber sie sind **überwiegend White-Label-Instanzen weniger Software-Engines**. Referenzquellen zählen für Deutschland 449 bis 806 Vergabequellen, doch technisch basieren die meisten auf einer Handvoll Plattformen, allen voran cosinex.

**Konsequenz für goVisor:** Nicht 200 Anbindungen bauen, sondern ~10 Engines + die großen kommerziellen Eigenplattformen. Eine Engine-Anbindung deckt Dutzende bis Hunderte Portale auf einmal ab. Das ist derselbe Befund wie im Bieterfragen-Report.

**Wichtig:** Oberschwellig ist alles ohnehin über **TED** (habt ihr) und künftig **DÖE** zentral erfassbar. Die Portale zählen vor allem für den **Unterschwellenbereich** — genau den Bereich, den Martin Ha als „erscheint gar nicht erst EU-weit" beschreibt und der euer Differenzierungsmerkmal ist.

---

## 1. DEUTSCHLAND

### 1.1 Die Engines (nach diesen priorisieren)

| Engine / Betreiber | Deckt ab | Priorität |
|---|---|---|
| **cosinex VMP/VMPSatellite** | DTVP, eVergabe-Online (Bund), Vergabemarktplätze NRW, Brandenburg, RLP, Metropole Ruhr, Vergabe24 (BW), viele Kommunen | **1 — höchste**, deckt den größten Teil ab |
| **Administration Intelligence (AI)** | evergabe.de, evergabe-online-Familie, diverse Landesportale | 2 |
| **Healy Hudson** | Deutsche eVergabe, NetServer-Portale (generisch, viele Kunden) | 3 |
| **RIB Software** | meinauftrag.rib.de, RIB Vergabe, iTWO tender (Bau-Fokus) | 4 |
| **subreport** | Subreport ELViS (bundesweit) | 5 |
| **AUMASS** | aumass-Portal (v. a. bayerische Kommunen) | 6 |
| **Staatsanzeiger-Verbund** | vergabe24, Staatsanzeiger-eServices (BW u. a.) | 7 |

Mit den Top 7 Engines ist laut Marktanteils-Referenzen der weit überwiegende Teil des deutschen Aufkommens abgedeckt.

### 1.2 Zentrale Bundes-/Meta-Quellen (zuerst, weil breit)

| Quelle | Rolle |
|---|---|
| **TED** | EU-weit oberschwellig — habt ihr bereits |
| **DÖE** (oeffentlichevergabe.de) | neue zentrale DE-Bekanntmachungsplattform, CC0-API — der strategische Hebel für unterschwellig |
| **service.bund.de** | Ausschreibungsübersicht des Bundes |
| **eVergabe-Online** (Beschaffungsamt BMI) | zentrale Bundesplattform (läuft auf cosinex) |

### 1.3 Wichtige Landesportale (meist cosinex-basiert)

Vergabemarktplatz NRW (vergabe.nrw.de), Vergabemarktplatz Brandenburg, Vergabe RLP, eVergabe Bayern, Staatsanzeiger BW, Vergabemarktplatz Niedersachsen, Hessische Ausschreibungsdatenbank (HAD), Vergabeplattform Berlin, Metropole Ruhr — technisch überwiegend cosinex-Familie, daher über die Engine mit abgedeckt.

### 1.4 Sektoren-Eigenportale (eigene Technik, einzeln)

Deutsche Bahn (Bieterportal), Autobahn GmbH des Bundes, Dataport (Hafen-/Verwaltungs-IT), Fraunhofer-Gesellschaft, diverse Stadtwerke. Diese haben teils eigene Systeme — einzeln zu bewerten, aber überschaubar und hochwertig (große Volumina).

---

## 2. ÖSTERREICH

Deutlich zentralisierter als Deutschland — weniger Aufwand.

| Quelle | Rolle | Priorität |
|---|---|---|
| **ANKÖ / eVergabe+** (ankoe.at) | marktführende Plattform, betreibt das ANKÖ Vergabeportal mit **allen** öffentlichen Ausschreibungen Österreichs | **1 — deckt fast alles** |
| **USP** (usp.gv.at) | Unternehmensserviceportal, offizielle Ausschreibungssuche des Bundes | 2 |
| **eVergabe.at** (Healy Hudson NetServer) | EU-weite, nationale, regionale Ausschreibungen | 3 |
| **e-beschaffung.at** | Bekanntmachungen öffentlicher Auftraggeber | 4 |
| **vemap.com-Instanzen** | Landes-/Kommunalportale (NÖ, St. Pölten u. a.) | 5 |
| **auftrag.at** | kommerzieller Aggregator (Wettbewerber-Typ, nicht Quelle) | — |

**Kernpunkt:** ANKÖ ist der zentrale Zugang. Wer ANKÖ + USP + eVergabe.at anbindet, hat Österreich zum großen Teil.

---

## 3. SCHWEIZ

Am einfachsten — faktisch **eine** zentrale Plattform.

| Quelle | Rolle | Priorität |
|---|---|---|
| **simap.ch** | die gemeinsame Plattform von Bund, Kantonen und Gemeinden. Seit 2011 publizieren **alle Kantone und der Bund** hier | **1 — deckt praktisch alles** |

**Kernpunkt:** simap.ch ist das offizielle Publikationsorgan der ganzen Schweiz. Eine Anbindung deckt den Großteil des Schweizer öffentlichen Beschaffungswesens. Seit Release 1.2 (2025) auch mit elektronischer Angebotseinreichung. Besonderheit: Publikationen erst am Folgetag sichtbar.

Daneben einzelne kantonale/kommunale Eigenlösungen, aber simap ist der dominante Zugang.

---

## 4. Anbindungs-Reihenfolge (Empfehlung)

Nach Abdeckung pro Aufwand:

| Schritt | Anbindung | Deckt ab |
|---|---|---|
| 1 | **TED** | EU-weit oberschwellig (DACH) — habt ihr |
| 2 | **DÖE** | DE unterschwellig zentral (CC0-API) |
| 3 | **simap.ch** | ganze Schweiz mit einer Anbindung |
| 4 | **ANKÖ + USP** | Österreich zum großen Teil |
| 5 | **cosinex-Engine** | größter Teil DE unterschwellig (DTVP + Landesmarktplätze) |
| 6 | **AI, Healy Hudson, RIB, subreport, AUMASS** | Rest der DE-Engines, absteigend nach Anteil |
| 7 | **Sektoren-Eigenportale** (Bahn, Autobahn, Dataport …) | hochwertige Einzelquellen |

Nach Schritt 5 ist der Großteil des DACH-Aufkommens abgedeckt — mit rund fünf bis sechs echten Anbindungen statt „200 Portalen".

---

## 5. Wichtige Realitäts-Hinweise

**Login-Grenze:** Viele Portale gaten Unterlagen und teils Bekanntmachungen hinter (kostenloser) Registrierung. Reine Bekanntmachungs-Metadaten sind oft offen, die Unterlagen dahinter nicht. Das berührt dieselbe Betriebsgrenze wie im Bieterfragen-Report (keine automatisierte Account-Anlage). Für die Lead-Erfassung reichen meist die offenen Metadaten.

**Rechtlicher Rahmen je Land:** DE (GWB/VgV/UVgO), AT (BVergG), CH (BöB/IVöB). Die Datenstrukturen unterscheiden sich — das Architekturprinzip (TED als Klammer + nationale Schicht je Land) trägt das, aber jede nationale Quelle braucht ihren eigenen Parser.

**Aggregatoren sind Wettbewerber, keine Quellen:** auftrag.at, DTAD, Bidfix, Patterno, Tendit, Vergabe24-Suche u. a. bündeln bereits — das sind Marktbegleiter, nicht Anzapfpunkte.

**TED reicht nicht:** Wer nur TED überwacht, verpasst zwar nichts Oberschwelliges, aber den ganzen Unterschwellenbereich — und genau der ist Martin Has Argument (5,8-Mio-Vergabe war EU-weit, aber die unterschwelligen „erscheinen gar nicht erst EU-weit").

---

## 6. Zusammenfassung

Die „200+ Portale" sind in Wahrheit wenige Software-Engines plus einige große Eigenplattformen. Für DACH gilt: Die Schweiz ist mit **simap.ch** praktisch mit einer Anbindung erschlossen, Österreich mit **ANKÖ + USP** zum großen Teil, und Deutschland über **DÖE + die cosinex-Engine** für den Löwenanteil, ergänzt um die weiteren Engines. Mit rund fünf bis sechs echten Anbindungen ist der Großteil des DACH-Aufkommens abgedeckt — die restlichen Quellen sind ein langer, dünner Schwanz, den man nach Volumen abarbeitet. Der strategische Wert liegt im Unterschwellenbereich, den TED nicht zeigt.
