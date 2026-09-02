# Sondierung Frankreich

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Frankreich hat keine Zeile in `data/gold` oder
> `data/silver` und bekommt hier keine. Dieses Kapitel ist Wissen über ein Land, nicht
> das Land. Die Trennung hält `scripts/pruefe_sondierung.py` maschinell — siehe den
> Polen-Fall in `docs/plan-portal-sondierung-eu.md` §0.2.

**Stand 2026-09-02.** Gemessen am TED-Monatspaket 2026-06, das im Cache lag.
**Kein französisches Portal wurde berührt.** Alle Zahlen stammen aus den
Bekanntmachungen selbst.

---

## 1. Mengengerüst

| | |
|---|---:|
| Bekanntmachungen im Juni 2026 | **8.027** |
| davon mit Portal-URL | 6.016 (**75 %**) |
| verschiedene Domains | **681** |

Zum Vergleich: Deutschland stellt 20,4 % aller TED-Bekanntmachungen (an derselben
Stichprobe gemessen), Frankreich liegt dahinter auf Platz drei nach Polen.

⚠ Die 75 % liegen deutlich unter den 96,6 %, die für offene deutsche Vergaben gemessen
wurden. Ob das an der Notice-Art liegt (das Monatspaket enthält auch Zuschläge und
Korrekturen, die keinen Unterlagen-Link tragen) oder an französischer Praxis, ist
**offen** und vor jeder Hochrechnung zu klären.

## 2. Die Portallandschaft

681 Domains, aber der Kopf trägt den Großteil:

| Portal | Bekanntmachungen | Engine |
|---|---:|---|
| marches-publics.info | 1.682 | `aws-achat` |
| marches-publics.gouv.fr (PLACE) | 1.166 | `boamp-place` |
| achatpublic.com | 751 | `achatpublic` |
| marches-securises.fr | 351 | `marches-securises` |
| marches.maximilien.fr | 217 | `atexo-mpe` |
| marches.megalis.bretagne.bzh | 138 | `atexo-mpe` |
| marchespublics596280.fr | 98 | `atexo-mpe` |
| demat-ampa.fr | 90 | `atexo-mpe` |
| plateforme.alsacemarchespublics.eu | 64 | `atexo-mpe` |
| xmarches.fr | 68 | `xmarches-php` |

## 3. Verdichtet auf Engines — der eigentliche Befund

| Engine | Anteil | erkannt am Pfad |
|---|---:|---|
| `aws-achat` | **25 %** | `/mpiaws/index.cfm?fuseaction=…` |
| `atexo-mpe` | **14 %** | `/entreprise/consultation/<id>?orgAcronyme=…` |
| `achatpublic` | 12 % | `/sdm/ent/gen/ent_detail.do?PCSLID=…` |
| `boamp-place` | 11 % | `marches-publics.gouv.fr` |
| `marches-securises` | 5 % | eigene Domain |
| `xmarches-php` | 1 % | `/entreprise/detailConsultation.php?key=…` |
| **unbekannt** | **31 %** | der lange Schwanz |

**Die Grundannahme des Plans bestätigt sich am ersten Land.** Fünf Portale, die wie fünf
Systeme aussehen — `maximilien`, `megalis`, `marchespublics596280`, `demat-ampa`,
`alsacemarchespublics` — tragen alle denselben Pfad `/entreprise/consultation/…?orgAcronyme=`.
Es ist **eine** Software. Wer je Domain arbeitet, prüft fünfmal dasselbe.

⚠ **Die 31 % sind nicht 31 % fremde Systeme.** Die Engine steht im Pfad; eine URL, die nur
auf die Startseite zeigt (`https://demat-ampa.fr`), lässt sich nicht zuordnen. Ein Teil des
Schwanzes sind mit hoher Wahrscheinlichkeit weitere Atexo-Instanzen. Das ist zu prüfen,
bevor jemand aus den 31 % einen Aufwand ableitet.

## 4. Schranke — geprüft am 2026-09-02

Vier Engines angesehen, je eine Vergabe, robots.txt zuerst, keine Konten, kein CAPTCHA
gelöst. Ergebnis:

| Engine | Anteil | robots.txt | Urteil |
|---|---:|---|---|
| `aws-achat` | 25 % | keine (404) | **CAPTCHA** — anonymer Abruf wird angeboten, ist aber durch ein Bildrätsel gesperrt |
| `atexo-mpe` inkl. PLACE | **25 %** | alles erlaubt | **Login-Wand**, an zwei Instanzen bestätigt |
| `achatpublic` | 12 % | **`Disallow: /`** | **gesperrt** — nur benannte Suchmaschinen zugelassen, wir nicht |
| `marches-securises` | 5 % | keine | **unbestimmt** — der TED-Einstieg führt auf 404, die Seite wurde umgebaut |
| unbekannt | 31 % | — | offen |

**Von den 62 %, die ich bestimmen konnte, ist nichts ohne Schranke einsammelbar.**

### Was jede Zeile wirklich sagt

