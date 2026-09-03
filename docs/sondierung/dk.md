# Sondierung Dänemark

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Sechs Plattformen, sechs verschiedene Antworten

| Plattform | Anteil | Ergebnis |
|---|---:|---|
| `eu.eu-supply.com` | **28,3 %** | ⛔ **Liste erlaubt, Dateien robots-gesperrt** |
| **`ethics.dk`** | **17,5 %** | ✅ **vollständig offen** |
| `comdia.com` | 16,2 % | ⛔ Anmeldung |
| `permalink.mercell.com` | 14,1 % | ⛔ Anmeldung |
| `levportal.amgros.dk` | 5,4 % | ⚪ nur Startseiten-Links |
| `my.ibinder.com` | 2,9 % | ⛔ Anmeldung |
| Schwanz (41 Domains) | 15,5 % | ungeprüft |

**Belegt offen: 17,5 %.** Dänemark ist damit das zersplittertste Land dieser Runde — nach
Deutschland (13 Abrufer) das zweite, in dem kein einziger Zugang die Mehrheit trägt.

## 2. ✅ ethics.dk (17,5 %) — offen, und die Schnittstelle sagt es im Namen

```
1  GET /ethics/publicTenderDocs/<tenderGuid>
       → tenderDocs: [{ _id, filename, cat, type, length, md5, checksum, state }, …]

2  GET /ethics/publicTenderDoc/<tenderGuid>/downloadFolder/<docId>
       → 200, ein ZIP je Ordner
```

Die Seite heisst **„Offentligt udbudsmateriale"** (öffentliches Vergabematerial), keine
robots.txt (404), keine Anmeldung.

**Geprüft an 8 von 8 Vergaben: alle antworten, zusammen 142 Dokumenteinträge.**
Drei Ordner vollständig geladen:

```
01-Dokumentfortegnelse_Bilag_1.zip        77.174 B
03-SAB og SB.zip                      11.019.812 B
07-Tegninger.zip                      64.440.964 B   ← Zeichnungen, ein einziger Ordner
```

⚠ **64 MB für einen Ordner.** Dänemark liefert Bauzeichnungen als PDF in voller Auflösung
(`A293728_FAS-011.pdf` allein 7 MB). Wer hier abruft, braucht eine Grössenschwelle — die
Schnittstelle liefert `length` je Datei, also **vor** dem Herunterladen.

Die Einträge tragen **MD5 und SHA1** (`md5`, `checksum`) — noch mehr als Bulgarien, das nur
MD5 gibt. Dazu `state: PUBLISHED`, eine Kategorie (`cat`) und bei Ordnern die Kindliste
(`folderFiles`).

## 3. ⛔ EU-Supply (28,3 %) — die Liste ist erlaubt, die Dateien sind es nicht

Das ist der lehrreichste Fall des Kapitels, und er wäre beinahe schiefgegangen.

Die robots.txt (374 Bytes, von 2000) sperrt fünf Pfade, darunter:
```
Disallow: /app/docmgmt
```

Die TED-Adresse führt aber auf `/app/rfq/rwlentrance_s.asp` und von dort auf
`/app/rfq/publicpurchase_docs.asp` — **beides nicht gesperrt**. Diese Seite liefert
anonym **107 Dateinamen** und Verweise der Form:

```html
javascript:DownloadPublicDocument('18911944','sDoc_18911944','538619');
```

Die Funktion heisst „DownloadPublicDocument". Alles sah nach einem offenen Land aus.

**Bis zur Definition der Funktion:**
```js
var strDownloadPublicDocumentURL = strDomain + '/app/docmgmt/downloadPublicDocument.asp';
```

⚠ **Die Dateien liegen genau unter dem einen Pfad, den die robots.txt sperrt.** Die
erlaubte Seite reicht die verbotene Adresse heraus — dieselbe Konstruktion wie bei
Griechenlands Διαύγεια, wo die offene Metadaten-Schnittstelle als `documentUrl` den
`/doc/*`-Pfad nennt, den dieselbe robots.txt untersagt.

**Es wurde keine Datei abgerufen.**

> **Die Regel, die daraus folgt:** ein Funktionsname ist keine Erlaubnis. `DownloadPublic…`
> sagt, wofür der Betreiber die Funktion hält; die robots.txt sagt, was er von Abrufern
> will. Nur das zweite zählt.

⚠ **Und das reicht über Dänemark hinaus.** EU-Supply bedient nach der Herstellerzählung
auch **Norwegen (99)** und die **Niederlande (3)**. Dieselbe robots.txt, derselbe Pfad —
wer dort einen Abrufer baut, läuft in dieselbe Sperre.

## 4. Die übrigen drei Sperren

**`comdia.com` (16,2 %)** leitet auf `/Login.aspx?...&ReturnUrl=...` mit Passwortfeld.
robots sperrt nur `/keepAlive.aspx` — die Grenze ist ein Konto, keine Regel.

**`permalink.mercell.com` (14,1 %)** leitet über `mercell.com/permalink/…` auf
`/en/tender/…` mit „Sign in / Tender access". Mercell ist ein kommerzieller Dienst.

**`my.ibinder.com` (2,9 %)** — ⚠ und das ist die Warnung, die es zu merken lohnt: die
Adresse endet auf **`/public`**, und trotzdem landet der Aufruf auf `signin.ibinder.com`
mit E-Mail und Passwort.

> **Gegenstück zur slowenischen Lehre.** Dort hiess es: *ein CAPTCHA auf der Suchmaske
> heisst nicht, dass der Abruf eines hat.* Hier gilt die Umkehrung: **das Wort „public" im
> Pfad ist kein Versprechen.** Beide Male entscheidet nur der Abruf selbst.

## 5. `levportal.amgros.dk` (5,4 %)

Verlinkt aus TED **ausschliesslich die Startseite** (`/Sider/Default.aspx`). Das ist der
dänische Anteil an den 11,9 % Startseiten-Links des Landes (siehe
[`linktiefe.md`](linktiefe.md)). Nicht gesperrt, nur nutzlos verlinkt.

## 6. Was nicht geprüft ist

- **41 Domains im Schwanz (15,5 %).** Bei dieser Zersplitterung ist das mehr als der ganze
  offene Anteil — aber es sind 41 Einzelfälle.
- **Die unterschwellige Ebene.** Dänemark führt `udbud.dk`; nicht angesehen.
- **Die Fonds-Ebene.**

## 7. Ergebnis

| | |
|---|---|
| Belegt offen | **17,5 %** (ethics.dk), 8 von 8 Vergaben |
| Gesperrt durch robots | **28,3 %** (EU-Supply, Pfad `/app/docmgmt`) |
| Anmeldung | **33,2 %** (comdia, Mercell, ibinder) |
| ⚠ Vorsicht | 64 MB je Ordner · `length` vor dem Abruf nutzen · MD5+SHA1 geliefert |

Dänemark braucht für 17,5 % einen eigenen Abrufer. Zum Vergleich: derselbe Aufwand öffnet in
Bulgarien 97 %, in Slowenien 100 %.
