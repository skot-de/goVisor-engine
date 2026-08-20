"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

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
  wert: { n: number; min: number | null; median: number | null; max: number | null; unter25k: number };
};

const nf = (n: number) => n.toLocaleString("de-DE");
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
  const [fach, setFach] = useState(fachgebiete[0]?.schluessel ?? "bau");
  const [region, setRegion] = useState("alle");
  const [offen, setOffen] = useState(false);
  const [erklaert, setErklaert] = useState<string | null>(null);
  const [groesse, setGroesse] = useState(2);          // 100.000 – 500.000 €: der dichteste Bereich
  const [antwort, setAntwort] = useState<Record<string, number>>({
    haftpflicht: 2, referenzen: 2, umsatz: 2,
  });
  const [hat, setHat] = useState<Record<string, boolean>>({});

  const zelle = check.zellen[`${fach}|${region}`] ?? { offen: 0, mitWert: 0, stufen: [0, 0, 0, 0, 0, 0] };
  const fachLabel = fachgebiete.find((f) => f.schluessel === fach)?.label ?? fach;
  const regionLabel = check.regionen.find((r) => r.schluessel === region)?.label ?? region;

  // Fällt ein Fachgebiet unter die 30 ausgewerteten Verfahren, rechnet der Katalog
  // fachgebietsübergreifend weiter — sichtbar gemacht, nicht stillschweigend.
  const eigenerKatalog = Boolean(check.katalog[fach]);
  const katalog = check.katalog[fach] ?? check.katalog["alle"];
  const profil = check.profile[fach] ?? check.profile["alle"];

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
    const basis = leiter?.je_fach[fach] ?? leiter?.je_fach["alle"];
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

  return (
    <section className="lp-check" id="check">
      <div className="ec-kacheln-block">
        <h2 className="lp-h2">Was heute offen ist. Und ob ihr drankommt.</h2>
        <ul className="ec-kacheln" role="group" aria-label="Fachgebiet wählen">
          {fachgebiete.map((f) => {
            const z = check.zellen[`${f.schluessel}|${region}`];
            return (
              <li key={f.schluessel}>
                <button type="button" aria-pressed={fach === f.schluessel}
                        aria-label={`${f.label}: ${nf(z?.offen ?? 0)} offene Vergaben`}
                        className={fach === f.schluessel ? "ec-kachel ec-kachel-an" : "ec-kachel"}
                        onClick={() => setFach(f.schluessel)}>
                  <b>{nf(z?.offen ?? 0)}</b>
                  <span>{f.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <p className="lp-klein">
          Gezählt sind Vorgänge mit laufender Frist, {regionLabel === "überall"
            ? "in allen drei Ländern" : regionLabel}. Dazu alles, was sich keinem dieser
          Gebiete zuordnen lässt: Lieferungen, Dienstleistungen, Sonderfälle. Der Zuschnitt
          läuft über CPV-Codes, nicht über Schlagworte.
        </p>
      </div>

      <div className="ec-text">
        <p className="lp-auge">Eignungs-Check</p>
        <h2 className="lp-h3">Jeder kann mitbieten. Auch ihr.</h2>
        <p>
          Öffentliche Aufträge gelten als eine Sache für Grosse. Der kleinste offene Auftrag
          im Bestand liegt bei {check.wert.min !== null ? euro(check.wert.min) : "—"},
          {" "}{nf(check.wert.unter25k)} offene Vergaben liegen unter 25.000 €, nach oben
          hört es bei {check.wert.max !== null ? euro(check.wert.max) : "—"} auf.
        </p>
        <p>
          Sagt uns, was ihr habt. Wir zeigen euch, was in eurem Fachgebiet tatsächlich
          verlangt wird und wie viel davon ihr schon mitbringt. Ohne Anmeldung, ohne
          Firmendaten, nichts davon verlässt euren Browser.
        </p>
      </div>

      <div className="ec-panel">
        <div className="ec-kopf">
          <label>
            <span>Region — die Kacheln oben rechnen mit</span>
            <select value={region} onChange={(e) => setRegion(e.target.value)}>
              {check.regionen.map((r) => (
                <option key={r.schluessel} value={r.schluessel}>{r.label}</option>
              ))}
            </select>
          </label>
        </div>

        <p className="ec-vorschau">
          <b>{nf(zelle.offen)}</b> offene Vergaben in {fachLabel}, {regionLabel}.
        </p>

        {!offen ? (
          <button type="button" className="ec-mehr" onClick={() => setOffen(true)}>
            Wie nah seid ihr dran? {ZAHLWORT[fragen] ?? String(fragen)} Fragen, keine Anmeldung
            <span aria-hidden="true">→</span>
          </button>
        ) : null}

        <div className={offen ? "ec-tief" : "ec-tief ec-zu"} hidden={!offen}>
          <Leiste titel="Aufträge bis zu welcher Grösse könnt ihr stemmen?"
                  optionen={check.stufen.map(stufenLabel)} wert={groesse} setzen={setGroesse} />

          {Object.entries(check.anforderungen).map(([name, a]) => (
            <Leiste key={name} titel={a.frage}
                    optionen={[a.unten, ...a.stufen.map((s) => (a.einheit === "€" ? euro(s) : String(s)))]}
                    wert={(antwort[name] ?? 0) + 1}
                    setzen={(i) => setAntwort({ ...antwort, [name]: i - 1 })} />
          ))}

          {/* Nachweisfragen kommen nur, wenn sie in diesem Feld überhaupt vorkommen: nach
              ISO 14001 zu fragen, wo es in 0,2 % der Unterlagen steht, ist Zeitraub. */}
          {nachweisfragen.map((n) => (
            <Leiste key={n.key} titel={`Habt ihr ${n.name}?`} optionen={["nein", "ja"]}
                    wert={hat[n.key] ? 1 : 0}
                    setzen={(i) => setHat({ ...hat, [n.key]: i === 1 })} />
          ))}

          <div className="ec-ergebnis">
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
                Für {fachLabel} sind bisher zu wenige Unterlagen ausgewertet, um zu sagen,
                bei wie vielen Verfahren es gereicht hätte. Belastbar wird das ab 30
                ausgewerteten Vergabeunterlagen je Fachgebiet.
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

            {/* Kopfzeile statt „belegt in" in jeder Zeile — elfmal dieselbe Präposition
                untereinander liest sich wie ein Formular, nicht wie ein Befund. */}
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
              <span><b>{erfuellt} von {zeilen.length} erfüllt</b> — die Formulare mitgezählt,
                die jeder ausfüllen kann.</span>
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

            <div className="ec-aktion">
              <Link className="lp-knopf" href="/onboarding">
                {treffer.offen > 0 ? `${nf(treffer.offen)} passende offene Vergaben ansehen`
                  : "Die passenden Vergaben ansehen"}
              </Link>
              <span className="ec-aktion-h">kostenfrei, ohne Zahlungsdaten</span>
            </div>

            <p className="ec-fuss">
              Grundlage: {nf(katalog?.n ?? 0)} ausgewertete Vergabeunterlagen
              {eigenerKatalog ? ` in ${fachLabel}` : " über alle Fachgebiete"}; Auftragswerte
              nur über die {nf(zelle.mitWert)} Vergaben dieses Zuschnitts mit
              veröffentlichtem Wert, davon liegen {nf(passendeGroesse)} in eurer
              Grössenordnung. „Belegt in {zeilen[0]?.anteil ?? 0} %" heisst: in so vielen der
              ausgewerteten Verfahren steht es wörtlich — was unsere Auswertung nicht erfasst
              hat, fehlt hier. Über die Zulassung im Einzelfall entscheidet die Vergabestelle.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
