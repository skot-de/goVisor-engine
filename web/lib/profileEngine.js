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
    nachbarFields: [],        // angrenzende Felder (teil-relevant, kein Volltreffer)
    regions: null,           // Array NUTS-Präfixe; null = bundesweit tätig
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
  p.nachbarFields = input.nachbarFields || [];
  p.regions = (input.regions && input.regions.length) ? input.regions : null;   // leer = bundesweit
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
export function matchLead(lead, p, leadValue) {
  if (!hasProfile(p)) return { relevanz: 'na', teile: [], blocker: [], partner: false };

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
    blocker.push({ art: 'partner', text: `Auftrag über eurer Alleingrenze (${fmtEur(p.maxAlleine)}) — realistisch nur mit Partner.` });
  }
  // Bürgschaft: fordert der Lead eine Bürgschaft und sprengt sie euren Rahmen?
  const fordertBuerg = leadFordertBuergschaft(lead);
  if (fordertBuerg && p.buergschaft != null && leadValue != null && leadValue * BUERG_QUOTE > p.buergschaft) {
    blocker.push({ art: 'buergschaft', text: `Geforderte Bürgschaft (~${fmtEur(leadValue * BUERG_QUOTE)}) übersteigt euren Rahmen (${fmtEur(p.buergschaft)}).` });
  } else if (fordertBuerg && p.buergschaft == null) {
    blocker.push({ art: 'buergschaft_offen', text: 'fordert eine Bürgschaft — hinterlegt euren Rahmen, dann prüfen wir das.' });
  }

  // ── Relevanz-Stufe ──────────────────────────────────────────────────────────
  const hartBlock = blocker.some((b) => b.art === 'buergschaft');
  let relevanz;
  if (ausgeschlossen) relevanz = 'niedrig';       // #27 §6.3: Ausschluss → aus der Relevanz
  else if (feld === 'aussen') relevanz = 'niedrig';
  else if (hartBlock) relevanz = 'niedrig';
  else {
    let s = 2;                                  // Feldtreffer ist die Basis
    if (feld === 'ok') s++;                      // voller Feldtreffer statt Nachbar
    if (region === 'ok' || region === 'bundesweit') s++;
    if (vol === 'ok') s++; else if (vol === 'unbekannt') s += 0.5;   // unbekannt: halber Kredit
    // Zielrichtung (#27 §6.2): Bestand gewichtet Bekanntes hoch, Expansion gibt Nachbarfeldern Kredit.
    if (p.zielrichtung === 'bestand' && p.cpvWins && p.cpvWins[cpv4]) s += 0.5;
    else if (p.zielrichtung === 'expandieren' && feld === 'nachbar') s += 0.5;
    relevanz = s >= 4.5 ? 'hoch' : s >= 3 ? 'mittel' : 'niedrig';
  }

  return { relevanz, teile, blocker, partner };
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
