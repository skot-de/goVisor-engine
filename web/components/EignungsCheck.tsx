"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { setzeCheckErgebnis } from "@/lib/checkErgebnis";

/**
 * Öffentlicher Eignungs-Check — der Einstieg, den die Startseite nicht hatte.
 *
 * **Was es drinnen schon gab und warum das nicht reichte.** Der Abgleich Profil gegen
 * Anforderung steckt seit Ticket #27 in der Anwendung und entscheidet dort mit („Nicht
 * bewerben, Pflichtanforderung verletzt"). Er setzt aber Konto, Onboarding und ein
 * gepflegtes Profil voraus. Wer die Seite zum ersten Mal sieht, hat nichts davon — und
 * seine Frage ist eine Nummer kleiner: *komme ich da überhaupt in Frage?*
 *
 * **Was hier gezeigt wird, ist nicht, was wir gefragt haben, sondern was gefunden wurde.**
 * Die erste Fassung zeigte vier Zeilen: die vier eigenen Fragen. Sven, zur Vorlage
 * `INPUT/v1 Features/add/govisor-eignungscheck-v1.html`: „was gefunden wurde finde ich da
 * besser." Stimmt — die interessante Liste ist die der tatsächlich verlangten Nachweise,
 * nach Häufigkeit sortiert, mit Häkchen daneben. Sie kommt aus den ausgewerteten
 * Vergabeunterlagen (`scripts/export_landing.py`, Block KATALOG).
 *
 * **Drei Ehrlichkeitsregeln, ohne die das Ding Werbung wäre.**
 * 1. „Belegt in 21 %" heisst: in so vielen der ausgewerteten Verfahren steht es wörtlich.
 *    Es heisst NICHT, dass vier Fünftel es nicht verlangen — was die Extraktion nicht
 *    erfasst hat, fehlt. Die Zahl ist eine Untergrenze und wird auch so benannt.
 * 2. Die Kernzahl zählt nur gegen Verfahren mit MINDESTENS EINER bezifferten Anforderung.
 *    Zwei Drittel der Unterlagen tragen keine; wer sie mitzählt, verkauft jedem „passt
 *    schon".
 * 3. Unter 30 ausgewerteten Verfahren je Fachgebiet gibt es keine Quote, sondern den
 *    Hinweis, dass die Grundlage fehlt. Eine geschätzte Zahl wäre schlechter als keine.
 *
 * **Warum hier auch die Fachgebiete stehen.** Es gab zwei Abschnitte direkt untereinander:
 * „Offen in eurem Fachgebiet" (Zahlen zum Anschauen) und den Check (dieselbe Auswahl noch
 * einmal als Menü). Sven: „sollte man besser verbinden." Jetzt SIND die Kacheln die
 * Auswahl, und sie rechnen mit der Region mit.
 *
 * **Warum ein Fenster mit drei Schritten und nicht alles untereinander.** Sven: „wenn du
 * alles untereinander baust, nimmt es zu viel platz ein. ich weiss nicht, ob alle leute die
 * brücke verstehen zwischen branche und dem eignungscheck." Beides hängt zusammen: auf der
 * Seite bleiben die Kacheln und EIN Satz, der die Brücke ausspricht („ihr arbeitet in Bau
 * und Handwerk — erfüllt ihr, was dort verlangt wird?"). Der Rest passiert im Fenster, in
 * drei benannten Schritten: was wir uns notiert haben, was ihr habt, was dabei herauskommt.
 * Schritt 1 wiederholt Fach und Region ausdrücklich, damit das Fenster auch versteht, wer
 * die Kachel oben übersehen hat.
 *
 * Technisch ein natives `<dialog>`: Escape, Hintergrund-Klick und die Inertisierung der
 * Seite dahinter kommen vom Browser statt aus nachgebautem JavaScript.
 *
 * **Kein Ergebnis wird verschickt.** Alles bleibt im Browser: keine Eingabe geht an einen
 * Server, es gibt keinen Endpunkt dafür. Das ist nicht nur Datenschutz, sondern der Grund,
 * warum jemand die Angaben überhaupt macht.
 */

type Leiter = {
  frage: string; einheit: string; unten: string; stufen: number[];
  je_fach: Record<string, { n: number; median: number; kum: number[] }>;
};

