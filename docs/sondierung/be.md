# Sondierung Belgien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.** Zweiter Anlauf — der erste endete bei „die API antwortete 500".

---

## 1. Zwei Plattformen

| | Anteil | |
|---|---:|---|
| `publicprocurement.be` (BOSA e-Procurement) | **60,5 %** (8.141) | 🟡 → §3 |
| `cloud.3p.eu` (3P) | **33,9 %** (4.554) | ⚠ Zustimmungsbanner |
| `ec.europa.eu` + Rest (21 Domains) | 5,6 % | — |

Links ohne Verfahren: nur **2,5 %** — sauber verlinkt.

## 2. ⚠ `cloud.3p.eu` — ein Cookie-Banner steht davor

Die Adressen heissen `/Downloads/1/1649/6U/2026`, also vielversprechend. Der Abruf liefert
aber eine **3-KB-Zwischenseite**: Länderwahl (België / Belgique / France) plus

> *„This site makes use of cookies to improve your user experience. Read our cookie
> policy" [Submit]*

keine robots-Sperre (404). **Nicht durchgeklickt** — ein Zustimmungsbanner anzunehmen ist
eine Erklärung im Namen des Nutzers, keine Beobachtung. Offen, ob dahinter die Dateien
liegen.

## 3. 🟡 BOSA — offen sichtbar, und der 500er war ein fehlender Kopf

**Die Dokumentenseite zeigt anonym alles**: Titel, Sprache, Dokumentversion,
Veröffentlichungsdatum, dazu einen Knopf „Alle Dokumente herunterladen".

```
202500459 - Hoogspanningscellen onderhoud - Selectieleidraad.docx / .pdf
202500459 Hoogspanningscellen onderhoud - Question_Answer.docx     ← Bieterfragen
6-7- VBS T infra SE Veiligheidsvoorschriften … .pdf
Bijlage onderaanneming … .docx · toegang tractiestation_kust.pdf   …
```

Die beiden Endpunkte:
```
GET /api/dos/publication-workspaces/<guid>/documents?full=false&type=WORKSPACE&…
GET /api/dos/publication-workspaces/<guid>/archive?full=false
```

**Aus `curl`: 8 von 8 Versuchen HTTP 500**, Antwort nur
`{"details":"Error id …","stack":""}`. Genau daran war der erste Anlauf gescheitert.

⚠ **Es war nicht der Server und nicht eine Sperre.** Im Netzprotokoll des Browsers stand
dieselbe Adresse einmal mit 500 und einmal mit 200 — die Anwendung ruft zweimal. Der
Unterschied lag in den Kopfzeilen:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6…
Accept-Language: de
BelGov-Trace-Id: 540906a3-3de7-4b2b-a51e-5919fd3af184
```

**Die Anwendung schickt ein Bearer-Token — auch beim anonymen Blättern.** Ohne das Token
antwortet die Schnittstelle mit 500 statt 401. Das ist die schlechteste Art, „dir fehlt ein
Kopf" zu sagen, und sie hat diese Sondierung ein ganzes Land gekostet.

> **Fünfter Fall derselben Klasse** — nach EE (`Accept:`), PT (curl-Kennung), PT/BG (leerer
> Parameter) und RO (`Referer`). ⚠ Und der bisher irreführendste: ein **500** liest sich wie
> ein Serverfehler, nicht wie eine fehlende Angabe.

## 4. ⛔ Wo ich angehalten habe

Das Token stammt aus einem Keycloak, und die Zugangsdaten dafür stehen **offen in der
Konfigurationsdatei**, die jeder Besucher lädt:

```
VITE_AUTH_URL:      https://www.publicprocurement.be/auth
VITE_AUTH_REALM:    supplier
VITE_AUTH_CLIENTID: frontend-public
VITE_AUTH_CLIENTSECRET: <steht dort im Klartext>
```

⚠ **Das ist ein Zugangsmerkmal, auch wenn es öffentlich ausgeliefert wird.** Damit ein Token
zu holen wäre technisch trivial und rechtlich vermutlich unbedenklich — es ist derselbe
anonyme Zugang, den jeder Browser bekommt, ohne Konto und ohne Personendaten.

**Ich habe es nicht getan.** Ein Client-Secret zu verwenden ist eine Entscheidung, keine
Messung. Sie gehört Sven.

**Was damit belegt ist:** Belgien ist nicht gesperrt, die Dokumente sind anonym sichtbar,
es gibt einen `archive`-Endpunkt für das ganze Paket, und der einzige fehlende Schritt ist
ein Token, dessen Beschaffungsweg offen dokumentiert ist.
**Was nicht belegt ist:** dass der Abruf danach durchläuft.

## 5. Ergebnis

| | |
|---|---|
| Sichtbarkeit | ✅ vollständig anonym (Titel, Version, Datum, Sprache) |
| robots | ✅ nichts untersagt |
| Abruf BOSA (60,5 %) | 🟡 **ein Bearer-Token fehlt** — Weg dokumentiert, nicht gegangen |
| Abruf 3P (33,9 %) | ⚠ Zustimmungsbanner davor, nicht angenommen |
| Links ohne Verfahren | 2,5 % |

⚠ **Und eine Lehre über Belgien hinaus:** „die API antwortete 500" war neun Kapitel lang
der Grund, Belgien liegen zu lassen. Ein Fehlercode ist kein Befund, solange nicht geklärt
ist, **worüber** er spricht.
