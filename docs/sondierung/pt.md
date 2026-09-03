# Sondierung Portugal

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Kein Connector, keine Tabelle, kein Kapitel in
> `docs/laender/`. Was hier steht, ist gemessen und belegt — aber nichts davon läuft.

**Stand 2026-09-03.**

---

## 1. Das beste Ergebnis der ganzen Sondierung

**88,8 % des portugiesischen Unterlagen-Felds sind ohne Anmeldung, ohne CAPTCHA und ohne
robots-Verstoß abrufbar.** Belegt, nicht vermutet: 12 Dokumente aus drei Vergaben bei
AcinGov, 90 Dateien aus neun Vergaben bei Vortal.

| Portal | Anteil `unterlagen_link` | Ergebnis |
|---|---:|---|
| **`community.vortal.biz`** | **48,6 %** (4.585) | ✅ offen, dreistufige Kette |
| **`acingov.pt`** | **40,2 %** (3.791) | ✅ offen, ein einziger GET |
| `anogov.com` + `compraspt.com` (dieselbe Software) | 9,3 % | 🟡 Liste offen, Download per JSF-POST |
| Rest (21 Domains) | 1,9 % | ungeprüft |

25 Domains insgesamt, 9.435 Nennungen über zwölf Monate.

## 2. ✅ AcinGov (40,2 %) — der einfachste Fall der Sondierung

TED verlinkt die Datei **direkt**. Ein GET, ein ZIP, fertig:

```
GET https://www.acingov.pt/acingovprod/2/zonaPublica/zona_publica_c/donwloadProcedurePiece/MTA5NDIzMQ
    → 200, content-disposition: attachment; filename="pecas_procedimento_307qiZGxG0.zip"
```

⚠ Der Tippfehler `donwload` steht so in der Adresse des Betreibers. Wer ihn beim Abtippen
korrigiert, bekommt nichts.

Die Kennung ist Base64 einer laufenden Nummer (`MTA5NDIzMQ` = `1094231`) — sie kommt aus
TED, es muss also nichts geraten werden. Drei Abrufe, drei gültige ZIPs (1,9 MB / 2,1 MB /
651 KB). Inhalt eines davon:

```
Processo Concurso/1_…_Caderno_de_Encargos_….docx     ← Leistungsbeschreibung
Processo Concurso/2_Programa_Concurso.pdf            ← Vergabebedingungen
Carta Convite ou Anúncio DR/ANÚNCIO DO PROCEDIMENTO NO DR.pdf
Dados do Procedimento/Minuta do anúncio.pdf
```

**robots.txt: 34 Bytes, vollständig gelesen** — gesperrt ist ausschließlich `MJ12bot`.

## 3. ⚠ Der 403, der keiner war

Der erste Abruf gab **HTTP 403, „Request forbidden by administrative rules"** — und das
sah nach einer Absage aus. Es war der **curl-Standard-Kopf**. Mit unserer eigenen Kennung
(`goVisor/1.0 (+https://govisor.eu)`) kam sofort HTTP 200 und das ZIP.

**Das ist dieselbe Fehlerklasse wie die estnische 500** (`Accept: application/json` → 500,
`Accept: application/json, text/plain, */*` → 200 und 586 KB) und wie Vortals eigene 500
unten. Dreimal dieselbe Lehre, in drei Ländern:

> ⚠ **Ein Fehlercode beim ersten Aufruf beschreibt oft meinen Kopf, nicht die Tür.**
> Wer bei 403 oder 500 aufhört, trägt ein offenes Land als verschlossen ein.

⚠ Und die Gegenrichtung gehört dazu: sich als Browser auszugeben wäre eine Falschangabe —
so wie es bei `uvo.gov.sk` gewesen wäre, sich `ClaudeBot` zu nennen. Hier war das nicht
nötig: die **ehrliche** Kennung genügte.

## 4. ✅ Vortal (48,6 %) — offen, aber hinter der falschen ersten Tür