export type Check = {
  regionen: { schluessel: string; label: string; offen: number }[];
  stufen: { von: number; bis: number | null }[];
  zellen: Record<string, { offen: number; mitWert: number; stufen: number[] }>;
  anforderungen: Record<string, Leiter>;
  katalog: Record<string, { n: number; zeilen: { key: string; n: number; anteil: number }[] }>;
  texte: Record<string, { name: string; art: "formular" | "schwelle" | "nachweis"; was: string; frage: string | null }>;
  profile: Record<string, { n: number; ohne: number; gruppen: number[][] }>;
  nachweise: { key: string; name: string }[];
  wert: { n: number; untergrenze: number; verworfen: number; p25: number | null;
    median: number | null; p75: number | null; p95: number | null;
    unter25k: number; ab1m: number };
};

const nf = (n: number) => n.toLocaleString("de-DE");
/** Welche Regionsschlüssel zu welchem Land gehören — nur DE ist unterhalb der Landesebene
 *  aufgelöst (16 Länder); AT und CH tragen im Bestand keine belastbare Regionalzuordnung. */
const LAENDER: Record<string, string[]> = {
  DE: ["Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
       "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz",
       "Saarland", "Sachsen", "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen"],
};
const ZAHLWORT: Record<number, string> = {
  2: "Zwei", 3: "Drei", 4: "Vier", 5: "Fünf", 6: "Sechs", 7: "Sieben", 8: "Acht",
};

