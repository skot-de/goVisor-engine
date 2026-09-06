# 12 · Fallenkatalog

> Jede Falle hier hat einmal Zeit gekostet. Die Spalte „gemessen" ist der Beleg — ohne sie
> wäre es Folklore.

## A · Fallen, die wie Erfolg aussehen

| # | Falle | Woran man es merkt | Gemessen |
|---|-------|--------------------|----------|
| A1 | **Gebaut, aber nicht verdrahtet** | Datei ist alt, Suite grün | `build_lead_text` 12 Tage, `build_lead_lot` 10 Tage still |
| A2 | **Parameter durchgereicht, nie gesetzt** | Funktion nimmt `country`, benutzt es aber nur für Pfade | `dedupe` lief für AT/CH mit DE-Rechtsformen |
| A3 | **Fix im toten Zweig** | Änderung wirkt nicht, Code ist korrekt | AT-Link-Fix in `build_at_gold`, seit 13.08. abgelöst |
| A4 | **Positivliste** | Ergänzung ist syntaktisch korrekt und wirkungslos | `_lead_context_sql` WHERE-Liste, zweimal |
| A5 | **Leeres Feld = „Quelle gibt nichts her"** | niemand fragt nach | AT Bindefrist/Bürgschaft/Lose je 0 %, 6 Wochen lang |
| A6 | **Nominell gefüllt, faktisch wertlos** | 79 % Abdeckung, eine einzige Ausprägung | alle 3.856 CH-Regionen hiessen „Schweiz/Suisse/Svizzera" |
| A7 | **„Alle Schritte grün"** | Lauf meldet Erfolg, Ergebnis ist alt | Anforderungs-Signale aus einem Index vom 31. Juli |
| A9 | **Registry-Eintrag für Code gehalten** | `uk-fts`/`fr-decp` stehen mit Namen, Format und Abdeckung da — und haben NULL Zeilen Code. `candidate` heisst recherchiert. |
| A8 | **Feld misst etwas anderes als sein Name** | `has_documents` = „Quelle bewirbt", nicht „wir haben". **Behoben 2026-08-25** durch ein zweites Feld (`unterlagen.gelesen`). ⚠ Die Falle trifft aber auch den LESER: am 2026-08-31 wurde `access` ausgezählt und `gelesen` gemeint — Arbeitsempfehlung auf einer Kennzahl ohne nachgeschlagene Bedeutung |
| A11 | **Beide Enden richtig, die Leitung fehlt** | Nichts wird rot, weil jede Seite fuer sich tut, was dasteht. Faellt nur auf, wenn jemand den Weg abgeht. | Eignungs-Check sammelte sechs Angaben, der Aufruf ins Onboarding war ein blankes `<a href>` — alles weg, und das Onboarding fragt sie nie |
| A12 | **Ins falsche Profil geschrieben** | Die Reparatur ist fertig, typgeprueft und wirkungslos: es gibt zwei Profile, und `capabilities` liest niemand | 2026-08-31, s. [Kapitel 09](09-frontend-und-i18n.md) |
| A13 | **Vorgabewert als Antwort gelesen** | Eine nie gestellte Frage steht als `false` da; wer den Zustand uebernimmt, schreibt ein „nein", das niemand gesagt hat — und die Abdeckung steigt | Check zeigt je Fachgebiet nur die Nachweise des Feldes (Bau 2, IT 3) |
| A14 | **Sammeln verdrahtet, Auswerten nicht** | Der Abrufer meldet täglich „ok", die Dateien liegen auf der Platte, und niemand liest sie. Nichts wird rot: ein Land sammelt Unterlagen, die nie zu Text werden. | `index-docs` stand an JEDER Stelle auf `--country DE` — auch nachdem der LU-Abrufer in den Tageslauf kam (2026-09-03). Eine Stufe früher als A10: dort war der Vermerk falsch, hier fehlt der Leser ganz |
| A15 | **Beschrieben, nicht gebaut** — der Zwilling von A1 | Ein Kommentar beschreibt ein Verhalten, das es nicht gibt. Nichts wird rot: der Code ist in sich stimmig, nur die Beschreibung ist es nicht. Wer sie liest, sucht den Fehler woanders. | dreimal in zwei Tagen (05./06.09.): `true AS termin_plausibel` im f01/f02-Zweig, waehrend der Auslauf-Zweig das Qualitaetsflag liest → 73 Leads mit 26–169 Jahren Laufzeit gingen UNMARKIERT als „gemessen" hinaus · „der Radar zeigt per Default nur Hauptlose" → 10.367 Neben-Lose ausgeliefert, die Spalten fehlen in `lead_export` ganz · `govisor/docsafety.py` vollstaendig gebaut UND getestet, kein einziger Aufrufer |
| A16 | **Ausfall sieht aus wie leeres Ergebnis** | Ein leeres Ergebnis ist eine AUSSAGE („hier gibt es nichts"). Kommt sie auch dann, wenn niemand nachgesehen hat, ist ein Ausfall zur Auskunft geworden — HTTP 200 inklusive. | `loadDataFile` gab fuer JEDEN Fehlschlag `null` (Datei fehlt, S3 500, Netz weg, Signatur abgelehnt); fuenf Routen machten daraus leere Antworten mit Status 200 — `/api/branchen` zeigte jede Branche mit 0 Leads, `/api/plz-geo` lieferte `{}` (Umkreissuche findet nichts). ⚠ `/api/branchen` brannte den leeren Korpus zusaetzlich in eine Modulvariable ein: aus einer voruebergehenden Stoerung wurde eine dauerhafte Falschauskunft. Und der Fristen-Lauf meldete `{ok:true}` und verschickte nichts. Behoben 2026-09-04/05 ueber `web/lib/ladegrund.js` |
| A10 | **Statusmeldung als Befund gelesen** | Ein Abrufer meldet „keine Datei"; niemand fragt, ob er an der richtigen Stelle gesucht hat. Der Fehler wirft keine Ausnahme und sieht im Bericht wie erledigte Arbeit aus. | seit 2026-08-24: acht Abrufer geprüft, acht Vermerke gefallen, 549 Vorgänge — s. [Kapitel 03](03-input-dokumente.md) |

## B · Fallen beim Zusammenführen von Ländern

| # | Falle | Warum sie beisst | Gemessen |
|---|-------|------------------|----------|
| B1 | **`union_by_name` auf fachlichem Schlüssel** | letzter Treffer gewinnt im Wörterbuch | `market_opportunity` nach `cpv4`: CH-Zahlen hätten DE ersetzt |
| B2 | **DACH-Summe statt je Land** | beantwortet keine Marktfrage und verdeckt beide | Strategie-Ansicht war komplett deutsch |
| B3 | **Wächter fragt nach DE** | fällt DE aus, sind AT/CH mit abgeschaltet | `_FILL = {G}/lead_region_fill.parquet` |
| B4 | **Silber-Glob DE-fest** | mitten in einem sonst länderfähigen Export | `ATTR` → Angebotsaufwand AT/CH genau 0 % |
| B5 | **Zwei Schichten derselben Annahme** | die zweite verschluckt die Reparatur der ersten | `region_ableiten` DE-only **und** Export DE-only |
| B6 | **Schreibpfad fest auf ein Land** | Nicht ein Leser, sondern der SCHREIBER legt falsch ab — danach ist die Herkunft im Bestand unwiederbringlich falsch, und jede Länderauswertung stimmt dazu passend. | `/api/lead-docs` und `process_upload.py` schrieben JEDEN Upload nach `data/docs/DE/`. ⚠ Es traf ausgerechnet AT und CH: dort ist der Upload wegen 0 % Portalabdeckung die EINZIGE Dokumentquelle. Gefunden 2026-09-03 |
| B6 | **Glob ins Leere** | DuckDB wirft einen Laufzeitfehler, kein leeres Ergebnis | CH hat keine `award_criteria` |
| B7 | **Namenskollision über Grenzen** | 22 Käufernamen in mehr als einem Land | trifft 463 von 117.241 Leads |
| B8 | **PLZ-Kollision** | AT und CH sind beide 4-stellig | 1010 = Wien AT / Lausanne CH |
| B9 | **Deckel gilt je Branche statt je Land** | drei Länder teilen sich einen Deckel | `CAP = 120`: deutscher Nutzer sähe 196 statt 379 Zuschlägen |
| B10 | **Hartkodierter Wert sieht aus wie ein Feld** | Quellen umgestellt, Ausgabe nicht | `"land": "DE"` mitten im Ausgabe-Aufbau |
| B11 | **Grenzgänger doppelt im Index** | Identität wird je Land eigenständig gebildet | ACP IT Solutions mit 4 Einträgen; Namensdubletten 134 → 868 |
| B12 | **Entartete Kennung verschmilzt Fremdes** | Platzhalter als Gleichheitsbeleg | 29 von 1.722 grenzüberschreitenden `identity_id` sind `solo:id:.` / `N/A` |
| B13 | **Firmen umgestellt, ihre Regionen nicht** | halbe Umstellung, sieht fertig aus | `clean_nuts` verlangte `len==3 and startswith('DE')` |

## C · Fallen bei Namen und Kennungen

| # | Falle | Gemessen |
|---|-------|----------|
| C1 | **Dachkennung** — eine ID, viele Stellen | `9110027589349` = ÖGK Wien + Steiermark + Kärnten; `FN92191a` = 60 ASFINAG-Namen |
| C2 | **Müllkennung** | „0" bei 510 verschiedenen Käufern, „1" bei 178, „AT" bei 133 |
| C3 | **Rechtsform-Reihenfolge** | „gesellschaft mbh" muss vor „ges.m.b.h." stehen, sonst bleibt „gesellschaft" stehen |
| C4 | **Verschiedene Kennungssysteme je Quelle** | TED meldet GLN, atverg Firmenbuch — für dieselbe Vergabe |
| C5 | **Fuzzy-Matching auf Namen** | Schwelle 0.7 → ~24 % Fehl-Merges bei Ertrag 1.428. Verworfen. |
| C6 | **Sperrliste als Teilzeichenkette** | `'land '` traf „Deutschland GmbH" — 211 Grossfirmen unauffindbar |
| C7 | **CPV-4 fürs Matching** | Elektriker bekam Aufzüge und Heizung als „hoch"; CPV-6 ist die Ebene |
| C8 | **Bedingung, die den Sonderfall unsichtbar ausschliesst** | Merge-Pass filterte auf `Method.NAME_ONLY` — aber `Kind.PUBLIC` landet bei `nicht_aufgeloest`. 37,7 % der Käufer waren nie Kandidat, und niemandem fiel es auf |
| C9 | **Säubern nach der Auflösung statt davor** | `clean_display_name` löst „vertreten durch" nur auf dem ANZEIGEnamen; der Merge-Schlüssel trug ihn weiter → „DB Netz AG" existierte 98-mal |
| C10 | **Normalisierer schneidet mehr weg, als man denkt** | `classify().normalized` cuttet am Komma: „Dresden, GB Finanzen" = „Dresden, GB Stadtentwicklung". Ein Namens-Merge darüber schmilzt still die Abteilungsebene ein (1.772 statt 1.162) — Produktentscheidung als Datenpflege getarnt |
| C11 | **Kürzesten Namen als Anzeigenamen wählen** | jede verstümmelte Variante gewinnt: „DB Netz" schlug „DB Netz AG". Die HÄUFIGSTE Schreibweise nehmen |
| C12 | **Ein Wort, zwei Bedeutungen** | „bestätigt" hiess an einer Stelle „Firma gefunden", an der anderen „Zugehörigkeit belegt" — der Abschlussbildschirm meldete beides gleichzeitig |
| C13 | **Regel widerspricht dem Hinweis daneben** | beide fuer sich vertretbar, zusammen ein Widerspruch, und keine Zusicherung faengt ihn: der Passwortpruefer wies genau die Passphrase ab, die er empfahl |
| C14 | **Dieselbe Regel an drei Stellen** | die SCHWAECHSTE gewinnt, weil sie erreichbar bleibt: Anlegen verlangte 12 Zeichen, die Einstellungen liessen 8 durch |
| C15 | **Kennung des Absenders als Kennung des Käufers** | Derselbe Fehlgriff wie D11, eine Zeile weiter — und teurer: `0204: 991-1405-10` (Beschaffungsamt des BMI) landete auf 33.966 DÖE-Käuferzeilen mit **1.831 verschiedenen Namen** und wurde zu EINER Entität `id:leitweg:991-1405-10` mit 13.401 Parteizeilen, benannt nach „Landeshauptstadt Magdeburg". 162 von 225 Leads unter diesem Namen gehörten jemand anderem (Deutscher Bundestag, Bundesagentur für Arbeit, TU Ilmenau). Gemessen 2026-09-01, behoben mit D11 |
| C16 | **Rolle des Absenders als Rolle des Käufers** | Der nächste Schritt nach C15: dort erbte der Käufer die *Kennung* des Absenders, hier dessen *Eigenschaft, Käufer zu sein*. eForms hängt den eSender in dieselbe Hülle wie den Käufer — ein zweiter `<cac:ContractingParty>`-Block, der statt einer Käuferpartei eine `<cac:ServiceProviderParty>` trägt. Darin steht `ORG-0000` = „Publications Office of the European Union", **und das sitzt in Luxemburg**. Gemessen 2026-09-03 beim ersten LU-Ingest: Paket 2024-05 war zu **4,6 %** luxemburgisch, 3.743 von 3.922 Sätzen waren fremd (polnische Kliniken, katalanische Krankenhäuser, griechische Gemeinden). ⚠ **Ein Jahr unsichtbar, weil LU in keiner Suchmenge stand** — für DE/AT/PL richtet der Fehler nichts an. Er wartet auf das erste Land, in dem eine EU-Einrichtung sitzt, und schlägt dort in voller Höhe zu. Behoben in `schema._eforms_buyer_org_ids` |

## D · Fallen bei Orten und Regionen

| # | Falle | Gemessen |
|---|-------|----------|
| D1 | **NUTS-Ebene ist nicht überall dieselbe** | DE 3 / AT 4 / CH 5 Stellen |
| D2 | **Behördendeutsch als Ortsname** | „stadt" in AT: 46 von 80 Widersprüchen |
| D3 | **Teilzeichenkette statt Wortfolge** | Widerspruch stieg 8,8 % → 21,7 % („senden" in „Wiesendendorf") |
| D4 | **Kürzester Treffer gewinnt** | „Stadt Neustadt am Rübenberge" → „neustadt" in Thüringen |
| D5 | **Vorsilbe auf der falschen Seite geschnitten** | CH: 646 von 4.520 Zeilen erkannt, vier grösste Kantone fielen aus |
| D6 | **Englische geonames-Dubletten** | „Bavaria" neben „Bayern" — überspringen, nicht übersetzen |
| D7 | **Sitz ≠ Leistungsort** | 88 % der AT-Ableitungen zeigen auf Wien (ÖBB, ASFINAG) |
| D8 | **Bundesweite Vergaben fallen aus dem Filter** | 4.144 DE-Leads, Regel war doppelt implementiert |
| D9 | **Quelle liefert nationale Kürzel statt NUTS** | simap: `ZH`/`VD`/`BE` roh in `performance_nuts`; 4.850 Zuschläge ohne Region, `BE` = Bern **oder Belgien** |
| D10 | **Regionsfilter je Verbraucher statt an der Quelle** | dieselbe DE-Annahme steckte in vier Exportern; Fix gehört in den Parser |
| D11 | **Anschrift des ABSENDERS als Anschrift des Käufers** | Der Käufer hat im eForms-XML kein NUTS-Feld, der eSender-Block darunter schon — und ein Suchlauf über den ganzen Teilbaum findet dessen Wert. DÖE kannte dadurch **genau einen** NUTS im gesamten Bestand: `DEA22` (Bonn, Sitz des Beschaffungsamts des BMI), auf 33.966 Käuferzeilen in 393 Orten, 30.831 davon nachweislich nicht in Bonn. Behoben 2026-09-01 (`schema._iter_named_ausserhalb`), Wächter: `scripts/pruefe_nuts_vorgabe.py` |
| D12 | **Wächter, der den eigenen Fund verpasst hätte** | Der naheliegende Test „eine NUTS mit auffällig vielen Orten" trennt NICHT: `DEA22` spannte 92 Orte, der ehrliche Höchstwert im Bestand liegt bei 110 (`DED42`, lauter Kleinstädte). Was trennt, ist die **Streuung der fremden Masse**: bei `DEA22` über 6 Bundesländer, bei jeder ehrlichen Kennung über höchstens 2 (Namensdoppelungen wie Halle, Weilheim, Dillingen) — gemessen 2026-09-01 über DE/AT/CH |
| D13 | **Ein dastehender Wert gilt als belegt** | `regionQuelle='amtlich'` sagte nur „ein NUTS steht da", nie „er passt zum Käuferort". 172 Magdeburger Leads standen so unter „Nordrhein-Westfalen", als belegt markiert. Die Gegenprobe in `region_ableiten.py` prüft seit 2026-09-01 auch die Leads, die schon eine Region tragen: DE 633 von 60.311 (1,0 %), AT 35 von 1.363, CH 44 von 4.818 |
| D14 | **Der Prüfer prüft mit dem schwächeren Zeugen** | dieselbe Gegenprobe nahm den ORTSNAMEN. Nachgemessen am 2026-09-02 gegen die Käufer-PLZ: von 274 entscheidbaren Widersprüchen waren **134 (49 %) Fehlalarm** — die Region stimmte, der Ortsname war zweideutig („Weilheim", „Heidenheim", „Esslingen"). Der Marker stand da schon im Frontend. Zeugen vergleichen, bevor man einen wählt: Ortsname 7 % prüfbar / 95 % eindeutig, PLZ 97 % / 99,8 % |
| D15 | **Eindeutig geprüft auf der falschen Namensebene** | der Riegel verglich VOLLE Schreibweisen, also galt „weilheim" als eindeutig, obwohl „Weilheim in Oberbayern" daneben steht. Ein Name ist erst eindeutig, wenn auch kein längerer Name in einer anderen Region mit denselben Wörtern beginnt |
| D16 | **Das Hilfsverzeichnis enthält etwas anderes, als sein Name sagt** | die geonames-**PLZ**-Datei ist kein Ortsverzeichnis: 5.317 von 17.628 deutschen Einträgen sind Firmen mit eigener Grosskunden-PLZ („siemens", „BERLIN-KÖLNISCHE VERSICHERUNGEN"). Latent ohne Wirkung, bis ein zweiter Riegel darauf aufbaut — dann macht eine Kölner Versicherung den Namen „berlin" mehrdeutig |

## E · Fallen bei Sprachen

| # | Falle | Gemessen |
|---|-------|----------|
| E1 | **Schlüssel zählen statt Werte** | Quelle liefert unbelegte Sprachen als `null` mit Schlüssel |
| E2 | **`{**a, **b}` kippt gefüllte Werte** | Merge lief, Ausbeute blieb **exakt gleich** |
| E3 | **Nur den ersten Knoten nehmen** | 3.511 Sätze sind nur in `summary` mehrsprachig |
| E4 | **`cpv_label` für eine Fassung halten** | 554 Leads bekämen eine Sprachwahl vorgegaukelt statt 76 |
| E5 | **Eine Fassung ist keine Wahl** | sonst zeigt die Oberfläche einen Umschalter mit einem Knopf |

## F · Fallen beim Messen und Testen

| # | Falle | Gemessen |
|---|-------|----------|
| F1 | **Test zählt Prosa mit** | dreimal: `readdir`, `server-only`, `{G}/lead_lot.parquet` — Kommentare vorher entfernen |
| F2 | **Test leiht sich einen echten Listeneintrag** | brach, als die Liste geleert wurde, mit einer Meldung vom Falschen |
| F3 | **Nicht-deterministischer Export** | Sortier-Gleichstand machte jeden Vorher/Nachher-Vergleich wertlos |
| F4 | **Datenzuwachs als Regression fehldeuten** | 346 Abweichungen, tatsächlich Zuwachs seit dem Nachtlauf |
| F5 | **Nur den Füllgrad messen** | CH-Kriterien 100 % gefüllt, 29 % davon reine Etiketten |
| F6 | **Falscher Schlüssel beim Nachmessen** | 0 % in allen Ländern heisst meist: den Schlüssel gibt es nicht |
| F7 | **Namenssuche hält Leichen für lebendig** | einziger Treffer war ein Kommentar, der die Ablösung erklärt |
| F8 | **Den Vorgabefall nicht mitprüfen** | Der Sonderfall wird getestet, der Normalbetrieb nicht — dabei läuft er millionenfach öfter. Ein Länderrang im `ORDER BY` brauchte ohne Vorrangliste einen Platzhalter; `0` ist dort eine SPALTENNUMMER („ORDER term out of range"), `NULL` ein Literal ohne Wirkung („non-integer literal has no effect"). Beide hätten JEDEN Lauf ohne Vorrangliste zerlegt, und beide erst zur Laufzeit im Dienst. Richtig ist, gar keinen Term auszugeben. Gefunden 2026-09-03 an einem künstlich gebauten Zwei-Länder-Fall, nicht an echten Daten — die hatten nur ein Land |

| F9 | **Gegenprobe gegen ALTEN Bytecode** | Python vermerkt im `.pyc` die Zeit der Quelldatei in GANZEN Sekunden. Eine Aenderung in derselben Sekunde, die die Datei gleich gross laesst (`<` zu `>`), ist unsichtbar — der naechste Ladevorgang fuehrt den alten Code aus. Das trifft genau den Rhythmus jeder Gegenprobe. Es luegt in BEIDE Richtungen: ein blinder Test sieht scharf aus, ein guter wirkt blind. | 2026-09-04, gemessen und reproduziert; 27 Testdateien laden Skripte ueber `spec_from_file_location`. Behoben: `tests/conftest.py` setzt `sys.dont_write_bytecode`. ⚠ Gilt NICHT fuer Ad-hoc-Messskripte |
| F10 | **Test prueft Vokabeln statt Wirkung** | Der Test sucht, ob die richtigen Woerter in der Datei stehen. Die Gegenprobe laeuft gruen, weil die Woerter noch dastehen — nur wirkungslos. | `if (grund === DATEN_STOERUNG)` auf `if (false)` gesetzt: Test blieb gruen, weil `DATEN_STOERUNG` und `503` weiterhin im Text standen. Richtig ist, den ZUSAMMENHANG zu pruefen |
| F11 | **Datenform-Test hinkt einen Tag hinterher** | Ein Test ueber die FORM der Daten sieht eine Aenderung erst, NACHDEM die Daten neu gebaut wurden. Wer eine Wertemenge erweitert, hat einen Tag Vorsprung vor seinem eigenen Waechter — die Suite ist gruen und wird ueber Nacht rot. | `competition_source` um `uncertain` erweitert (05.09.), Vokabular-Register vergessen; rot wurde es erst nach dem Lauf vom 06.09. |
| F12 | **Das Muster sieht die Stelle nicht** | Ein Wachmuster, das an der echten Schreibweise vorbeigeht, meldet Sauberkeit. Drei Formen, alle gemessen: geschachtelte Klammern, regulaere Ausdruecke, Dateiendungen. | `[^)]*?` kam an `get(g("incumbent_source"), "echt")` nicht vorbei · ein Regex-Literal in `impressum.ts` (`href\s*=\s*["\']`) sah fuer den Kommentarfilter wie eine Zeichenkette aus, verschluckte 9.797 Zeichen und liess fuenf LEBENDE Pruefschritte als Leichen erscheinen · Sonde 7 verlangte das Anfuehrungszeichen direkt nach dem Modulnamen und meldete in ihrer ERSTEN Nacht `lib/ladegrund.js` als Leiche — importiert an fuenf Stellen, mit `.js` |
| F13 | **Der Waechter liest die eigene Dokumentation** | Wer im Quelltext nach einem Namen sucht, findet auch den Kommentar, der ihn erklaert — und haelt die reparierte Datei fuer den Fund. Drei Mal in einer Sitzung. | Endpunkt-Regel fand ihren eigenen Erklaertext in `kategorie.py`; i18n-Waechter fand einen Beispielsatz im Kommentar; Cron-Test fand den Pfad in seinem eigenen Kommentar. Gegenmittel: den SYNTAXBAUM fragen, nicht den Text |

## G · Fallen im Betrieb

| # | Falle | Gemessen |
|---|-------|----------|
| G1 | **`ps aux` schneidet bei 80 Zeichen ab** | ohne Terminal fällt „govisor" weg → „Bahn frei" |
| G2 | **`grep -q` mit `pipefail` → Exit 141** | Erfolg sieht aus wie Fehler → „Bahn frei" |
| G3 | **System-Python ohne duckdb** | launchd scheitert stumm |
| G4 | **Import ohne `sys.path`** | unter launchd fehlt das Arbeitsverzeichnis |
| G5 | **`git add -A` mit zweiter Sitzung** | zweimal fremde Änderungen mitcommittet |
| G6 | **Falsche Parameter beim Neubau** | `--ab-jahr 2026` statt `2004 --alle-arten` schrieb die Tabelle schmaler |
| G7 | **`SIGALRM` von Playwright verschluckt** | Abrufer hängt und meldet nichts |

| G8 | **Huelle statt Prozess** | Eine Kommandozeile `<shell> -c '<grosser String>'` ENTHAELT den gesuchten Namen, fuehrt ihn aber nicht aus. Die Kollisionspruefung meldet dann Arbeit, die es nicht gibt — und wer staendig grundlos „⛔ NICHT starten" liest, hoert auf hinzusehen. Genau dann rutscht die echte Kollision durch. | 2026-09-04: drei zsh-Huellen in der Liste. Gefiltert wird jetzt auf `<shell> -c`; vorher gemessen, dass alle drei Startarten (`./x.sh`, `bash x.sh`, `sh -c x.sh`) weiterhin als `bash <pfad>` gefunden werden |
| G9 | **Der Schrittname traegt ein Datum** | Der Name ist der Schluessel der Zeitmessung (`⏱ <Name> — <n>s`). Steht eine Variable darin, heisst der Schritt jede Nacht anders und die Reihe zerfaellt — unbemerkt, weil jede einzelne Nacht plausibel aussieht. | `step "Gold-Rebuild (Leads mit Stichtag $TODAY)"`: 13 von 61 Schrittnamen aus 14 Naechten waren derselbe, groesste Schritt. Wandernde Angaben gehoeren in die AUSGABE |
| G10 | **Eine Bremse, an der ein Weg vorbeifuehrt** | Der Deckel sitzt in EINER Funktion. Wer selbst anruft, hat ihn nicht — und die gebremsten Wege halten sich fuer geschuetzt. | `govisor/kategorie.py` rief OpenRouter mit eigenem `requests.post` und eigenem Schluessel-Leser an: ohne Geldwache, ohne Kostenbuch, ohne Bodenpreis. 1.179 Titel, 40 Stapel, JEDE NACHT. Die naechtliche Modellmarkt-Rechnung stand damit auf unvollstaendigen Buchungen |
| G11 | **Die Baugrenze zaehlt niemand** | `next build` stirbt bei rund 156.000 Dateien unter `web/data` (SIGABRT im Node-Heap) — dokumentiert an zwei Stellen und von nichts gemessen. Der Deckel schlaegt erst beim Bauen ein, und kein Alltagslauf faehrt `next build`. Ein SIGABRT sieht dazu nach zu wenig Speicher aus, nicht nach zu vielen Dateien. | Stand 2026-09-04: 116.307 Dateien. Gefaehrlich ist nicht das Rinnsal (341/Tag), sondern das naechste „eine Datei je X": `firma/` und `suppliers/` legten an EINEM Tag 75.389 an. Jetzt Sonde 6 |

## H · Fallen beim Bauen von Kennzahlen

| # | Falle | Gemessen |
|---|-------|----------|
| H1 | **Plausible Verbesserung ohne Nutzen** | ARGE-Zerlegung bewegt 0,6 % der Nachfolgen |
| H2 | **Naives Gewinner-Matching** | ergäbe 78 % Verdrängung statt belastbarer 28,3 % |
| H3 | **Artefakt für Kennzahl halten** | 7 % Incumbent-Rate war ein Paarungsartefakt |
| H4 | **Harte Datumspflicht** | `publication_date`-Pflicht verwarf 93 % von DÖE |
| H5 | **Anreicherung lockern** | „Titel identisch genügt": 28 → 393 Werte, mit fremden Fristen |
| H6 | **Quellen zusammen zitieren** | TED 43,5 % reich / Ø 1,68 Lose gegen DÖE 20,8 % / Ø 1,00 |

## Die Meta-Regel

Fast jede Falle hier hat dieselbe Form:

> **Etwas sieht aus wie eine Aussage über die Welt und ist in Wahrheit eine Aussage über
> unsere Leitung.**

Ein leeres Feld sieht aus wie „gibt es nicht". „Zu wenig Daten" sieht aus wie eine Aussage
über die Vergabestelle. Eine alte Datei sieht aus wie eine frische. Eine Region namens
„Schweiz" sieht aus wie eine Region.

Die Gegenfrage, die man sich zur Gewohnheit machen muss:

> **Fehlt der Wert, oder fehlt die Leitung?**
