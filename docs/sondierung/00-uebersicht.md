# Sondierung: Übersicht über alle 30 TED-Länder

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Was hier „offen" heisst, ist gemessen — aber kein
> einziges dieser Länder hat einen Connector, eine Tabelle oder ein Kapitel in
> `docs/laender/`. Ausnahmen: DE, AT, CH und PL sind angebunden (PL nur in Silber).

**Stand 2026-09-03.** Grundlage: 410.605 Unterlagen-Links über 12 Monate
(`data/sondierung/_tief/`), Linktiefe über 3 Monate (`scripts/miss_linktiefe.py`).

---

## 1. Die Gesamtzahl

| | Anteil der EU-Unterlagen-Links |
|---|---:|
| **gemessen erreichbar** | **24,6 %** |
| auf ungeklärten Ländern | 9,2 % |
| belegt nicht erreichbar | 66,3 % |

⚠ **Was „erreichbar" heisst:** ohne Anmeldung, ohne CAPTCHA, ohne robots-Verstoss belegt
abgerufen. Nicht: „gebaut". Gebaut ist davon nur Deutschland.

⚠ Und **die 66,3 % sind kein technisches Urteil.** Der grösste Einzelposten ist Frankreich
(14,0 % der EU, 0 % erreichbar) — dort ist die Grenze CAPTCHA und Anmeldung, nicht Können.

## 2. Alle Länder

| Land | EU-Anteil | offen | Links ohne Verfahren | Lage | Kapitel |
|---|---:|---:|---:|---|---|
| **DE** | 21,0 % | 32 % | 1,4 % | ✅ angebunden, 13 Abrufer | — |
| **PL** | 16,2 % | 19 % ober / 35 % unter | 45,0 % ⚠ | 🟡 Silber ohne Gold | [pl](pl.md) |
| **FR** | 14,0 % | **0 %** | 33,6 % ⚠ | ⛔ CAPTCHA + Login + robots | [fr](fr.md) |
| **ES** | 6,7 % | 5 % | 21,5 % ⚠ | 🟡 nur Katalonien | [es](es.md) |
| **IT** | 4,6 % | 15,1 % | 42,1 % ⚠ | 🟡 538 Domains | [it](it.md) |
| **CZ** | 4,5 % | 28 % | **62,2 %** ⚠ | 🟡 verlinkt Käuferprofile | [cz](cz.md) |
| **BE** | 3,3 % | ? | 2,5 % | ⚪ API antwortete 500 | [be](be.md) |
| **NL** | 2,6 % | **73 %** | 0,7 % | ✅ offizielle API | [nl](nl.md) |
| **SE** | 2,6 % | **0 %** | 0,1 % | ⛔ 88 % robots-gesperrt | [se](se.md) |
| **PT** | 2,3 % | **88,8 %** | 1,5 % | ✅ Vortal + AcinGov | [pt](pt.md) |
| **BG** | 2,2 % | **97 %** | 0,0 % | ✅ robots sagt `Allow: /` | [bg](bg.md) |
| **LT** | 2,0 % | **~99 %** | 0,4 % | ✅ European Dynamics | [baltikum](baltikum.md) |
| **HR** | 1,9 % | **0 %** | 0,0 % | ⛔ `Allow: /$` — nur Startseite | [hr](hr.md) |
| **FI** | 1,9 % | 9,2 % | 2,8 % | 🟡 Zwei-Klassen-Land | [fi](fi.md) |
| **NO** | 1,8 % | ? | 0,6 % | ⚪ Mercell/EU-Supply | [se](se.md) |
| **SI** | 1,6 % | **100 %** | 0,0 % | ✅ ein GET auf die Datei | [si](si.md) |
| **LV** | 1,6 % | ? | 0,0 % | 🟡 Liste offen, Weg ungeklärt | [baltikum](baltikum.md) |
| **CH** | 1,5 % | 0 % | 0,0 % | ⛔ Anmeldung (Sven-Entscheid) | — |
| **IE** | 1,4 % | **86 %** | 1,6 % | ✅ European Dynamics | [ie](ie.md) |
| **HU** | 1,1 % | **64 %** | 0,0 % | ✅ typisiert an der Quelle | [hu](hu.md) |
| **SK** | 1,1 % | **0 %** | 0,5 % | ⛔ Freigabeliste | [sk](sk.md) |
| **DK** | 0,9 % | 17,5 % | 11,9 % | 🟡 6 Plattformen, 6 Antworten | [dk](dk.md) |
| **GR** | 0,9 % | *bedingt* | **40,8 %** ⚠ | 🟡 sichtbar, Sitzung nötig | [gr](gr.md) |
| **EE** | 0,9 % | ? | 0,3 % | 🟡 Liste offen, Dateiweg fehlt | [baltikum](baltikum.md) |
| **LU** | 0,5 % | *offen* | 1,5 % | ⏳ nur bis Fristende | [lu](lu.md) |
| **MT** | 0,3 % | **100 %** | 0,6 % | ✅ European Dynamics | [european-dynamics](european-dynamics.md) |
| **CY** | 0,3 % | **100 %** | 0,0 % | ✅ European Dynamics | [european-dynamics](european-dynamics.md) |
| **AT** | 0,1 % | ? | **76,4 %** ⚠ | ✅ angebunden | — |
| **IS** | 0,1 % | ? | 17,9 % | ⚪ nur TED | — |
| **RO** | 0,0 % | ? | **50,0 %** ⚠ | ⚪ nur TED, ⚠ nur 44 Links/Jahr | — |

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

- **Neun Länder ohne belastbare Zahl** (9,2 % des Volumens): BE, NO, LV, EE, GR, LU, AT,
  IS, RO.
- **Mercell** — sechs Länder, nie als Abrufer geprüft.
- **Die Fonds-Ebene** — nur CZ und PL untersucht, zehn Länder offen
  ([fonds-ebene](fonds-ebene.md)).
- **Die unterschwellige Ebene** ist nur dort geklärt, wo sie im selben Register liegt
  (IE, SI, HU, BG teilweise).
- ⚠ **Rumänien: 44 Unterlagen-Links im Jahr.** Bei der Landesgrösse ist das kein Ergebnis,
  sondern eine Auffälligkeit — entweder verlinkt RO nicht, oder unsere Extraktion greift
  dort nicht.
