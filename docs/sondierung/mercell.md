# Sondierung Mercell — sechs Länder, ein Ergebnis

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.** Der grösste verbliebene Einzelhebel der Sondierung — und ein Fehlschlag,
aus zwei verschiedenen Gründen.

---

## 1. Warum Mercell überhaupt dran war

Die Hersteller-Zählung ([`european-dynamics.md`](european-dynamics.md) §3a) zeigte Mercell
in **sechs Ländern**, mehr als jeden anderen Anbieter:

```
NO 286 · NL 202 · DK 39 · DE 18 · FI 7 · LU 2
```

Bisher war Mercell nur als **Abdeckungsgrad** vermessen (NO 63 %, DK 11 %, FI 1 %, Baltikum
0 %), nie als Abrufer geprüft. Ein Modul für sechs Länder wäre der beste Schnitt gewesen.

## 2. Es sind drei verschiedene Hosts, und sie verhalten sich verschieden

| Host | Länder | robots | Ergebnis |
|---|---|---|---|
| **`s2c.mercell.com`** | NL 203 · DE 18 · LU 2 | ⛔ `Disallow: /` | gesperrt |
| **`mercell.com`** / `permalink.` | NO 285 · DK 218 | erlaubt (nur 3 Vergaben ausgenommen) | 🟡 → §4 |
| `supplierportal.c1.app.` | FI 7 · NO 1 · DK 2 | weiches 404 | ungeprüft (0,2 %) |

⚠ **Wer „Mercell" als eine Quelle behandelt, misst falsch.** Der grösste Länderanteil
(Niederlande, 203 von 530) liegt auf dem Host, der ausdrücklich alles sperrt — und die
robots.txt von `mercell.com` sagt nichts darüber, weil es eine andere Domain ist.

## 3. ⛔ `s2c.mercell.com` — 69 Bytes, unmissverständlich

```
# Tell robots not to crawl the website
User-agent: *
Disallow: /
```

Damit sind **die Niederlande und Deutschland** auf diesem Weg zu. (Für DE ist das ohne
Folge — dort läuft der Bestand über cosinex/DTVP.)

## 4. 🟡 `mercell.com` — Katalog offen, Dateien hinter einer Bot-Prüfung

Die robots.txt von `mercell.com` ist bemerkenswert: sie sperrt **drei einzelne Vergaben**
(dieselbe Ausschreibung in drei Sprachfassungen, offenbar auf Wunsch), sonst nichts, und
nennt eine Sitemap. Crawlen ist also erlaubt.

Und die Vergabeseite zeigt anonym **viel**:

```
Notice type · Procedure · Publication date · Closing date · Questions closing date
Accepts parallel bids · Accepts variant bids · Buyer …
```

dazu **17 Dateinamen** im Klartext:
```
Del II - Rammeavtale R01922.pdf
Del II - Vedlegg 2.1 - Rammeavtalens spesielle bestemmelser.pdf
Vedlegg 11 - Krav til sjekkpunkter ved kontroll og service.pdf
Del III - Vedlegg 16 - CV-mal.docx           …
```

Und im Quelltext steht sogar der Abrufweg, je Datei einer:
```
/m/file/GetFile.ashx?id=284814389&version=0
```

**Der Aufruf endet bei HTTP 403 mit:**

> *„Just a moment… Enable JavaScript and cookies to continue"*

Das ist eine **Cloudflare-Bot-Prüfung**, keine Rechteverweigerung. ⛔ **Und damit ist hier
Schluss.** Eine Bot-Erkennung ist eine Grenze, keine Hürde — wir umgehen sie nicht, auch
nicht mit einem Browser, der sie bestehen würde. Ein Abrufer im Betrieb stünde ohnehin vor
derselben Wand.

## 5. Ergebnis

| | |
|---|---|
| NL (203) · DE (18) · LU (2) | ⛔ robots `Disallow: /` auf `s2c.` |
| NO (285) · DK (218) | ⛔ Dateien hinter Cloudflare-Bot-Prüfung |
| FI (7) · Rest | ⚪ ungeprüft, 0,2 % |

**Mercell ist kein Hebel.** Der Anbieter mit der grössten Länderreichweite ist zugleich der,
bei dem am wenigsten zu holen ist — und zwar zweimal aus verschiedenen Gründen, die man nur
sieht, wenn man die drei Hosts getrennt betrachtet.

⚠ Was bleibt: **der Katalog ist öffentlich.** Titel, Fristen, Verfahrensart, Käufer und die
**Dateinamen** stehen ohne Anmeldung da. Für eine Lead-Liste reicht das; für die
Dokumentenanalyse nicht. Falls Mercell je gebraucht wird, ist das die Grenze — Metadaten ja,
Dateien nein.
