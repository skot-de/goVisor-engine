/* Profil-Engine — das Fundament der Personalisierung.
 *
 * Ein Firmenprofil ist ein strukturiertes Objekt (nicht die grobe klein/mittel/gross-
 * Heuristik). `matchLead` rechnet einen Lead gegen ein Profil und liefert eine
 * ERKLÄRBARE Passung: je Dimension ein Status mit Begründung, plus harte K.-o.-Kriterien.
 *
 * Wichtig (Produktprinzip): Unbekanntes schließt nie aus. Ein fehlender Auftragswert
 * macht einen Lead „nicht prüfbar", nicht „unpassend". Die Richtung einer Lücke wird
 * nie behauptet, solange sie unbekannt ist.
 *
 * Denselben Profil-Vertrag erzeugen später Onboarding UND die Testsicht — die Engine
 * kennt die Quelle nicht.
 */

export function emptyProfile() {
  return {
    firma: null,
    entityConfidence: null,   // 'belegt' | 'unsicher' | null — steuert den ⚠-Guard (Ticket #11 §4.2)
    cpvFields: [],            // CPV4-Codes: die eigenen Schwerpunkte (Nachbarfeld-Ebene)
    cpvFields6: [],           // CPV6-Codes: gewerkscharfe Volltreffer-Menge (trennt Aufzug≠Elektro)
    cpvLabels: [],           // Klartext-Labels zu cpvFields (nur Anzeige)
    cpvWins: {},             // cpv4 → eigene Zuschläge (aus dem Onboarding-Match, für Direktvergleich)
    // ⚠ GEHOERT HIERHER, WEIL `brancheFromProfile` ES LIEST. Das Feld fehlte, und
    // `buildProfile` warf es damit weg — unsichtbar, solange niemand ein rohes Profil
    // durch die Normalisierung schickte. Seit `loadProfile` das am 2026-09-17 tut, kam
    // ein Profil mit `branche: "bau"` als `branche: undefined` zurueck; der Explorer fiel
    // auf den Vorgaberaum „it" zurueck und zeigte **0 von 0**.
    //
    // `brancheFromProfile` kann die Branche zwar aus den CPV-Feldern ableiten — aber nur
    // als Rueckfall. Eine ausdrueckliche Angabe schlaegt jede Ableitung, und genau die
    // ging verloren.
    /** @type {string|null} Grundraum, ausdruecklich gesetzt (schlaegt die CPV-Ableitung).
     *  ⚠ Die Annotation ist noetig, nicht schmueckend: ohne sie inferiert TypeScript aus
     *  `null` den Typ `null`, und der Schnitt mit `branche?: string` in
     *  `supabase/auth.ts` wird zu `never` — die ganze Profile-Form kippt. */
    branche: null,
    nachbarFields: [],        // angrenzende Felder (teil-relevant, kein Volltreffer)
    regions: null,           // Array NUTS-Präfixe; null = bundesweit tätig
    regionTyp: null,         // 'regional'|'teilregional'|'bundesweit' — aus der Historie gemessen
    regionLabels: [],        // Klartext-Labels zu regions (nur Anzeige)
    volMin: null,
    volMax: null,
    maxAlleine: null,        // größter Auftrag ohne Partner (€) — stärkster Einzelwert
    buergschaft: null,       // Bürgschaftsrahmen (€); null = nicht hinterlegt
    rahmen: null,            // bevorzugte Rechtsrahmen (vgv/vob/…); null = alle
    capabilities: [],        // Fähigkeitsfelder (keys)
    // #27 §6 — wirken auf die Relevanz (Deferral aufgelöst):
    exclusions: null,        // {wert_min,wert_max,regionen_aus[],cpv_aus[],keine_bietergemeinschaft}
    zielrichtung: 'ausgewogen', // 'bestand' | 'ausgewogen' | 'expandieren'
  };
}

/* Ein Profil aus Onboarding-Eingaben bauen. Genau der Vertrag, den die Engine erwartet —
 * dieselbe Funktion füllt später auch die verteilte Erhebung (Ticket #11 §6). */