Vortal ist eine JavaScript-Anwendung; die Seite selbst ist eine 686-Byte-Hülle. Der
naheliegende Aufruf führt in die Irre:

```
GET /public/api/PublicTenderDocuments/GetPublicTenderInformation?uniqueIdentifierEncrypted=<aus TED>
    → 200 — aber documentList: []
```

**Zehn von zehn Vergaben lieferten null Dokumente bei `tenderIsPublished: true`.** Das sah
nach einer Anmeldeschranke aus. Es war die falsche Tür: die Antwort nennt eine zweite
Ansicht, und die trägt alles.

**Die Kette, die funktioniert — drei Aufrufe, alle anonym:**

```
1  GET /public/api/PublicTenderDocuments/GetPublicTenderInformation?uniqueIdentifierEncrypted=…&languageCode=pt-PT
       → contractNoticeUrl: …/contract-notice-view/PT1.NTC.3672051/

2  GET /public/api/ContractNoticeDetail/GetContractNoticeDocuments?contractNoticeUId=PT1.NTC.3672051
       → [ { name, fileId, downloadUrl }, … ]

3  GET https://community.vortal.biz/archive/api/PublicDownload/download?token=<base64>
       → 200, die Datei
```

⚠ `languageCode` **muss gefüllt sein** — leer gibt 500. Dieselbe Falle wie in Estland.

**Geprüft an neun Vergaben: 9 von 9 lieferten Dokumente, 90 Dateien insgesamt** (2 bis 42
je Vergabe). Ein Download vollständig durchgezogen: `Programa de Procedimento.pdf`,
**1.027.022 Bytes, PDF 1.7, 49 Seiten**.

Was in einer einzigen Vergabe hängt (15 Dateien), zeigt die Tiefe:

```
Programa de Procedimento.pdf · Caderno de Encargos.pdf
Lote 1 - Avenida Igreja.zip … Lote 5 - 14Fogos CH.zip      ← je Los ein Paket
Resposta Erros e Omissões.zip                              ← die Bieterfragen-Antworten
Anúncio DR - prorrogação prazo.pdf                         ← Fristverlängerung
```

⚠ **`Resposta Erros e Omissões` ist genau das, was der Bieterfragen-Zähler liest** — die
portugiesische Entsprechung zur deutschen Bieterinformation. Die Sprecher-Zuordnung müsste
dafür ein portugiesisches Muster lernen (`Questão`/`Resposta` statt `Frage`/`Antwort`).

### ⚠ Die robots-Frage, ehrlich

`community.vortal.biz/robots.txt` antwortet **403 — auch im echten Browser, auch mit
unserer Kennung.** Der Host liefert für niemanden eine robots.txt.

Das ist uneindeutig, und ich schreibe es als das hin, was es ist:

- **RFC 9309 §2.3.1.4** behandelt 4xx als „unavailable" → ein Abrufer **darf** zugreifen.
- **Dagegen** spricht, dass 403 anders als 404 eine aktive Ablehnung ist.
- **Dafür** spricht die Benennung des Betreibers selbst: der Pfad heißt
  `/Public/public-tender-documents`, die Schnittstelle `PublicTenderDocuments`, der
  Dateiendpunkt **`PublicDownload`**. Wer eine Route dreimal „öffentlich" nennt, drückt
  damit eine Absicht aus.

**Meine Einschätzung: zugänglich.** Aber es ist eine Einschätzung, keine Messung — und
anders als bei AcinGov (34 Bytes, eindeutig) gehört das vor einem Anschluss geklärt, im
Zweifel durch eine kurze Anfrage an den Betreiber (siehe [[govisor-api-vor-abgriff]]).

## 5. 🎁 Nebenfund: eine offene Suchschnittstelle über drei Länder

```
POST /public/api/Tendering/SearchTenders     Header: LanguageCode: pt-PT
     {"pageNumber":1,"pageSize":60}
     → totalCount: 220.826
```

