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

## 4. Schranke — noch nicht geprüft

**Frage 3 des Auftrags ist offen.** Sie verlangt, ein Portal anzusehen, und das ist der
Schritt, der zuerst nach der offiziellen Schnittstelle fragt und robots.txt liest.

Ein Hinweis liegt aber schon in den TED-Daten selbst, ganz ohne Zugriff:

```
https://www.marches-publics.info/mpiaws/index.cfm?fuseaction=dematEnt.login&type=DCE&IDM=1827025
```

Die URL, die **TED als Unterlagen-Link veröffentlicht**, nennt `fuseaction=dematEnt.**login**`
und `type=**DCE**` — das Dossier de Consultation des Entreprises hinter einer Anmeldung.
Bei 25 % Anteil wäre das die größte französische Engine hinter einer Schranke.

⚠ Das ist ein **Indiz aus einem Dateinamen, keine Messung.** Es kann sein, dass die
Login-Seite nur der beworbene Weg ist und ein anonymer Download daneben existiert. Genau
das klärt Schritt 4 — und erst danach gehört hier eine Ampel hin.

## 5. Was als Nächstes zu tun ist

1. Den langen Schwanz auf Atexo prüfen (mehr Monate lesen, damit tiefe Links auftauchen).
2. Die 75-%-Lücke aufklären: fehlt der Link, oder ist es die Notice-Art?
3. Schritt 4 für die vier großen Engines — **eine** Vergabe je Engine, offizielle
   Schnittstelle zuerst, robots.txt vorher, keine Konten.
4. DECP: Frankreich hat einen Open-Data-Auftrag für Vergabedaten. Ob er die **Unterlagen**
   umfasst oder nur die Vergabedaten, ist offen und wäre die billigste aller Türen.