export function buildProfile(input) {
  const p = emptyProfile();
  p.firma = input.firma ? String(input.firma).trim() : null;
  p.entityConfidence = input.entityConfidence || null;
  p.cpvFields = input.cpvFields || [];
  p.cpvFields6 = input.cpvFields6 || [];
  p.cpvLabels = input.cpvLabels || [];
  p.cpvWins = input.cpvWins || {};
  p.branche = input.branche || null;
  p.nachbarFields = input.nachbarFields || [];
  p.regions = (input.regions && input.regions.length) ? input.regions : null;   // leer = bundesweit
  p.regionTyp = input.regionTyp || null;
  p.regionLabels = input.regionLabels || [];
  p.volMin = numOrNull(input.volMin);
  p.volMax = numOrNull(input.volMax);
  p.maxAlleine = numOrNull(input.maxAlleine);
  p.buergschaft = numOrNull(input.buergschaft);
  p.capabilities = input.capabilities || [];
  p.exclusions = input.exclusions || null;
  p.zielrichtung = input.zielrichtung || 'ausgewogen';
  return p;
}

function numOrNull(v) {
  if (v == null || v === '') return null;
  const n = typeof v === 'number' ? v : parseFloat(String(v).replace(/[^\d.,]/g, '').replace(/\./g, '').replace(',', '.'));
  return isNaN(n) ? null : n;
}

/* Wie viele der Angaben, die die Pruefung wirklich liest, sind hinterlegt?
 *
 * ⚠ DIE ZAHL IM NENNER IST KEINE MEINUNG. Gezaehlt wird genau das, was `matchLead` weiter
 * unten ausliest UND was ein Mensch im Profil setzen kann. Ein Feld, das niemand fuellen
 * kann (`cpvWins` kommt aus dem Onboarding-Abgleich, `nachbarFields` leiten wir ab), waere
 * im Nenner eine Schuld, die man nicht begleichen kann.
 *
 * ⚠ DESHALB HEISST ES „4 von 6" UND NICHT „67 %". Ein Prozentsatz verspricht, dass 100
 * erreichbar ist. Wer keine Buergschaft hat und keine will, kommt nie dorthin und wird
 * dafuer jeden Tag angetippt. „4 von 6" sagt dasselbe, ohne das Versprechen.
 *
 * ⚠ `regions: null` heisst NICHT „nicht ausgefuellt", sondern „bundesweit taetig" (s.
 * `buildProfile`: leere Eingabe wird bewusst zu null). Wer das als Luecke zaehlt, fordert
 * eine Angabe ein, die der Nutzer schon gemacht hat. `regionTyp` traegt die Absicht.
 */
export function angabenStand(p) {
  const gesetzt = (v) => {
    if (v == null || v === false || v === '') return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'object') return Object.values(v).some(gesetzt);
    if (typeof v === 'number') return v !== 0;
    return true;
  };
  const felder = [
    ['fach',   gesetzt(p && p.cpvFields)],
    ['region', !!(p && ((p.regions && p.regions.length) || p.regionTyp === 'bundesweit'))],
    ['wert',   !!(p && (p.volMin != null || p.volMax != null))],
    ['allein', !!(p && p.maxAlleine != null)],
    ['buerg',  !!(p && p.buergschaft != null)],
    ['aus',    gesetzt(p && p.exclusions)],
  ];
  return {
    voll: felder.filter((f) => f[1]).length,
    gesamt: felder.length,
    offen: felder.filter((f) => !f[1]).map((f) => f[0]),
  };
}

export function hasProfile(p) {
  return !!(p && p.cpvFields && p.cpvFields.length);
}

// CPV-Division (2-stellig) → Grundraum. Autoritativ aus dim_cpv.branche + der BRANCHE-CASE
// in export_web_leads.py (dieselbe Zuordnung, mit der die leads-<branche>.json gebaut werden).
// Alles Nicht-Gelistete → 'beratung' (der ELSE-Zweig).
const DIVISION_BRANCHE = {
  '30': 'it', '32': 'it', '48': 'it', '64': 'it', '72': 'it', '31': 'it', '38': 'it',
  '44': 'bau', '45': 'bau', '51': 'bau', '70': 'bau', '71': 'bau', '50': 'bau',
  '33': 'medizin', '85': 'medizin',
  '35': 'sicherheit',
  '09': 'energie', '76': 'energie', '65': 'energie', '41': 'energie', '90': 'energie', '24': 'energie', '14': 'energie',
};