/** 250000 → „250.000 €", 3000000 → „3 Mio €". Auf einer Auswahlleiste zählt Kürze. */
function euro(n: number): string {
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${(Math.round(m * 10) / 10).toLocaleString("de-DE")} Mio €`;
  }
  return `${nf(n)} €`;
}

function stufenLabel(s: { von: number; bis: number | null }): string {
  if (s.von === 0) return `bis ${euro(s.bis as number)}`;
  if (s.bis === null) return `über ${euro(s.von)}`;
  return `${euro(s.von)} – ${euro(s.bis)}`;
}

/** Eine Auswahlleiste: Knöpfe statt Aufklappmenü, weil man die Nachbarwerte sehen soll. */
function Leiste({ titel, hinweis, optionen, wert, setzen }: {
  titel: string; hinweis?: string; optionen: string[]; wert: number; setzen: (i: number) => void;
}) {
  return (
    <div className="ec-frage">
      <span className="ec-frage-t">{titel}</span>
      {hinweis ? <span className="ec-frage-h">{hinweis}</span> : null}
      <div className="ec-leiter" role="group" aria-label={titel}>
        {optionen.map((o, i) => (
          <button key={o} type="button" aria-pressed={wert === i}
                  className={wert === i ? "ec-opt ec-opt-an" : "ec-opt"}
                  onClick={() => setzen(i)}>{o}</button>
        ))}
      </div>
    </div>
  );
}

export function EignungsCheck({ check, fachgebiete }: {
  check: Check; fachgebiete: { schluessel: string; label: string; offen: number }[];
}) {
  // Bewusst OHNE Vorauswahl: das rechte Feld soll auffordern, nicht schon Ergebnisse
  // zeigen, die niemand angefragt hat. Der erste Klick auf eine Kachel ist der Einstieg.
  const [fach, setFach] = useState<string | null>(null);
  const [region, setRegion] = useState("alle");
  const [schritt, setSchritt] = useState(1);
  const [erklaert, setErklaert] = useState<string | null>(null);
  const [groesse, setGroesse] = useState(2);          // 100.000 – 500.000 €: der dichteste Bereich
  const [antwort, setAntwort] = useState<Record<string, number>>({
    haftpflicht: 2, referenzen: 2, umsatz: 2,
  });
  const [hat, setHat] = useState<Record<string, boolean>>({});

  const gesamtOffen = fachgebiete.reduce(
    (summe, f) => summe + (check.zellen[`${f.schluessel}|${region}`]?.offen ?? 0), 0);
  const zelle = check.zellen[`${fach}|${region}`] ?? { offen: 0, mitWert: 0, stufen: [0, 0, 0, 0, 0, 0] };
  const fachLabel = fachgebiete.find((f) => f.schluessel === fach)?.label ?? "eurem Fachgebiet";
  const regionLabel = check.regionen.find((r) => r.schluessel === region)?.label ?? region;

  // Fällt ein Fachgebiet unter die 30 ausgewerteten Verfahren, rechnet der Katalog
  // fachgebietsübergreifend weiter — sichtbar gemacht, nicht stillschweigend.
  const eigenerKatalog = Boolean(fach && check.katalog[fach]);
  const katalog = (fach ? check.katalog[fach] : undefined) ?? check.katalog["alle"];
  const profil = (fach ? check.profile[fach] : undefined) ?? check.profile["alle"];

  // „In eurer Grössenordnung" heisst: alles bis zu der Grösse, die ihr stemmt.
  const passendeGroesse = zelle.stufen.slice(0, groesse + 1).reduce((a, b) => a + b, 0);

  /** Welche Nachweisfragen überhaupt gestellt werden — nur die, die im Feld vorkommen. */
  const nachweisfragen = check.nachweise.filter(
    (n) => katalog?.zeilen.some((z) => check.texte[z.key]?.frage === n.key));

  const fragen = 1 + Object.keys(check.anforderungen).length + nachweisfragen.length;

  /** Verlangte Stufe erfüllt? −1 heisst „in diesem Verfahren nicht beziffert". */
  const reicht = (verlangt: number, eigene: number) => verlangt < 0 || eigene >= verlangt;

  const treffer = useMemo(() => {
    if (!profil) return { passt: 0, offen: 0, mit: 0 };
    let passt = 0, offenPasst = 0, mit = 0;
    for (const g of profil.gruppen) {
      const [h, r, u, pq, i9, i14, istOffen, anzahl] = g;
      const fordert = h >= 0 || r >= 0 || u >= 0 || pq === 1 || i9 === 1 || i14 === 1;
      if (!fordert) continue;
      mit += anzahl;
      const ok = reicht(h, antwort.haftpflicht ?? -1) && reicht(r, antwort.referenzen ?? -1)
        && reicht(u, antwort.umsatz ?? -1)
        && (pq === 0 || hat.pq) && (i9 === 0 || hat.iso9001) && (i14 === 0 || hat.iso14001);
      if (!ok) continue;
      passt += anzahl;
      if (istOffen === 1) offenPasst += anzahl;
    }
    return { passt, offen: offenPasst, mit };
  }, [profil, antwort, hat]);

  /** Je Katalogzeile: erfüllt ihr das, und woran erkennt man es. */
  const zeilen = useMemo(() => (katalog?.zeilen ?? []).map((z) => {
    const t = check.texte[z.key];
    if (!t) return null;
    if (t.art === "formular") {
      return { ...z, ...t, ok: true, ihr: "erfüllbar", schwach: false };
    }
    if (t.art === "nachweis") {
      const da = Boolean(hat[t.frage ?? ""]);
      return { ...z, ...t, ok: da, ihr: da ? "vorhanden" : "fehlt", schwach: !da };
    }
    // Schwelle: die eigene Stufe gegen das, was üblicherweise verlangt wird (Median).
    const leiter = check.anforderungen[t.frage ?? ""];
    const basis = (fach ? leiter?.je_fach[fach] : undefined) ?? leiter?.je_fach["alle"];
    const i = antwort[t.frage ?? ""] ?? -1;
    const eigene = i < 0 ? null : leiter?.stufen[i];
    const ok = Boolean(basis && eigene !== null && eigene !== undefined && eigene >= basis.median);
    return {
      ...z, ...t, ok,
      ihr: eigene === null || eigene === undefined
        ? leiter?.unten ?? "keine"
        : leiter?.einheit === "€" ? euro(eigene) : String(eigene),
      schwach: !ok,
      median: basis ? (leiter.einheit === "€" ? euro(basis.median) : String(basis.median)) : null,
    };
  }).filter(Boolean) as (
    { key: string; n: number; anteil: number; name: string; art: string; was: string;
      frage: string | null; ok: boolean; ihr: string; schwach: boolean; median?: string | null })[],
    [katalog, check.texte, check.anforderungen, fach, antwort, hat]);

  const erfuellt = zeilen.filter((z) => z.ok).length;
  const luecke = zeilen.filter((z) => !z.ok).sort((a, b) => b.n - a.n)[0] ?? null;

  // Das Ergebnis nach unten reichen, sobald es eines gibt: die Relevanz-Spalte der drei
  // Masse zeigt es dann statt eines Verweises. Erst ab Schritt 3, weil vorher niemand
  // etwas beantwortet hat, und wieder weg, wenn die Auswahl aufgehoben wird.
  useEffect(() => {
    setzeCheckErgebnis(fach && schritt === 3 && zeilen.length
      ? { fachLabel, erfuellt, von: zeilen.length, luecke: luecke?.name ?? null }
      : null);
  }, [fach, schritt, fachLabel, erfuellt, zeilen.length, luecke]);

  const SCHRITTE = ["Euer Feld", "Eure Angaben", "Die Auswertung"];

  /** Kachel angeklickt: Feld setzen und im rechten Feld vorn anfangen. */
  const waehlen = (schluessel: string) => {
    setFach(schluessel);
    setSchritt(1);
  };

  // Haltepunkt NUR, solange der Abschnitt ins Fenster passt. Gemessen bei 1.400 × 900: mit
  // offener Auswertung ist er 1.185 px hoch, und der Versuch, seinen unteren Teil zu lesen,
  // wurde vom Einrasten zurückgezogen (gewollt +500 px, gelandet bei +341). Genau dieser
  // Widerhaken ist der Grund, warum Vollbild-Sektionen auf Werkzeugseiten scheitern; hier
  // lässt der Halt los, sobald das Ergebnis offen ist.
  return (
    <section className={`lp-check${fach && schritt === 3 ? "" : " lp-halt"}`} id="check">

      {/* EIN Kasten, zwei Bereiche: links die Arbeitsfläche, rechts die Bedienleiste.
          Sven: „optisch ist das irgendwie unsauber, die architektur stimmt nicht so ganz."
          Sie stimmte auch nicht — es waren zwei getrennte Dinge nebeneinander (eine
          schwebende Karte und eine lose Kachelgruppe), mit ungleich hohen Spalten und zwei
          Schattenrändern. Jetzt sind es zwei Bereiche EINES Rahmens: gemeinsame Kante,
          gemeinsame Höhe, die Leiste durch ihren Grundton als Bedienung erkennbar.
          Dass die Auswahl rechts steht, bleibt („bring das fenster von rechts nach links"). */}
      <div className="ec-zwei">
        {/* ⚠ Der Titel stand bis zum 2026-08-21 ÜBER dem Rahmen und wirkte dort, so Sven,
            „verloren": eine Zeile Text über einem schweren Kasten, ohne Verbindung. Und die
            linke obere Ecke des Rahmens war leer, während rechts schon die Leiste anfing.
            Beides derselbe Fehler — dem Rahmen fehlte ein Kopf. Jetzt trägt er ihn über
            beide Bereiche, und der Titel sitzt an dem, was er benennt. */}
        <div className="ec-rahmenkopf">
          <h2>Was heute offen ist. Und ob ihr drankommt.</h2>
          {/* ⚠ „in überall" stand hier kurz — der Schlüssel „alle" trägt als Beschriftung
              ein Adverb, das sich nicht in „in …" einsetzen lässt. */}
          <p>
            {nf(gesamtOffen)} offene Vergaben in sechs Fachgebieten
            {region === "alle" ? ", in allen drei Ländern" : `, ${regionLabel}`}
          </p>
        </div>

        <div className="ec-fenster">
          {!fach ? (
            <div className="ec-leer">
              {/* ⚠ Hier stand bis zum 2026-08-21 nur eine Aufforderung, und der Rest der
                  Fläche war leer — Sven: „optisch ist das irgendwie unsauber". Eine leere
                  Arbeitsfläche neben einer vollen Leiste sieht nach halbfertig aus. Jetzt
                  steht hier, was wir OHNE jede Angabe schon wissen: die häufigsten
                  Anforderungen über alle Fachgebiete. Erst geben, dann fragen. */}
              <h3>Das wird in Vergabeunterlagen am häufigsten verlangt.</h3>
              <p className="ec-leer-p">
                Aus {nf(check.katalog["alle"]?.n ?? 0)} ausgewerteten Unterlagen aller
                Fachgebiete. Wählt euer Fachgebiet, dann steht hier dessen eigene Liste,
                und nach {(ZAHLWORT[fragen] ?? String(fragen)).toLowerCase()} Fragen daneben,
                was ihr davon erfüllt.
              </p>

              <p className="ec-fundkopf" aria-hidden="true">
                <span>Anforderung</span><span>belegt in</span>
              </p>
              <ul className="ec-fund ec-fund-still">
                {(check.katalog["alle"]?.zeilen ?? []).slice(0, 6).map((z) => (
                  <li key={z.key}>
                    <span className="ec-haken ec-haken-still" aria-hidden="true">·</span>
                    <span className="ec-f-name">{check.texte[z.key]?.name ?? z.key}</span>
                    <span className="ec-f-quote">{z.anteil} %</span>
                  </li>
                ))}
              </ul>

              <p className="ec-leer-f">
                Die Hälfte der Vergaben mit veröffentlichtem Wert liegt zwischen{" "}
                {check.wert.p25 !== null ? euro(check.wert.p25) : "?"} und{" "}
                {check.wert.p75 !== null ? euro(check.wert.p75) : "?"};{" "}
                {nf(check.wert.unter25k)} offene liegen unter 25.000 €,{" "}
                {nf(check.wert.ab1m)} über einer Million. Ohne Anmeldung, ohne Firmendaten.
              </p>
            </div>
          ) : (
            <>
              <div className="ec-fenster-kopf">
                <ol className="ec-schritte">
                  {SCHRITTE.map((t, i) => (
                    <li key={t} aria-current={schritt === i + 1 ? "step" : undefined}
                        className={schritt > i + 1 ? "ec-s-fertig" : schritt === i + 1 ? "ec-s-jetzt" : ""}>
                      <b>{i + 1}</b> {t}
                    </li>
                  ))}
                </ol>
                <button type="button" className="ec-zu" aria-label="Auswahl aufheben"
                        onClick={() => { setFach(null); setSchritt(1); }}>×</button>
              </div>

              <div className="ec-fenster-koerper">
                {schritt === 1 ? (
                  <>
                    <h3 className="ec-d-h">{fachLabel}, {regionLabel}</h3>
                    <p className="ec-d-sub">Das ist die Grundlage, auf der wir gleich rechnen.</p>
                    <ul className="ec-teaser">
                      <li><b>{nf(zelle.offen)}</b><span>offene Vergaben</span></li>
                      <li><b>{nf(katalog?.n ?? 0)}</b><span>ausgewertete Vergabeunterlagen
                        {eigenerKatalog ? "" : ", alle Fachgebiete"}</span></li>
                      <li><b>{nf(zelle.mitWert)}</b><span>davon mit veröffentlichtem Wert</span></li>
                    </ul>
                    <p className="ec-d-fuss">
                      Aus diesen Unterlagen lesen wir, welche Nachweise verlangt werden. Im
                      nächsten Schritt fragen wir, was ihr davon habt: {fragen} Fragen, alle
                      zum Anklicken.
                    </p>
                  </>
                ) : null}

                {schritt === 2 ? (
                  <>
                    <h3 className="ec-d-h">Was habt ihr?</h3>
                    <p className="ec-d-sub">
                      {fragen} Fragen. Danach sagen wir euch, bei wie vielen der ausgewerteten
                      Verfahren das gereicht hätte.
                    </p>
                    <Leiste titel="Aufträge bis zu welcher Grösse könnt ihr stemmen?"
                            optionen={check.stufen.map(stufenLabel)} wert={groesse} setzen={setGroesse} />
                    {Object.entries(check.anforderungen).map(([name, a]) => (
                      <Leiste key={name} titel={a.frage}
                              optionen={[a.unten, ...a.stufen.map((x) => (a.einheit === "€" ? euro(x) : String(x)))]}
                              wert={(antwort[name] ?? 0) + 1}
                              setzen={(i) => setAntwort({ ...antwort, [name]: i - 1 })} />
                    ))}
                    {/* Nachweisfragen nur, wenn sie im Feld überhaupt vorkommen: nach
                        ISO 14001 zu fragen, wo es in 0,2 % der Unterlagen steht, ist Zeitraub. */}
                    {nachweisfragen.map((n) => (
                      <Leiste key={n.key} titel={`Habt ihr ${n.name}?`} optionen={["nein", "ja"]}
                              wert={hat[n.key] ? 1 : 0}
                              setzen={(i) => setHat({ ...hat, [n.key]: i === 1 })} />
                    ))}
                  </>
                ) : null}

                {schritt === 3 ? (
                  <>
                    {profil && treffer.mit >= 30 ? (
                      <div className="ec-gross">
                        <p className="ec-bigline">
                          <span className="ec-bignum">{nf(treffer.passt)}</span>
                          <span className="ec-bigrest">
                            der {nf(treffer.mit)} ausgewerteten Verfahren hätten gepasst.
                          </span>
                        </p>
                        <p className="ec-bigsub">
                          Gezählt gegen die Verfahren in {eigenerKatalog ? fachLabel : "allen Fachgebieten"},
                          deren Unterlagen mindestens eine bezifferte Anforderung tragen.
                          {treffer.offen > 0
                            ? ` ${nf(treffer.offen)} davon sind heute noch offen.`
                            : " Keines davon ist heute noch offen."}
                        </p>
                      </div>
                    ) : (
                      <p className="ec-bigsub">
                        Für {fachLabel} sind bisher zu wenige Unterlagen ausgewertet, um zu
                        sagen, bei wie vielen Verfahren es gereicht hätte. Belastbar wird das
                        ab 30 ausgewerteten Vergabeunterlagen je Fachgebiet.
                      </p>
                    )}

                    <div className="ec-listenkopf">
                      <h3>Was gefordert wurde</h3>
                      <p>
                        Nach Häufigkeit, aus {nf(katalog?.n ?? 0)} ausgewerteten Unterlagen
                        {eigenerKatalog ? "" : " aller Fachgebiete"}. Das Fragezeichen erklärt,
                        was dahintersteckt.
                      </p>
                    </div>

                    <p className="ec-fundkopf" aria-hidden="true">
                      <span>Anforderung</span><span>belegt in</span><span>ihr</span>
                    </p>
                    <ul className="ec-fund">
                      {zeilen.map((z) => (
                        <li key={z.key} className={z.ok ? "ec-f-ok" : "ec-f-weg"}>
                          <span className={z.ok ? "ec-haken" : "ec-haken ec-haken-weg"} aria-hidden="true">
                            {z.ok ? "✓" : "–"}
                          </span>
                          <span className="ec-f-name">
                            {z.name}
                            <button type="button" className="ec-was"
                                    aria-expanded={erklaert === z.key}
                                    aria-label={`Was ist ${z.name}?`}
                                    onClick={() => setErklaert(erklaert === z.key ? null : z.key)}>?</button>
                            {z.art === "schwelle" && z.median
                              ? <span className="ec-f-med">üblich: {z.median}</span> : null}
                          </span>
                          <span className="ec-f-quote">{z.anteil} %</span>
                          <span className={z.ok ? "ec-f-ihr" : "ec-f-ihr ec-f-ihr-weg"}>{z.ihr}</span>
                          {erklaert === z.key ? <p className="ec-erklaerung">{z.was}</p> : null}
                        </li>
                      ))}
                    </ul>

                    <p className="ec-summe">
                      <span aria-hidden="true">Σ</span>
                      <span><b>{erfuellt} von {zeilen.length} erfüllt</b>, die Formulare
                        mitgezählt, die jeder ausfüllen kann.</span>
                      <span className="ec-summe-p">
                        {zeilen.length ? Math.round((erfuellt / zeilen.length) * 100) : 0} %
                      </span>
                    </p>

                    {luecke ? (
                      <p className="ec-luecke">
                        <b>Eure grösste Lücke ist {luecke.name}.</b> In {nf(luecke.n)} der{" "}
                        {nf(katalog?.n ?? 0)} ausgewerteten Unterlagen steht es drin.
                      </p>
                    ) : (
                      <p className="ec-fazit">
                        <span className="ec-punkt" aria-hidden="true" />
                        <span>Von dem, was in diesen Unterlagen belegt ist, erfüllt ihr alles.</span>
                        <span className="ec-marke">gemessen, nicht geschätzt</span>
                      </p>
                    )}

                    <p className="ec-fuss">
                      Grundlage: {nf(katalog?.n ?? 0)} ausgewertete Vergabeunterlagen
                      {eigenerKatalog ? ` in ${fachLabel}` : " über alle Fachgebiete"};
                      Auftragswerte nur über die {nf(zelle.mitWert)} Vergaben dieses
                      Zuschnitts mit veröffentlichtem Wert, davon liegen {nf(passendeGroesse)}
                      {" "}in eurer Grössenordnung. „Belegt in {zeilen[0]?.anteil ?? 0} %"
                      heisst: in so vielen der ausgewerteten Verfahren steht es wörtlich. Was
                      unsere Auswertung nicht erfasst hat, fehlt hier. Über die Zulassung im
                      Einzelfall entscheidet die Vergabestelle.
                    </p>
                  </>
                ) : null}
              </div>

              <div className="ec-fenster-fuss">
                {schritt > 1
                  ? <button type="button" className="ec-zurueck"
                            onClick={() => setSchritt(schritt - 1)}>Zurück</button>
                  : <span className="ec-fuss-hinweis">Ohne Anmeldung, ohne Firmendaten</span>}
                {schritt < 3 ? (
                  <button type="button" className="lp-knopf" onClick={() => setSchritt(schritt + 1)}>
                    {schritt === 1 ? "Weiter zu euren Angaben" : "Auswertung ansehen"}
                  </button>
                ) : (
                  <Link className="lp-knopf" href="/onboarding">
                    {treffer.offen > 0 ? `${nf(treffer.offen)} passende offene Vergaben ansehen`
                      : "Die passenden Vergaben ansehen"}
                  </Link>
                )}
              </div>
            </>
          )}
        </div>
        {/* Region ÜBER den Kacheln, so breit wie sie: sie ändert deren Zahlen, und ein
            Regler gehört über das, was er regelt, nicht daneben. Die Spalte steht rechts,
            damit das Gewicht der Seite nicht nach rechts kippt — links steht der Inhalt. */}
        <div className="ec-auswahl">
          {/* Der Inhalt der Leiste klebt: bei offener Auswertung ist die Arbeitsfläche
              tausend Pixel hoch, und wer dann das Fachgebiet wechseln will, soll nicht
              zurückscrollen müssen. Der Grund der Leiste bleibt dabei durchgehend. */}
          <div className="ec-auswahl-innen">
          <label className="ec-regionwahl">
            <span>Region</span>
            {/* Nach Ländern gruppiert wie in der Vorlage: das Aufklappmenü listete vorher
                „überall, Deutschland gesamt, Österreich, Schweiz" und dann sechzehn
                Bundesländer ohne erkennbare Zugehörigkeit. `optgroup` zieht die Trennlinien
                und beschriftet sie, das macht der Browser selbst. */}
            <select value={region} onChange={(e) => setRegion(e.target.value)}>
              {check.regionen.filter((r) => r.schluessel === "alle").map((r) => (
                <option key={r.schluessel} value={r.schluessel}>{r.label}</option>
              ))}
              <optgroup label="Deutschland">
                {check.regionen
                  .filter((r) => r.schluessel === "DE" || LAENDER.DE.includes(r.schluessel))
                  .map((r) => (
                    <option key={r.schluessel} value={r.schluessel}>{r.label}</option>
                  ))}
              </optgroup>
              {check.regionen.some((r) => r.schluessel === "AT") ? (
                <optgroup label="Österreich">
                  <option value="AT">
                    {check.regionen.find((r) => r.schluessel === "AT")?.label ?? "Österreich"}
                  </option>
                </optgroup>
              ) : null}
              {check.regionen.some((r) => r.schluessel === "CH") ? (
                <optgroup label="Schweiz">
                  <option value="CH">
                    {check.regionen.find((r) => r.schluessel === "CH")?.label ?? "Schweiz"}
                  </option>
                </optgroup>
              ) : null}
            </select>
          </label>
          <p className="ec-leiste-t">Fachgebiet</p>
          <ul className="ec-kacheln" role="group" aria-label="Fachgebiet wählen">
            {fachgebiete.map((f) => {
              const z = check.zellen[`${f.schluessel}|${region}`];
              return (
                <li key={f.schluessel}>
                  <button type="button" aria-pressed={fach === f.schluessel}
                          aria-label={`${f.label}: ${nf(z?.offen ?? 0)} offene Vergaben`}
                          className={fach === f.schluessel ? "ec-kachel ec-kachel-an" : "ec-kachel"}
                          onClick={() => waehlen(f.schluessel)}>
                    <b>{nf(z?.offen ?? 0)}</b>
                    <span>{f.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          </div>
        </div>
      </div>

      {/* Eine Zeile, volle Breite: gekürzt, bis sie ohne Umbruch unter den Kasten passt. */}
      <p className="lp-klein ec-zuschnitt">
        Gezählt sind Vorgänge mit laufender Frist; der Zuschnitt läuft über CPV-Codes, nicht
        über Schlagworte. Was sich keinem der sechs Gebiete zuordnen lässt, steht drinnen.
      </p>
    </section>
  );
}
