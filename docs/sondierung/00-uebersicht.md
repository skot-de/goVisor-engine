# Sondierung: Übersicht über alle 30 TED-Länder

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Was hier „offen" heisst, ist gemessen — aber kein
> einziges dieser Länder hat einen Connector, eine Tabelle oder ein Kapitel in
> `docs/laender/`. Ausnahmen: DE, AT, CH und PL sind angebunden (PL nur in Silber).

**Stand 2026-09-03, nach dem Neulauf mit reparierten Mustern.** Grundlage: **442.276
Ausschreibungen / 436.661 Unterlagen-Links** über 12 Monate (`data/sondierung/_tief/`),
Linktiefe über 3 Monate (`scripts/miss_linktiefe.py`). **31 Länder** — Rumänien, Österreich
und Liechtenstein waren mit den alten Mustern unsichtbar oder untermessen.

---

## 1. Die Gesamtzahl

| | Anteil der EU-Unterlagen-Links |
|---|---:|
| **gemessen erreichbar** | **30,6 %** |
| belegt nicht erreichbar | 65,2 % |
| ungeklärt (NO, GR, AT, IS, LI) | 4,2 % |

⚠ **Was „erreichbar" heisst:** ohne Anmeldung, ohne CAPTCHA, ohne robots-Verstoss belegt
abgerufen. Nicht: „gebaut". Gebaut ist davon nur Deutschland.

⚠ Und **die 64,0 % sind kein technisches Urteil.** Der grösste Einzelposten ist Frankreich
(13,2 % der EU, 0 % erreichbar) — dort ist die Grenze CAPTCHA und Anmeldung, nicht Können.
Dahinter Polen (15,2 %, nur teilweise) und Deutschland (20,4 %, 32 % — das einzige gebaute
Land).

## 2. Alle Länder

| Land | EU-Anteil | offen | ohne Verfahren | Lage | Kapitel |
|---|---:|---:|---:|---|---|
| **DE** | 20.4 % | 32 % | 3,3 % | ✅ angebunden, 13 Abrufer | — |
| **PL** | 15.2 % | 19 / 35 % | 45,0 % ⚠ | 🟡 Silber ohne Gold | [pl](pl.md) |
| **FR** | 13.2 % | **0 %** | 33,6 % ⚠ | ⛔ CAPTCHA + Login | [fr](fr.md) |
| **ES** | 6.5 % | 5 % | 20,0 % ⚠ | 🟡 nur Katalonien | [es](es.md) |
| **IT** | 4.3 % | 15,1 % | 42,1 % ⚠ | 🟡 538 Domains | [it](it.md) |
| **CZ** | 4.2 % | 28 % | 62,2 % ⚠ | 🟡 verlinkt Käuferprofile | [cz](cz.md) |
| **RO** | 3.2 % | **~85 %** | 15,1 % | ✅ `e-licitatie.ro` 99,7 %, zweiphasig | [ro](ro.md) |
| **BE** | 3.1 % | ? | 2,5 % | 🟡 Token fehlt, Weg dokumentiert | [be](be.md) |
| **SE** | 3.1 % | **0 %** | 0,1 % | ⛔ 88 % robots-gesperrt | [se](se.md) |
| **NL** | 2.4 % | **73 %** | 0,7 % | ✅ offizielle API | [nl](nl.md) |
| **PT** | 2.2 % | **88,8 %** | 1,5 % | ✅ Vortal + AcinGov | [pt](pt.md) |
| **BG** | 2.1 % | **97 %** | 0,0 % | ✅ robots sagt `Allow: /` | [bg](bg.md) |
| **LT** | 1.8 % | **~99 %** | 0,4 % | ✅ European Dynamics | [baltikum](baltikum.md) |
| **HR** | 1.8 % | **0 %** | 0,0 % | ⛔ `Allow: /$` — nur Startseite | [hr](hr.md) |
| **FI** | 1.8 % | 9,2 % | 2,8 % | 🟡 Zwei-Klassen-Land | [fi](fi.md) |
| **NO** | 1.7 % | ? | 0,6 % | ⚪ Mercell/EU-Supply gesperrt | [mercell](mercell.md) |
| **SI** | 1.5 % | **100 %** | 0,0 % | ✅ ein GET auf die Datei | [si](si.md) |
| **AT** | 1.5 % | ? | 31,5 % ⚠ | ✅ angebunden, Unterlagen hinter Anmeldung | — |
| **LV** | 1.5 % | **100 %** | 0,0 % | ✅ zweistufig, `.edoc` | [baltikum](baltikum.md) |
| **CH** | 1.4 % | 0 % | 0,0 % | ⛔ Anmeldung | — |
| **IE** | 1.4 % | **86 %** | 1,6 % | ✅ European Dynamics | [ie](ie.md) |
| **HU** | 1.1 % | **64 %** | 0,0 % | ✅ typisiert an der Quelle | [hu](hu.md) |
| **SK** | 1.0 % | **0 %** | 0,5 % | ⛔ Freigabeliste | [sk](sk.md) |
| **DK** | 0.9 % | 17,5 % | 11,9 % | 🟡 6 Plattformen, 6 Antworten | [dk](dk.md) |
| **GR** | 0.9 % | *bedingt* | 40,8 % ⚠ | 🟡 ADF-Bootstrap fehlt | [gr](gr.md) |
| **EE** | 0.8 % | **100 %** | 0,3 % | ✅ `documents-temp-url` | [baltikum](baltikum.md) |
| **LU** | 0.4 % | **100 %** | 1,5 % | ⏳ offen, nur bis Fristende | [lu](lu.md) |
| **MT** | 0.3 % | **100 %** | 0,6 % | ✅ European Dynamics | [european-dynamics](european-dynamics.md) |
| **CY** | 0.3 % | **100 %** | 0,0 % | ✅ European Dynamics | [european-dynamics](european-dynamics.md) |
| **IS** | 0.1 % | ? | 17,9 % | ⚪ nur TED | — |
| **LI** | 0.0 % | ? | 0,0 % | ⚪ nur TED | — |