/* Grundraum (Branche) aus dem Profil ableiten — damit ein Kunde nach dem Onboarding SEINE Leads
 * sieht, nicht den IT-Default. Explizite p.branche gewinnt (Nicht-Match-Pfad); sonst der Grundraum,
 * in dem die Firma die meisten Zuschläge hat (gewichtet über cpvWins, sonst gezählt). */
export function brancheFromProfile(p) {
  if (!p) return null;
  if (p.branche) return p.branche;
  const fields = p.cpvFields || [];
  if (!fields.length) return null;
  const wins = p.cpvWins || {};
  const score = {};
  for (const f of fields) {
    const br = DIVISION_BRANCHE[String(f).slice(0, 2)] || 'beratung';
    score[br] = (score[br] || 0) + (wins[f] || 1);
  }
  let best = null, bw = -1;
  for (const br in score) if (score[br] > bw) { bw = score[br]; best = br; }
  return best;
}

// Bürgschaften liegen typisch bei ~5 % der Auftragssumme (Bietungs-/Vertragserfüllung).
const BUERG_QUOTE = 0.05;

/* Erklärbare Passung eines Leads gegen ein Profil.
 * leadValue: der geparste Auftragswert in € (oder null = unbekannt) — außerhalb geparst,
 * damit die Engine frei von Parsing-Heuristik bleibt. */
/* Passungszahl — dieselbe Rechnung wie die Relevanz-Stufe, nur nicht auf drei Stufen
 * gerundet. `s` laeuft von 2 (nichts passt ausser dem Nachbarfeld) bis 5,5 (alles passt).
 *
 * ⚠ Sie ist BEWUSST grob. `s` springt in Halbschritten, es gibt genau acht erreichbare
 * Werte: 0 · 14 · 29 · 43 · 57 · 71 · 86 · 100. Wer daraus eine feine Skala liest, liest
 * mehr hinein als drin ist.
 *
 * ⚠ Und sie ist KEIN Prozentsatz und keine Gewinnwahrscheinlichkeit. Sie ordnet, sie
 * prognostiziert nicht. Eine kalibrierte Zahl haben wir woanders (dim_displaceability,
 * ECE 0,016) — diese hier ist eine Rangzahl. Darum bleibt die STUFE die Aussage; die Zahl
 * dient dem Sortieren und einem Mindestwert. Nie ohne die Beleglage zeigen (dichte.ts):
 * „71 bei duenner Beleglage" ist eine andere Aussage als „71 bei reicher".
 *
 * Die Grenzen der Stufen liegen skaliert bei 71 (hoch) und 29 (mittel) — dieselben
 * Schwellen wie oben, nur in der 100er-Darstellung. */
const S_MIN = 2, S_MAX = 5.5;
export function passungsZahl(s) {
  const v = Math.round(((s - S_MIN) / (S_MAX - S_MIN)) * 100);
  return Math.max(0, Math.min(100, v));
}

/* ── Wie viele Stufen hat diese Zahl WIRKLICH? ────────────────────────────────────────
 *
 * `s` wird aus vier Zuschlaegen gebaut und kann nur Vielfache von 0,5 zwischen 2 und 5,5
 * annehmen. `passungsZahl` streckt das auf 0 bis 100 — und damit sieht die Anzeige wie
 * ein Prozentsatz mit hundert Abstufungen aus, waehrend es genau ACHT gibt:
 *
 *     s      2,0  2,5  3,0  3,5  4,0  4,5  5,0  5,5
 *     Zahl     0   14   29   43   57   71   86  100
 *     Stufe    0    1    2    3    4    5    6    7
 *
 * 86 bedeutet: Feldtreffer voll, Region passt, Volumen passt, kein Zielrichtungsbonus.
 * Das ist der Normalfall eines gut passenden Leads — deshalb stand die Zahl am
 * 2026-09-17 bei so vielen Leads, dass sie wie ein Platzhalter wirkte („alle leads haben
 * relevanz 86, kann auch nicht sein oder?"). Die Rechnung war richtig; die DARSTELLUNG
 * hat eine Feinheit behauptet, die es nicht gibt.
 *
 * ⚠ DIE ZAHL BLEIBT — sie sortiert. Der Kopf von `passungsZahl` sagt das seit jeher:
 * „die STUFE bleibt die Aussage; die Zahl dient dem Sortieren und einem Mindestwert."
 * Geaendert wird, was der Nutzer SIEHT, nicht was die Liste rechnet.
 *
 * ⚠ NICHT AUS DER 100er-ZAHL ZURUECKRECHNEN. `Math.round(passung / (100/7))` trifft heute
 * zufaellig richtig, weil die acht Werte gleichmaessig liegen. Aendert jemand einen
 * Zuschlag von 0,5 auf 0,25, stimmt die Ruecktransformation stumm nicht mehr. Die Stufe
 * kommt deshalb direkt aus `s`.
 */
