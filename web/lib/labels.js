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
 */

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
    volHintFramework: ' Rahmenvertrag — der Nennwert ist Ober-/Schätzgrenze; real abgerufen wird oft ein Vielfaches.',
  },
};

let LANG = 'de';
export function setLang(code) { if (CATALOG[code]) LANG = code; }
function cat() { return CATALOG[LANG] || CATALOG.de; }

/* Anzeige-Felder eines Leads aus seinen Codes ableiten. Nur fehlende Felder werden gesetzt. */
export function applyLabels(l) {
  if (!l) return l;
  const c = cat();
  if (l.src && l.srcLabel == null)      l.srcLabel = c.src[l.src] || l.src;
  if (l.src && l.phaseLabel == null)    l.phaseLabel = c.src[l.src] || l.src;
  if (l.contractKind && l.art == null)  l.art = c.art[l.contractKind] || null;
  if (l.naturKat && l.natur == null)    l.natur = c.natur[l.naturKat] || l.naturKat;
  if (l.volumen && l.volumen.hint == null) {
    const base = c.volHint[l.volumen.src] || '';
    l.volumen.hint = base + (l.istRahmen ? c.volHintFramework : '');
  }
  return l;
}
