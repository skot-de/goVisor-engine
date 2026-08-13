/* UI-Anzeige-Labels — die Sprachschicht des Frontends.
 *
 * Prinzip (Analog zu `profile_type` auf der Datenseite): der Daten-Export trägt nur
 * sprachneutrale CODES (src, contractKind, naturKat, volumen.src …), NIE fertige
 * deutsche Anzeige-Strings. Übersetzt wird hier. Eine zweite Sprache ist damit ein
 * zweiter Katalog + eine Sprachwahl — die exportierte JSON bleibt unverändert neutral.
 *
 * `applyLabels(lead)` füllt die Anzeige-Felder aus den Codes, aber NUR wenn sie fehlen —
 * die hand-kuratierten Prototyp-Demo-Leads (die ihre Labels literal tragen) bleiben
 * unangetastet; nur die aus dem Export geladenen echten Leads werden übersetzt.
 *
 * Oberflächensprache: der Katalog unten bleibt DEUTSCH — er ist eine Modul-Konstante und
 * würde die Sprache beim Import einfrieren. Übersetzt wird erst in `applyLabels`, also beim
 * Erzeugen des Anzeige-Textes (`tk`, die React-freie Fassung von `t`, s. lib/i18n).
 */

import { tk } from './i18n';

const CATALOG = {
  de: {
    src:   { auslauf: 'Vertragsende', f02: 'Ausschreibung offen', f01: 'Ankündigung', award: 'Zuschlag erteilt' },
    art:   { framework: 'Rahmenvertrag', recurring: 'Wiederkehrende Leistung',
             one_off_works: 'Bauwerk (einmalig)', works_other: 'Bauleistung',
             other: 'Einzelauftrag' },
    natur: { dienst: 'Dienstleistung', liefer: 'Lieferung', bau: 'Bauleistung' },
    // volumen.src ist ein Code (echt/schaetz/unbekannt) — hier zum Herkunfts-Satz übersetzt.
    volHint: { echt: 'Aus der Bekanntmachung.',
               schaetz: 'Abgeleitet — nicht veröffentlicht.',
               unbekannt: 'Abgeleitet — nicht veröffentlicht.' },
    // Ohne führendes Leerzeichen: der Abstand entsteht beim Zusammensetzen unten. Ein Schlüssel
    // mit Randweißraum findet seine Übersetzung sonst nicht wieder.
    volHintFramework: 'Rahmenvertrag — der Nennwert ist Ober-/Schätzgrenze; real abgerufen wird oft ein Vielfaches.',
  },
};

let LANG = 'de';
export function setLang(code) { if (CATALOG[code]) LANG = code; }
function cat() { return CATALOG[LANG] || CATALOG.de; }

/* Anzeige-Felder eines Leads aus seinen Codes ableiten. Nur fehlende Felder werden gesetzt. */
export function applyLabels(l, neu = false) {
  if (!l) return l;
  const c = cat();
  // `neu = true` beim Sprachwechsel: die Labels sind zwischengespeichert (nur setzen, wenn
  // leer), damit ein zweiter Lauf nichts kostet. Genau dieser Cache liess die bereits
  // geladene Liste nach dem Umschalten deutsch stehen — sichtbar in der Phase-Spalte.
  const frisch = (wert) => neu || wert == null;
  /* Code → Anzeige-Text in der Oberflächensprache. Unbekannte Codes bleiben roh stehen
     („lieber unbekannt zeigen als falsch"), werden also NICHT durch tk geschickt. */
  const lab = (tabelle, code, fallback) => (tabelle[code] ? tk(tabelle[code]) : fallback);
  if (l.src && frisch(l.srcLabel))      l.srcLabel = lab(c.src, l.src, l.src);
  if (l.src && frisch(l.phaseLabel))    l.phaseLabel = lab(c.src, l.src, l.src);
  if (l.contractKind && frisch(l.art))  l.art = lab(c.art, l.contractKind, null);
  if (l.naturKat && frisch(l.natur))    l.natur = lab(c.natur, l.naturKat, l.naturKat);
  if (l.volumen && frisch(l.volumen.hint)) {
    const teile = [];
    const base = c.volHint[l.volumen.src];
    if (base) teile.push(tk(base));
    if (l.istRahmen) teile.push(tk(c.volHintFramework));
    l.volumen.hint = teile.join(' ');
  }
  return l;
}