export const PASSUNG_STUFEN = 7;
export function passungsStufe(s) {
  const v = Math.round((s - S_MIN) / 0.5);
  return Math.max(0, Math.min(PASSUNG_STUFEN, v));
}

export function matchLead(lead, p, leadValue) {
  if (!hasProfile(p)) return { relevanz: 'na', passung: null, stufe: null, teile: [], blocker: [], partner: false };

  const teile = [];        // {dim, label, status, text}
  const blocker = [];      // harte Ausschluss-/Warnhinweise
  let partner = false;

  // ── Feld (CPV) — das Kernkriterium, es begrenzt nach oben ──────────────────
  // Gewerkscharf auf CPV-6: exakte CPV-6 = Volltreffer, gleiche CPV-4-Klasse (aber anderes Gewerk,
  // z. B. Aufzug 453131 vs. Elektro 453112) = Nachbarfeld. Alt-Profile ohne cpvFields6 → CPV-4-Verhalten.
  const cpv4 = String(lead.cpv || '').slice(0, 4);
  const cpv6 = String(lead.cpv || '').slice(0, 6);
  const has6 = !!(p.cpvFields6 && p.cpvFields6.length);
  let feld;
  if (has6) {
    if (p.cpvFields6.includes(cpv6)) feld = 'ok';
    else if (p.cpvFields.includes(cpv4) || p.nachbarFields.includes(cpv4)) feld = 'nachbar';
    else feld = 'aussen';
  } else {
    if (p.cpvFields.includes(cpv4)) feld = 'ok';
    else if (p.nachbarFields.includes(cpv4)) feld = 'nachbar';
    else feld = 'aussen';
  }
  teile.push({
    dim: 'feld', label: 'Feld',
    status: feld === 'ok' ? 'ok' : feld === 'nachbar' ? 'teil' : 'no',
    text: feld === 'ok' ? 'euer Schwerpunkt' : feld === 'nachbar' ? 'Nachbarfeld (angrenzendes Gewerk)' : 'außerhalb eurer Felder',
  });

  // ── Region ────────────────────────────────────────────────────────────────
  const nuts = String(lead.marktRegion && lead.nuts || lead.nuts || '');
  const bundSel = p.regions && p.regions.includes('BUND');     // „Bund" = föderaler Käufer (§12)
  const nutsSel = p.regions ? p.regions.filter((r) => r !== 'BUND') : null;
  let region;
  if (lead.is_nationwide === true) region = 'bundesweit';
  else if (!p.regions) region = 'ok';                          // bundesweit tätig
  else if (bundSel && isFederalBuyer(lead.buyer)) region = 'ok';
  else if (nutsSel && nutsSel.length && nutsSel.some((r) => nuts.startsWith(r))) region = 'ok';
  else if (nutsSel && !nutsSel.length && bundSel) region = 'no';   // nur Bund gewählt, kein Bundes-Käufer
  else region = 'no';
  teile.push({
    dim: 'region', label: 'Region',
    status: region === 'no' ? 'no' : 'ok',
    text: region === 'bundesweit' ? 'bundesweit erbringbar' : region === 'ok' ? 'in eurem Gebiet' : 'außerhalb eures Gebiets',
  });

  // ── Volumen (unbekannt schließt NICHT aus) ─────────────────────────────────
  let vol;
  if (leadValue == null) vol = 'unbekannt';
  else if (p.volMin != null && leadValue < p.volMin) vol = 'klein';
  else if (p.volMax != null && leadValue > p.volMax) vol = 'gross';
  else vol = 'ok';
  teile.push({
    dim: 'vol', label: 'Volumen',
    status: vol === 'ok' ? 'ok' : vol === 'unbekannt' ? 'unbekannt' : 'no',
    text: vol === 'ok' ? 'in eurer Spanne' : vol === 'unbekannt' ? 'nicht veröffentlicht' : vol === 'klein' ? 'unter eurer Spanne' : 'über eurer Spanne',
  });

  // ── Ausschlusskriterien (#27 §6.3) — bewusste Abwahl. Unbekanntes schließt NIE aus. ──
  const ex = p.exclusions || {};
  let ausgeschlossen = false;
  const leadCpv = String(lead.cpv || '');
  if (Array.isArray(ex.cpv_aus) && ex.cpv_aus.some((c) => c && leadCpv.startsWith(String(c)))) {
    ausgeschlossen = true;
    blocker.push({ art: 'ausschluss', text: 'gehört zu einer von euch abgewählten Leistungsart.' });
  } else if (Array.isArray(ex.regionen_aus) && ex.regionen_aus.some((r) => r && nuts.startsWith(String(r)))) {
    ausgeschlossen = true;
    blocker.push({ art: 'ausschluss', text: 'liegt in einer von euch ausgeschlossenen Region.' });
  } else if (leadValue != null && ex.wert_max != null && leadValue > ex.wert_max) {
    ausgeschlossen = true;
    blocker.push({ art: 'ausschluss', text: `über eurer Höchstgrenze (${fmtEur(ex.wert_max)}).` });
  } else if (leadValue != null && ex.wert_min != null && leadValue < ex.wert_min) {
    ausgeschlossen = true;
    blocker.push({ art: 'ausschluss', text: `unter eurer Mindestgrenze (${fmtEur(ex.wert_min)}).` });
  }

  // ── Harte K.-o.-Kriterien / Partner-Hinweis ────────────────────────────────
  // Alleinkapazität: großer Auftrag über der Alleingrenze → nur mit Partner (kein Ausschluss).
  // „Keine Bietergemeinschaften" (#27 §6.3) unterdrückt den Partner-Zusatz.
  if (p.maxAlleine != null && leadValue != null && leadValue > p.maxAlleine && !ex.keine_bietergemeinschaft) {
    partner = true;
    blocker.push({ art: 'partner', text: `Auftrag über eurer Alleingrenze (${fmtEur(p.maxAlleine)}), realistisch nur mit Partner.` });
  }
  // Bürgschaft: fordert der Lead eine Bürgschaft und sprengt sie euren Rahmen?
  const fordertBuerg = leadFordertBuergschaft(lead);
  if (fordertBuerg && p.buergschaft != null && leadValue != null && leadValue * BUERG_QUOTE > p.buergschaft) {
    blocker.push({ art: 'buergschaft', text: `Geforderte Bürgschaft (~${fmtEur(leadValue * BUERG_QUOTE)}) übersteigt euren Rahmen (${fmtEur(p.buergschaft)}).` });
  } else if (fordertBuerg && p.buergschaft == null) {
    blocker.push({ art: 'buergschaft_offen', text: 'fordert eine Bürgschaft. Hinterlegt euren Rahmen, dann prüfen wir das.' });
  }

  /* Verpflichtender Ortstermin ausserhalb eures Gebiets.
   *
   * Ein Pflichttermin ist eine Zulassungsbedingung: wer nicht erscheint, darf nicht bieten.
   * Innerhalb des eigenen Gebiets ist das ein Vormittag und keine Meldung wert; weit
   * ausserhalb kippt es die Rechnung, und zwar BEVOR man die Unterlagen liest.
   *
   * ⚠ KEIN AUSSCHLUSS, sondern ein Hinweis wie der Partner-Fall. Man KANN hinfahren, und
   * bei einem grossen Auftrag lohnt es sich. Die Relevanz zu nullen hiesse, dem Nutzer die
   * Entscheidung abzunehmen, die ihm gehoert. Deshalb `art: 'ortstermin'` und kein
   * `hartBlock`.
   *
   * ⚠ DREIWERTIG GELESEN. `ortsterminPflicht` ist nur gesetzt, wenn ueberhaupt ein Termin
   * erkannt wurde; `null` heisst „die Unterlagen sagen nichts", nicht „kein Termin". Aus
   * einer fehlenden Angabe darf keine Entwarnung werden.
   *
   * Gemessen am 2026-09-01: 3.723 Vorgaenge mit erkanntem Ortstermin, davon 108
   * verpflichtend. Der Fall ist selten — und genau deshalb faellt er im Alltag durch, bis
   * jemand vor der Absage steht. */
  if (lead.anf && lead.anf.ortsterminPflicht === true && region === 'no') {
    blocker.push({ art: 'ortstermin',
      text: 'verlangt einen verpflichtenden Ortstermin außerhalb eures Gebiets. Ohne Teilnahme kein Angebot.' });
  }

  // ── Relevanz-Stufe + Passungszahl ──────────────────────────────────────────
  const hartBlock = blocker.some((b) => b.art === 'buergschaft');
  let relevanz, passung, stufe;
  if (ausgeschlossen) { relevanz = 'niedrig'; passung = 0; stufe = 0; }   // #27 §6.3: Ausschluss → aus der Relevanz
  else if (feld === 'aussen') { relevanz = 'niedrig'; passung = 0; stufe = 0; }
  else if (hartBlock) { relevanz = 'niedrig'; passung = 0; stufe = 0; }
  else {
    let s = 2;                                  // Feldtreffer ist die Basis
    if (feld === 'ok') s++;                      // voller Feldtreffer statt Nachbar
    if (region === 'ok' || region === 'bundesweit') s++;
    if (vol === 'ok') s++; else if (vol === 'unbekannt') s += 0.5;   // unbekannt: halber Kredit
    // Zielrichtung (#27 §6.2): Bestand gewichtet Bekanntes hoch, Expansion gibt Nachbarfeldern Kredit.
    if (p.zielrichtung === 'bestand' && p.cpvWins && p.cpvWins[cpv4]) s += 0.5;
    else if (p.zielrichtung === 'expandieren' && feld === 'nachbar') s += 0.5;
    relevanz = s >= 4.5 ? 'hoch' : s >= 3 ? 'mittel' : 'niedrig';
    passung = passungsZahl(s);
    stufe = passungsStufe(s);
  }

  return { relevanz, passung, stufe, teile, blocker, partner };
}