Anonym, ohne Schlüssel. Je Treffer: `uniqueIdentifier`, `reference`, `description`,
`authorityName`, `country`, `contractLocationLabel`, `publishDate`, `deadline`, `basePrice`,
`procedureTypeLabel`, `contractNoticeStateLabel`.

Zwei Dinge daran sind größer als sie aussehen:

1. **Die unterschwellige Ebene ist dabei.** Ein Treffer der ersten Seite heißt wörtlich
   *„Procedimento de Concurso Público **sem Publicação no Jornal Oficial da União
   Europeia**"* — also eine Vergabe, die in TED nie erscheint.
2. **Die Trefferliste führt PT, ES und `AD`.** Andorra ist **kein TED-Land**; es kommt in
   keiner der 30 Länderdateien der Tiefensondierung vor. Über Vortal wäre es sichtbar.

⚠ Ungeprüft: ob `SearchTenders` filtern kann (Land, Datum, CPV) und wie weit die 220.826
zurückreichen. Beides entscheidet, ob das eine Quelle oder nur ein Schaufenster ist.

## 6. 🟡 AnoGov / compraspt (9,3 %) — offen sichtbar, Download verwinkelt

Beide fahren dieselbe Software (`/…/faces/app/acessoDocs.jsp?codigoAcesso=<Kennung>`).
Die Seite heißt im Titel selbst **„List of Documents"** und listet ohne Anmeldung:

```
0305-2026_Anuncio_JOUE.pdf · 1-…_Caderno de Encargos.pdf
2-…_Programa do Concurso.pdf · 3-Anexo II.docx · 4-ANEXO III_Caucao.docx
DEUCP.zip                                        ← die ESPD
```

**Kein Passwortfeld auf der Seite.** Der Download läuft aber über ein JSF-Formular mit
`jsessionid` — also POST mit Sitzung statt GET. Machbar, aber ein eigener Abrufer.

Dieselbe Bauform wie Lettlands `eis.gov.lv` (Modal per POST). Wer eines von beiden löst,
löst wahrscheinlich beide.

## 7. Die beiden anderen Ebenen

**Unterschwellig — `base.gov.pt` (Portal BASE):** keine robots-Sperre (404). Aber jeder
Aufruf jenseits der Startseite gab **HTTP 999 mit einer WebKnight-Firewall-Meldung**. Das
ist kein Verbot, sondern ein Filter — und an einem Filter klopfe ich nicht weiter, bis
geklärt ist, was ihn auslöst. **Ungeprüft, nicht gesperrt.**

⚠ Zu beachten: Vortals `SearchTenders` (§5) enthält unterschwellige Verfahren bereits.
Ob das BASE ersetzt oder nur überlappt, ist offen.

**Fonds-Ebene: nicht recherchiert.** Eine Vermutung, die ich ausdrücklich **nicht** als
Befund führe: Portugal verpflichtet Fördermittelempfänger über den CCP auf dieselbe
Veröffentlichung wie öffentliche Auftraggeber — dann fiele diese Ebene mit BASE zusammen
und wäre keine eigene Quelle. **Das ist ungeprüft.** Siehe
[`fonds-ebene.md`](fonds-ebene.md), wo Portugal zu den zehn offenen Ländern zählt.

## 8. Was Portugal für den Plan bedeutet

| | Domains | offen |
|---|---:|---:|
| **PT** | **25** | **88,8 %** |
| LT | 2 | ~99 % |
| IT | 538 | 15,1 % |
| SK | 13 | 0 % |

Zwei Abrufer decken 88,8 % eines ganzen Landes — und einer davon (AcinGov) ist ein
einzelner GET auf eine Adresse, die schon in TED steht.

⚠ Was das **nicht** heißt: dass Portugal aufgenommen wäre. Es gibt keinen Connector, keine
Bronze-Zeile, kein Kapitel in `docs/laender/`. Der Weg von hier bis dorthin steht in
[`docs/land-onboarding.md`](../land-onboarding.md) und ist der lange Teil.