**`aws-achat` — und hier lag ich vorher falsch.** Ich hatte aus dem URL-Namen
`fuseaction=dematEnt.login` auf eine Login-Wand geschlossen. Die Seite sagt das Gegenteil:

> „Conformément à l'arrêté du 14/12/2009, vous avez la possibilité de retirer le DCE en
> **mode anonyme**."

Der anonyme Abruf ist französische Rechtspflicht und wird angeboten. Das Formular dahinter
verlangt aber `captchaVal` gegen ein Bild unter `/captcha/Captcha_*.png`. Für einen
Menschen gangbar, für einen Automaten nicht — und CAPTCHA ist eine Grenze, keine Hürde.

⚠ **Das ist eine eigene Kategorie**, nicht dasselbe wie eine Login-Wand: es braucht kein
Konto, nur einen Menschen. Wer Frankreich manuell erschließen will, kommt hier durch.

**`atexo-mpe` — die Engine ist dieselbe, die Konfiguration auch.** Getestet auf PLACE
(staatlich) und Maximilien (Île-de-France), beide mit identischem Wortlaut:

> „Vous devez être connecté pour accéder aux actions ci-dessous."

Der Download-Link heißt auf beiden `EntrepriseDemandeTelechargementDce`. Die öffentliche
**Suche** ist frei (PLACE listet 2.374 laufende Vergaben ohne Anmeldung), die **Dateien**
nicht. Damit ist der Katalog holbar, der Inhalt nicht.

**`achatpublic` — kein Zugangsproblem, ein Verbot.** `User-agent: * → Disallow: /`, mit
einer Freigabeliste, auf der Bingbot, Googlebot und ein paar andere stehen. Wir nicht.
Die Seite wurde deshalb nicht aufgerufen.

### Ein Nebenbefund, der zu unseren Kennzahlen passt

AWS schreibt auf der eigenen Hinweisseite:

> „à l'échelle de la plateforme AWS (qui publie environ 150 avis par jour), **28 % des avis
> font l'objet d'une modification, d'un rectificatif, d'une correspondance, ou d'un sans
> suite**"

Der Betreiber beziffert die Fortschreibungsquote selbst auf 28 %. Das ist eine unabhängige
Bestätigung der Kennzahl „Fortschreibungsdichte" aus `docs/bieterfragen-datenmodell.md` —
und ein Hinweis, dass sie in Frankreich ähnlich trägt wie in Deutschland.

## 5. Was daraus folgt

**Für einen Automaten ist Frankreich heute zu.** Nicht wegen fehlender Konnektoren, sondern
wegen CAPTCHA (25 %), Login (25 %) und robots-Verbot (12 %).

**Für einen Menschen ist ein Viertel offen.** Der anonyme AWS-Weg braucht kein Konto, nur
jemanden, der das Bildrätsel löst. Das ist der „du lieferst"-Pfad, den die DACH-Karte für
die Login-Engines schon kennt.

### Offen geblieben

1. Der 31-%-Schwanz: mehr Monate lesen, damit tiefe Links auftauchen und sich zeigt,
   wie viel davon ebenfalls Atexo ist.
2. `marches-securises` (5 %): neuer Einstiegspunkt zu finden.
## 6. DECP — geprüft am 2026-09-02, und es ist keine Tür

Am offiziellen Schema gemessen (`139bercy/format-commande-publique`, v2.0.3), nicht an
einer Beschreibung.

**Für die Unterlagen: nichts.** Das Schema enthält **null Treffer** für `dce`, `dossier`,
`document`, `piece`, `fichier`, `attach`, `url`, `lien` und `telecharg`. Es führt genau
zwei Objekte, `marche` und `contrat-concession`, mit Käufer, CPV, Laufzeit, Preisform,
Ausführungsort, Unterauftragsakten und Änderungen.

**Und es setzt zu spät an.** DECP sind Daten **nach dem Zuschlag**. Für eine laufende
Ausschreibung, deren Unterlagen gerade verfügbar sind, gibt es dort nichts — und genau
die sind der verfallende Teil.

**Wofür DECP trotzdem taugt, und das ist nicht wenig:** die Veröffentlichungspflicht
greift **ab 40.000 EUR netto** (README des Schemas). Das ist weit unter den EU-Schwellen,
also genau die unterschwellige Ebene, zu der TED schweigt. Als Antwort auf **Frage 1**
des Auftrags ist DECP für Frankreich damit die gefundene Quelle — als Antwort auf
**Frage 2 und 3** ist sie keine.

Der Eintrag `fr-decp` steht bereits in der Registry (`status=candidate`,
`tier=unterschwellig`) und trägt diese beiden Grenzen jetzt im Klartext.

### Offen geblieben

1. Der 31-%-Schwanz: mehr Monate lesen, damit tiefe Links auftauchen und sich zeigt,
   wie viel davon ebenfalls Atexo ist.
2. `marches-securises` (5 %): neuer Einstiegspunkt zu finden.