/* Kompakte HTML-Zeile „Feld ✓ · Region ✓ · Volumen unbekannt" — kompatibel zum
 * bestehenden relWhy-Feld der Demo-Leads. */
export function whyHtml(match) {
  if (!match || !match.teile.length) return '';
  const mark = { ok: '<span class="ok">✓</span>', teil: '<span class="no">teilweise</span>',
                 no: '<span class="no">✗</span>', unbekannt: 'unbekannt' };
  return match.teile.map((t) => `${t.label} ${mark[t.status] || ''}`).join(' · ');
}

/* Föderaler Käufer (Ticket #2 §12: „Bund" über Käufer-Typ, nicht NUTS). Namens-Heuristik,
 * weil buyer_type nicht im Web-Export liegt — Bundesstellen sind am Namen erkennbar. */
const FEDERAL_RE = /\bbundes(republik|ministerium|amt|anstalt|wehr|agentur|netzagentur|druckerei|kartellamt|rechnungshof|bank|polizei|kriminalamt|nachrichtendienst|zentrale)/i;
const FEDERAL_EXTRA = /\bBWI\b|\bITZBund\b|\bBAAINBw\b|Auswärtige[sn]? Amt|Deutsche[r]? Bundestag|Bundesrepublik Deutschland|Beschaffungsamt|Zoll\b|Generalzolldirektion/i;
export function isFederalBuyer(name) {
  const n = String(name || '');
  return FEDERAL_RE.test(n) || FEDERAL_EXTRA.test(n);
}

function leadFordertBuergschaft(lead) {
  const a = lead.aufwand;
  if (a && a.buergschaft && /^ja/i.test(String(a.buergschaft))) return true;
  if (lead.bgForm) return true;                 // aus dem Export gesetztes Bürgschafts-Signal
  return false;
}

function fmtEur(v) {
  if (v == null) return '—';
  if (v >= 1e6) return (v / 1e6).toFixed(1).replace('.', ',') + ' Mio €';
  return Math.round(v).toLocaleString('de-DE') + ' €';
}