## 3. Ertrag je Abrufer — die Achse, die zählt

Wer nach Landesgrösse sortiert, fängt in Frankreich an und bekommt null. Wer nach
**Ertrag je gebautem Abrufer** sortiert, fängt hier an:

| Land | ein Abrufer öffnet | Aufwand |
|---|---:|---|
| **SI** | 100 % | ein GET, TED verlinkt die Datei |
| **BG** | 97 % | drei Aufrufe, MD5 mitgeliefert |
| **PT** | 88,8 % | zwei Abrufer (Vortal, AcinGov) |
| **LT + IE + MT + CY** | 99/86/100/100 % | **ein einziger** (European Dynamics) |
| **HU** | 64 % | ein POST, ZIP serverseitig gebündelt |

## 4. Die zweite Achse: nach Software statt nach Land

Portale werden je Hersteller gebaut, nicht je Land. Gezählt am Host, letzter Monat:

| Hersteller | Länder | Lage |
|---|---:|---|
| **European Dynamics** | 4 (LT, IE, MT, CY) | ✅ erledigt, ein Abrufer |
| cosinex/DTVP | 2 (DE, LU) | ✅ gebaut |
| E-ZAK | 1 (CZ) | 🟡 |
| **Mercell** | **6** (NO, NL, DK, DE, FI, LU) | ❌ nie als Abrufer geprüft |
| **EU-Supply** | 3 (NO, DK, NL) | ⛔ Dateien robots-gesperrt (`/app/docmgmt`) |
| Jaggaer | 4 (FR, IT, ES, IE) | ❌ ungeprüft |

Dieselbe Beobachtung von der anderen Seite: **LV `eis.gov.lv`, PT AnoGov und GR ΕΣΗΔΗΣ
brauchen alle drei denselben sitzungsführenden Abrufer** (POST mit Formularzustand).

## 5. Die Fallen, die sich wiederholen

| Falle | Wo sie zuschlug |
|---|---|
| **Fehlercode beschreibt meinen Kopf, nicht die Tür** | EE (`Accept:` → 500), PT (curl-UA → 403), PT/BG (leerer Parameter → 500) |
| **robots ganz lesen — die Sammelregel steht zuletzt** | SK (`head -c 300` schnitt sie ab) |
| **Der erlaubte Weg nennt den verbotenen Pfad** | GR Διαύγεια (`/doc/*`), DK EU-Supply (`/app/docmgmt`) |
| **Ein Funktionsname ist keine Erlaubnis** | DK (`DownloadPublicDocument` → gesperrter Pfad) |
| **„public" im Pfad ist kein Versprechen** | DK iBinder (`/public` → Anmeldung) |
| **CAPTCHA auf der Suche ≠ CAPTCHA am Abruf** | SI (39/39 ohne), FR (genau dort eines) |
| **Die Regelmässigkeit ist das Verdächtige** | FI (immer genau eine Datei fehlte = Zählfehler) |
| **Domain ≠ Verfahren** | GR 40,8 %, CZ 62,2 %, PL 45,0 % Startseiten-Links |
| ⏳ **Unterlagen können verschwinden** | LU (nach Fristende weg) |

## 6. Was offen bleibt

- **Fünf Länder ohne belastbare Zahl** (4,2 %): NO, GR, AT, IS, LI. ✅ RO, LU, LV, EE **und
  BE** sind am 2026-09-03 gelöst worden und tragen zusammen **7,3 Punkte** bei.
- ⛔ **Belgiens zweite Hälfte ist geklärt und zu:** `cloud.3p.eu` (33,9 % des Landes) hat ein
  **reCAPTCHA** vor dem Formular. Nicht der Cookie-Banner war die Schranke — ⚠ und das CAPTCHA
  war in drei Textprüfungen unsichtbar, weil es als iframe lädt ([be](be.md) §2).
- ✅ **Mercell ist geprüft und kein Hebel** ([mercell](mercell.md)): NL/DE/LU per robots
  gesperrt, NO/DK hinter einer Cloudflare-Bot-Prüfung.
- **Die Fonds-Ebene** — nur CZ und PL untersucht, zehn Länder offen
  ([fonds-ebene](fonds-ebene.md)).
- **Die unterschwellige Ebene** ist nur dort geklärt, wo sie im selben Register liegt
  (IE, SI, HU, BG teilweise).
- ✅ **Rumänien ist erledigt** — und die Auffälligkeit („44 Links im Jahr") war unsere
  Extraktion, nicht das Land. `e-licitatie.ro` trägt 99,7 % und ist offen ([ro](ro.md)).
- ✅ **Österreich ist nachgemessen und damit erledigt.** 1.668 Ausschreibungen in 3 Monaten,
  90 Domains, `*.vergabeportal.at` 49,7 % · `wien.gv.at` 14,7 % · `provia.at` 9,7 %,
  31,5 % der Links ohne Verfahren (vorher stand hier 76,4 % aus 33 Links — wertlos).
  ⚠ **Keine weitere Sondierung**: AT ist angebunden, und die Lage ist mehrfach geprüft —
  ohne Anmeldung kommt man nicht an die Unterlagen (Sven, stehende Entscheidung).
