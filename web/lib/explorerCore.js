/* Oberflaechensprache: `tk` ist die React-freie Fassung von `t` (s. lib/i18n).
 * Die Renderer hier sind Prototyp-verbatim und laufen ausserhalb jedes React-
 * Kontexts; der Provider schiebt die gewaehlte Sprache per `setzeKernSprache`
 * ins Modul. Der deutsche Satz IST der Schluessel — fehlt eine Uebersetzung,
 * steht schlicht wieder Deutsch da. */
import { tk, aktuelleSprache } from "./i18n";

/* eslint-disable */
import { emptyProfile, matchLead, whyHtml, hasProfile } from './profileEngine';
import { recommend, begruendungskette } from './recommendation';
import { applyLabels } from './labels';
import { dichte } from './dichte';
/**
 * goVisor Explorer — Kern-Logik & Demo-Daten, VERBATIM aus dem Prototyp
 * govisor-explorer-v4.4.html. Reine Funktionen (String-/Datenrückgabe, keine
 * DOM-Manipulation) und der Seed-Datensatz. Nur die Render-Schicht (renderHead/
 * renderTable/renderDetail …) wird als React neu gebaut — diese Logik bleibt die
 * einzige Wahrheit für Formatierung, Filter, Sortierung.
 *
 * ⚠️ Übergabenotiz §9: Demo-Umschalter (Beispiel-Käufer, Kontostatus, Blur mit
 * echten Werten) sind Prototyp-Behelfe. Werte werden in der Umsetzung serverseitig
 * zurückgehalten; dieser Seed ist nur zum Aufbau der UI.
 */

/* ── Eigene Firma + Match-Güte (aus Onboarding) ── */
const MEINE_FIRMA = 'Nordwand IT-Systeme GmbH';
let firmaMatch = 'hr';
// Account-Status (Übergabenotiz §9: kein Demo-DOM-Flag mehr, echter Zustand).
// true = Free/limitiert. React schiebt ihn über applyState({accountLimit}) herein.
let accountLimit = false;
const isFreeLimit = () => accountLimit;

/* ── Datenmodell — die Demo-Leads (Prototyp-Seed) ── */
/* ── Datenmodell — Leads kommen aus `web/data/leads-<branche>.json` ── */
// Hier stand ein Prototyp-Seed: 12 erfundene Ausschreibungen mit erfundenen Firmen
// („Kessler Kälte & Klima GmbH"), erfundenen Kontakten und erfundenen Kennzahlen.
// Er ist raus, weil er GENAU DAS verdeckt hat, was man sehen will: wo die echten Daten
// Lücken haben. Ein leeres Feld ist eine Aussage, ein erfundenes Feld ist eine Lüge.
// `setLeads()` befüllt das Array beim Laden — deshalb `const` mit Array, nicht `let`.
/** @type {any[]} */   // ohne Annotation verliert TS beim leeren Literal den Elementtyp
const LEADS = [];

/* ── Mutabler Zustand (Defaults; React verwaltet ihn später) ── */
let activeId = null, activeTab = 'uebersicht';
let filters = {ungesichtet:false, gemerkt:false, kandidaten:false, netz:false};
let editBestand = false;
let offeneGruppen = new Set();   // welche Begriffs-Gruppen sind ausgeklappt   // Bestand kuratieren: + / − direkt in der Liste
let searchTokens = [];   // [{type, value, label, radius?}]
let openFacet = null;    // 'phase' | 'leistung' | 'region' | null
let openRadius = null;   // Index des Ort-Tokens, dessen Radius-Menü offen ist

/* ── Referenz-Maps + reine Formatierer + Filter-Helfer ── */
const RAHMEN_NACHWEIS = {
  vob:   {n:"Präqualifikation Bau (PQ-VOB)", x:"VOB/A verlangt in der Regel den Eintrag im Präqualifikationsverzeichnis oder Einzelnachweise je Angebot."},
  vgv:   {n:'Eignungsnachweise nach VgV',    x:"VgV lässt die Einheitliche Europäische Eigenerklärung zu. Nachweise erst auf Verlangen."},
  uvgo:  {n:"Präqualifikation IT",           x:"Viele Stellen erkennen bei UVgO Präqualifikationsverzeichnisse an und verzichten dann auf Einzelnachweise."},
  sektvo:{n:'Eignungsnachweise nach SektVO', x:"Sektorenauftraggeber führen häufig eigene Prüfsysteme mit Voranmeldung."},
};

const RAHMEN = {
  vgv:   {kurz:'VgV',    lang:'Vergabeverordnung',        x:"Liefer- und Dienstleistungen oberhalb der EU-Schwelle"},
  vob:   {kurz:'VOB/A',  lang:"Vergabe- und Vertragsordnung für Bauleistungen", x:'Bauleistungen'},
  uvgo:  {kurz:'UVgO',   lang:'Unterschwellenvergabeordnung', x:"unterhalb der EU-Schwellenwerte"},
  sektvo:{kurz:'SektVO', lang:'Sektorenverordnung',       x:'Verkehr, Energie, Wasser'},
};

/* Angebotsaufwand: was es kostet mitzubieten — die Achse, die neben Relevanz und Chance fehlte.
   Bewusst grob: drei Stufen, und bei zu dünner Datenlage gar keine. */
function aufwandStufe(l){
  const t = [];
  let punkte = 0, bekannt = 0;
  const a = l.aufwand;
  if(a){
    // Demo-Pfad: handkuriertes aufwand-Objekt der Prototyp-Leads.
    if(a.buergschaft!=null){ bekannt++; if(a.buergschaft!=='nein'){ punkte+=2; t.push(tk("Bietungsbürgschaft")); } }
    if(a.bindefrist!=null){ bekannt++; const d=parseInt(a.bindefrist,10);
      if(d>=90){ punkte+=2; t.push(tk('lange Bindefrist')); } else if(d>=60){ punkte+=1; t.push(tk('Bindefrist {d}', {d: a.bindefrist})); } }
    if(a.eabgabe!=null){ bekannt++; if(a.eabgabe==='Pflicht'){ punkte+=1; t.push(tk('Portalregistrierung')); } }
    if(a.lebenslauf!=null){ bekannt++; if(a.lebenslauf==='ja'){ punkte+=2; t.push(tk("Lebensläufe gefordert")); } }
  } else if(l.anf){
    // #18 Aufwands-Indikator: aus echten strukturierten Anforderungen (#15) + Zuschlagskriterien.
    // Fehlende Signale zählen NICHT als „gering", sondern bleiben unbekannt (bekannt-Zähler).
    const anf = l.anf;
    if(anf.buergschaft!=null){ bekannt++; if(anf.buergschaft===true){ punkte+=2; t.push(tk("Sicherheit/Bürgschaft gefordert")); } }
    if(anf.eignung && anf.eignung.length){ bekannt++; punkte+=Math.min(3, anf.eignung.length);
      t.push(tk(anf.eignung.length>1 ? '{n} Eignungsnachweise' : '{n} Eignungsnachweis', {n: anf.eignung.length})); }
    if(anf.bindefristTage!=null){ bekannt++;
      if(anf.bindefristTage>=90){ punkte+=2; t.push(tk('lange Bindefrist ({n} Tage)', {n: anf.bindefristTage})); }
      else if(anf.bindefristTage>=60){ punkte+=1; t.push('Bindefrist '+anf.bindefristTage+' Tage'); } }
    if(anf.nebenangebote!=null){ bekannt++; if(anf.nebenangebote===true){ punkte+=1; t.push(tk('Nebenangebote zugelassen')); } }
    if(anf.zertifikate && anf.zertifikate.length){ punkte+=1; t.push(anf.zertifikate.slice(0,2).join(', ')); }
    const nk = (l.zuschlag||[]).length; if(nk){ bekannt++; if(nk>=3){ punkte+=1; t.push(tk('{n} Zuschlagskriterien', {n: nk})); } }
    if(l.rahmen==='vob'){ bekannt++; punkte+=1; t.push(tk("Präqualifikation (VOB)")); }
  } else return {stufe:'na', bekannt:0, treiber:[]};
  if(bekannt<2) return {stufe:'na', bekannt, treiber:t};
  return {stufe: punkte>=4?'hoch' : punkte>=2?'mittel' : 'niedrig', bekannt, treiber:t};
}

/* #19 Bid/No-Bid — führt die vier vorhandenen Analysen zu EINER Einordnung zusammen:
   Chance (Relevanz + Incumbent-Angreifbarkeit) × Aufwand (#18), mit K.o.-Vorschaltung
   der Eignung (#15). Ordnet ein, entscheidet nicht — jeder Faktor bleibt nachvollziehbar. */
function bidNoBid(l){
  const m = l.match;
  // Aufwand + Eignung + Angreifbarkeit sind INTRINSISCH (kein Profil nötig) — immer berechnen.
  const auf = aufwandStufe(l);
  const aufDots = {niedrig:1, mittel:2, hoch:3, na:0}[auf.stufe] || 0;
  const aufGering = auf.stufe==='niedrig';                  // na = unbekannt, nicht „gering"
  const hartBlock = m && m.blocker ? m.blocker.find(b=>b.art==='buergschaft') : null;
  const eignungOk = !hartBlock;
  if(!m || m.relevanz==='na'){
    // Ohne Profil: Aufwand + Angreifbarkeit zeigen; nur die Passung (Chance) braucht das Profil.
    const wDots = {hoch:3, mittel:2, niedrig:1}[l.wechsel] || 0;
    return {noProfile:true, chanceDots:wDots,
            chance: (l.wechsel && l.wechsel!=='na') ? 'Amtsinhaber '+l.wechsel+' angreifbar' : 'Profil einrichten',
            aufDots, aufwand:auf.stufe, aufTreiber:auf.treiber, eignungOk, hartBlock,
            einordnung:{t:tk("Profil hinterlegen für die Chance"), cls:'weigh',
                        x:tk("Aufwand und Angreifbarkeit des Amtsinhabers seht ihr schon jetzt, für die Passung zu eurem Betrieb euer Profil einrichten.")}};
  }
  const relScore = {hoch:3, mittel:2, niedrig:1}[m.relevanz] || 0;
  const wScore = {hoch:1, mittel:0.6, niedrig:0.2}[l.wechsel] || 0.4;   // Angreifbarkeit
  const chanceDots = Math.max(1, Math.min(4, Math.round(relScore + wScore)));
  const chanceHoch = m.relevanz==='hoch';
  let einordnung;
  if(!eignungOk)                     einordnung = {t:'K.o.', x:'ohne diese Voraussetzung chancenlos.', cls:'ko'};
  else if(chanceHoch && aufGering)   einordnung = {t:'Klarer Fall', x:tk("hohe Chance bei überschaubarem Aufwand, bieten."), cls:'go'};
  else if(chanceHoch && !aufGering)  einordnung = {t:tk("Abwägen"), x:tk("gute Chance, aber spürbarer Aufwand, lohnt sich der Einsatz?"), cls:'weigh'};
  else if(!chanceHoch && aufGering)  einordnung = {t:'Mitnahme', x:tk("begrenzte Chance, aber wenig Aufwand, wenn Kapazität frei ist."), cls:'take'};
  else                               einordnung = {t:'Meiden', x:tk("begrenzte Chance bei hohem Aufwand. Kapazität besser anderswo."), cls:'skip'};
  return {chanceDots, chance:m.relevanz, aufDots, aufwand:auf.stufe, aufTreiber:auf.treiber,
          eignungOk, hartBlock, einordnung};
}
function dots(n){ let s=''; for(let i=0;i<4;i++) s += i<n?'●':'○'; return s; }

/* Ticket 22 — Empfehlung: ein Handlungs-Urteil (antreten/überspringen/offen) als dünne
 * Ableitung über Relevanz + Chance (Verdrängbarkeit). Kein neues Modell. Prinzip: lieber
 * „offen" als ein falsches Urteil. Schwellen zentral, Gründe aus festem Katalog (nicht generativ).
 * Aufwand fließt NICHT als Auslöser eines „überspringen" ein (Freitext-Aufwand = V2). */
const EMPF_SCHWELLEN = { relHi:'hoch', relLo:'niedrig', chanceHi:'hoch', chanceLo:'niedrig' };
const EMPF_GRUND = {
  kein_profil:  "Ohne geschärftes Profil keine Relevanz. Urteil nicht möglich.",
  keine_chance: "Erstvergabe. Kein Amtsinhaber, keine Vorgängerdaten für die Chance.",
  offene_gebote:"Läuft noch, keine Gebotsgrundlage für ein Wettbewerbs-Urteil.",
  fit_offen:    "Hohe Passung, Wettbewerb offen, hier lohnt der Einsatz.",
  fit_angreif:  'Hohe Passung, Amtsinhaber angreifbar.',
  rel_niedrig:  "Passt nur halb. Relevanz niedrig.",
  incumbent:    "Amtsinhaber sitzt fest, geringe Verdrängbarkeit.",
  grenzfall:    "Grenzfall. Relevanz und Chance mittel, kein klares Urteil.",
};
const EMPF = {
  antreten:     { t:'Antreten',     cls:'empf-go'   },
  ueberspringen:{ t:"Überspringen", cls:'empf-skip' },
  offen:        { t:'Offen',        cls:'empf-open' },
};
function empfehlung(l){
  const m = l.match;
  const rel = m ? m.relevanz : 'na';          // Relevanz braucht ein Profil
  const chance = l.wechsel;                    // Verdrängbarkeit: hoch/mittel/niedrig/na
  // „offen" ist vollwertig, kein Fehler — immer, wenn ein Eingang für ein Urteil fehlt.
  if(rel === 'na')                    return { v:'offen', code:'kein_profil' };
  if(l.src === 'f01')                 return { v:'offen', code:'keine_chance' };   // Ankündigung
  if(chance == null || chance === 'na')
    return { v:'offen', code: l.neu ? 'keine_chance' : 'offene_gebote' };
  // Antreten: hohe Relevanz UND gute Chance (beide 🟢-Eingänge)
  if(rel === EMPF_SCHWELLEN.relHi && (chance === 'hoch' || chance === 'mittel'))
    return { v:'antreten', code: chance === 'hoch' ? 'fit_angreif' : 'fit_offen' };
  // Überspringen: belegtes Negativ — niedrige Relevanz ODER fester Amtsinhaber.
  if(rel === EMPF_SCHWELLEN.relLo)    return { v:'ueberspringen', code:'rel_niedrig' };
  if(chance === EMPF_SCHWELLEN.chanceLo) return { v:'ueberspringen', code:'incumbent' };
  // Sonst: Graubereich → offen (ehrlicher als ein weiches Urteil).
  return { v:'offen', code:'grenzfall' };
}

/* #26 für die Liste — eine Zelle, zwei Inhalte: Handlungsempfehlung (Kaskade B) wenn verfügbar,
 * sonst Einordnung (Kaskade A). Farbklasse rec-go/def/open/skip, kurzer Grund. */
const REC_CLS = { gruen:'go', blau:'def', neutral:'open', gedaempft:'skip' };
// Aussagestärke für die Sortierung (§4.1): Bewerben/Hohe Passung zuerst, Nicht bewerben zuletzt.
const REC_RANK = { 'Bewerben':0, 'Hohe Passung':0, 'Verteidigen':1, 'Bestandsvertrag':1,
  "Noch zu klären":2, 'Passung mittel':2, 'Geringe Passung':3, 'Frist zu knapp':3, 'Nicht bewerben':3 };
function recForList(l){
  const r = recommend(l, userProfile, { ownBuyers: userContracts.map(c=>c.buyer_name).filter(Boolean) });
  const src = r.empfehlung || r.einordnung;
  const grund = (src.gruende && src.gruende.length) ? src.gruende[0]
    : (src.frage || (r.gesperrt==='keine_unterlagen' ? tk("Für eine Empfehlung fehlen die Vergabeunterlagen.")
      : r.gesperrt==='kaltstart' ? 'Profil-Mindestabdeckung fehlt.' : ''));
  return { label: src.label, cls: REC_CLS[src.cls] || 'open', grund, rank: REC_RANK[src.label] ?? 2 };
}

const BRANCHEN = {
  it:        'IT & Software',
  bau:       'Bau & Infrastruktur',
  medizin:   'Medizin & Gesundheit',
  beratung:  'Beratung & Dienstleistung',
  sicherheit:'Sicherheit & Verteidigung',
  energie:   'Energie & Versorgung',
  // Leads, deren Quelle keinen CPV-Code führt (NetServer-Trefferlisten, Teile von DÖE).
  // Seit die CPV-Pflicht aus dem Lead-Bau raus ist, sind sie im Bestand statt verworfen —
  // 306 laufende Ausschreibungen, die vorher lautlos fehlten.
  //
  // ⚠ ABSICHTLICH NUR HIER. In `app/settings` und `app/onboarding` steht dieselbe Liste,
  // dort aber als AUSWAHL der eigenen Branche — und niemandes Geschäft ist „ohne
  // Kategorie". Der Grundraum ist ein Anzeigefach für Vergaben, kein Gewerk.
  ohne:      'Ohne Kategorie',
};
let profilBranche = 'it';      // aus dem Profil abgeleitet
let aktiveBranche = 'it';      // ggf. temporär gewechselt (Ausbruch)
let wsOpen = false;

const FACETS = {
  rahmen:{label:'Rechtsrahmen', opts:Object.entries(RAHMEN).map(([k,v])=>({v:k, l:v.kurz+' — '+v.x}))},
  phase:   { label:'Phase', opts:[
    {v:'auslauf',l:'Vertragsende'},{v:'f02',l:'Ausschreibung offen'},{v:'f01',l:"Ankündigung"},
    {v:'award',l:'Zuschlag erteilt'}], match:(l,v)=>l.src===v },
  leistung:{ label:'Leistung', opts:[
    {v:'dienst',l:'Dienstleistung'},{v:'liefer',l:'Lieferung'},{v:'bau',l:'Bauleistung'}], match:(l,v)=>l.naturKat===v },
};
// Land-Codes → Anzeigename (Detail-Eckdaten + Filter-Panel). DACH-Fundament: aktuell trägt
// nur DE Daten, AT/CH sind im Filter vorbereitet und greifen, sobald ihre Pipelines andocken.
const LAND_LABEL = {DE:'Deutschland', AT:"Österreich", CH:'Schweiz'};

// Ort→Region (Demo). Echt: NUTS-Geokodierung.
// Region-Filter über echte NUTS1-Präfixe (Leistungsort/Käufersitz der Leads).
// matchToken('ort') prüft l.nuts.startsWith(region) — Bundesland-genau über den ganzen Bestand.
const ORTE = {
  'baden-württemberg':{region:'DE1',label:"Baden-Württemberg"},'bawü':{region:'DE1',label:"Baden-Württemberg"},
  'bayern':{region:'DE2',label:'Bayern'},'berlin':{region:'DE3',label:'Berlin'},
  'brandenburg':{region:'DE4',label:'Brandenburg'},'bremen':{region:'DE5',label:'Bremen'},
  'hamburg':{region:'DE6',label:'Hamburg'},'hessen':{region:'DE7',label:'Hessen'},
  'mecklenburg-vorpommern':{region:'DE8',label:'Mecklenburg-Vorpommern'},'mv':{region:'DE8',label:'Mecklenburg-Vorpommern'},
  'niedersachsen':{region:'DE9',label:'Niedersachsen'},
  'nordrhein-westfalen':{region:'DEA',label:'Nordrhein-Westfalen'},'nrw':{region:'DEA',label:'Nordrhein-Westfalen'},
  'rheinland-pfalz':{region:'DEB',label:'Rheinland-Pfalz'},'rlp':{region:'DEB',label:'Rheinland-Pfalz'},
  'saarland':{region:'DEC',label:'Saarland'},'sachsen':{region:'DED',label:'Sachsen'},
  'sachsen-anhalt':{region:'DEE',label:'Sachsen-Anhalt'},
  'schleswig-holstein':{region:'DEF',label:'Schleswig-Holstein'},'sh':{region:'DEF',label:'Schleswig-Holstein'},
  'thüringen':{region:'DEG',label:"Thüringen"},'thueringen':{region:'DEG',label:"Thüringen"},
};
// PLZ-Erststelle → NUTS1 (grob; NUR Fallback für 2–4-stellige Eingaben, wenn keine echte
// Koordinate vorliegt). Nicht kreisscharf.
const PLZ = {'0':'DED','1':'DE3','2':'DE9','3':'DE9','4':'DEA','5':'DEA','6':'DE7','7':'DE1','8':'DE2','9':'DE2'};

// PLZ→[lat, lon, ort], country-verschachtelt {DE:{plz:…}, CH:{…}, AT:{…}} (via /api/plz-geo,
// einmal geladen). Basis der ECHTEN Umkreissuche. AT und CH sind BEIDE 4-stellig und
// kollidieren (1010 = Wien/Lausanne) → 4-stellige PLZ werden über den aktiven Länderfilter
// (PLZ_LAND) aufgelöst, sonst CH bevorzugt (live), dann AT.
let PLZ_GEO = {};
let PLZ_LAND = '';   // aktiver DACH-Länderfilter (ein einzelnes Land) für die 4-stellige Auflösung
function setPlzGeo(d){ PLZ_GEO = d || {}; }
function setPlzLand(l){ PLZ_LAND = l || ''; }
// PLZ → [lat, lon, ort] mit Länder-Disambiguierung. 5-stellig = DE eindeutig; 4-stellig = CH/AT.
function plzLookup(q){
  if(/^\d{5}$/.test(q)) return (PLZ_GEO.DE || {})[q] || null;
  if(/^\d{4}$/.test(q)){
    const pref = (PLZ_LAND === 'CH' || PLZ_LAND === 'AT') ? PLZ_LAND : null;
    if(pref && (PLZ_GEO[pref] || {})[q]) return PLZ_GEO[pref][q];
    return (PLZ_GEO.CH || {})[q] || (PLZ_GEO.AT || {})[q] || null;   // CH zuerst (live)
  }
  return null;
}
// Großkreis-Distanz in km (Haversine). Für den PLZ-Umkreisfilter.
function haversine(la1, lo1, la2, lo2){
  const R = 6371, r = x => x * Math.PI / 180;
  const dLa = r(la2 - la1), dLo = r(lo2 - lo1);
  const a = Math.sin(dLa/2)**2 + Math.cos(r(la1)) * Math.cos(r(la2)) * Math.sin(dLo/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
// Erreichbare Regionen je Umkreis (Demo)
const PLACE_RADIUS = {
  'DE21':{25:['DE21'],50:['DE21','DE27'],100:['DE21','DE27','DE22','DE23','DE25']},
  'DE6' :{25:['DE6'],50:['DE6'],100:['DE6','DE9']},
  'DEA2':{25:['DEA2'],50:['DEA2','DEA1'],100:['DEA']},
  'DE25':{25:['DE25'],50:['DE25','DE21'],100:['DE25','DE21','DE24']},
};

// Volltext-Basis der Suche: Titel + Käufer + Leistung + Beschreibung + Stichworte.
// Beschreibung ist bei echten Leads der eigentliche Inhalt (Titel oft nur ein Zweizeiler),
// deshalb mitgesucht — findet Begriffe, die nur im Beschreibungstext stehen.
const leadText = l => (l.titel+' '+l.buyer+' '+l.buyerShort+' '+l.natur+' '+(l.beschreibung||'')+' '+(l.kw||[]).map(k=>k.w).join(' ')).toLowerCase();

function matchToken(l,t){
  if(t.type==='ort'){
    if(t.coord){                                    // volle PLZ → echter km-Radius (Haversine)
      if(l.lat==null || l.lon==null) return false;  // ohne Koordinate kein Umkreis-Treffer
      return haversine(t.coord[0], t.coord[1], l.lat, l.lon) <= (t.radius || 25);
    }
    const reach = (t.radius && PLACE_RADIUS[t.value]?.[t.radius]) || [t.value];
    return reach.some(code => (l.nuts||'').startsWith(code));
  }
  if(t.type==='phase')    return l.src===t.value;
  if(t.type==='leistung') return l.naturKat===t.value;
  if(t.type==='rahmen')   return l.rahmen===t.value;
  if(t.type==='cpv')      return String(l.cpv).startsWith(t.value);
  if(t.type==='buyer')    return l.buyerShort===t.value;
  return leadText(l).includes(t.value); // text
}

/* Wo wurde ein Suchwort gefunden? Ohne diesen Beleg wirken Volltext-Treffer wie Fehler. */
function fundstelle(l, wort){
  const w = wort.toLowerCase();
  if((l.titel||'').toLowerCase().includes(w)) return {ort:'Titel', text:null};
  if((l.natur||'').toLowerCase().includes(w) || (cpvLabel(l)||'').toLowerCase().includes(w))
    return {ort:'Leistungsart', text:null};
  if(l.lose){
    const los = l.lose.find(x=>(x.titel||'').toLowerCase().includes(w));
    if(los) return {ort:`Los ${los.nr}`, text:los.titel};
  }
  const be = l.beschreibung||'';
  const i = be.toLowerCase().indexOf(w);
  if(i>=0){
    const von = Math.max(0, be.lastIndexOf(' ', i-45));
    const bis = Math.min(be.length, be.indexOf(' ', i+w.length+45));
    return {ort:'Beschreibung', text:(von>0?'… ':'')+be.slice(von, bis<0?be.length:bis).trim()+' …'};
  }
  if((l.buyer||'').toLowerCase().includes(w)) return {ort:'Auftraggeber', text:null};
  return null;
}
function hervorheben(text, wort){
  const e = esc(text);                 // erst escapen (Datenwert), dann highlighten
  if(!wort) return e;
  const re = new RegExp('('+esc(wort).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig');
  return e.replace(re,'<mark>$1</mark>');
}

function hasToken(type,value){ return searchTokens.some(t=>t.type===type && t.value===value); }
function toggleToken(tok){
  const i = searchTokens.findIndex(t=>t.type===tok.type && t.value===tok.value);
  if(i>=0) searchTokens.splice(i,1); else searchTokens.push(tok);
  syncLocationColumn();
}

function classifyQuery(raw){
  const q = raw.trim().toLowerCase(); if(!q) return null;
  if(ORTE[q]) return {type:'ort',label:ORTE[q].label,value:ORTE[q].region};
  // Exakter Stadtname → Umkreis-Token (Enter ohne Vorschlagswahl).
  const _c = PLZ_GEO._cities && PLZ_GEO._cities.DE && PLZ_GEO._cities.DE[q];
  if(_c) return {type:'ort', value:'city:'+q, coord:[_c[0], _c[1]], radius:25, label:_c[2]};
  if(/^\d{4,5}$/.test(q)){                   // volle PLZ (DE 5-, CH/AT 4-stellig) → echte Umkreissuche
    const g = plzLookup(q);
    if(g) return {type:'ort', value:q, coord:[g[0], g[1]], radius:25,
                  label:'PLZ '+q+(g[2] ? ' '+g[2] : '')};
  }
  // 2–4-stellig (oder PLZ ohne Koordinate): grobe NUTS1-Region als ehrlicher Fallback.
  if(/^\d{2,5}$/.test(q) && PLZ[q[0]]) return {type:'ort',label:'PLZ '+q+' (Region)',value:PLZ[q[0]]};
  return {type:'text',label:'„'+raw.trim()+'"',value:q};
}
let sortKey = 'frist', sortDir = 1;

const SRC_TEXT = {
  echt:"Gemessen · aus der Bekanntmachung",
  schaetz:"Geschätzt · abgeleitet, nicht veröffentlicht",
  unsicher:"Unsicher · Datenlage widersprüchlich",
  unbekannt:"Unbekannt · nicht veröffentlicht",
  na:'Nicht anwendbar'
};
// XSS-Schutz: alle DATENWERTE (Titel, Käufer, Beschreibung, Extras … aus externen Quellen wie
// TED/simap) werden über dangerouslySetInnerHTML gerendert → vor dem Einsetzen HTML-escapen.
// Nur auf Datenwerte anwenden, NICHT auf selbst erzeugtes Markup.
/* CPV-Bezeichnung in der Oberflaechensprache. Die Uebersetzungen stammen aus derselben
 * amtlichen EU-Codeliste wie das deutsche Label (s. `gold.build_dim_cpv_label`) — sie
 * gehen NICHT durch den Sprachkatalog: 9.454 Rechtsbegriffe sind keine UI-Texte, und
 * geraten waere schlechter als amtlich („Bauarbeiten" heisst „Construction work", nicht
 * „Building work"). Fehlt die Fassung (11 % Legacy-CPV-2003), bleibt Deutsch stehen. */
/* „in 3 Mon." — der Exporter liefert die ZAHL (`endetMonate`), den Satz bauen wir hier.
 * Vorformuliert waere er nicht uebersetzbar, ohne fuer jede Monatszahl einen eigenen
 * Katalogeintrag anzulegen. `endet` bleibt Rueckfallebene fuer aeltere Exporte. */
const endetText = l => (l && l.endetMonate != null) ? tk('in {n} Mon.', {n: l.endetMonate}) : (l && l.endet) || '';

const cpvLabel = l => {
  if (!l) return '';
  const sp = aktuelleSprache();
  return (sp === 'en' && l.cpvLabelEn) || (sp === 'fr' && l.cpvLabelFr) || l.cpvLabel || '';
};

const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const val = (text, src, hint) =>
  `<span class="val" data-src="${src}" title="${esc(tk(SRC_TEXT[src]) + (hint ? ' — ' + tk(hint) : ''))}">${esc(text)}</span>`;

const bandMeter = (level, risk, cap, naTitle) => {
  // naTitle erklärt bei „n/a" die URSACHE (fehlende Angaben), statt den Nutzer raten zu lassen.
  const t = (level==='na' && naTitle) ? ` title="${esc(naTitle)}"`
          : cap ? ` title="${esc(cap)}: ${level==='na'?'n/a':level}"` : '';
  return level==='na'
    ? `<span class="band" data-level="na"${t}><span class="segs"><i></i><i></i><i></i></span><span class="lbl">n/a</span></span>`
    : `<span class="band ${risk?'risk':''}" data-level="${level}"${t}><span class="segs"><i></i><i></i><i></i></span><span class="lbl">${level}</span></span>`;
};
/* Zweite Achse zur Relevanz-Stufe: die Passungszahl, IMMER gepaart mit der Beleglage.
 *
 * Die Paarung ist der ganze Zweck, nicht Beiwerk. „71" allein laesst offen, ob die Zahl auf
 * gelesenen Vergabeunterlagen steht oder auf blossen Kopfdaten. „71 · nur Kopfdaten" sagt es.
 * Darum stecken beide in EINEM Baustein: wer sie auf zwei Funktionen aufteilt, zeigt die Zahl
 * frueher oder spaeter ohne ihren Vorbehalt.
 *
 * ⚠ Die Zahl ist eine Rangzahl zum Sortieren, KEIN Prozentsatz und keine
 * Gewinnwahrscheinlichkeit. Deshalb steht „/100" dran und nie ein Prozentzeichen. Sie kennt
 * genau acht Werte (0·14·29·43·57·71·86·100), weil `s` in Halbschritten springt; eine feinere
 * Darstellung wuerde Genauigkeit behaupten, die es nicht gibt. Herkunft: profileEngine.js.
 * Die kalibrierte Zahl des Hauses ist eine andere (dim_displaceability, ECE 0,016). */
const BELEG_WORT = { reich: "belegt", mittel: "teils belegt", duenn: "nur Kopfdaten" };
function passungAchse(l, kompakt){
  if(l.passung == null) return '';
  const d = dichte(l);
  const wort = tk(BELEG_WORT[d] || BELEG_WORT.duenn);
  const titel = tk("Passung {n} von 100. Eine Rangzahl zum Sortieren, kein Prozentsatz und keine Gewinnwahrscheinlichkeit. Beleglage: {beleg}.",
                   { n: l.passung, beleg: wort });
  return `<span class="passung" data-beleg="${d}" title="${esc(titel)}">`
       + `<b>${l.passung}</b><i>/100</i>`
       + (kompakt ? '' : `<em>${esc(wort)}</em>`)
       + `</span>`;
}

const STAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linejoin="round"><path d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8L12 4Z"/></svg>`;
const LVL = {hoch:3, mittel:2, niedrig:1, na:0};
const WF = {
  interessant:{label:'Interessant', cls:'wf-int'},
  pruefung:   {label:"In Prüfung",  cls:'wf-pru'},
  fragen:     {label:'Offene Fragen',cls:'wf-fra'},
  verworfen:  {label:'Verworfen',   cls:'wf-ver'},
};
const wfPill = k => `<span class="wf ${WF[k].cls} filled">${tk(WF[k].label)}</span>`;
function konkCell(l){
  const k = l.konk;
  if(k.src==='na' || k.src==='unbekannt'){
    return `<span class="kf"><span class="kf-none">${k.wert}</span></span>`;
  }
  return `<span class="kf kf-${k.stufe}" title="${esc(k.hint)}">
      <span class="ksegs"><i></i><i></i><i></i></span>
      ${val(k.wert, k.src, k.hint)}</span>`;
}
const ME = {author:'Du', initials:'DK'};

/* ── Spalten-Definition ── */
const COLS = [
  {key:'netz',  label:'',          on:false, lock:true,  th:'center'},
  {key:'own',   label:'Unserer',   on:false, lock:true,  th:'center'},
  {key:'star',  label:'',          on:true,  lock:true,  th:'center'},
  {key:'src',   label:'Phase',     on:true},
  {key:'wf',    label:'Status',    on:true},
  {key:'empf',  label:'Empfehlung',on:true},
  {key:'titel', label:'Ausschreibung', on:true, lock:true},
  {key:'natur', label:'Leistung',  on:true},
  {key:'rahmen',label:'Rahmen',    on:false},
  {key:'buyer', label:'Auftraggeber', on:true},
  {key:'frist', label:'Frist',     on:true},
  // Die drei Entscheidungs-Achsen stehen bewusst NEBENEINANDER — man liest sie zusammen:
  // lohnt es sich (Relevanz), kann ich gewinnen (Chance), was kostet es (Aufwand).
  {key:'relevanz', label:'Relevanz', on:true, th:'center'},
  {key:'wechsel',  label:'Chance',   on:true, th:'center'},
  {key:'aufwand',label:'Aufwand',  on:true, th:'center'},
  {key:'neu',   label:'Wettbewerb',on:true, th:'center'},
  {key:'konk',  label:'Konkurrenz',on:false},
  {key:'vol',   label:'Volumen',   on:true,  th:'right'},
  {key:'region',label:'Region',    on:false},
  {key:'inc',   label:'Amtsinhaber', on:false},
  {key:'status',label:'Sichtung',  on:false},
];

/* ── Chance/Bieter-Lücke/Frist + visible()/sorted() ── */
const chanceCap = () => 'Chance';
const istEigen = l => !!(l && l.eigen && l.eigenBestaetigt!==false);

/* Die Chance stützt sich auf die Bieterzahl. Zwei Fälle, in denen sie fehlt —
   beide müssen sichtbar sein, sonst sieht Geraten aus wie Gemessen. */
function bieterLuecke(l){
  if(!l || l.wechsel==='na') return null;
  if(l.src==='f02') return {
    kurz:tk("Ausschreibung läuft noch"),
    lang:tk("Diese Ausschreibung läuft noch. Es hat also noch niemand geboten. Die Zahl der Mitbewerber ist einer der Faktoren hinter der Chance, und sie fehlt hier.")};
  if(l.rahmen==='uvgo') return {
    kurz:'unterschwellig',
    lang:tk("Unterschwellige Vergaben nach UVgO veröffentlichen keine Bieterzahlen. Der Faktor, der sonst am meisten zur Chance beiträgt, fehlt hier vollständig.")};
  return null;
}

// #24 Zuschlagsphase — Status-Zelle: „vor N Tagen" statt Countdown (kein Bieten, sondern Anrufen).
function awardWhen(l){
  const a = l.award ? l.award.ago : null;
  const txt = a==null ? '—' : a===0 ? 'heute' : a===1 ? 'gestern' : `vor ${a} Tagen`;
  return `<span class="award-when ${a!=null && a<=3?'hot':''}">${txt}<span class="cdsub">${tk("Zuschlag")}</span></span>`;
}
// #24 Empfehlungs-Zelle: Ansprechen / Prüfen / (kein Eintrag bei hoher Feldüberschneidung).
function awardEmpfCell(l){
  const a = l.award || {};
  const sub = a.subcontracting==='geregelt' ? tk("Unteraufträge geregelt") : tk("keine Angabe zu Unteraufträgen");
  const netz = ''; // Netzwerk-Freigabe: kein Bestand → nicht behaupten
  if(a.empfehlung==='ansprechen')
    return `<td class="c-empf"><span class="empf empf-go" title="${esc(tk("Unterauftragsvergabe geregelt und geringe Feldüberschneidung, hier lohnt der Anruf"))}">${tk("Ansprechen")}</span><span class="empf-grund">${sub}${netz}</span></td>`;
  if(a.empfehlung==='pruefen')
    return `<td class="c-empf"><span class="empf empf-open" title="${esc(tk("Keine Angabe zu Unteraufträgen oder mittlere Feldüberschneidung. Prüfen, ob der Anruf lohnt"))}">${tk("Prüfen")}</span><span class="empf-grund">${sub}</span></td>`;
  // hohe Feldüberschneidung → direkter Wettbewerb, keine Empfehlung
  return `<td class="c-empf"><span class="empf-grund" title="${esc(tk("Hohe Feldüberschneidung. Direkter Wettbewerb, keine Kontaktempfehlung"))}">${tk("direkter Wettbewerb")}</span></td>`;
}

function fristCell(l){
  if(l.tage != null){                       // offene Ausschreibung: Countdown
    const urg = l.tage <= 14;
    return `<span class="cd ${urg?'urg':''}">${val(tk('{n} Tage', {n: l.tage}), l.timing.src, l.timing.hint)}<span class="cdsub">${tk("bis Schluss")}</span></span>`;
  }
  if(l.src==='f01') return `<span class="cd none">—<span class="cdsub">${tk("noch keine Frist")}</span></span>`;
  return `<span class="cd">${val(endetText(l), l.timing.src, l.timing.hint)}<span class="cdsub">${tk("Vertragsende")}</span></span>`;
}

function visible(){
  const groups = {};
  for(const t of searchTokens){ (groups[t.type] ||= []).push(t); }
  return LEADS.filter(l => {
    if(l.branche !== aktiveBranche) return false;   // Grundraum: Branche aus Profil/Wechsel
    // Bestand = Verträge, in denen wir drin sind. Akquise = alles andere.
    if(filters.kandidaten) return !!l.eigenKandidat && l.eigenBestaetigt!==false;
    // Netzwerk-relevant = Mehrlos-Vergaben: dort kann ein Partner weitere Lose abdecken.
    if(filters.netz && !(l.lose && l.lose.length > 1)) return false;
    if(filters.ungesichtet && l.status!=='ungesichtet') return false;
    if(filters.gemerkt && !l.merk) return false;
    if(filters.relevant && l.relevanz!=='hoch') return false;   // „nur passende" (Testprofil)
    for(const [type, toks] of Object.entries(groups)){
      const ok = type==='text'
        ? toks.every(t=>matchToken(l,t))   // Stichworte: UND
        : toks.some(t=>matchToken(l,t));    // Facetten: ODER
      if(!ok) return false;                 // zwischen Facetten: UND
    }
    return true;
  });
}

// Ort-Filter aktiv → Region-Spalte automatisch einblenden
function syncLocationColumn(){
  const hasOrt = searchTokens.some(t=>t.type==='ort');
  const rc = COLS.find(c=>c.key==='region');
  if(rc) rc.on = hasOrt ? true : (rc._userOff ? false : rc.on);
}

/* Gesamtrang für die Akquise-Startansicht. Bewusst additiv und flach gewichtet (kein Score im
 * Sinne einer Präzisionsbehauptung) — er ordnet nur, was zuerst angesehen gehört:
 *   Relevanz ×2  ·  Chance ×1,5  ·  wenig Aufwand ×1  ·  ausreichende Frist ×1
 * Unbekannt = neutrale Mitte, nie eine Abwertung. */
function topScore(l){
  const R = LVL[l.relevanz] || 0;                 // hoch 3 · mittel 2 · niedrig 1 · na 0
  const W = l.wechsel && l.wechsel !== 'na' ? LVL[l.wechsel] : 2;   // unbekannt → Mitte
  const a = aufwandStufe(l).stufe;
  const A = a === 'niedrig' ? 3 : a === 'mittel' ? 2 : a === 'hoch' ? 1 : 2;   // wenig Aufwand = besser
  const t = (l.frist && typeof l.frist.tage === 'number') ? l.frist.tage
          : (typeof l.tage === 'number' ? l.tage : null);
  // Frist: genug Zeit zum Bieten ist ein Plus, akute Knappheit ein Minus, unbekannt neutral.
  const F = t == null ? 2 : t >= 14 ? 3 : t >= 7 ? 2.5 : t >= 3 ? 1.5 : 0.5;
  return 2 * R + 1.5 * W + 1 * A + 1 * F;
}

function sorted(rows){
  const g = l => {
    switch(sortKey){
      // Kombiniertes Ranking (Ticket #1): gewichtetes Mittel aus Relevanz & Wechsel-Chance,
      // beste zuerst. Wechsel „na" (Erstausschreibung) → nur Relevanz. Negativ, damit die
      // aufsteigende Sortierung die höchsten Scores nach oben bringt.
      // „Top-Leads" (Default mit Profil): die vier Achsen, die über ein Angebot entscheiden —
      // lohnt es sich (Relevanz), kann ich gewinnen (Chance), was kostet es (Aufwand), habe ich
      // noch Zeit (Frist). Unbekanntes wird NEUTRAL gewertet (fällt nicht nach unten) — sonst
      // würden dünn dokumentierte Ausschreibungen systematisch verschwinden.
      case 'ranking': return -topScore(l);
      // #24 Zuschlag: innerhalb der Phase nach Zuschlagsdatum absteigend (frisch zuerst) → ago aufsteigend
      case 'frist': return l.src==='award' ? (l.award ? l.award.ago : 9999)
                         : l.tage != null ? l.tage : (l.endTage!=null ? l.endTage : 9999);
      case 'vol': return l.volumen.src==='unbekannt' ? -1 : parseFloat(String(l.volumen.wert).replace(/[^\d,]/g,'').replace(',','.'))||0;
      case 'empf': return l.src==='award' ? 9 : recForList(l).rank;   // #26 §4.1 Aussagestärke, stärkste zuerst
      /* Passungszahl statt Stufe: dieselbe Richtung, nur feiner. Sie ist monoton aus
         demselben `s` abgeleitet wie die Stufe, die Reihenfolge der Baender bleibt also
         erhalten — innerhalb von „hoch" trennt sie jetzt 71 / 86 / 100. „na" (kein Profil)
         bleibt unter allem, wie vorher mit LVL['na']=0 unter LVL['niedrig']=1. */
      case 'relevanz': return l.relevanz === 'na' ? -1 : (l.passung ?? 0);
      case 'wechsel': return LVL[l.wechsel];
      case 'aufwand': return LVL[aufwandStufe(l).stufe];
      case 'konk': { const m={gering:1,mittel:2,hoch:3}; return m[l.konk.stufe]||9; }
      case 'buyer': return l.buyerShort;
      case 'src': return l.src;
      default: return l.titel;
    }
  };
  return [...rows].sort((a,b)=>{
    // #24 Phasen-Gruppierung (Ticket §3.2): Zuschläge sind ein eigener, zeitkritischer Block —
    // als zusammenhängende Gruppe oben (mit Alert-Band), innerhalb nach Zuschlagsdatum absteigend
    // (frisch zuerst). Der Phasenfilter schaltet die Gruppe ab, wer nur bieten will.
    const aw = a.src==='award', bw = b.src==='award';
    if(aw !== bw) return aw ? -1 : 1;
    if(aw && bw) return (a.award?a.award.ago:9999) - (b.award?b.award.ago:9999);
    const x=g(a), y=g(b);
    return (x<y?-1:x>y?1:0)*sortDir;
  });
}

/* ── cellHTML — Zellen-Renderer (liefert HTML-String) ── */
function cellHTML(l, key){
  switch(key){
    case 'netz': {
      const dabei = netzInteresse.has(l.id);
      const match = dabei && l.netzPartner;
      // Zwei verbundene Ringe = Bietergemeinschaft. Klick wie beim Stern, direkt in der Liste.
      const ringe = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
        <circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/></svg>`;
      const frei = isFreeLimit();
      const such = l.netzSuchend==null ? ''
        : frei ? `<span class="such lock" title="${esc(tk("Im Pro-Zugang seht ihr, wie viele hier schon einen Partner suchen, bevor ihr euch meldet"))}"><span class="nz-blur">${l.netzSuchend}</span></span>`
        : `<span class="such ${l.netzSuchend>=4?'viel':''}" title="${esc(tk(l.netzSuchend>=4?'Hier bildet sich bereits ein Feld':'Noch wenig Bewegung — freie Wahl bei den Losen'))}">${l.netzSuchend}</span>`;
      return `<td class="c-netz"><span class="netzcell">
        <button class="nzring ${dabei?'on':''} ${match?'match':''}"
          data-netzint="${l.id}"
          title="${match ? "Ihr sucht hier einen Partner — eine Firma ergänzt euch bereits"
                : dabei ? tk("Ihr sucht hier einen Partner, klicken zum Zurückziehen")
                : 'Wir suchen hier einen Partner'}"
          aria-pressed="${dabei}" aria-label="Bietergemeinschaft">${ringe}</button>${such}
        </span></td>`;
    }
    case 'own': {
      const drin = l.eigen && l.eigenBestaetigt!==false;
      return `<td class="c-own"><button class="owntog ${drin?'on':''}" data-own="${l.id}:${drin?'nein':'ja'}"
        title="${esc(tk(drin?'Aus dem Bestand entfernen':'Zum Bestand hinzufügen'))}">${drin?'−':'+'}</button></td>`;
    }
    case 'star': return `<td class="c-star"><button class="tstar" data-star="${l.id}" ${l.merk?`data-merk="${l.merk}"`:''} aria-label="Merken">${STAR}</button></td>`;
    case 'src': return `<td class="c-src"><span class="srcpill src-${l.src}">${l.srcLabel}</span></td>`;
    case 'titel': {
      const wort = (searchTokens.find(t=>t.type==='text')||{}).value;
      const f = wort ? fundstelle(l, wort) : null;
      const beleg = f && f.ort!=='Titel'
        ? `<span class="fund"><span class="fund-o">${f.ort}</span>${f.text?`<span class="fund-t">${hervorheben(f.text, wort)}</span>`:''}</span>`
        : '';
      const akt = l.aktualitaet
        ? `<span class="akttag akt-${l.aktualitaet.art}" title="${esc(l.aktualitaet.text+' ('+l.aktualitaet.am+')')}">${
            l.aktualitaet.art==='aufgehoben'?'aufgehoben':tk("geändert")}</span>` : '';
      const eigen = l.eigen && l.eigenBestaetigt!==false
        ? `<span class="eigentag" title="${esc(tk("Ihr seid hier Auftragnehmer. Für euch ein Risiko, kein Neugeschäft"))}">${tk("euer Vertrag")}</span>` : '';
      // #12: Bei Mehr-Los-Vergaben zeigen, über welches Los die Relevanz kommt (Best-Los).
      const lotHint = l.bestLot
        ? `<span class="ttitel-lot" title="${esc(tk('Diese Ausschreibung ist groß, relevant ist für euch Los {nr}', {nr: l.bestLot.nr}) + (l.bestLot.region?' ('+l.bestLot.region+')':''))}">▸ passt über Los ${l.bestLot.nr}</span>` : '';
      // #24 Zuschlag: Untertitel „Gewinner · Vergabestelle" (statt nur Vergabestelle)
      const awardSub = l.src==='award' && l.award
        ? `<span class="award-sub">${esc(l.award.winner)} · ${esc(l.buyerShort||l.buyer)}</span>` : '';
      return `<td class="c-titel"><span class="ttitel">${wort?hervorheben(l.titel, wort):esc(l.titel)}${akt}${eigen}</span>${awardSub}${lotHint}${beleg}</td>`;
    }
    case 'titel_alt': return `<td class="c-titel"><span class="ttitel" title="${esc(l.titel)}">${esc(l.titel)}</span></td>`;
    case 'buyer': return `<td class="c-buyer" title="${esc(l.buyer)}">${esc(l.buyerShort)}</td>`;
    case 'frist': return `<td class="c-frist">${l.src==='award'?awardWhen(l):fristCell(l)}</td>`;
    case 'natur': return `<td class="c-natur"><span class="nat nat-${l.naturKat}">${esc(l.natur)}</span></td>`;
    case 'konk': return `<td class="c-konk">${konkCell(l)}</td>`;
    case 'neu': return `<td class="c-neu" style="text-align:center">${l.neu
        ? `<span class="wettb neu" title="${esc(tk("Neuvergabe. Kein Amtsinhaber, offenes Feld"))}">${tk("Neu")}</span>`
        : `<span class="wettb folge" title="${esc(tk("Folgevergabe. Amtsinhaber vorhanden"))}">${tk("Folge")}</span>`}</td>`;
    case 'relevanz': return `<td class="c-band">${bandMeter(l.relevanz)}${passungAchse(l, true)}</td>`;
    case 'wechsel': { const lue = bieterLuecke(l);
      return `<td class="c-band">${bandMeter(l.wechsel, true, chanceCap())}${
        lue ? `<span class="pdot pdot-schaetz" title="${esc(tk("Geschätzt, {k}: keine Bieterzahl verfügbar", {k: tk(lue.kurz)}))}"></span>` : ''}</td>`;
    }
    case 'vol': {
      if(l.lose && l.lose.length>1){
        const werte = l.lose.map(x=>parseInt(x.wert.replace(/\D/g,''),10)).filter(n=>!isNaN(n));
        const min = Math.min(...werte);
        const fmt = n => n.toLocaleString('de-DE')+' €';
        return `<td class="c-vol"><span class="volwrap">
          <span class="v-num">${fmt(werte.reduce((a,b)=>a+b,0))}</span>
          <span class="volmin" title="${esc(tk("Kleinstes Los. So viel braucht ihr mindestens, um mitzubieten"))}">ab ${fmt(min)}</span>
        </span></td>`;
      }
      return `<td class="c-vol">${l.volumen.src==='unbekannt' ? `<span style="color:var(--ink-300)">${tk("Wert offen")}</span>` : val(l.volumen.wert, l.volumen.src, l.volumen.hint)}</td>`;
    }
    case 'rahmen': return `<td class="c-rahmen">${l.rahmen
      ? `<span class="rah rah-${l.rahmen}" title="${esc(tk(RAHMEN[l.rahmen].lang) + ' — ' + tk(RAHMEN[l.rahmen].x))}">${RAHMEN[l.rahmen].kurz}</span>`
      : '<span style="color:var(--ink-300)">—</span>'}</td>`;
    case 'aufwand': {
      // Zuschlag erteilt → man kann sich nicht mehr bewerben; „Angebotsaufwand" trifft nicht zu.
      // Das ist etwas anderes als „unbekannt" und wird deshalb auch anders gezeigt.
      if(l.src==='award')
        return `<td class="c-band"><span class="band-na" title="${esc(tk("Zuschlag bereits erteilt, kein Angebotsaufwand mehr"))}">—</span></td>`;
      const a = aufwandStufe(l);
      const naHint = a.bekannt === 0
        ? tk("Die Bekanntmachung nennt keine Anforderungen, wir schätzen den Aufwand nicht.")
        : tk(tk("Nur {n} von mindestens 2 nötigen Angaben bekannt, zu wenig für eine belastbare Einstufung."), {n: a.bekannt});
      return `<td class="c-band">${bandMeter(a.stufe, true, tk('Angebotsaufwand'), naHint)}</td>`;
    }
    case 'empf': {
      if(l.src==='award') return awardEmpfCell(l);
      // #26: eine Spalte, zwei Inhalte — Handlungsempfehlung wenn möglich, sonst Einordnung.
      const r = recForList(l);
      return `<td class="c-empf"><span class="empf rec-${r.cls}" title="${esc(tk(r.grund))}">${tk(r.label)}</span>` +
             `<span class="empf-grund">${esc(tk(r.grund))}</span></td>`;
    }
    case 'region': return `<td class="c-region">${esc(tk(l.region||''))}</td>`;
    case 'inc': return `<td class="c-inc">${l.incumbent ? val(l.incumbent.name, l.incumbent.src) : `<span style="color:var(--ink-300)">${tk('offen')}</span>`}</td>`;
    case 'status': return `<td class="c-status"><span class="stat">${tk(l.seen || (l.status==='ungesichtet'?'neu':'gesichtet'))}</span></td>`;
    case 'wf': return `<td class="c-wf">${l.userStatus ? wfPill(l.userStatus) : '<span class="wf-none">—</span>'}</td>`;
  }
}

/* ── Token-Icons + Radien ── */
const TOKICON = {
  ort:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6.4 7-11a7 7 0 1 0-14 0c0 4.6 7 11 7 11Z"/><circle cx="12" cy="10" r="2.4"/></svg>',
  cpv:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
  phase:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"/></svg>',
  leistung:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>',
  buyer:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 20v-1a5 5 0 0 1 10 0v1M9 4a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z"/></svg>',
  text:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.4-3.4"/></svg>'
};
const RADII = [0,5,10,25,50,100];

/* ── tokenLabel ── */
function tokenLabel(t){
  if(t.type==='ort') return t.label + (t.radius ? ` · ${t.radius} km` : '');
  return t.label;
}

/* ── Netzwerk-Konstanten ── */
const NETZ_FREI_MAX = 3;   // Free: gleichzeitige Meldungen. Kern-Schleife bleibt frei.
let netzInteresse = new Set();

/* ── suggestList (Vorschlags-Suche) ── */
function suggestList(raw){
  const q = raw.trim().toLowerCase(); if(!q) return [];
  const out=[]; const seen=new Set();
  const push=(o)=>{const k=o.type+o.value; if(!seen.has(k)){seen.add(k); out.push(o);}};
  for(const [k,v] of Object.entries(ORTE)) if(k.startsWith(q)) push({type:'ort',value:v.region,label:v.label,cat:'Ort'});
  // Stadtname → echter Umkreis-Token (Koordinate aus dem Stadt-Index). Die Stadt erscheint oben,
  // die Auftraggeber-Treffer mit demselben Namen folgen darunter — beide Wege parallel.
  const _cities = (PLZ_GEO._cities && PLZ_GEO._cities.DE) || null;
  if(_cities && !/^\d/.test(q)){
    const cityKeys = [];
    if(_cities[q]) cityKeys.push(q);                       // exakter Treffer zuerst
    const pre = [];
    for(const key in _cities){ if(key!==q && key.startsWith(q)){ pre.push(key); if(pre.length>=60) break; } }
    pre.sort((a,b)=> a.length-b.length || a.localeCompare(b));
    for(const key of pre.slice(0,3)) cityKeys.push(key);
    for(const key of cityKeys){ const c=_cities[key];
      push({type:'ort', value:'city:'+key, coord:[c[0],c[1]], radius:25, cat:'Umkreis', label:c[2]}); }
  }
  const _pg = /^\d{4,5}$/.test(q) ? plzLookup(q) : null;
  if(_pg){                                                // volle PLZ (DE 5-, CH/AT 4-stellig)
    push({type:'ort', value:q, coord:[_pg[0], _pg[1]], radius:25, cat:'Umkreis',
          label:'PLZ '+q+(_pg[2] ? ' '+_pg[2] : '')});
  } else if(/^\d{2,5}$/.test(q) && PLZ[q[0]]) push({type:'ort',value:PLZ[q[0]],label:'PLZ '+q+' (Region)',cat:'Ort'});
  // Leere Werte VOR dem Vergleich aussortieren, nicht erst beim Zugriff. Ein einziger Lead
  // ohne `natur` liess hier die ganze App abstuerzen — `n.toLowerCase()` auf undefined, bei
  // JEDEM Tastendruck in der Suche. Zeile 472 derselben Datei sichert dasselbe Feld mit
  // `(l.natur||'')` ab; die Uneinheitlichkeit war der eigentliche Fehler.
  const vorschlagen = (werte, bauen) => {
    for(const v of new Set(werte)){ if(typeof v === 'string' && v && v.toLowerCase().includes(q)) push(bauen(v)); }
  };
  vorschlagen(LEADS.map(l=>l.buyerShort), b => ({type:'buyer',value:b,label:b,cat:'Auftraggeber'}));
  vorschlagen(LEADS.flatMap(l=>(l.kw||[]).map(k=>k.w)), w => ({type:'text',value:w.toLowerCase(),label:w,cat:'Stichwort'}));
  vorschlagen(LEADS.map(l=>l.natur), n => ({type:'text',value:n.toLowerCase(),label:n,cat:'Leistung'}));
  return out.slice(0,9);
}

/* ═══ DETAIL-SCHICHT (Prototyp verbatim) ═══════════════════════════════ */
/* ── Detail-Zustand: Profil/Angaben/Netzwerk-Freigabe ── */
const PROFIL = {
  // Nur die ehrliche Leerstufe. Vorher standen hier zwei weitere Stufen mit ERFUNDENEN
  // Kennzahlen und erfundenen Kundennamen („Landkreis Bad Tölz-Wolfratshausen", 23 Siege,
  // 4,2 Mio €). Sie waren nur über einen Demo-Umschalter erreichbar und haben beim
  // Draufschauen den Eindruck erzeugt, die Zahlen kaemen aus den Daten. Echte Werte
  // kommen aus `user_contracts` und dem Firmenprofil — bis dahin steht hier nichts.
  neu: {siege:0, kunden:0, seit:null, volumen:null, median:null, anteil:null, rang:null,
        kundenListe:[], nachbarn:[]},
};
/* Markt hängt NUR an Branche × Region — immer gefüllt, auch ohne einen einzigen Sieg */
const PMARKT = {
  // Leer, bis `setMarket()` echte Zahlen einsetzt. Vorher stand hier ein erfundener Markt
  // (1.284 Vergaben, „Bezirk Oberbayern", „Zweckverband IT Süd", Einstiegs-Lose mit
  // Wunschpreisen). Kommen die echten Daten nicht an, sah das aus wie ein Ergebnis statt
  // wie eine Luecke — der teuerste Fehler, den eine Analyse-Oberflaeche machen kann.
  vergaben:null, offen:null, stellen:null, regionen:null, topStellen:[], einstieg:[],
};
let profilStufe = 'neu';   // ohne Onboarding: aspiring bidder — keine Firmen-Historie

/* Der ECHTE Bestand der angemeldeten Firma, gesetzt aus `/api/firma?id=<identityId>`
   (vorberechnet in scripts/export_firma_profiles.py, 5.334 Identitäten aus dem Gold-Layer).
   Bis zum 2026-08-22 gab es diesen Weg nicht: `renderProfil` las ausschliesslich `PROFIL`,
   und dort steht seit der Ehrlichkeits-Korrektur nur noch die Leerstufe. Position und
   Profil blieben deshalb auch dann leer, wenn die Firma 248 Zuschläge im Bestand hat —
   die Zahlen lagen bereit, es holte sie nur niemand ab. */
let BESTAND = null;

/* Abbildung von der Firmenprofil-JSON auf die Felder, die `renderProfil` braucht.
   ⚠ Bewusst NICHT gefüllt werden `anteil` und `rang`: der Marktanteil wäre „Siege über
   alle Branchen" geteilt durch „Markt einer Branche × Region" — eine Zahl, die grösser
   aussieht als sie ist. Die Oberfläche zeigt dort „—" bzw. „zu wenige Siege", und das
   ist die richtige Antwort, solange wir es nicht sauber rechnen. */
const geld = v => v == null ? null
  : v >= 1e9 ? (v/1e9).toFixed(1).replace('.',',') + ' Mrd €'
  : v >= 1e6 ? (v/1e6).toFixed(1).replace('.',',') + ' Mio €'
  : Math.round(v).toLocaleString('de-DE') + ' €';

function setBestand(fp){
  if(!fp || !fp.kpi){ BESTAND = null; return; }
  const sits = Array.isArray(fp.sits) ? fp.sits : [];
  const jahre = sits.map(s=>s.seit).filter(Boolean);
  BESTAND = {
    siege:   fp.kpi.wins_total || 0,
    kunden:  fp.n_vergabestellen || sits.length,
    seit:    jahre.length ? Math.min(...jahre) : null,
    // ⚠ Beide Felder gehen ungeformt in die Oberflaeche (`n(v)` setzt den Wert roh ein).
    // Die alte Demo-Stufe trug fertige Zeichenketten („4,2 Mio €"), die echten Zahlen sind
    // Fliesskomma: ohne diese Formatierung stand dort „17270807468.510025".
    volumen: geld(fp.kpi.vol_sum),
    median:  geld(fp.kpi.vol_median),
    anteil:  null,
    rang:    null,
    // Die Vergabestellen, bei denen die Firma schon gewonnen hat. `offen` zählt live aus
    // dem geladenen Leadbestand, wie viele Vergaben dieser Stelle gerade laufen.
    kundenListe: sits.slice(0,8).map(s=>({
      n: s.buyer, gewonnen: s.auftraege || 0, seit: s.seit || null,
      bindung: s.bindung || null,
      offen: LEADS.filter(l=>l.src==='f02' && l.buyer===s.buyer).length,
    })),
    // ⚠ `fp.felder` sind die EIGENEN Schwerpunkte der Firma („60 % Bauarbeiten für
    // Rohrleitungen"), NICHT die benachbarten. Sie hier einzusetzen hiesse, gemessene
    // Daten unter eine falsche Überschrift zu stellen. Die echten Nachbarfelder kommen
    // aus der CPV-Nähe je Branche, s. `setNachbarn`.
    nachbarn: [],
  };
}

/* Nachbarfelder je Branche (CPV-Nähe aus Firmen-Co-Occurrence, scripts/export_strategie.py).
   Die Strategie-Ansicht hat die Zahlen ohnehin geladen und reicht sie hier herein. */
let NACHBARN = [];
function setNachbarn(liste){
  NACHBARN = (Array.isArray(liste) ? liste : []).slice(0,6).map(x=>({
    n: x.label, naehe: (x.naehe||0) >= 70 ? 'hoch' : 'mittel', firmen: x.firmen || 0,
  }));
}
/* Was wir NICHT messen können, sondern was die Firma selbst angibt.
   Trennung ist wichtig: abgeleitet = gemessen, angegeben = unbestätigt. */
let angaben = {   // erklärtes Profil — leer bis der Nutzer es im Onboarding/Profil-Tab pflegt
  schwerpunkte:[],
  nachweise:[],
  regionen:[],
  min:'', max:'',
  partner:false,   // Partnersuche: standardmäßig AUS, beidseitig freiwillig
};
const VORSCHLAG = {
  schwerpunkte:['Netzwerktechnik','IT-Sicherheit','Softwareentwicklung','Clientmanagement',
                'Telekommunikation','Cloud & Hosting','Fachverfahren','Schulungen'],
  nachweise:['ISO 27001','ISO 9001','BSI C5','BSI-Grundschutz',"Präqualifikation IT",
             'TISAX','ISO 14001','BITV 2.0'],
  regionen:['Baden-Württemberg','Bayern','Berlin','Brandenburg','Hamburg','Hessen',
            'Niedersachsen','Nordrhein-Westfalen','Rheinland-Pfalz','Sachsen','Bundesweit'],
};
let offenerPicker = null;
let potTab = 'chancen';   // chancen | position | profil | netzwerk

/* ── Netzwerk-Freigabe + angFeld (erklärtes Profil-Feld) ── */
let netzFreigabe  = new Set();
/* Angehakte eigene Lose, als `${leadId}:${losNr}`. Vor der Meldung eine reine Auswahl im
   Browser, danach der gespeicherte Zustand vom Server (`/api/netz`). */
let netzLose = new Set();
function toggleNetzLos(key){ netzLose.has(key) ? netzLose.delete(key) : netzLose.add(key); }
function netzLoseVon(leadId){
  return [...netzLose].filter(k=>k.startsWith(leadId+':')).map(k=>+k.split(':').pop()).filter(Boolean);
}
/* Serverzustand für EINEN Lead in den Kern schieben: Meldung, Freigabe, Treffer.
   Vor dem 2026-08-22 gab es diesen Weg nicht — `netzPartner` setzte niemand, also konnte
   der Treffer-Zweig der Oberfläche nie erscheinen. */
function setNetzZustand(leadId, z){
  const l = LEADS.find(x=>x.id===leadId);
  if(!z || !z.interesse){
    netzInteresse.delete(leadId); netzFreigabe.delete(leadId);
    if(l){ l.netzPartner = null; l.netzDeckung = 0; }
    return;
  }
  netzInteresse.add(leadId);
  z.interesse.freigabe ? netzFreigabe.add(leadId) : netzFreigabe.delete(leadId);
  [...netzLose].forEach(k=>{ if(k.startsWith(leadId+':')) netzLose.delete(k); });
  (z.interesse.lose||[]).forEach(n=>netzLose.add(leadId+':'+n));
  if(l){ l.netzPartner = z.partner || null; l.netzDeckung = (z.interesse.lose||[]).length; }
}

/* Ein Feld mit abgeleiteten (gemessen) und angegebenen (unbestätigt) Werten */
function angFeld(key, titel, zweck, abgeleitet){
  const eigene = angaben[key]||[];
  return `<div class="ang-f">
    <div class="ang-h"><span class="ang-t">${titel}</span><span class="ang-x">${zweck}</span></div>
    <div class="ang-chips">
      ${abgeleitet.map(w=>`<span class="ang-c ang-abg" title="${esc(tk("Aus euren gewonnenen Vergaben abgeleitet"))}">${w}<i>${tk("gemessen")}</i></span>`).join('')}
      ${eigene.map(w=>`<span class="ang-c ang-eig" title="${esc(tk("Von euch angegeben, nicht überprüft"))}">${w}
        <button class="ang-x-btn" data-angrm="${key}:${w}" aria-label="Entfernen">×</button></span>`).join('')}
      <span class="ang-add">
        <button class="ang-plus" data-angadd="${key}">${tk("+ ergänzen")}</button>
        ${offenerPicker===key?`<span class="ang-pop">
          ${VORSCHLAG[key].filter(v=>!eigene.includes(v)).map(v=>
            `<button class="ang-opt" data-angset="${key}:${v}">${v}</button>`).join('')}
        </span>`:''}
      </span>
    </div>
  </div>`;
}


/* ── Team-Tab: LOGMARK + renderLog + renderTeam ── */
const LOGMARK = {
  create:'●', view:'○', analyze:'◆', status:'◐', watch:'★', dossier:'▣', export:'⇩', alert:'!'
};
function renderLog(l){
  return l.log.map(ev =>
    `<div class="logrow" data-kind="${ev.kind}">
      <span class="logmark">${LOGMARK[ev.kind]||'·'}</span>
      <div class="logtxt">${esc(ev.text)}${ev.who?` <b>${esc(ev.who)}</b>`:''}</div>
      <span class="logts">${ev.ts}</span>
    </div>`).join('');
}
function renderTeam(l){
  const n = l.comments.length;
  const thread = n ? l.comments.map(c => {
    const mine = c.author==='Du';
    return `<div class="cmt ${mine?'mine':''}">
      <div class="cmt-av ${mine?'you':''}" title="${esc(c.author)}">${esc(c.initials)}</div>
      <div class="cmt-bubble">
        <div class="cmt-meta"><b>${mine?'Du':esc(c.author)}</b><span>${esc(c.ts)}</span></div>
        <div class="cmt-body">${esc(c.body)}</div>
      </div></div>`; }).join('')
    : `<div class="thread-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.5 8.7 8.7 0 0 1-4-.9L3 20l1.4-5.5a8.4 8.4 0 0 1-.9-4A8.5 8.5 0 0 1 12 2a8.4 8.4 0 0 1 9 9.5Z"/></svg>
        <p>${tk("Noch ruhig hier. Schreibt die erste Notiz, euer Team sieht sie.")}</p>
      </div>`;
  return `<div class="dbody">
    <div class="teamgrid">
      <section class="teamcol">
        <h4>${tk("Notizen")}<span class="cov">${n?n+' · ':''}für euer Team sichtbar</span></h4>
        <div class="thread">${thread}</div>
        <div class="composer">
          <div class="cmt-av you">${ME.initials}</div>
          <div class="composer-field">
            <textarea data-cmt rows="1" placeholder="Schreibt eurem Team…"></textarea>
            <button class="composer-send" data-cmtsend aria-label="Senden">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
            </button>
          </div>
        </div>
      </section>
      <section class="teamcol logcol">
        <h4>${tk("Verlauf")}<span class="cov">${tk("automatisch protokolliert")}</span></h4>
        <div class="log">${renderLog(l)}</div>
      </section>
    </div>
  </div>`;
}


/* ── Tab-Renderer: pdotT, Übersicht, Teilnahme, Bewertung(analyse), Markt, Vergabestelle(buyer), Gate ── */
const pdotT = (src,hint)=> src && src!=='echt'
  ? `<span class="pdot pdot-${src}" title="${esc(tk(SRC_TEXT[src])+(hint?' — '+tk(hint):''))}"></span>` : '';

// Eigener „Unterlagen"-Tab: alles Dokument-Getriebene (Vergabe-Analyse / Upload / Volltext).
// Upload-Prompt NUR bei offenen Ausschreibungen (src='f02', Frist nicht vorbei) — bei
// auslaufenden/geplanten Verfahren gibt es keine ladbaren Unterlagen.
// §7.2 Kennzeichnungsstufen → Badge
function _markBadge(m){
  const M={Zitat:['Zitat','m-z'], Extrahiert:['Extrahiert','m-e'], Abgeleitet:['Abgeleitet','m-a']};
  const [t,c]=M[m]||M.m_e||['Extrahiert','m-e']; return `<span class="mark ${c}">${t}</span>`;
}
// Funktionale Checklisten-Gruppen (wie der Prototyp: K.-o. → Bewertung → … → Offen → Weitere).
const _CL_GROUPS = [
  ['ko',    'K.-o.-Kriterien',      new Set(['mindestumsatz','referenz_anzahl','referenz_mindestwert','zertifikat','ausschlussgrund','eignung_technisch','eignung_personal','berufshaftpflicht'])],
  ['bew',   'Bewertung',            new Set(['zuschlagskriterium'])],
  ['leist', 'Leistung & Technik',   new Set(['leistung_menge','technische_mindestanforderung'])],
  ['vertr', 'Vertrag & Auflagen',   new Set(['vertragsstrafe','haftung','laufzeit','kuendigung'])],
  ['form',  'Fristen & Formalien',  new Set(['frist','formalie','einzureichendes_dokument'])],
];
function _clDone(leadId){ try{ return JSON.parse(localStorage.getItem('govisor.checkstate.'+leadId)||'{}'); }catch(e){ return {}; } }
function _clHasBlocks(){ try{ return (JSON.parse(localStorage.getItem('govisor.blocks')||'[]')||[]).length>0; }catch(e){ return false; } }

// §7 Checkliste im Prototyp-Design: Kopf (Stand+Haftung) · TOC · funktionale
// Gruppen mit Zitat+Fundstelle+Kennzeichnung+editierbarem Baustein+Kombi-Button+Abhaken.
/* KENNZAHL 1 — Aufwand gegen Zeitfenster.
 *
 * ⚠ DIE ERSTE DEUTUNG WAR FALSCH. Der Median liegt bei 34 Tagen, in jeder Aufwandsklasse
 * (bis 10 Anforderungen 33 Tage, ueber 100 Anforderungen 35), Korrelation 0,08. Daraus wurde
 * zuerst „der Markt gibt dieselbe Zeit, egal wie viel Arbeit drinsteckt". Klingt gut, stimmt
 * nicht: 68 % aller Fenster liegen zwischen 28 und 40 Tagen, die haeufigsten Werte sind 30
 * bis 36 — dort liegen die gesetzlichen Mindestfristen. Die Frist reagiert nicht auf den
 * Aufwand, weil sie ueberhaupt nicht auf ihn reagieren soll.
 *
 * ⚠ UND DER VERGLEICH GEHT NUR JE REGELWERK. Unter den Vorgaengen mit hoechstens 28 Tagen
 * sind 21 % UVgO, im Rest 4 %: unterschwellig gelten andere Mindestfristen. Ein globaler
 * Median haette jede UVgO-Vergabe als „knapp" markiert, obwohl sie ihrem Rahmen entspricht.
 * Die Bezugsgroessen-Regel in ihrer strengsten Form: ein Vergleichswert, der zwei
 * Rechtsgrundlagen mischt, ist keiner.
 *
 * WAS BLEIBT: die Kennzahl braucht BEIDE Seiten und kann deshalb sonst niemand rechnen. Die
 * Aussage ist nur enger — nicht „der Markt ist blind fuer den Aufwand", sondern „diese
 * Vergabe gibt weniger Zeit als neun von zehn ihres Regelwerks, bei so vielen Anforderungen".
 *
 * ⚠ Nur der ENGE Fall und nur im zehnten Perzentil. Erste Fassung zeigte beide Raender am
 * Viertel — die Zeile erschien bei 51 % aller Vorgaenge. Und „mehr Zeit als ueblich" aendert
 * keine Entscheidung: man bewirbt sich nicht, WEIL viel Zeit ist. */
const _RAHMEN_NAME = { vgv: 'VgV', vob: 'VOB/A', uvgo: 'UVgO', sonst: null };
function renderFensterBlock(a, l){
  const f = l.lbFenster;
  if(!f || f.tage == null || !f.median || f.eng == null) return '';
  const n = (a.checklist||[]).length;
  if(!n) return '';
  if(f.tage > f.eng) return '';
  const spanne = Math.max(1, f.oben - f.unten);
  const pos = Math.max(0, Math.min(100, Math.round(((f.tage - f.unten) / spanne) * 50 + 25)));
  // Den Rahmen NENNEN, wenn wir ihn kennen: „marktueblich 34 Tage" ohne Angabe, unter welcher
  // Ordnung, waere genau die Vermischung, die der Vergleich vermeidet.
  const rn = _RAHMEN_NAME[f.rahmen];
  const bezug = rn
    ? tk("üblich sind {d} Tage unter {r}", {d: f.median, r: rn})
    : tk("üblich sind {d} Tage in vergleichbaren Verfahren", {d: f.median});
  return `<div class="fenster eng">
    <span class="fenster-t">${tk("{n} Anforderungen in {d} Tagen", {n: n, d: f.tage})}</span>
    <span class="bstat-leiste" aria-hidden="true"><i class="band"></i><i class="mitte"></i>
      <i class="punkt" style="left:${pos}%"></i></span>
    <span class="fenster-m">${bezug}<em>${tk("engstes Zehntel")}</em></span>
  </div>`;
}

function renderChecklistBlock(a, l){
  const items = (a.checklist||[]).map((it,i)=>({...it, _i:i}));
  /* AKTIVIERUNG A: welche erwarteten Unterlagen fehlen, und was dagegen zu tun ist.
     Bis zum 2026-09-01 kannte diese Stelle nur die Zuschlagskriterien und endete in einer
     Sackgasse („Bitte selbst pruefen"). Gemessen ueber 8.675 Analysen fehlen aber drei Arten
     regelmaessig: Zuschlagskriterien 5.978, Eignung 2.099, Aufforderung 1.431 — zusammen die
     haeufigsten Luecken ueberhaupt.

     ⚠ Die Bitte ist SPEZIFISCH. „Ladet die Unterlagen hoch" hilft niemandem weiter, der schon
     welche geschickt hat; „die Wertungsmatrix fehlt" sagt, WELCHE Datei gebraucht wird. */
  const FEHLT = {
    zuschlagskriterien: ["Zuschlagskriterien",
      "Die Zuschlagskriterien stehen nicht in den Unterlagen, die uns vorliegen. Ladet die Wertungsmatrix hoch, dann ergänzen wir die Auswertung."],
    eignung: ["Eignungsnachweise",
      "Welche Eignungsnachweise verlangt werden, steht nicht in den Unterlagen, die uns vorliegen. Ladet das Eignungsformular hoch, dann prüfen wir es gegen euer Profil."],
    aufforderung: ["Aufforderung zur Angebotsabgabe",
      "Die Aufforderung zur Angebotsabgabe fehlt uns. Sie trägt Fristen und Formvorgaben; ladet sie hoch, dann ergänzen wir beides."],
  };
  const fehlend = (a.missing_expected||[]).filter(m => FEHLT[m]);
  const other = a.other_documents||[];
  if(!items.length && !fehlend.length && !other.length) return '';
  const done = _clDone(l.id);
  let tot=0, dn=0;

  const itemHtml = it=>{
    const val = it.value!=null && it.value!=='' ? ` <span class="cl-val">${esc(String(it.value))}${it.unit?(' '+esc(String(it.unit))):''}</span>` : '';
    const isDone = !!done[it._i]; if(!isDone) {} // Zählung s.u.
    tot++; if(isDone) dn++;
    const q = it.quote
      ? `<div class="quote"><div class="lbl"><span>${it.parser?'Struktur ausgelesen':'Aus den Unterlagen'}</span>${_markBadge(it.marking)}</div><q>${esc(it.quote)}</q><div class="src">${esc(it.source_file||'')}${it.source_page?(' · S. '+esc(String(it.source_page))):''}${it.parser?tk(" · Parser, kein LLM"):''}</div></div>`
      : `<div class="quote"><div class="lbl"><span>${it.parser?'Struktur ausgelesen':'Aus den Unterlagen'}</span>${_markBadge(it.marking)}</div><q>${esc(it.label||'')}${val?(' — '+esc(String(it.value))+(it.unit?' '+esc(String(it.unit)):'')):''}</q>${it.source_file?`<div class="src">${esc(it.source_file)}${it.parser?tk(" · Parser, kein LLM"):''}</div>`:''}</div>`;
    const kombi = JSON.stringify({theme:it.theme, label:it.label, quote:it.quote||'', i:it._i});
    const block = `<div class="block"><div class="lbl"><span>${tk("Euer Textbaustein")}</span><span class="mark m-v">${tk("aus eurem Profil")}</span></div>
      <textarea class="ta cl-edit" placeholder="${esc(tk("Textbaustein aus eurem Profil einsetzen …"))}"></textarea>
      <div class="blockfoot"><span class="cl-hist"></span><span class="acts">
        <button class="btn btn-q btn-sm" data-clnutzen='${esc(kombi)}'>${tk("Aus Bibliothek")}</button>
        <button class="btn btn-p btn-sm" data-clkombi='${esc(kombi)}'>${tk("Kopieren &amp; speichern")}</button></span></div></div>`;
    return `<article class="item${isDone?' done':''}" data-clitem="${it._i}">
      <div class="ih"><button class="dchk" data-clchk="${it._i}">✓</button><b>${esc(it.label||it.req_type)}${val}</b></div>
      <div class="dsum">${tk("Abgehakt.")}<button class="re" data-clchk="${it._i}">${tk("wieder öffnen")}</button></div>
      <div class="ibody">${q}${block}</div></article>`;
  };

  const fensterHtml = renderFensterBlock(a, l);
  const groupsHtml = _CL_GROUPS.map(([id,title,set])=>{
    const gi = items.filter(it=>set.has(it.req_type)); if(!gi.length) return '';
    return `<details class="grp" id="clg-${id}"${id==='ko'?' open':''}><summary><span class="caret">›</span>${title}<span class="cnt">${gi.length}</span></summary><div class="gbody">${gi.map(itemHtml).join('')}</div></details>`;
  }).join('');
  // §7.4 Offen (Zuschlag nicht gefunden) + §7.5 Weitere Dokumente
  /* ⚠ EINE BITTE, KEIN BEFUND. Vorher stand hier „In den Unterlagen nicht eindeutig
     auffindbar. Bitte selbst pruefen." — richtig, aber eine Sackgasse: der Nutzer erfaehrt,
     dass etwas fehlt, und kann nichts tun. Jetzt steht daneben, WELCHE Datei hilft und ein
     Knopf, der sie entgegennimmt. Derselbe Upload-Weg wie ueberall, kein zweiter Pfad. */
  const offen = fehlend.length ? `<details class="grp" id="clg-offen" open><summary><span class="caret">›</span>${tk("Offen")}<span class="cnt">${fehlend.length}</span></summary><div class="gbody">${
    fehlend.map(m=>`<article class="item"><div class="ih"><span style="width:19px;text-align:center;color:var(--ink-400)">—</span><b>${tk(FEHLT[m][0])}</b><span class="mark m-a" style="margin-left:auto">${tk("Nicht gefunden")}</span></div>
      <div class="ibody"><div class="block" style="color:var(--ink-500);font-size:13px;line-height:1.6">
        ${tk(FEHLT[m][1])}
        <div style="margin-top:var(--s3)"><button class="va-upload-btn" data-uploaddocs="${l.id}">${tk("Hier hochladen (ZIP/PDF)")}</button></div>
      </div></div></article>`).join('')
  }</div></details>` : '';
  const weitere = other.length ? `<details class="grp" id="clg-weit"><summary><span class="caret">›</span>${tk("Weitere Dokumente")}<span class="cnt">${other.length}</span></summary><div class="gbody"><div class="flist" style="margin-bottom:11px">${other.slice(0,20).map(f=>`<div class="f"><span class="dot">·</span> ${esc(f)}</div>`).join('')}</div></div></details>` : '';

  // TOC-Chips je nicht-leerer Gruppe
  const chips = _CL_GROUPS.map(([id,title,set])=>{ const n=items.filter(it=>set.has(it.req_type)).length; return n?`<button class="tchip" data-cljump="clg-${id}">${esc(title)} <span class="n">${n}</span></button>`:''; }).join('')
    + (fehlend.length?`<button class="tchip" data-cljump="clg-offen">${tk("Offen")}<span class="n">${fehlend.length}</span></button>`:'')
    + (other.length?`<button class="tchip" data-cljump="clg-weit">${tk("Weitere")}<span class="n">${other.length}</span></button>`:'');

  const portal = (l.unterlagen&&l.unterlagen.url) ? `<a href="${esc(l.unterlagen.url)}" target="_blank" rel="noopener" class="link">${tk("Zum Vergabeportal ↗")}</a>` : '';
  const chead = `<div class="chead"><div class="r1"><span class="stand">Stand der Unterlagen: ${l.lbFiles||1} Datei${(l.lbFiles||1)===1?'':'en'}</span>${portal}</div>
    <div class="disc">Bitte regelmäßig prüfen, ob neue Unterlagen vorliegen. LLM-gestützte Analyse — kann Fehler enthalten. Jede Angabe ist mit Fundstelle im Originaldokument belegt${a.rejected_items>0?`; ${a.rejected_items} unbelegte Aussagen wurden verworfen`:''}; maßgeblich bleiben die Vergabeunterlagen.</div></div>`;
  const toc = `<div class="toc"><div class="th"><b>${tk("Eure Checkliste")}</b><span class="pr"><span class="cl-doneN">${dn}</span> von ${tot} erledigt</span></div><div class="chips">${chips}<button class="tchip all" data-clcollapse>${tk("Alle zuklappen")}</button></div><div class="tprog"><i class="cl-tprog" style="width:${tot?Math.round(dn/tot*100):0}%"></i></div></div>`;

  // a2 Erstnutzer: leere Bibliothek → die Textbausteine sind noch generische Vorlagen (§9.1).
  const firstday = !_clHasBlocks() ? `<div class="cl-firstday">${tk("Eure Bausteinbibliothek ist noch leer, die Textvorschläge unten sind generische Vorlagen.")}<a href="/bausteine" class="link">${tk("Bibliothek füllen →")}</a>${tk("Dann setzt goVisor eure echten Referenzen und Zertifikate ein statt Platzhalter.")}</div>` : '';
  return `<div class="va-checklist" data-clroot="${l.id}">${chead}${firstday}${fensterHtml}${toc}${groupsHtml}${offen}${weitere}</div>`;
}

// Download-Knopf für unsere extrahierte Tabelle (nicht für die Original-Unterlagen — die
// bleiben beim Portal, siehe /api/lead-export). Der Text wird bei JEDEM Aufruf gebaut, nicht
// als Modulkonstante: dort würde `tk()` beim Import auswerten und die Sprache einfrieren.
function csvLink(id, was){
  const titel = was==='lv' ? tk("Alle Positionen als CSV herunterladen (Excel-tauglich)")
                           : tk("Alle Kriterien als CSV herunterladen (Excel-tauglich)");
  return `<a class="dl-csv" href="/api/lead-export?was=${was}&id=${encodeURIComponent(id)}"
    download title="${esc(titel)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
    ><path d="M12 3v12m0 0-4-4m4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>CSV</a>`;
}

function renderDocs(l){
  const istOffen = l.src === 'f02' && (l.tage == null || l.tage >= 0);
  const check = items => (items&&items.length) ? `<ul class="va-check">${items.map(x=>{
    const t = typeof x==='string' ? x : (x.nachweis||'');
    const tag = (x&&x.kategorie) ? ` <span class="va-tag">${esc(x.kategorie)}</span>` : '';
    return `<li><label><input type="checkbox"><span>${esc(t)}${tag}</span></label></li>`;}).join('')}</ul>` : '';
  const bl = (title,body)=> body ? `<div class="va-block"><h5>${title}</h5>${body}</div>` : '';

  const head = l.lbAnalyse ? (()=>{
    const a = l.lbAnalyse;
    const AMP = {gruen:['●','Bietbar','va-go'], gelb:['●',tk("Abwägen"),'va-weigh'], rot:['●',tk("Hohe Hürde"),'va-stop']};
    const [icon,label,cls] = AMP[a.ampel] || AMP.gelb;
    /* ⚠ WOHER DIE UNTERLAGEN KOMMEN, GEHOERT AN DIE ANALYSE. Ein Nutzer kann Unterlagen
       zu JEDEM Vorgang hochladen; das Ergebnis sehen danach alle. Bis zum 2026-08-27 sah
       eine hochgeladene Auswertung genauso aus wie eine aus dem Portal geholte, und der
       §5-4-Zweifel ("der Auftraggeber des Leads kommt in den Unterlagen gar nicht vor")
       ging als einmalige Meldung an den Hochladenden — alle anderen bekamen dieselbe
       Analyse ohne jeden Vorbehalt. */
    const quelle = a.herkunft === "upload"
      ? `<p class="va-herkunft">${tk("Diese Auswertung stammt aus Unterlagen, die ein Nutzer hochgeladen hat.")}</p>` : '';
    const zweifel = a.zuordnung_zweifelhaft
      ? `<p class="va-zweifel">${tk("Achtung: der Auftraggeber dieses Leads kommt in den hochgeladenen Unterlagen nicht vor. Möglicherweise gehören sie zu einem anderen Verfahren. Prüft die Angaben, bevor ihr euch darauf verlasst.")}</p>` : '';
    const vahead = `<div class="va-head"><span class="va-amp ${cls}">${icon} ${label}</span><span class="cov">${tk("Vergabe-Analyse · aus den Unterlagen")}</span></div>
      ${zweifel}${quelle}
      ${a.ampel_grund?`<p class="va-grund">${esc(a.ampel_grund)}</p>`:''}
      ${a.zusammenfassung?`<p class="va-sum">${esc(a.zusammenfassung)}</p>`:''}`;
    // Reiche Checkliste (§7, Prototyp-Design) wenn vorhanden — sie trägt Kopf/Haftung/Erfolgshonorar selbst.
    if(a.checklist && ('checklist' in a)) {
      return `<section class="sec va-sec">${vahead}${renderChecklistBlock(a, l)}</section>`;
    }
    // Legacy-Fallback (Alt-Format-Analysen ohne checklist)
    const body = `${bl(tk("Muss erfüllt sein. K.o.-Kriterien"), check(a.ko_kriterien))}
         ${bl('Einzureichen — Eignungsnachweise', check(a.eignung))}
         ${(a.zuschlag&&a.zuschlag.length)?bl('Zuschlagskriterien', `<div class="zug">${a.zuschlag.map(z=>`<div class="zug-row"><span class="zug-k">${esc(z.kriterium)}</span><span class="zug-bar"><i style="width:${Math.max(3,Math.min(100,Number(z.gewicht)||0))}%"></i></span><span class="zug-v">${esc(String(z.gewicht))} %</span></div>`).join('')}</div>`):''}
         ${(a.fristen&&a.fristen.length)?bl('Fristen', `<div class="kv">${a.fristen.map(f=>`<div class="kvi"><span class="k">${esc(f.typ||'')}</span><span class="vv"><span class="v">${esc(f.wert||'')}</span></span></div>`).join('')}</div>`):''}
         ${bl('Aufwandstreiber', check(a.aufwand))}`;
    return `<section class="sec va-sec">${vahead}${body}
      <p class="rt-note">${tk("LLM-gestützte Analyse. Kann Fehler enthalten; Angaben mit Fundstelle belegt, maßgeblich bleiben die Vergabeunterlagen.")}</p>
    </section>`;
  })() : istOffen ? (()=>{
    const u = l.unterlagen || {};
    const ext = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg>`;
    const dl = u.url
      ? `<a class="va-dl" href="${esc(u.url)}" target="_blank" rel="noopener">Beim Vergabeportal herunterladen ${ext}</a>`
      : `<span class="va-dl-off">${tk("Unterlagen beim Vergabeportal herunterladen")}</span>`;
    /* Was das Portal ueber den Zugang sagt. ⚠ `access` stand bis zum 2026-08-23 bei ALLEN
       13.849 Vergaben mit Link auf „unknown" — das Feld gab es, gefuellt hat es niemand.
       Die Schweiz liefert die Antwort seit dem simap-Ingest: 660 offen, 55 nur auf Anfrage,
       4 kostenpflichtig. Wer vorher weiss, dass er nichts bekommt, spart sich den Weg. */
    const ZUG = {offen: tk("Unterlagen sind ohne Anmeldung abrufbar"),
                 auf_anfrage: tk("Unterlagen gibt es nur auf Anfrage"),
                 kostenpflichtig: tk("Unterlagen sind kostenpflichtig")};
    const zugang = ZUG[u.access] ? `<p class="va-zugang va-zugang-${u.access}">${ZUG[u.access]}</p>` : '';
    /* ⚠ WIR HABEN DIE UNTERLAGEN SCHON, SAGTEN ES ABER NICHT.
       `unterlagen.gelesen` (seit 2026-08-25) sagt, ob der Volltext bei UNS liegt —
       `access` sagt nur, was die Quelle anbietet. Ohne diese Trennung landete jeder Lead
       mit vorhandenem Volltext, aber noch ohne Auswertung, im Aufforderungs-Zweig „Hier
       hochladen (ZIP/PDF)". Gemessen am 2026-08-25: 1.154 von 5.899 offenen Leads mit
       Volltext. Der Nutzer wurde also gebeten, uns etwas zu schicken, das wir hatten. */
    if (u.gelesen) return `<section class="sec va-empty">
      <h4>${tk("Vergabe-Analyse")}<span class="cov">${tk("Unterlagen liegen vor")}</span></h4>
      <p class="va-sum">${tk("Die Vergabeunterlagen liegen uns bereits vor. Die Auswertung steht noch aus und erscheint hier, sobald sie durchgelaufen ist.")}</p>
      <p class="va-eigen">${dl}${zugang}</p>
      <p class="va-sum va-eigen-hint">${tk("Du kannst nicht warten? Lade deine eigene Fassung hoch, dann wird sie sofort ausgewertet.")}</p>
      <ol class="va-steps">
        <li><span class="va-step-n">1</span><div><button class="va-upload-btn" data-uploaddocs="${l.id}">${tk("Hier hochladen (ZIP/PDF)")}</button></div></li>
        <li><span class="va-step-n">2</span><div class="va-step-res">${tk("Ampel + Checkliste erscheinen automatisch")}</div></li>
      </ol>
      <div class="va-status" data-upstatus="${l.id}"></div>
    </section>`;
    /* ⚠ AUS DIESEM LAND HABEN WIR NOCH NICHTS. Gemessen am 2026-09-01: Deutschland hat
       Volltext fuer 9.788 Vorgaenge, Oesterreich und die Schweiz fuer NULL — bei zusammen
       2.783 offenen Vergaben. Wer dort bietet, sieht bei uns nie eine Auswertung.

       Die Bitte ist deshalb eine andere: nicht „lade hoch, dann geht es schneller", sondern
       „ihr waert die ersten". Das ist der ehrlichste Hebel, den wir haben, und zugleich der
       einzige Weg zu Unterlagen aus Portalen, an die wir nicht herankommen.

       ⚠ `landOhneDocs` ist eine MESSUNG aus dem Export, kein fester Satz. Kommt die erste
       Unterlage, verschwindet die Bitte von allein. Ein hart geschriebenes „keine einzige"
       wuerde ab dem Tag luegen, ohne dass es jemand merkt. */
    if (l.landOhneDocs) return `<section class="sec va-empty">
      <h4>${tk("Vergabe-Analyse")}<span class="cov">${tk("noch keine Unterlagen aus diesem Land")}</span></h4>
      <p class="va-sum">${tk("Aus diesem Land liegen uns bisher keine Vergabeunterlagen vor. Eure wären die ersten, und sie helfen allen, die hier bieten.")}</p>
      <ol class="va-steps">
        <li><span class="va-step-n">1</span><div>${dl}${zugang}</div></li>
        <li><span class="va-step-n">2</span><div><button class="va-upload-btn" data-uploaddocs="${l.id}">${tk("Hier hochladen (ZIP/PDF)")}</button></div></li>
        <li><span class="va-step-n">3</span><div class="va-step-res">${tk("Ampel + Checkliste erscheinen automatisch")}</div></li>
      </ol>
      <div class="va-status" data-upstatus="${l.id}"></div>
    </section>`;
    return `<section class="sec va-empty">
      <h4>${tk("Vergabe-Analyse")}<span class="cov">${tk("aus euren Unterlagen")}</span></h4>
      <p class="va-sum">${tk("Aus den Vergabeunterlagen machen wir in Sekunden eine")}<b>${tk("Ampel-Einschätzung")}</b>${tk(", eine abhakbare")}<b>${tk("Bieter-Checkliste")}</b>${tk("(K.o.-Kriterien, Eignungsnachweise, Zuschlagsgewichte) und")}<b>${tk("füllen Firmenangaben vor")}</b>.</p>
      <ol class="va-steps">
        <li><span class="va-step-n">1</span><div>${dl}${zugang}</div></li>
        <li><span class="va-step-n">2</span><div><button class="va-upload-btn" data-uploaddocs="${l.id}">${tk("Hier hochladen (ZIP/PDF)")}</button></div></li>
        <li><span class="va-step-n">3</span><div class="va-step-res">${tk("Ampel + Checkliste erscheinen automatisch")}</div></li>
      </ol>
      <div class="va-status" data-upstatus="${l.id}"></div>
    </section>`;
  })() : `<section class="sec va-empty">
      <h4>${tk("Vergabe-Analyse")}</h4>
      <p class="va-sum va-none">${l.src==='auslauf'
        ? tk("Diese Ausschreibung läuft aus bzw. ist abgeschlossen, die Vergabeunterlagen sind nur während der laufenden Angebotsfrist verfügbar. Sobald der Nachfolge-Auftrag ausgeschrieben ist, kannst du hier dessen Unterlagen analysieren.")
        : tk("Diese Ausschreibung ist noch nicht offen (Vorinformation). Sobald die Angebotsfrist läuft, kannst du hier die Vergabeunterlagen hochladen und analysieren.")}</p>
    </section>`;

  const anforderungen = (!l.lbAnalyse && l.lbSignals) ? (()=>{
    const s = l.lbSignals, rows = [];
    /* DER BELEG ZUR BEHAUPTUNG. `evidence` traegt je Signal den Satz aus dem Dokument
       (Median 88 Zeichen) und lag bis zum 2026-09-01 vollstaendig vor, ohne je im Frontend
       anzukommen — 9.409 von 9.788 Vorgaengen mit Volltext.

       ⚠ Am Zeigen, nicht im Fliesstext. Fuenf Zitate zu je 88 Zeichen wuerden den Block
       verdoppeln und die Anforderungen selbst unlesbar machen. Der Beleg gehoert dorthin,
       wo der Zweifel entsteht: an die Zeile, ueber die man stolpert. */
    let beleg = {};
    try { beleg = s.evidence ? JSON.parse(s.evidence) : {}; } catch { beleg = {}; }
    /* ⚠ Das Zitat ist ein AUSSCHNITT und beginnt oft mitten im Wort („che, Vertragsstrafe").
       Auf Wortgrenzen beschneiden und Auslassungspunkte setzen: es bleibt ein Fragment, sieht
       aber nicht nach Fehler aus.
       NICHT angefasst wird die Trennung aus dem PDF („erfor- derlich"). Sie sieht schlechter
       aus, aber „Bau- und Betriebskosten" ist dieselbe Zeichenfolge — wer sie zusammenzieht,
       zerstoert echte Bindestriche. Lieber sichtbar unschoen als still falsch. */
    const zitat = (roh) => {
      let z = String(roh).trim();
      // Vorn das angebrochene Wort wegnehmen: „che, Vertragsstrafe" ist kein Satzanfang.
      if (!/^[A-ZÄÖÜ0-9„"(]/.test(z)) z = '… ' + z.replace(/^\S+\s+/, '');
      /* ⚠ HINTEN NICHTS WEGNEHMEN. Die erste Fassung schnitt das letzte Wort ab, wenn das
         Zitat nicht auf einem Satzzeichen endete — und machte aus „Bindefrist: 30.10.2026"
         ein „Bindefrist: …". Ausgerechnet die Zahl, wegen der man hinschaut.
         Kurze Zitate sind meist vollstaendig und bekommen gar nichts. */
      if (z.length >= 40 && !/[.!?»"]$/.test(z)) z += ' …';
      return z;
    };
    const mitBeleg = (schluessel, wert) => {
      const z = beleg[schluessel];
      return z ? `<span class="hat-beleg" title="${esc(zitat(z))}">${esc(wert)}</span>` : esc(wert);
    };
    if(s.guarantee!=null) rows.push([tk('Sicherheit / Bürgschaft'),
      mitBeleg('guarantee_evidence', s.guarantee?tk('gefordert'):tk("nicht gefordert"))]);
    if(s.bindingDays!=null) rows.push([tk('Bindefrist'),
      mitBeleg('binding_evidence', tk('{n} Tage', {n: s.bindingDays}))]);
    if(s.eligibility) rows.push(['Eignungsnachweise', esc(s.eligibility+tk(" im Text genannt"))]);
    // ⚠ AUS DEM DOKUMENT. Zertifikatsnamen kommen aus fremdem Text und muessen escapen.
    if(s.certificates && s.certificates.length) rows.push(['Geforderte Zertifikate', esc(s.certificates.join(', '))]);
    if(s.variants!=null) rows.push(['Nebenangebote', esc(s.variants?'zugelassen':tk("nicht zugelassen"))]);
    if(s.framework) rows.push(['Rahmenvereinbarung', esc('ja')]);
    /* ⚠ Sechs Signale wurden bis zum 2026-09-01 erhoben und nie gezeigt. Sie fielen im
       Export aus einer handgetippten Spaltenliste (s. govisor/kennzahlen.py).

       Die Reihenfolge folgt dem, was eine Bietentscheidung kippt: erst was Aufwand macht
       (Ortstermin, Praesentation), dann was Geld kostet (Vertragsstrafe), dann die Frist,
       dann das Angenehme (Skonto). */
    if(s.siteVisit) rows.push([tk('Ortstermin'),
      mitBeleg('site_visit_evidence', s.siteVisitMandatory ? tk("verpflichtend") : tk("vorgesehen"))]);
    if(s.presentationRequired) rows.push([tk('Präsentation'),
      mitBeleg('presentation_evidence', tk("gefordert"))]);
    if(s.penaltyPct!=null) rows.push([tk('Vertragsstrafe'),
      mitBeleg('penalty_evidence', `${s.penaltyPct} %`)]);
    /* Die Bindefrist steht zweimal, und das ist Absicht: „90 Tage" sagt, wie lange ihr
       gebunden seid, „bis 14.11." sagt, ob es in eure Auslastung passt. Das Datum ist im
       Bestand ausserdem viel haeufiger ablesbar (5.747 gegen 150 Saetze). */
    // ⚠ AUS DEM DOKUMENT, s. Zertifikate.
    if(s.bindingUntil) rows.push([tk('Bindefrist bis'), esc(s.bindingUntil)]);
    if(s.skontoPct!=null) rows.push([tk('Skonto'), esc(`${s.skontoPct} %`)]);
    const w = (s.weights && Object.keys(s.weights).length) ? s.weights : null;
    if(!rows.length && !w) return '';
    return `<section class="sec">
      <h4>${tk("Anforderungen")}<span class="cov">${tk("aus den Vergabeunterlagen extrahiert")}</span></h4>
      ${rows.length ? `<div class="kv">${rows.map(([k,v])=>`<div class="kvi"><span class="k">${k}</span><span class="vv"><span class="v">${/* ⚠ v IST FERTIGES HTML. Jede `rows.push`-Stelle escaped selbst, weil `mitBeleg` einen Span liefert und hier kein `esc()` mehr steht. Zertifikatsnamen und Bindefrist-Datum kommen aus Vergabeunterlagen, also aus fremdem Text — wer hier eine Zeile ergaenzt, MUSS `esc()` benutzen. */''}${v}</span></span></div>`).join('')}</div>` : ''}
      ${w ? `<div class="zug"><div class="zug-h">${tk("Zuschlagsgewichte")}</div>${Object.entries(w).map(([k,v])=>`<div class="zug-row"><span class="zug-k">${esc(k)}</span><span class="zug-bar"><i style="width:${Math.max(3,Math.min(100,Number(v)||0))}%"></i></span><span class="zug-v">${esc(String(v))} %</span></div>`).join('')}</div>` : ''}
    </section>`;
  })() : '';

  // Leistungsumfang: das Leistungsverzeichnis selbst (GAEB beim Bau, Preisblatt sonst).
  // Die Mengen-Summen gelten fuer ALLE Positionen; die Tabelle ist ein gekennzeichneter
  // Auszug in Dokumentreihenfolge — eine eigene Rangfolge waere bei gemischten Einheiten
  // (150 m² gegen 3 Stueck) eine Scheinordnung.
  const umfang = (l.lbStruktur && l.lbStruktur.nPositionen) ? (()=>{
    const s = l.lbStruktur, pos = s.positionen || [];
    const mengen = Object.entries(s.mengen || {}).sort((a,b)=>b[1]-a[1]).slice(0,8);
    const zahl = n => Number(n).toLocaleString('de-DE', {maximumFractionDigits:1});
    const herkunft = s.quelle && s.quelle.indexOf('gaeb') >= 0
      ? tk("aus dem GAEB-Leistungsverzeichnis") : tk("aus dem Preisblatt der Unterlagen");
    return `<section class="sec">
      <h4>${tk("Leistungsumfang")}<span class="cov">${herkunft}</span>${csvLink(l.id,'lv')}</h4>
      <p class="lu-sum">${tk("{n} Positionen im Leistungsverzeichnis.", {n: zahl(s.nPositionen)})}</p>
      ${mengen.length ? `<div class="lu-mengen">${mengen.map(([e,v])=>
        `<span class="lu-chip"><b>${esc(zahl(v))}</b> ${esc(e)}</span>`).join('')}</div>` : ''}
      ${pos.length ? `<table class="lu-tab"><thead><tr>
          <th>${tk("Pos.")}</th><th>${tk("Leistung")}</th><th class="lu-r">${tk("Menge")}</th><th>${tk("Einheit")}</th>
        </tr></thead><tbody>${pos.map(p=>`<tr>
          <td class="lu-no">${esc(p.rno||'')}</td>
          <td>${esc(p.text||'')}</td>
          <td class="lu-r">${p.menge==null?'':esc(zahl(p.menge))}</td>
          <td>${esc(p.einheit||'')}</td></tr>`).join('')}</tbody></table>
        ${s.nPositionen > pos.length
          ? `<p class="lu-more">${tk("Auszug, erste {a} von {b} Positionen. Vollständig in den Unterlagen beim Vergabeportal.", {a: pos.length, b: zahl(s.nPositionen)})}</p>`
          : ''}` : ''}
    </section>`;
  })() : '';

  // Entscheidungskriterien aus der UfAB-Matrix. A und B getrennt, weil sie verschiedene
  // Fragen beantworten: A entscheidet ueber Teilnahme (nicht erfuellt = raus), B ueber Punkte.
  const kriterien = (l.lbStruktur && l.lbStruktur.kriterien) ? (()=>{
    const k = l.lbStruktur.kriterien, a = k.ausschluss || [], b = k.bewertung || [];
    if(!a.length && !b.length) return '';
    const zeile = x => `<li><span class="kr-code">${esc(x.code||'')}</span>
      <span class="kr-txt">${esc(x.text||'')}</span>
      ${x.gewichtung!=null?`<span class="kr-gew">${esc(String(x.gewichtung))}</span>`:''}</li>`;
    return `<section class="sec">
      <h4>${tk("Entscheidungskriterien")}<span class="cov">${tk("aus der Kriterienmatrix der Unterlagen")}</span>${csvLink(l.id,'kriterien')}</h4>
      ${a.length ? `<div class="kr-block kr-ko">
        <div class="kr-h"><b>${tk("Ausschlusskriterien")}</b>
          <span class="kr-n">${a.length}</span>
          <span class="kr-hint">${tk("nicht erfüllt = Angebot fliegt raus")}</span></div>
        <ul class="kr-list">${a.map(zeile).join('')}</ul></div>` : ''}
      ${b.length ? `<div class="kr-block">
        <div class="kr-h"><b>${tk("Bewertungskriterien")}</b>
          <span class="kr-n">${b.length}</span>
          <span class="kr-hint">${tk("bringen Punkte, Gewichtung rechts")}</span></div>
        <ul class="kr-list">${b.map(zeile).join('')}</ul></div>` : ''}
    </section>`;
  })() : '';

  const volltext = l.lbText ? `<section class="sec sec-raw">
      <h4>${tk("Leistungsbeschreibung")}<span class="cov">aus den Vergabeunterlagen · ${l.lbFiles||1} Datei${(l.lbFiles||1)===1?'':'en'}</span></h4>
      <details class="rawtext"${l.lbAnalyse?'':' open'}>
        <summary><span class="rt-open">${tk("Volltext aus den Unterlagen")}</span><span class="rt-len">${Math.round((l.lbChars||l.lbText.length)/1000)} Tsd. Zeichen${l.lbTruncated?tk(" · gekürzt"):''}</span></summary>
        <div class="rt-body lb-doc">${l.lbText.split(/\n\n+/).slice(0,400).map(p=>`<p>${esc(p.trim())}</p>`).join('')}</div>
      </details>
    </section>` : '';

  /* Dateiliste des Portals — was dort LIEGT, ohne dass wir es gelesen haben.
     ⚠ Die Trennung ist der ganze Punkt. subreport (DE) und vergabeportal.at (AT) geben die
     Dateien nur gegen Anmeldung heraus, die LISTE aber öffentlich. Gemessen 2026-08-22:
     944 heute offene Vergaben haben eine solche Liste und KEINEN Volltext — 134 davon in
     Österreich, wo es bis dahin gar keine Dokumentsignale gab. Sie beantwortet zwei Fragen,
     die sonst offen bleiben: gibt es ein Leistungsverzeichnis, und welche Nachweise werden
     verlangt. Sie ersetzt die Unterlagen NICHT, und die Anzeige sagt das in jeder Zeile. */
  const liste = (l.lbListe && (l.lbListe.dateien||[]).length) ? (()=>{
    const li = l.lbListe;
    // Alle Typen, die in den Listen wirklich vorkommen (gezählt am 2026-08-22). Ein Typ
    // ohne Eintrag fiele als `technische_anlage` in der Oberfläche auf — Kleinschreibung
    // mit Unterstrich, mitten in deutschem Text.
    const TYP = {leistungsbeschreibung:tk("Leistungsbeschreibung"), eignung:tk("Eignung"),
                 vertrag:tk("Vertrag"), aufforderung:tk("Aufforderung"),
                 zuschlagskriterien:tk("Zuschlagskriterien"), eigenerklaerung:tk("Eigenerklärung"),
                 formblatt:tk("Formblatt"), technische_anlage:tk("Technische Anlage"),
                 preisblatt:tk("Preisblatt"), datenschutz:tk("Datenschutz"),
                 informationsblatt:tk("Informationsblatt"), fragenantworten:tk("Fragen und Antworten")};
    const schwer = (li.schwerpunkte||[]).map(t=>`<span class="dl-typ">${esc(TYP[t]||t)}</span>`).join('');
    const zeilen = (li.dateien||[]).slice(0,40).map(d=>
      `<li><span class="dl-n">${esc(d.name||'')}</span>${
        d.typ && d.typ!=='sonstiges' ? `<span class="dl-t">${esc(TYP[d.typ]||d.typ)}</span>` : ''}</li>`).join('');
    const rest = Math.max(0, (li.dateien||[]).length - 40);
    return `<section class="sec va-liste">
      <h4>${tk("Was dort liegt")}<span class="cov">${tk("Dateiliste des Portals, nicht gelesen")}</span></h4>
      <p class="dl-x">${tk("{quelle} zeigt die Namen der Vergabeunterlagen öffentlich an, die Dateien selbst nur nach Anmeldung. Wir haben keine davon geöffnet — was hier steht, ist der Dateiname und der daraus erkannte Typ.")
          .replace('{quelle}', esc(li.quelle||''))}</p>
      ${schwer ? `<div class="dl-schwer">${tk("Erkannt:")} ${schwer}</div>` : ''}
      <ul class="dl-liste">${zeilen}</ul>
      ${rest ? `<p class="dl-rest">${tk("und {n} weitere").replace('{n}', rest)}</p>` : ''}
    </section>`;})() : '';

  return `<div class="dbody dbody-ov">${head}${anforderungen}${kriterien}${umfang}${liste}${volltext}</div>`;
}

// #24 Zuschlag-Detail (Ticket §5): gleiche Detailstruktur wie ein Lead, andere Frage —
// nicht „soll ich bietentk(", sondern „lohnt sich der Anruf"). Zuschlag- + Gewinner-Karte,
// Passungshinweis (IMMER als Ableitung), Pflicht-Erläuterung, Aktionen.
function renderAwardUebersicht(l){
  const a = l.award || {};
  const s = a.winnerStats || {};
  const topField = (a.winnerFields && a.winnerFields[0]) ? a.winnerFields[0].label : null;
  const subTxt = a.subcontracting==='geregelt' ? 'in den Unterlagen geregelt' : tk("keine Angabe");
  const bars = (a.winnerFields||[]).map(f=>`
    <div class="aw-brow"><div><div class="aw-blab">${esc(f.label||'')}</div>
      <div class="aw-btrack"><i style="width:${Math.max(3,f.pct||0)}%"></i></div></div>
      <span class="aw-bv">${f.pct||0} %</span></div>`).join('');
  // Passungshinweis — abgeleitet aus der Zuschlagshistorie
  const passung = a.overlap==='gering'
      ? tk("Euer Schwerpunkt ergänzt, statt zu konkurrieren.")
    : a.overlap==='mittel'
      ? tk("Teilweise Überschneidung mit eurem Feld, im Einzelfall prüfen.")
      : tk("Starke Feldüberschneidung, hier ist eher Wettbewerb als Zusammenarbeit zu erwarten.");
  const fuehrt = a.overlap==='gering' ? tk("führt es selten selbst aus")
              : a.overlap==='mittel' ? tk("führt es teils selbst aus") : tk("führt es überwiegend selbst aus");
  const passungHead = topField
    ? `${esc(a.winner)} gewinnt überwiegend ${esc(topField)} und ${fuehrt}${
        s.subQuote ? ` — bei ${s.subQuote} Aufträgen war Unterauftragsvergabe geregelt` : ''}. ${passung}`
    : passung;
  const isoDe = d => { const m=String(d).match(/^(\d{4})-(\d{2})-(\d{2})/); return m?`${m[3]}.${m[2]}.${m[1]}`:String(d); };
  const firma = a.winnerId
    ? `<button class="aw-btn aw-btn-p" data-firma="${esc(a.winnerId)}">${tk("Firmenprofil")}</button>` : '';
  return `<div class="dbody dbody-ov">
    <div class="aw-cards">
      <section class="aw-card">
        <h4>${tk("Der Zuschlag")}</h4>
        <div class="aw-line"><span class="k">${tk("Gewinner")}</span><span class="v">${esc(a.winner)}</span></div>
        <div class="aw-line"><span class="k">${tk("Vergabestelle")}</span><span class="v">${esc(l.buyer||'—')}</span></div>
        <div class="aw-line"><span class="k">${tk("Zuschlag erteilt")}</span><span class="v">${a.date?isoDe(a.date):'—'}</span></div>
        <div class="aw-line"><span class="k">${tk("Auftragswert")}</span><span class="v">${esc(l.volumen.wert)}<span class="aw-vm">${l.volumen.src==='echt'?'gemessen':tk("geschätzt")}</span></span></div>
        <div class="aw-line"><span class="k">${tk("Laufzeit")}</span><span class="v">${a.laufzeit?'bis '+a.laufzeit:tk("nicht veröffentlicht")}</span></div>
        <div class="aw-line"><span class="k">${tk("Unteraufträge")}</span><span class="v">${subTxt}</span></div>
      </section>
      <section class="aw-card">
        <h4>${esc(a.winner)} — was wir wissen</h4>
        <div class="aw-line"><span class="k">${tk("Zuschläge 36 Monate")}</span><span class="v">${s.wins36!=null?s.wins36:'—'}</span></div>
        <div class="aw-line"><span class="k">${tk("Ø Auftragswert")}</span><span class="v">${s.avgValue||'—'}</span></div>
        <div class="aw-line"><span class="k">${tk("mit Unterauftrags-Regelung")}</span><span class="v">${s.subQuote||'—'}</span></div>
        ${bars ? `<h4 style="margin-top:14px">${tk("Leistungsfelder")}</h4><div class="aw-bars">${bars}</div>` : ''}
      </section>
    </div>

    <div class="aw-note aw-note-g">
      <div><b>${tk("Warum das zu euch passen könnte:")}</b> ${passungHead}
      <div class="aw-mini">${tk("Abgeleitet aus der Zuschlagshistorie · kein Hinweis auf konkreten Bedarf")}</div></div>
    </div>

    <div class="aw-note aw-note-n">
      <div>${tk("„Unteraufträge geregelt\" heißt: In den Vergabeunterlagen ist Unterauftragsvergabe vorgesehen. Ob und was tatsächlich vergeben wird, steht nirgends, das Feld liegt bei etwa einem Drittel der Verfahren vor.")}</div>
    </div>

    <div class="aw-actbar">
      <span class="aw-hint">${tk("goVisor täuscht keine Vermittlung vor: ohne beidseitige Netzwerk-Freigabe kein Kontaktknopf, nur öffentliche Angaben.")}</span>
      <span class="aw-acts">
        <button class="aw-btn" data-merk="${l.id}">${tk("Merken")}</button>
        ${firma}
      </span>
    </div>
  </div>`;
}

function renderUebersicht(l){
  if(l.src==='award') return renderAwardUebersicht(l);
  const inc = l.incumbent;
  const pdot = (src,hint)=> src && src!=='echt'
    ? `<span class="pdot pdot-${src}" title="${esc(tk(SRC_TEXT[src])+(hint?' — '+tk(hint):''))}"></span>` : '';
  const iv = (text,src,hint,num)=>{
    const cls = (src==='unbekannt'?'v-unk ':src==='na'?'v-na ':'')+(num?'v-num':'');
    return `<span class="v ${cls}">${esc(text)}</span>${pdot(src,hint)}`;
  };
  return `<div class="dbody dbody-ov">
    <section class="sec">
      <h4>${tk("Eckdaten")}</h4>
      <div class="kv">
        <div class="kvi kvi-lead"><span class="k">${tk("Auftragsvolumen")}</span>
          <span class="vv">${l.volumen.src==='unbekannt'?`<span class="v v-unk">${tk("Nicht veröffentlicht")}</span>`:iv(l.volumen.wert,l.volumen.src,l.volumen.hint,true)}</span></div>
        <div class="kvi kvi-lead"><span class="k">${tk("Frist")}</span>
          <span class="vv">${l.tage!=null?iv(tk('{n} Tage', {n: l.tage}),l.timing.src,l.timing.hint,true)+`<span class="vm">${tk('bis Schluss')}</span>`:iv(endetText(l),l.timing.src,l.timing.hint,true)}</span></div>
        <div class="kvi"><span class="k">${tk("Art der Leistung")}</span>
          <span class="vv">${iv(l.natur,'echt')}<span class="vm">CPV ${l.cpv}</span></span></div>
        <div class="kvi"><span class="k">${tk("Wettbewerbslage")}</span>
          <span class="vv">${l.neu?`<span class="tag-neu">${tk("Neuvergabe")}</span>`:`<span class="tag-folge">${tk("Folgevergabe")}</span>`}<span class="vm">${l.neu?tk("kein Amtsinhaber"):tk('Amtsinhaber vorhanden')}</span></span></div>
        <div class="kvi"><span class="k">${tk("Land")}</span>
          <span class="vv">${iv(tk(LAND_LABEL[l.land]||l.land||'Deutschland'),'echt')}</span></div>
        <div class="kvi"><span class="k">${tk("Leistungsort")}</span>
          <span class="vv">${iv(tk(l.region||''),'echt')}${l.marktOk===false
            ? `<span class="vm">${tk("nicht kreisgenau, kein Marktkontext")}</span>`
            : `<button class="inline-link" data-tab="markt">${tk('Markt ansehen')}</button>`}</span></div>
        <div class="kvi"><span class="k">${tk("Vertragsart")}</span>
          <span class="vv">${l.art?iv(l.art,'echt'):l.istRahmen?iv('Rahmenvertrag','echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
      <div class="kvi"><span class="k">${tk("Grundlaufzeit")}</span>
          <span class="vv">${l.laufzeit?iv(l.laufzeit,'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Geplanter Beginn")}</span>
          <span class="vv">${l.beginnGeplant?iv(l.beginnGeplant,'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Geplantes Ende")}</span>
          <span class="vv">${l.endeGeplant?iv(l.endeGeplant,'echt'):(l.endet?iv(endetText(l),'schaetz',tk("Aus der Laufzeit geschätzt, die Ausschreibung nennt kein Enddatum.")):`<span class="v-unk">${tk("nicht angegeben")}</span>`)}</span></div>
        <div class="kvi"><span class="k">${tk("Verlängerung")}</span>
          <span class="vv">${l.verlaengerung?iv(l.verlaengerung,'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Rechtsrahmen")}</span>
          <span class="vv">${l.rahmen?`${iv(RAHMEN[l.rahmen].kurz,'echt')}<span class="vm">${tk(RAHMEN[l.rahmen].lang)}</span>`:`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Verfahren")}</span>
          <span class="vv">${l.verfahren?iv(tk(l.verfahren),'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}${
            l.verfahren&&l.verfahren.startsWith('Verhandlung')
              ?`<span class="vm">${tk("Gespräche möglich. Beziehung zählt mehr als bei offenen Verfahren")}</span>`:''}</span></div>
      </div>
    </section>

    ${(l.extras && l.extras.length) ? `<section class="sec">
      <h4>${tk("Zusätzliche Angaben")}<span class="land-tag">${l.land==='CH'?tk("🇨🇭 nur Schweiz"):l.land==='AT'?tk("🇦🇹 nur Österreich"):(l.land||'')}</span></h4>
      <div class="kv">
        ${l.extras.map(e=>`<div class="kvi"><span class="k">${e.label}</span>
          <span class="vv">${iv(e.value,'echt')}</span></div>`).join('')}
      </div>
    </section>` : ''}

    ${!l.beschreibung ? `<section class="sec">
      <h4>${tk("Leistungsbeschreibung")}</h4>
      <div class="kurztext leer">${tk("Die Bekanntmachung enthält keinen Beschreibungstext.")}</div>
      <p class="rt-note">${tk("Das kommt häufig vor. Rund sechs von zehn Bekanntmachungen tragen weniger als 200 Zeichen, viele gar nichts. Was tatsächlich beschafft wird, steht dann ausschließlich in den Vergabeunterlagen.")}</p>
    </section>` : ''}

    ${l.beschreibung && !l.hasDetail ? `<section class="sec">
      <h4>${tk("Leistungsbeschreibung")}</h4>
      <div class="kurztext">${esc(l.beschreibung)}</div>
      <p class="rt-note">${tk("Mehr steht in der Bekanntmachung nicht. Das ist der Normalfall, bei rund sechs von zehn Ausschreibungen umfasst der Beschreibungstext weniger als 200 Zeichen. Die eigentliche Leistungsbeschreibung liegt in den Vergabeunterlagen auf dem Vergabeportal.")}</p>
    </section>` : ''}

    ${l.hasDetail && l.beschreibung ? `<section class="sec sec-raw">
      <h4>${tk("Leistungsbeschreibung")}<span class="cov">${tk("unverändert aus der Bekanntmachung")}</span></h4>
      <details class="rawtext" open>
        <summary><span class="rt-open">${tk("Originaltext")}</span><span class="rt-len">${
          l.beschreibung.trim().split(/\s+/).length} Wörter</span></summary>
        <div class="rt-body">${l.beschreibung.split(/\n\n+/).map(p=>`<p>${esc(p.trim())}</p>`).join('')}</div>
      </details>
      <p class="rt-note">${tk("Wir kürzen und glätten nichts. Was die Vergabestelle geschrieben hat, steht so da.")}</p>

      ${(l.extrakt||[]).length ? `<div class="ex">
        <div class="ex-head">
          <span class="ex-h">${tk("Aus dem Text gelesen")}</span>
          <button class="ex-link" data-tab="analyse" data-anchor="anforderungen">
            Anforderungs-Check${isFreeLimit()?` <i>${tk('· nutzt eine Bewertung')}</i>`:''}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
        <div class="ex-cols">
          ${(()=>{
            const G = [['nachweis','Nachweise'],['bedingung','Bedingungen'],
                       ['leistung','Leistung'],['technik','Technik'],['menge','Mengen']];
            const wort = (searchTokens.find(t=>t.type==='text')||{}).value;
            const ex = l.extrakt||[]; const KAP = 5;
            return G.map(([k,label])=>{
              let items = ex.filter(x=>x.k===k); if(!items.length) return '';
              if(wort) items = [...items].sort((a,b)=>
                (b.w.toLowerCase().includes(wort)?1:0) - (a.w.toLowerCase().includes(wort)?1:0));
              const offen = offeneGruppen.has(k);
              const zeig = offen ? items : items.slice(0,KAP);
              const rest = items.length - zeig.length;
              return `<div class="ex-col ${k==='nachweis'?'ex-ko':''}">
                <span class="ex-gh">${label}<i>${items.length}</i></span>
                ${zeig.map(x=>{
                  const tref = wort && x.w.toLowerCase().includes(wort);
                  return `<button class="ex-t ex-${x.s} ${x.unsicher?'ex-uns':''} ${tref?'on':''}" data-mark="${x.w}"
                    title="${x.s==='cpv'?"Aus der amtlichen CPV-Einordnung":'Aus dem Beschreibungstext gelesen'}${
                    x.unsicher?tk("Zahl aus dem Fließtext, ungeprüft"):''}${x.rand?tk("Randleistung, nicht der Kern"):''}">
                    <span class="ex-w">${x.w}</span>
                    <i class="ex-src">${tref?'gesucht':x.s==='cpv'?'CPV':'Text'}</i>
                  </button>`;}).join('')}
                ${rest>0?`<button class="ex-more" data-grp="${k}">+ ${rest}</button>`:''}
                ${offen&&items.length>KAP?`<button class="ex-more" data-grp="${k}">${tk("weniger")}</button>`:''}
              </div>`;
            }).join('');
          })()}
        </div>
        <div class="ex-legend">
          <span><b>${tk("CPV")}</b>${tk("aus der amtlichen Einordnung")}</span>
          <span><b>${tk("Text")}</b>${tk("aus der Beschreibung gelesen")}</span>
          <span class="ex-hint">${tk("Klick einen Begriff, um ihn im Text zu finden.")}</span>
        </div>
      </div>` : ''}
    </section>` : ''}

<section class="sec">
      <h4>${tk("Auftraggeber")}</h4>
      <div class="kv">
        <div class="kvi kvi-full"><span class="k">${tk("Vergabestelle")}</span>
          <span class="vv"><span class="v">${esc(l.buyer)}</span></span></div>
      </div>
      <button class="sec-link" data-tab="buyer">${tk("Käufer-Dossier ansehen")}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </button>
    </section>

    <section class="sec">
      <h4>${l.eigen ? 'Euer Vertrag' : 'Aktueller Auftragnehmer'}</h4>
      ${!l.eigen && inc ? `<div class="ownclaim">
        <span>Ist das euer Vertrag? ${l.eigenKandidat?tk("Der Name ähnelt eurem, war aber nicht eindeutig genug."):''}</span>
        <button class="oc-claim" data-own="${l.id}:ja">${tk("Als unseren übernehmen")}</button>
      </div>` : ''}
      ${l.eigen && l.eigenBestaetigt===null ? `<div class="ownconfirm">
        <div class="oc-t"><b>${tk("Gehört dieser Vertrag euch?")}</b></div>
        <div class="oc-x">Wir haben ${MEINE_FIRMA} als Auftragnehmer erkannt, aber nur über den Firmennamen —
        das ist bei etwa jedem zwanzigsten Namen nicht eindeutig. Erst wenn du bestätigst, behandeln wir den Vertrag
        als euren und warnen euch vor dem Auslaufen.</div>
        <div class="oc-btns">
          <button class="oc-yes" data-own="${l.id}:ja">${tk("Ja, gehört uns")}</button>
          <button class="oc-no" data-own="${l.id}:nein">${tk("Nein, nicht unserer")}</button>
        </div>
      </div>` : ''}
      ${!inc ? `<div class="note-box"><b>${tk("Noch nicht vergeben.")}</b>${tk("Diese Ausschreibung ist offen. Kein Amtsinhaber, kein Wechsel-Score. Offenes Feld.")}</div>`
      : inc.src==='unsicher' && !l.eigen ? `<div class="note-box"><b><span class="pdot pdot-unsicher"></span>${esc(inc.name)}</b><br>${tk("Nur über den Namen aufgelöst. Wir zeigen keine Vertragsdauer, solange die Zuordnung nicht eindeutig ist.")}</div>`
      : `<div class="kv">
          <div class="kvi kvi-full"><span class="k">${tk("Firma")}</span><span class="vv"><span class="v">${esc(inc.name)}</span>${
            inc.groupId?`<button class="inline-link" data-firma="${esc(inc.groupId)}">${tk("Firmenprofil ›")}</button>`:''}${
            l.eigen&&l.eigenBestaetigt===true?`<span class="oc-tag">${tk("von euch bestätigt")}</span>`:''}</span></div>
          <div class="kvi"><span class="k">${tk("Auftragnehmer seit")}</span><span class="vv">${iv(inc.seit,'echt',null,true)}</span></div>
          ${l.kette ? `<div class="kvi"><span class="k">${tk("Nachfolge-Kette")}</span><span class="vv"><span class="v">${Number(l.kette.tiefe)} Verträge in Folge${l.kette.seit?` seit ${esc(l.kette.seit)}`:''}</span> <span class="oc-tag">${tk("wiederkehrender Bedarf")}</span></span></div>` : ''}
          <div class="kvi"><span class="k">Zuschläge in CPV ${l.cpv}</span><span class="vv">${iv('47','echt',null,true)}</span></div>
        </div>`}
    </section>

    <section class="sec">
      <h4>${tk("Quelle")}</h4>
      ${(()=>{
        // Echter Quell-Link: TED-Notices → TED-Viewer (id ist die notice_id `NNNNNN_YYYY`, TED
        // nutzt den Bindestrich). Sonst der hinterlegte Vergabeportal-Link. Kein toter href="#".
        const ext = /*svg*/`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg>`;
        const isTed = /^\d+_\d{4}$/.test(String(l.id||''));
        const href = isTed ? `https://ted.europa.eu/en/notice/-/detail/${String(l.id).replace('_','-')}`
                   : (l.unterlagen && l.unterlagen.url) ? l.unterlagen.url : null;
        const label = isTed ? 'TED' : 'Vergabeportal';
        return href
          ? `<a class="tedlink" href="${esc(href)}" target="_blank" rel="noopener">${label} ${ext}</a>`
          : `<span class="v-unk">${tk("nicht verlinkt")}</span>`;
      })()}
    </section>

        <div class="prov-legend">
      <span class="pdot pdot-schaetz"></span>${tk("geschätzt")}<span class="pdot pdot-unsicher"></span>${tk("unsicher")}<span class="pl-unk">${tk("grau")}</span>${tk("unbekannt")}<span class="pl-plain">${tk("· belegte Werte ohne Markierung")}</span>
    </div>
  </div>`;
}

function renderTeilnahme(l){
  const iv = (text,src,hint,num)=>{
    const cls = (src==='unbekannt'?'v-unk ':src==='na'?'v-na ':'')+(num?'v-num':'');
    return `<span class="v ${cls}">${esc(text)}</span>${pdotT(src,hint)}`;
  };
  return `<div class="dbody dbody-ov">
    <section class="sec sec-unterlagen">${(()=>{
      const u = l.unterlagen;
      // Wasserfall-Herkunft: 'docs' = echter Unterlagen-Link, 'portal' = nur Plattform-Startseite,
      // demo-Leads tragen stattdessen einen Portal-Namen (kein url). Plattform NIE als „Unterlagen".
      const isDocs = u && (u.source==='docs' || (!u.source && u.portal));   // demo: portal-Name = Unterlagen
      const isPortal = u && u.source==='portal';
      const href = u && u.url ? u.url : '#';
      const desc = isDocs
        ? (u.portal ? `Vollständige Leistungsbeschreibung, Vertragsbedingungen und Formulare auf <b>${u.portal}</b>.`
                    : tk("Direkter Link zu den Vergabeunterlagen. Leistungsbeschreibung, Vertragsbedingungen und Formulare."))
        : isPortal
          ? tk("Kein direkter Unterlagen-Link veröffentlicht, nur die Vergabeplattform. Dort mit der Vergabenummer suchen.")
          : 'Die Bekanntmachung nennt keinen Link zu den Unterlagen.';
      const btn = isDocs
        ? `<a class="unt-btn" href="${href}" target="_blank" rel="noopener">${tk("Unterlagen öffnen")}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></a>`
        : isPortal
          ? `<a class="unt-btn unt-btn-portal" href="${href}" target="_blank" rel="noopener">${tk("Zur Vergabeplattform")}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></a>`
          : `<span class="unt-leer">${tk("kein Link")}</span>`;
      return `
      <div class="unt">
        <div class="unt-m">
          <span class="unt-t">${tk("Vergabeunterlagen")}</span>
          <span class="unt-x">${desc}${l.aufwand&&l.aufwand.eabgabe==='Pflicht'?`<br>${tk('Abgabe nur elektronisch — die Registrierung dauert und sollte früh erledigt sein.')}`:''}</span>
        </div>
        ${btn}
      </div>`;
    })()}</section>

    <section class="sec">
      <h4>${tk("Fristen")}</h4>
      <div class="kv">
        <div class="kvi"><span class="k">${tk("Frist für Rückfragen")}</span>
          <span class="vv">${l.fragefrist?iv('bis '+l.fragefrist,'echt')
            :(l.aufwand&&l.aufwand.fragefrist?iv('noch '+l.aufwand.fragefrist,'echt'):`<span class="v-unk">${tk("nicht veröffentlicht")}</span>`)}</span></div>
        <div class="kvi"><span class="k">${tk("Angebotsfrist")}</span>
          <span class="vv">${(()=>{
            // #16: echte Angebotsfrist aus den Daten — Datum + Resttage, Dringlichkeit gefärbt.
            // frist.date (aus dem Export) hat Vorrang; demo/Alt-Leads fallen auf l.tage zurück.
            const f = l.frist;
            const tage = (f && f.tage!=null) ? f.tage : l.tage;
            if(tage==null && !(f && f.date)) return `<span class="v-unk">${tk("nicht veröffentlicht")}</span>`;
            const cls = tage==null ? '' : tage<0 ? 'frist-ab' : tage<3 ? 'frist-risk' : tage<=14 ? 'frist-flag' : '';
            const rest = tage==null ? '' : tage<0 ? ' <span class="frist-t frist-ab">abgelaufen</span>'
                       : ` <span class="frist-t ${cls}">noch ${tage} ${tage===1?'Tag':'Tage'}</span>`;
            const datum = (f && f.date) ? f.date : null;
            const est = (f && f.src==='schaetz');
            // rest/voraussichtlich sind selbst erzeugtes Markup → NICHT durch iv() (das esc()t die
            // Datenwerte). Datum/Uhrzeit einzeln escapen, Markup roh anhängen.
            const body = datum
              ? `${esc(datum)}${f&&f.uhrzeit?', '+esc(f.uhrzeit)+' Uhr':''}${rest}`
              : tk('noch {n} Tage', {n: tage});
            return `<span class="v">${body}${est?' <span class="vm">voraussichtlich</span>':''}</span>${pdotT(est?'schaetz':'echt')}`;
          })()}</span></div>
        <div class="kvi kvi-full"><span class="k">${tk("Submissionstermin")}</span>
          <span class="vv">${l.submission
            ? `${iv(l.submission,'echt')}<span class="vm">${l.rahmen==='vob'?tk("öffentliche Öffnung. Teilnahme möglich, ihr seht die Mitbieter"):tk("öffentliche Angebotsöffnung")}</span>`
            : `<span class="v-unk">${tk("nicht veröffentlicht")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Bindefrist")}</span>
          <span class="vv">${l.aufwand&&l.aufwand.bindefrist?iv(l.aufwand.bindefrist,'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        </div>
    </section>

    <section class="sec">
      <h4>${tk("Zuschnitt")}</h4>
      <div class="kv">
        <div class="kvi"><span class="k">${tk("Teilbar")}</span>
          <span class="vv">${l.lose&&l.lose.length>1
            ? `${iv('ja — '+l.lose.length+' Lose','echt')}` : iv('nein — ein Gesamtlos','echt')}</span></div>
        <div class="kvi"><span class="k">${tk("Angebot auf höchstens")}</span>
          <span class="vv">${l.loseMaxAngebot?iv(l.loseMaxAngebot+' Lose','echt'):`<span class="v-na">${tk("nicht begrenzt")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Zuschlag auf höchstens")}</span>
          <span class="vv">${l.loseMaxZuschlag?iv(l.loseMaxZuschlag+' Lose','echt'):`<span class="v-na">${tk("nicht begrenzt")}</span>`}</span></div>
        <div class="kvi kvi-full"><span class="k">${tk("Bietergemeinschaft")}</span>
          <span class="vv">${l.bgKlausel?iv(l.bgKlausel,'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Nebenangebote")}</span>
          <span class="vv">${l.nebenangebote?iv(l.nebenangebote,'echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
        <div class="kvi"><span class="k">${tk("Rahmenvereinbarung")}</span>
          <span class="vv">${l.rahmenvertrag?iv(l.rahmenvertrag,'echt'):l.istRahmen?iv('ja','echt'):`<span class="v-unk">${tk("nicht angegeben")}</span>`}</span></div>
      </div>
    </section>

${l.lose && l.lose.length>1 ? (()=>{
      // Nur bei ECHTER Mehr-Los-Vergabe (>1) die Lose-Aufschlüsselung zeigen — ein Gesamtlos
      // (length≤1) ist „ganz oder gar nichttk(", da wären Einstiegsschwelle/„kleinstes Los") sinnlos.
      // Echte Lose können „Wert offen" tragen (keine Ziffern) → NaN. Auf 0 normieren,
      // damit min/Index nicht kippt (l.lose[-1] wäre undefined → Crash).
      const werte = l.lose.map(x=>parseInt(String(x.wert||'').replace(/\D/g,''),10)||0);
      const min = Math.min(...werte), minI = Math.max(0, werte.indexOf(min));
      const fmt = n => n.toLocaleString('de-DE')+' €';
      // #12: das Los, über das die Ausschreibung relevant wurde (Best-Los-Vererbung).
      const passtNr = l.bestLot ? l.bestLot.nr : null;
      return `<section class="sec">
        <h4>${tk("Lose")}<span class="cov">${l.lose.length} Teilleistungen</span></h4>
        ${passtNr!=null?`<div class="los-passt-hint">${tk("Für euch relevant ist")}<b>Los ${passtNr}</b>${l.bestLot.titel?`: ${l.bestLot.titel}`:''}${l.bestLot.region?` · ${l.bestLot.region}`:''} — die Ausschreibung erbt dessen Relevanz, auch wenn sie insgesamt größer ist.</div>`:''}
        <div class="einstieg">
          <div class="ein-m">
            <span class="ein-k">${tk("Einstiegsschwelle")}</span>
            <span class="ein-v">${fmt(min)}</span>
          </div>
          <span class="ein-x">Ihr müsst nicht auf die volle Summe von ${fmt(werte.reduce((a,b)=>a+b,0))}
          bieten. Das kleinste Los ist einzeln vergeben — <b>${l.lose[minI].titel}</b>.</span>
        </div>
        <div class="lose">
          <div class="los los-head"><span>${tk("Los")}</span><span>${tk("Leistung")}</span><span>${tk("Wert")}</span><span>${tk("Laufzeit")}</span><span>${tk("Ort")}</span></div>
          ${l.lose.map((x,i)=>`<div class="los ${i===minI?'los-min':''} ${x.nr===passtNr?'los-passt':''}">
            <span class="los-n">${x.nr}</span>
            <span class="los-t">${esc(x.titel)}${x.nr===passtNr?`<span class="los-tag los-tag-passt">${tk("passt")}</span>`:''}${i===minI?`<span class="los-tag">${tk("kleinstes")}</span>`:''}</span>
            <span class="los-w">${x.wert}</span>
            <span class="los-d">${x.dauer}</span>
            <span class="los-r">${x.region}</span>
          </div>`).join('')}
        </div>
        ${l.optionen||l.verlaengerung?`<div class="note-box" style="margin-top:var(--s3)">
          <b>${tk("Über die Grundlaufzeit hinaus:")}</b> ${[l.optionen?'Optionen vorgesehen':null,
          l.verlaengerung?`Verlängerung möglich (${l.verlaengerung})`:null].filter(Boolean).join(' · ')}.
          Der tatsächliche Vertragswert kann deutlich über der Summe der Lose liegen.</div>`:''}
      </section>`;
    })() : ''}

    
    ${l.lose && l.lose.length && l.loseMaxZuschlag ? `<section class="sec" id="an-partner">
      <h4>${tk("Partner nötig?")}</h4>

      <div class="pnfacts">
        <div class="pnf">
          <span class="pnf-k">${tk("Lose insgesamt")}</span>
          <span class="pnf-v"><span class="v-num">${l.lose.length}</span></span></div>
        <div class="pnf">
          <span class="pnf-k">${tk("Ihr dürft anbieten auf")}</span>
          <span class="pnf-v"><span class="v-num">${l.loseMaxAngebot}</span></span></div>
        <div class="pnf pnf-hero">
          <span class="pnf-k">${tk("Ihr könnt höchstens gewinnen")}</span>
          <span class="pnf-v"><span class="v-num">${l.loseMaxZuschlag}</span></span></div>
      </div>
      <p class="pn-deut">${tk("Selbst wenn ihr alles anbietet, bekommt ihr höchstens")}<b>${l.loseMaxZuschlag} von ${l.lose.length} Losen</b>. Wer den Gesamtauftrag will,
      braucht Partner — wer allein bietet, kalkuliert ${l.lose.length-l.loseMaxZuschlag} Lose umsonst.</p>

      ${(()=>{ const frei=isFreeLimit();
        if(l.netzSuchend==null) return '';
        return `<div class="nz-vor ${frei?'lock':''}">
          <span class="nz-v-k">${tk("Firmen, die hier schon einen Partner suchen")}</span>
          <span class="nz-v-v">${frei?`<span class="nz-blur">${l.netzSuchend}</span>`:`<span class="v-num">${l.netzSuchend}</span>`}</span>
          <span class="nz-v-x">${frei
            ? `${tk('Im Pro-Zugang seht ihr das,')} <b>${tk('bevor')}</b> ${tk('ihr euch selbst meldet.')}`
            : l.netzSuchend>=4 ? tk("Hier bildet sich bereits ein Feld. Je früher ihr dabei seid, desto mehr Lose bleiben übrig.")
            : tk("Noch wenig Bewegung. Wer sich früh meldet, hat die freie Wahl bei den Losen.")}</span>
        </div>`;})()}

      ${(()=>{
        /* ⚠ HIER STAND „zugelassen" — IMMER. Ohne einen einzigen Beleg, und daneben eine
           erfundene Haftungsform. Wer als Bieter darauf baut und sich eine Partnerschaft
           organisiert, hat es von uns gehoert. Nur simap veroeffentlicht die Angabe
           strukturiert (55 % seiner Vorgaenge); eForms hat bieterseitig kein Feld mit
           Substanz. Deshalb dreiwertig: erlaubt / nicht erlaubt / keine Angabe. */
        const bg = (l.anf||{}).bietergemeinschaft;
        const wert = bg === true ? tk("zugelassen")
                   : bg === false ? tk("nicht zugelassen")
                   : tk("keine Angabe in der Bekanntmachung");
        return `<div class="pn-bg${bg==null?' pn-bg-offen':''}">
        <span class="pn-bg-k">${tk("Bietergemeinschaft")}</span>
        <span class="pn-bg-v">${wert}</span>
        <span class="pn-bg-x">${esc(tk(l.bgForm||''))}</span>
      </div>`;})()}

      ${!angaben.partner ? `<div class="pn-off">
        <div><b>${tk("Partner finden?")}</b>
        <span>${tk("Aktiviert das Netzwerk, dann könnt ihr euch für solche Ausschreibungen melden, und wir prüfen, wer euch ergänzt.")}</span></div>
        <button class="pn-btn" data-tonetz>${tk("Zum Netzwerk")}</button>
      </div>`
      : !netzInteresse.has(l.id) ? `<div class="pn-off pn-wahl">
        <div><b>${tk("Sucht ihr hier einen Partner?")}</b>
        <span>${tk("Hakt die Lose an, die ihr selbst abdeckt. Wir suchen dann eine Firma, die genau die übrigen kann. Sichtbar werdet ihr nur für solche Firmen.")}</span>
        <div class="nz-loswahl">${(l.lose||[]).map(x=>`<button class="nz-los ${netzLose.has(l.id+':'+x.nr)?'on':''}"
          data-netzlos="${l.id}:${x.nr}">${tk("Los")} ${x.nr}<i>${esc(x.titel||'')}</i></button>`).join('')}</div></div>
        <button class="pn-btn" data-netzint="${l.id}" ${[...netzLose].some(k=>k.startsWith(l.id+':'))?'':'disabled'}
          >${tk("Interesse bekunden")}</button>
      </div>`
      : l.netzPartner ? (()=>{ const frei = netzFreigabe.has(l.id); return `<div class="nz-match">
        <div class="nz-m-h"><b>${tk("Eine Firma ergänzt euch")}</b><span class="nz-m-s">seit ${l.netzPartner.seit}</span></div>
        <div class="nz-m-r">
          <span class="nz-m-n">${frei&&l.netzPartner.n?esc(l.netzPartner.n)
            :`<span class="nz-blur">${tk("Firmenname sichtbar nach Freigabe")}</span>`}</span>
          <span class="nz-m-f">${esc(l.netzPartner.feld||tk("Feld nicht hinterlegt"))}</span>
          <span class="nz-m-g">${esc(l.netzPartner.groesse||'')}</span>
          <span class="nz-m-d">${tk("deckt {n} Lose")
            .replace('{n}', l.netzPartner.deckung)}</span>
        </div>
        <p class="nz-m-x">${tk("Zusammen kommt ihr auf")}<b>${(l.netzDeckung||0)+l.netzPartner.deckung} von ${(l.lose||[]).length} Losen</b>.
        ${frei&&l.netzPartner.n?tk("Beide Seiten haben freigegeben, die Kontaktdaten liegen jetzt bei euch beiden.")
             :frei?tk("Ihr habt freigegeben. Sichtbar wird der Name erst, wenn die andere Seite ebenfalls freigibt.")
             :l.netzPartner.freigabeGegenseite?tk("Die andere Seite hat bereits freigegeben. Gebt ihr auch frei, tauschen wir die Kontakte aus.")
             :tk("Gebt den Kontakt frei, wenn ihr sprechen wollt. Die andere Seite muss ebenfalls freigeben.")}</p>
        ${frei?`<div class="nz-kontakt"><b>${esc(l.netzPartner.n||tk("Firma ohne Namen in unseren Daten"))}</b>
          <span>${l.netzPartner.kontakt ? esc(l.netzPartner.kontakt)
            : tk("Kontaktdaten liegen uns nicht vor, die Firma erreicht ihr über die Vergabestelle.")}</span></div>`
        :`<button class="nz-frei" data-netzfrei="${l.id}">${tk("Kontakt freigeben")}</button>`}
      </div>`;})()
      : `<div class="nz-wait">${tk("Ihr habt euch gemeldet. Noch keine ergänzende Firma. Wir melden uns, sobald jemand andere Lose abdeckt als ihr.")}<button class="nz-rueck" data-netzint="${l.id}">${tk("Meldung zurückziehen")}</button></div>`}
    </section>` : ''}

    <section class="sec">
      <h4>${tk("Was die Bekanntmachung nicht beantwortet")}</h4>
      <p class="offen-x">${tk("Diese Fragen entscheiden über die Vertragsphase. Beantwortet werden sie erst in den Unterlagen, nicht in der Bekanntmachung. Wir zeigen sie hier, damit ihr wisst, wonach ihr suchen müsst.")}</p>
      <div class="offen">
        <div class="off-g"><span class="off-t">${tk("Zahlung")}</span>
          <span class="off-x">${tk("Zahlungsziele, Abschlagszahlungen, Skonto, Sicherheitseinbehalt")}</span></div>
        <div class="off-g"><span class="off-t">${tk("Leistung")}</span>
          <span class="off-x">${tk("Ausführungsfristen, Zwischentermine, Abnahmen, Mitwirkungspflichten")}</span></div>
        <div class="off-g"><span class="off-t">${tk("Qualität und Haftung")}</span>
          <span class="off-x">${tk("Vertragsstrafen, Mängelhaftung, Gewährleistungsfristen, Service-Level")}</span></div>
        <div class="off-g"><span class="off-t">${tk("Ausstieg")}</span>
          <span class="off-x">${tk("Kündigungsrechte, Sonderkündigung, Folgen bei Nichterfüllung")}</span></div>
      </div>
      <span class="offen-hin">${tk("Den Link zu den Unterlagen findest du oben in diesem Tab.")}</span>
    </section>

  </div>`;
}

function renderAnalyse(l){
  const nav = [
    ['bewertung','Bewertung'],
    ['zuschlag','Zuschlagskriterien'],
    ['vergleich','Direktvergleich'],
    ['anforderungen','Anforderungs-Check'],
    ['luecke',tk("Lücke")],
    ['vertraege',tk("Eure Verträge")],
    ['historie','Wettbewerbs-Historie'],
    ['kontakt',tk("Nächster Schritt")],
  ];
  // Sprung-Submenu (ananav) bewusst entfernt — es wanderte beim Scrollen nicht mit; der
  // Bewertung-Tab läuft jetzt als durchgehender Fließtext (Sven, 2026-07-30). `nav` bleibt als
  // Abschnitts-Referenz erhalten, falls später ein sticky Menü gewünscht wird.
  void nav;
  return `<div class="dbody dbody-ana">
    <div class="anagrid">

    <section class="sec" id="an-bewertung" data-sec="bewertung">
      <h4>${tk("Bewertung")}</h4>
      ${(()=>{
        // #26 Handlungsempfehlung (ersetzt #19). Kaskade A/B je Datenzustand + Abdeckung, plus
        // Begründungskette E1–E10 und Zusätze. Nie ein Verdikt ohne offengelegte Bedingungen (§7).
        const rec = recommend(l, userProfile, { ownBuyers: userContracts.map(c=>c.buyer_name).filter(Boolean) });
        const CLS = { gruen:'go', blau:'def', neutral:'open', gedaempft:'skip' };
        const kette = begruendungskette(rec.evals);
        const zTags = rec.zusaetze.map(z=>`<span class="rec-z">${esc(tk(z.t))}</span>`).join('');
        let head;
        if(rec.empfehlung){
          const b = rec.empfehlung;
          head = `<div class="rec-verdict rec-${CLS[b.cls]}"><span class="rec-label">${esc(tk(b.label))}</span>`
            + (b.gruende&&b.gruende.length?`<span class="rec-grund">${esc(b.gruende.map(tk).join(' · '))}</span>`:'')
            + (b.frage?`<span class="rec-frage">${esc(tk(b.frage))}</span>`:'') + `</div>`
            + (b.schritt?`<div class="rec-step">${tk("Nächster Schritt:")}<b>${esc(tk(b.schritt))}</b></div>`:'');
        } else {
          const a = rec.einordnung;
          const hint = rec.gesperrt==='keine_unterlagen' ? tk("Für eine Empfehlung fehlen die Vergabeunterlagen.")
            : rec.gesperrt==='kaltstart' ? tk("Für eine Empfehlung fehlt die Mindestabdeckung im Eignungsprofil.")
            : rec.gesperrt==='kein_profil' ? tk("Für eine Empfehlung fehlt das Eignungsprofil.") : '';
          head = `<div class="rec-verdict rec-${CLS[a.cls]}"><span class="rec-label">${esc(tk(a.label))}</span>`
            + (a.gruende&&a.gruende.length?`<span class="rec-grund">${esc(a.gruende.map(tk).join(' · '))}</span>`:'') + `</div>`
            + (hint?`<div class="rec-hint">${esc(hint)}</div>`:'');
        }
        return `<div class="rec26">${head}`
          + (zTags?`<div class="rec-zusaetze">${zTags}</div>`:'')
          + `<table class="rec-kette"><tbody>${kette.map(k=>`<tr><td class="rec-e">${k.E}</td><td class="rec-kl">${esc(tk(k.label))}</td><td class="rec-kz">${esc(tk(k.zustand))}</td><td class="rec-kq">${esc(tk(k.quelle))}</td></tr>`).join('')}</tbody></table></div>`;
      })()}
      <div class="scores">
        <div class="score" data-level="${l.relevanz}">
          <span class="name">${tk("Relevanz")}</span>
          ${bandMeter(l.relevanz)}
          <span class="scoreword">${l.relevanz==='na'?'—':l.relevanz}</span>
          ${passungAchse(l)}
        </div>
        <div class="score" data-level="${l.wechsel}">
          <span class="name" id="chanceName">${istEigen(l)?tk("Verdrängungs-Risiko"):'Wechsel-Chance'}</span>
          ${bandMeter(l.wechsel, true)}
          <span class="scoreword">${l.wechsel==='na'?'—':tk(l.wechsel)}</span>
        </div>
        <div class="score" data-level="${aufwandStufe(l).stufe}">
          <span class="name">${tk("Angebotsaufwand")}</span>
          ${bandMeter(aufwandStufe(l).stufe, true)}
          <span class="scoreword">${aufwandStufe(l).stufe==='na'?'—':aufwandStufe(l).stufe}</span>
        </div>
      </div>

      ${(()=>{ const a=aufwandStufe(l);
        const R={hoch:2,mittel:1,niedrig:0,na:-1}[l.relevanz];
        const A={hoch:2,mittel:1,niedrig:0,na:-1}[a.stufe];
        let satz;
        if(A<0) satz = tk("Zum Aufwand wissen wir zu wenig, die Bekanntmachung nennt weder Bürgschaft noch Bindefrist.");
        else if(R>=2 && A<=0) satz = tk("Passt gut und kostet wenig. Das ist die Sorte Ausschreibung, die man mitnimmt.");
        else if(R>=2 && A>=2) satz = tk("Passt gut, kostet aber viel. Lohnt sich, wenn ihr die Kapazität habt, sonst blockiert es zwei andere Angebote.");
        else if(R<=0 && A>=2) satz = tk("Passt mäßig und kostet viel. Hier würden wir abraten, wenn ihr Alternativen habt.");
        else satz = tk("Mittlere Passung bei mittlerem Aufwand, entscheidet die Auslastung.");
        // Profil-Blocker überschreibt den Auslastungs-Satz: eine harte Grenze zählt mehr als die Aufwand-Abwägung.
        const m = l.match;
        const buerg = m && m.blocker.find(b=>b.art==='buergschaft');
        let block = '';
        if(buerg) block = `<span class="ds-block"><b>K.-o.:</b> ${buerg.text}</span>`;
        else if(m && m.partner) block = `<span class="ds-block">${tk("Nur mit Partner realistisch, der Auftrag übersteigt eure Alleingrenze.")}</span>`;
        return `<div class="dreisatz">
          <span class="ds-t">${tk("Zusammengenommen")}</span>
          <span class="ds-x">${satz}</span>
          ${block}
          ${a.treiber.length?`<span class="ds-tr">Aufwandstreiber: ${a.treiber.join(' · ')}</span>`:''}
          ${a.stufe!=='na'&&a.bekannt<4?`<span class="ds-cov">Aus ${a.bekannt} von 4 Angaben — die übrigen stehen nicht in der Bekanntmachung.</span>`:''}
        </div>`;})()}

      ${(()=>{ const a=l.aufwand; if(!a) return '';
        const z=[[tk('Bietungsbürgschaft'),a.buergschaft],[tk('Bindefrist'),a.bindefrist],
                 [tk('Angebotsabgabe'),a.eabgabe],[tk('Lebensläufe gefordert'),a.lebenslauf]];
        return `<div class="aufl">${z.map(([k,v])=>`<div class="auf-r">
          <span class="auf-k">${k}</span>
          <span class="auf-v ${v==null?'unk':''}">${v==null?tk("nicht angegeben"):v}</span>
        </div>`).join('')}</div>`;})()}
      ${(()=>{ const lue = bieterLuecke(l); if(!lue) return '';
        return `<div class="score-caveat">
          <span class="pdot pdot-schaetz"></span>
          <span>${tk(lue.lang)} ${tk("Die Bewertung stützt sich auf Vertragsart, Rechtsrahmen und Branche und ist entsprechend gröber als bei Vergaben mit bekannter Bieterzahl.")}</span>
        </div>`;})()}
      <div class="score-note">
        <span class="sn-label">${tk("Konkurrenz zuletzt")}</span>
        <span class="sn-val">${l.konk.src==='na'||l.konk.src==='unbekannt'
          ? `<span class="unk">${l.konk.wert==='n/a'?tk("nicht anwendbar. Neuvergabe"):tk("von der Vergabestelle nicht angegeben")}</span>`
          : val(l.konk.wert, l.konk.src, l.konk.hint)}</span>
        <span class="sn-txt">${l.konk.src==='echt'||l.konk.src==='schaetz'
          ? (l.konk.stufe==='gering'?tk("Wenige Bieter beim letzten Mal, das stützt die Chance."):tk("So viele boten in der Vorgänger-Vergabe. Dieser Wert fließt bereits in die Chance oben ein."))
          : tk("Ohne Bieterzahl aus einem Vorgänger bleibt dieser Baustein der Chance offen.")}</span>
      </div>
    </section>

    ${l.hasCmp ? `
    ${(()=>{
      const z = l.zuschlag;
      if(!z || !z.length) return `<section class="sec" id="an-zuschlag" data-sec="zuschlag">
        <h4>${tk("Zuschlagskriterien")}</h4>
        <div class="note-box"><b>${tk("Nicht veröffentlicht.")}</b>${tk("Bei knapp jeder fünften Ausschreibung fehlen die Kriterien in der Bekanntmachung, sie stehen dann nur in den Vergabeunterlagen.")}</div>
      </section>`;
      const ohneGew = z.some(x=>x.pct==null);
      const preis = (z.find(x=>x.art==='preis')||{}).pct;
      const deutung = ohneGew
        ? tk("Wir wissen, worauf bewertet wird, aber nicht mit welchem Gewicht, das steht nur in den Vergabeunterlagen.")
        : preis===100 ? tk("Reiner Preiswettbewerb. Das günstigste zulässige Angebot gewinnt. Konzeptarbeit zahlt sich hier nicht aus.")
        : preis!=null && preis<=50 ? `Der Preis entscheidet nur zu ${preis} %. Über die restlichen ${100-preis} % könnt ihr euch mit Konzept und Referenzen absetzen.`
        : `Der Preis wiegt ${preis} %. Konzeptarbeit hilft, den Ausschlag gibt aber die Kalkulation.`;
      return `<section class="sec" id="an-zuschlag" data-sec="zuschlag">
        <h4>${tk("Zuschlagskriterien")}</h4>
        ${ohneGew?'':`<div class="zbar">${z.map(x=>
          `<i class="zseg z-${x.art}" style="width:${x.pct}%" title="${esc(x.label)}: ${x.pct} %"></i>`).join('')}</div>`}
        <div class="zlist">${z.map(x=>`<span class="zitem">
          <i class="zdot z-${x.art}"></i>${x.label}
          <b>${x.pct!=null?x.pct+' %':`<span class="v-unk">${tk("ohne Angabe")}</span>`}</b></span>`).join('')}</div>
        ${(l.zuschlagNamen||[]).length ? `<div class="zname">
          <span class="zname-k">${tk("So nennt die Vergabestelle sie")}</span>
          ${l.zuschlagNamen.map(n=>`<span class="zname-i">${esc(n)}</span>`).join('')}
        </div>` : ''}
        <p class="zdeut">${deutung}</p>
      </section>`;
    })()}

    <section class="sec" id="an-vergleich" data-sec="vergleich">
      <h4>${tk("Direktvergleich")}<span class="cov">im Feld ${cpvLabel(l)}, nach Anzahl Zuschlägen</span></h4>
      <table class="cmp">
        <thead><tr><th>${tk("Kennzahl")}</th><th>${tk("Ihr")}</th><th></th><th>${l.incumbent ? l.incumbent.name.split(' ')[0] : '—'}</th></tr></thead>
        <tbody>
          ${(()=>{ const inc=l.incumbent, cpv4=String(l.cpv||'').slice(0,4);
            const uw = (userProfile && userProfile.cpvWins && userProfile.cpvWins[cpv4]);
            const me = v => v==null?'<td class="me num" style="color:var(--ink-300)">—</td>':`<td class="me num">${v}</td>`;
            const edge = (m,t)=> (m==null||t==null)?'<td></td>':(m>t?'<td class="edge up">&#9656;</td>':m<t?'<td class="edge down">&#9666;</td>':'<td class="edge"></td>');
            // #14 Floor-Semantik: die Win-Zahl ist ein Gruppen-Aggregat. Ist die Firmen-
            // Auflösung nicht hoch-konfident, kann Fragmentierung Zuschläge auf Dubletten
            // streuen → die Zahl ist eine UNTERGRENZE, nicht der exakte Wert.
            const floor = inc.src==='unsicher' || (inc.conf!=null && inc.conf<0.9);
            const winCell = inc.wins==null ? '—'
              : floor ? `<span title="${esc(tk("Untergrenze. Bei unsicherer Firmen-Auflösung können Zuschläge auf Namensvarianten liegen; die echte Zahl kann höher sein"))}">&#8805;&#8202;${inc.wins}</span>`
              : String(inc.wins);
            const r=[];
            r.push(`<tr><th>Zuschläge im Feld (CPV ${cpv4})</th>${me(uw)}${edge(uw,inc.wins)}<td class="them num">${winCell}</td></tr>`);
            r.push(`<tr><th>${tk("Marktanteil im Feld")}</th>${me(null)}<td></td><td class="them num">${inc.marktanteil!=null?(floor?'&#8805;&#8202;':'')+inc.marktanteil+' %':'—'}</td></tr>`);
            r.push(`<tr><th>${tk("Marktrang im Feld")}</th>${me(null)}<td></td><td class="them num">${inc.rang!=null?'#'+inc.rang:'—'}</td></tr>`);
            if(inc.trend!=null) r.push(`<tr><th>${tk("Trend (Vorjahr)")}</th>${me(null)}<td></td><td class="them num ${inc.trend>0?'up':inc.trend<0?'down':''}">${inc.trend>0?'+':''}${inc.trend} %</td></tr>`);
            return r.join(''); })()}
        </tbody>
      </table>
      <div class="cmpfoot">
        <span>${l.incumbent.seit?tk('Amtsinhaber seit {j}', {j: l.incumbent.seit}):tk("Amtsinhaber im Feld")}${l.incumbent.src==='unsicher'?tk(" · nur über den Namen erkannt"):''}${(l.incumbent.src==='unsicher'||(l.incumbent.conf!=null&&l.incumbent.conf<0.9))?' · &#8805; = Untergrenze (Firmen-Fragmentierung möglich)':''}</span>
        <span>${(userProfile&&userProfile.cpvWins&&userProfile.cpvWins[String(l.cpv||'').slice(0,4)]!=null)?tk("Zahlen: Zuschläge, 3-J-Fenster"):'Eure Feld-Zahlen: nach Firmen-Zuordnung'}</span>
      </div>
    </section>` : `
    <section class="sec" id="an-vergleich" data-sec="vergleich">
      <h4>${tk("Direktvergleich")}</h4>
      ${l.incumbent ? `<div class="note-box"><b>Wahrscheinlicher Amtsinhaber: ${esc(l.incumbent.name)}.</b>
      Die Firmen-Auflösung ist hier zu unsicher${l.incumbent.conf!=null?` (Konfidenz ${Math.round(l.incumbent.conf*100)} %)`:''}
      für belastbare Feld-Zahlen — wir zeigen sie deshalb nicht, statt eine erfundene Statistik zu behaupten.
      Der Name kommt aus der letzten Zuschlagsbekanntmachung, nur über die Schreibweise erkannt.</div>`
      : `<div class="note-box"><b>${tk("Offenes Feld.")}</b>${tk("Ohne Amtsinhaber gibt es niemanden zu vergleichen, alle Bieter starten hier gleich.")}</div>`}
    </section>`}

    <section class="sec" id="an-anforderungen" data-sec="anforderungen">
      <h4>${tk("Anforderungs-Check")}</h4>
      <div class="reqs">
        ${(()=>{ const r = l.rahmen && RAHMEN_NACHWEIS[l.rahmen]; if(!r) return '';
          const hab = (angaben.nachweise||[]).some(x=>
            x.toLowerCase().includes('präqualifikation') && (l.rahmen==='vob'?x.toLowerCase().includes('bau'):true));
          const hart = l.rahmen==='vob';
          return `<div class="req req-rahmen">
            <span class="mk ${hab?'y':hart?'n':'q'}">${hab?'&#10003;':hart?'&#10007;':'?'}</span>
            <span class="code">${RAHMEN[l.rahmen].kurz}</span>
            <span class="lbl">${r.n}</span>
            <span class="st">${hab?'In eurem Profil hinterlegt'
              : hart?tk("Fehlt in eurem Profil, ohne diesen Nachweis kein Angebot")
              : 'Nicht hinterlegt — hier meist nachreichbar'}</span>
          </div>`;})()}
        ${(()=>{ const a = l.anf; if(!a) return '';
          // #15 Weg A — strukturierte Anforderungen aus eForms (echt, wo vorhanden; fehlende
          // werden weggelassen statt als „nicht veröffentlicht" zu rauschen).
          const EIG = {'tp-abil':tk("technische Leistungsfähigkeit"),'sui-act':tk("Befähigung zur Berufsausübung"),'ef-stand':tk("wirtschaftliche Leistungsfähigkeit")};
          const rows=[];
          if(a.buergschaft===true){
            const hat = userProfile && userProfile.buergschaft!=null;
            rows.push(`<div class="req"><span class="mk ${hat?'y':'q'}">${hat?'&#10003;':'?'}</span>
              <span class="code">${tk("Bürgschaft")}</span><span class="lbl">${tk("Sicherheit gefordert")}</span>
              <span class="st">${hat?tk("Euer Bürgschaftsrahmen ist hinterlegt"):tk("Hinterlegt euren Rahmen, dann prüfen wir die Höhe")}</span></div>`);
          } else if(a.buergschaft===false){
            rows.push(`<div class="req"><span class="mk y">&#10003;</span><span class="code">${tk("Bürgschaft")}</span>
              <span class="lbl">${tk("keine gefordert")}</span><span class="st">${tk("Keine Sicherheit verlangt")}</span></div>`);
          }
          if(a.nebenangebote!=null) rows.push(`<div class="req"><span class="mk i">i</span>
            <span class="code">${tk("Nebenangebote")}</span><span class="lbl">${a.nebenangebote?'zugelassen':tk("nicht zugelassen")}</span>
            <span class="st">${a.nebenangebote?tk("Alternative Lösungen möglich"):tk("Nur das ausgeschriebene Konzept")}</span></div>`);
          if(a.bindefristTage) rows.push(`<div class="req"><span class="mk i">i</span>
            <span class="code">${tk("Bindefrist")}</span><span class="lbl">${a.bindefristTage} Tage</span>
            <span class="st">${tk("So lange bindet euer Angebot nach Abgabe")}</span></div>`);
          if(a.eignung && a.eignung.length) rows.push(`<div class="req"><span class="mk i">i</span>
            <span class="code">${tk("Eignung")}</span><span class="lbl">${a.eignung.map(e=>EIG[e]||e).join(' · ')}</span>
            <span class="st">${tk("Im Angebot nachzuweisen")}</span></div>`);
          if(!rows.length) return '';
          return `<div class="reqgroup-h">${tk("Strukturierte Anforderungen")}<span class="prov-echt">${tk("aus der Bekanntmachung")}</span></div>`+rows.join('');
        })()}
        ${(()=>{ const m = l.match;
          if(!m || m.relevanz==='na') return `<div class="req req-noprofile">
            <span class="mk q">?</span>
            <span class="lbl">${tk("Ohne hinterlegtes Profil können wir die Passung nicht prüfen. Wählt oben eine Testsicht oder richtet euer Firmenprofil ein.")}</span></div>`;
          const MK = {ok:['y','&#10003;'], teil:['q','~'], no:['n','&#10007;'], unbekannt:['q','?']};
          const WERT = {feld:[l.cpv, cpvLabel(l)], region:['Region', l.region], vol:['Volumen', l.volumen.wert]};
          const rows = m.teile.map(t=>{ const [cls,sym]=MK[t.status]||['q','?']; const [code,lbl]=WERT[t.dim]||['',''];
            return `<div class="req"><span class="mk ${cls}">${sym}</span>
              <span class="code">${code}</span><span class="lbl">${lbl}</span><span class="st">${t.text}</span></div>`;}).join('');
          const blk = m.blocker.map(b=>{ const rot = b.art==='buergschaft';
            return `<div class="req req-blk"><span class="mk ${rot?'n':'q'}">${rot?'&#10007;':'!'}</span>
              <span class="lbl">${b.text}</span></div>`;}).join('');
          const ok = m.teile.filter(t=>t.status==='ok').length;
          return rows + blk + `<div class="reqsum"><b>${ok} von ${m.teile.length} Kriterien erfüllt</b>${m.partner?tk(" · nur mit Partner realistisch"):''}</div>`;
        })()}
      </div>
    </section>

    <section class="sec" id="an-luecke" data-sec="luecke">
      <h4>${tk("Lücke")}</h4>
      ${(()=>{ const m = l.match;
        if(!m || m.relevanz==='na') return `<div class="note-box">${tk("Ohne hinterlegtes Profil gibt es nichts abzugleichen. Richtet euer Firmenprofil ein, dann zeigen wir hier, woran dieser Lead scheitert oder passt.")}</div>`;
        // Die härteste Lücke zuerst: harter Blocker > Feld > Region > Volumen
        const buerg = m.blocker.find(b=>b.art==='buergschaft');
        const feld  = m.teile.find(t=>t.dim==='feld' && t.status!=='ok');
        const reg   = m.teile.find(t=>t.dim==='region' && t.status==='no');
        if(buerg) return `<div class="note-box gap"><b>${tk("Bürgschaft übersteigt euren Rahmen.")}</b><br>
          ${buerg.text} Hinterlegt einen höheren Rahmen oder tretet mit einem Partner an.
          <div class="acts"><button>${tk("Rahmen anpassen")}</button><button>${tk("Trifft nicht zu")}</button></div></div>`;
        if(feld && feld.status==='no') return `<div class="note-box gap">
          <b>${tk("Dieses Feld liegt außerhalb eurer Schwerpunkte.")}</b><br>
          ${cpvLabel(l)} (CPV ${l.cpv}) gehört nicht zu euren hinterlegten Feldern. Wenn ihr das abdeckt,
          trag es nach — dann steigt die Relevanz dieses und ähnlicher Leads.
          <div class="acts"><button>${tk("Feld ergänzen")}</button><button>${tk("Trifft nicht zu")}</button></div></div>`;
        if(feld && feld.status==='teil') return `<div class="note-box gap">
          <b>${tk("Nachbarfeld, kein voller Treffer.")}</b><br>
          ${cpvLabel(l)} grenzt an eure Schwerpunkte, ist aber keiner davon. Solche Leads zeigen wir
          abgeschwächt. Trag das Feld als Schwerpunkt nach, wenn ihr es voll bedient.
          <div class="acts"><button>${tk("Als Schwerpunkt setzen")}</button><button>${tk("Trifft nicht zu")}</button></div></div>`;
        if(reg) return `<div class="note-box gap"><b>${tk("Außerhalb eures Gebiets.")}</b><br>${tk("Der Leistungsort liegt nicht in euren hinterlegten Regionen. Falls ihr dort tätig seid, erweitert euer Gebiet, sonst bleibt dieser Lead nachrangig.")}<div class="acts"><button>${tk("Region erweitern")}</button><button>${tk("Trifft nicht zu")}</button></div></div>`;
        if(m.partner) return `<div class="note-box">
          <b>${tk("Passt fachlich, aber groß.")}</b> ${cpvLabel(l)} liegt in eurem Feld, das Volumen übersteigt
          aber eure Alleingrenze. Realistisch nur mit Partner; im Netzwerk-Tab findet ihr Kandidaten.</div>`;
        return `<div class="note-box"><b>${tk("Keine Lücke.")}</b>${tk("Feld, Region und Volumen passen zu eurem Profil. Das ist die Sorte Lead, die oben in eurer Liste stehen soll.")}</div>`;
      })()}
    </section>

    ${(()=>{
      // Eigene Verträge bei DIESEM Auftraggeber (Name-Substring-Match gegen user_contracts).
      const bn = String(l.buyer||l.buyerShort||'').toLowerCase();
      const eigene = bn ? userContracts.filter(c=>{ const cb=String(c.buyer_name||'').toLowerCase();
        return cb && (cb.includes(bn.slice(0,18)) || bn.includes(cb.slice(0,18))); }) : [];
      const fmtE = v => v==null ? null : (v>=1e6 ? (v/1e6).toFixed(1).replace('.',',')+' Mio €' : Math.round(v).toLocaleString('de-DE')+' €');
      if(eigene.length) return `
      <section class="sec" id="an-vertraege" data-sec="vertraege">
        <h4>Eure Verträge bei ${esc(l.buyerShort)}</h4>
        <div class="contracts">
          ${eigene.map(c=>`<div class="ct"><span class="t">${esc(c.titel||c.buyer_name||'Vertrag')}${c.is_framework?' <span class="st-tag">Rahmen</span>':''}</span>
            <span class="v">${c.value_euro?fmtE(c.value_euro):'—'}</span>
            <span class="e">${c.end_date?'bis '+new Date(c.end_date).toLocaleDateString('de-DE',{month:'2-digit',year:'numeric'}):''}</span></div>`).join('')}
          <div class="reqsum">${eigene.length===1?'Ein laufender Vertrag':eigene.length+tk(" laufende Verträge")} — ihr kennt diesen Auftraggeber bereits.</div>
        </div>
      </section>`;
      return `
      <section class="sec">
        <h4>Eure Verträge bei ${esc(l.buyerShort)}</h4>
        <div class="note-box">${tk("Kein hinterlegter Vertrag bei dieser Vergabestelle. Gewonnene Aufträge könnt ihr über „Als gewonnen markieren\" erfassen, dann erscheinen sie hier und im Strategie-Tab.")}</div>
      </section>`;
    })()}

    <section class="sec" id="an-historie" data-sec="historie">
      <h4>${tk("Wettbewerbs-Historie")}</h4>
      <div class="note-box build">
        <b>${tk("In Aufbau.")}</b>${tk("Verdrängungs-Bilanz, Verlustquote und Vertragskette brauchen eine verifizierte Vorgänger-Verknüpfung. Aktuell sind rund 35 % der Verträge sicher verkettbar. Zu wenig, um daraus für diesen Lead eine belastbare Aussage zu machen. Wir zeigen hier nichts, bevor es stimmt.")}</div>
    </section>

    <section class="sec" id="an-kontakt" data-sec="kontakt">
      <h4>${tk("Nächster Schritt")}<span class="cov">${tk("Direktkontakt zur Vergabestelle")}</span></h4>
      <div class="contact">
        <div class="ct-row"><span class="ct-k">${tk("Ansprechpartner")}</span><span class="ct-v">${esc(l.buyer)} · Referat Z 3</span></div>
        <div class="ct-row"><span class="ct-k">${tk("E-Mail")}</span><span class="ct-v"><a class="tedlink" href="mailto:vergabe@${l.buyerShort.toLowerCase().replace(/[^a-z]/g,'')}.bund.de">vergabe@${l.buyerShort.toLowerCase().replace(/[^a-z]/g,'')}.bund.de</a></span></div>
        <div class="ct-row"><span class="ct-k">${tk("Frist für Rückfragen")}</span><span class="ct-v">${
          l.aufwand&&l.aufwand.fragefrist ? val('noch '+l.aufwand.fragefrist,'echt',tk("Aus der Bekanntmachung, nicht geschätzt."))
          : l.tage!=null ? val((l.tage-7)+' Tage','schaetz',tk("Nicht veröffentlicht. Übliche Rückfragefrist endet eine Woche vor Angebotsschluss."))
          : '—'}</span></div>
        <p class="ct-note">${tk("Wer früh Rückfragen stellt, prägt oft die Leistungsbeschreibung mit. Kontakt aufnehmen, bevor die Frist läuft.")}</p>
      </div>
    </section>
    </div>

    <div class="legend" style="margin-top:var(--s6);padding-top:var(--s4);border-top:1px solid var(--line)">
      <span><i class="lg-echt"></i>${tk("gemessen")}</span>
      <span><i class="lg-sch"></i>${tk("geschätzt")}</span>
      <span><i class="lg-uns"></i>${tk("unsicher")}</span>
      <span><i class="lg-unb"></i>${tk("unbekannt")}</span>
    </div>
  </div>`;
}

function gateCard(titel, text){
  return `<aside class="gateside">
    <div class="gatecard">
      <span class="gc-lock"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/></svg></span>
      <span class="gc-t">${titel}</span>
      <span class="gc-x">${text}</span>
      <button class="gc-btn" data-upgrade>${tk("Freischalten")}</button>
      <span class="gc-p">${tk("29 € / Monat · jederzeit kündbar")}</span>
    </div>
  </aside>`;
}

const REGIONS = {
  ffm: {
    name:"Frankfurt am Main", kreis:'Kreisfreie Stadt', ew:'749.596',
    vergeben:'9.571', offen:'107', stellen:'128',
    volumen:'2.093 Mio €', coverage:'13 %', single:'32 %',
    je1000:'12,77',
    betriebe:'591', beschaeftigte:'8.333', jeBetrieb:'16,19',
    genehmigungen:'347', invKopf:'616 €', schuldenKopf:'3.543 €',
    kontext:true,
  },
  bonn: {
    name:'Bonn', kreis:'Kreisfreie Stadt', ew:'321.680',
    vergeben:'2.391', offen:'557', stellen:'196',
    volumen:'1.019 Mio €', coverage:'33 %', single:'33 %',
    je1000:'7,43',
    betriebe:'129', beschaeftigte:'1.056', jeBetrieb:'18,53',
    genehmigungen:'158', invKopf:'540 €', schuldenKopf:'6.384 €',
    kontext:true,
  },
  muc: {
    name:"München", kreis:"Stadt und Landkreis gleichnamig", ew:null,
    vergeben:'4.812', offen:'214', stellen:'87',
    volumen:null, coverage:null, single:'29 %',
    je1000:null,
    betriebe:null, beschaeftigte:null, jeBetrieb:null,
    genehmigungen:null, invKopf:null, schuldenKopf:null,
    kontext:false,
  },
};
// Mediane über alle 422 Regionen — der Normalfall als Bezugsgröße
const RMED = {je1000:'0,40', jeBetrieb:'0,34', genehmigungen:'135', invKopf:'642 €', schuldenKopf:'1.276 €'};
let aktiveRegion = 'ffm';

function renderMarkt(l){
  const s = l && l.marktSegment;
  if(!s){
    return `<div class="mbody"><div class="mwarn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
      <span><b>${tk("Für dieses CPV-Segment liegen noch keine Marktdaten vor.")}</b>${tk("Wir zeigen hier lieber nichts als einen fremden Markt.")}</span></div></div>`;
  }
  const strukCls = {fragmentiert:'ok', moderat:'mid', oligopol:'risk'}[s.struktur] || 'mid';
  const strukNote = {
    fragmentiert:'Offenes Feld — als Neuer hast du realistische Chancen.',
    moderat:'Einige feste Groessen, aber Raum fuer Neue.',
    oligopol:tk("Wenige teilen fast alles unter sich auf."),
  }[s.struktur] || '';
  const na = v => v==null ? `<span class="v-sparse">${tk("zu wenig Daten")}</span>` : `<span class="v-num">${v}</span>`;
  return `<div class="mbody">
    <div class="buyer-head"><div>
      <div class="buyer-name">${s.label}</div>
      <div class="buyer-sub">Marktsegment &middot; CPV ${s.cpv4}${s.zeitraum?` &middot; ${s.zeitraum}`:''}</div>
    </div></div>

    <section class="bsec">
      <h4>${tk("Wie stark ist die Nachfrage?")}</h4>
      <div class="bstats">
        <div class="bstat"><span class="bstat-k">${tk("Vergaben im Segment")}</span><span class="bstat-v">${na(s.nAwards.toLocaleString('de-DE'))}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Chancen-Score")}</span><span class="bstat-v">${na(s.score!=null?s.score+' / 100':null)}</span><span class="bstat-m">${tk("Perzentil ueber alle Segmente")}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Chronisch erfolglose Bedarfe")}</span><span class="bstat-v">${na(s.chronic||0)}</span><span class="bstat-m">${tk("seit Jahren erfolglos gesucht")}</span></div>
      </div>
    </section>

    <section class="bsec">
      <h4>${tk("Wo ist das Feld schwach?")}<span class="cov">${tk("= wo es sich lohnt")}</span></h4>
      <div class="bstats bstats-2">
        <div class="bstat"><span class="bstat-k">${tk("Erfolglose Ausschreibungen")}</span><span class="bstat-v">${na(s.erfolglos!=null?s.erfolglos+' %':null)}</span><span class="bstat-m">${tk("kein Gewinner &rarr; neu ausgeschrieben")}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Nur ein Bieter")}</span><span class="bstat-v">${na(s.singleBidder!=null?s.singleBidder+' %':null)}</span><span class="bstat-m">${tk("kaum Wettbewerb")}</span></div>
      </div>
    </section>

    <section class="bsec">
      <h4>${tk("Wie ist das Feld verteilt?")}</h4>
      <div class="bhero bhero-${strukCls}">
        <div class="bhero-val" style="font-size:19px;min-width:auto">${s.struktur||'&mdash;'}</div>
        <div class="bhero-lbl"><span class="bhero-title">${tk("Die drei groessten Anbieter halten")}<b>${s.top3} %</b>${tk("der Auftraege")}</span>
          <span class="bhero-note">${strukNote}</span></div>
      </div>
    </section>

    <section class="bsec">
      <h4>${tk("Wer dominiert das Segment?")}</h4>
      <div class="bwinners"><span class="bwin-k">${tk("Die staerksten Anbieter &mdash; potenzielle Wettbewerber oder Partner")}</span>
        <div class="bwin-list">
          ${s.dominatoren.map(d=>`<div class="bwin-row">
            <span class="bwin-bar"><i style="width:${Math.min(100,d.share*4)}%"></i></span>
            <span class="bwin-name">${d.n}</span>
            <span class="bwin-p"><span class="v-num">${d.share} %</span></span>
            <span class="bwin-c"><span class="v-num">${d.wins}</span>${tk("Siege")}</span>
          </div>`).join('') || `<span class="v-sparse">${tk("keine Gewinner erfasst")}</span>`}
        </div>
      </div>
    </section>
  </div>`;
}

function renderBuyer(l){
  const free = isFreeLimit();
  const view = istEigen(l) ? 'verteidigung' : 'angriff';   // Sicht folgt dem Lead, nicht einem Modus
  // Echtes Vergabestellen-Profil des Leads (aus buyer_stats). Ohne Treffer: ehrlicher
  // Leerzustand statt fremder Demo-Käufer.
  const d = l.buyerProfile || {
    name:(l.buyer||'diese Vergabestelle'), sparse:true, total:null, zeitraum:'',
    perYear:null, decision:null, median:null, volume:null, coverage:null,
    division:null, categories:null, winners:null, mix:[], top3:null,
    concentration:'fragmentiert', topWinners:[], winsAvg:null, single:null,
    avgBidders:null, retention:null, retentionLevel:null, below:null, recent:[] };

  const sparse = `<span class="v-sparse" title="${esc(tk("Zu wenige Vergaben für eine belastbare Kennzahl"))}">${tk("zu wenig Daten")}</span>`;
  const b = (val) => val==null ? sparse
    : free ? `<span class="blur" aria-hidden="true">${val}</span><span class="lockmark" title="${esc(tk("Im Pro-Zugang"))}">🔒</span>`
    : val;
  const bnum = (val) => val==null ? sparse
    : free ? `<span class="blur blur-num" aria-hidden="true">${val}</span>`
    : `<span class="v-num">${val}</span>`;
  const upsell = '';   // kein Aufruf je Block — er steht einmal in der Seitenspalte

  const concClass = {fragmentiert:'ok', moderat:'mid', oligopol:'risk'}[d.concentration];
  const concNote = {
    fragmentiert:tk("Das Feld ist offen, als Neuer hast du realistische Chancen."),
    moderat:tk("Einige feste Größen, aber es gibt Raum für Neue."),
    oligopol:tk("Wenige teilen fast alles unter sich auf, als Neuer schwer reinzukommen."),
  }[d.concentration];

  // Retention sichtabhängig deuten: dieselbe Zahl heißt in Akquise vs. Bestand Gegenteiliges
  const treu = d.retentionLevel==='hoch';
  const retNote = d.retention==null ? '' : (view==='verteidigung'
    ? (treu ? tk("Käufer bleibt meist bei Bestandslieferanten, euer Vorsprung ist stabil.")
            : tk("Käufer wechselt häufig, euer Bestand ist angreifbar."))
    : (treu ? tk("Käufer bleibt meist bei Bestandslieferanten, als Neuer schwer reinzukommen.")
            : tk("Käufer wechselt häufig. Gute Chance, als Neuer Fuß zu fassen.")));

  return `<div class="dbody dbody-buyer">
    <div class="buyer-head">
      <div>
        <div class="buyer-name">${d.name}</div>
        <div class="buyer-sub">${tk("Vergabestelle · Käufer-Dossier")}${d.quelle === "unterschwellig" ? ` · <span class="v-sparse" title="${esc(tk("Diese Stelle schreibt unterhalb der EU-Schwellenwerte aus. Wir kennen sie aus oeffentlichevergabe.de, nicht aus TED — deshalb fehlen hier Kennzahlen wie Single-Bidder-Anteil und Wechselquote."))}">${tk("unterschwellig")}</span>` : ""}</div>
        <button class="sec-link" data-buyerleads="${esc(l.buyerShort)}">${tk("Alle Leads dieser Vergabestelle")}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </div>

    <div class="gatelayout ${free?'':'solo'}">
    <div class="gatemain">
    <section class="bsec">
      <h4>${tk("Ist der Käufer aktiv?")}
        ${/* AKTIVIERUNG D: die Stelle beobachten, an der Fundstelle. Der Schalter steht in der
             Ueberschrift des Kaeufer-Abschnitts, also genau dort, wo man sich fuer die Stelle
             interessiert — nicht in einem Menue.
             ⚠ KEINE VORHERSAGE. Der Vorschlag aus dem Uebergabepapier, einen Ausschreibungs-
             Rhythmus zu nennen, ist aus unseren Daten nicht belegbar; die Messung steht in
             `lib/supabase/buyerWatch.ts`. Der Schalter verspricht nur, was er halten kann. */''}
        <button class="bwatch" data-buyerwatch="${esc(l.buyer||'')}" aria-pressed="false"
          title="${esc(tk("Wir sagen euch Bescheid, wenn diese Stelle etwas ausschreibt."))}">
          ${tk("Stelle beobachten")}
        </button>
      </h4>
      <div class="bstats">
        <div class="bstat"><span class="bstat-k">${tk("Vergaben gesamt")}</span><span class="bstat-v">${bnum(d.total)}</span><span class="bstat-m">${d.zeitraum}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Vergaben pro Jahr")}</span><span class="bstat-v">${bnum(d.perYear)}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Bekanntmachung bis Zuschlag")}</span><span class="bstat-v">${bnum(d.decision)}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Typischer Auftragswert")}</span><span class="bstat-v">${bnum(d.median)}</span><span class="bstat-m">${tk("Median")}</span></div>
        <div class="bstat bstat-wide"><span class="bstat-k">${tk("Bekanntes Volumen")}</span><span class="bstat-v">${b(d.volume)}</span>
          ${d.coverage?`<span class="bstat-flag">Untergrenze — nur ${d.coverage} der Vergaben haben einen veröffentlichten Wert</span>`:''}</div>
      </div>
      <div class="bmix">
        <div class="bmix-head">
          <span class="bmix-t">${tk("Vergabe-Profil")}</span>
          <span class="bmix-basis">Anteile nach Anzahl der Vergaben${d.categories?` · ${d.categories} Themenfelder`:''}</span>
        </div>
        <div class="bmix-body">
          <div class="bmix-ring">
            ${(()=>{
              const R=54, C=2*Math.PI*R; let off=0;
              const segs = d.mix.map((m,i)=>{
                const len=(m.pct/100)*C;
                const cls = m.own?'own' : m.rest?'rest' : 'g'+i;
                const el=`<circle class="dseg ${cls}" cx="70" cy="70" r="${R}" fill="none" stroke-width="17"
                  stroke-dasharray="${len.toFixed(2)} ${(C-len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}"
                  transform="rotate(-90 70 70)"><title>${tk("goVisor · Lead Explorer v4.4")}</title></circle>`;
                off+=len; return el;
              }).join('');
              const own = d.mix.find(m=>m.own);
              return `<svg viewBox="0 0 140 140" class="donut">
                <circle cx="70" cy="70" r="${R}" fill="none" stroke="var(--surface-3)" stroke-width="17"/>
                ${segs}
              </svg>
              <div class="bmix-center">
                <span class="bmix-cv">${own ? (free?`<span class="blur blur-num">${own.pct} %</span>`:`${own.pct} %`) : '—'}</span>
                <span class="bmix-ck">${tk("euer Feld")}</span>
              </div>`;
            })()}
          </div>
          <div class="bmix-list">
            ${d.mix.map(m=>`<div class="bmix-row ${m.own?'own':''}">
              <i class="bmix-dot ${m.own?'own':''} ${m.rest?'rest':''}"></i>
              <span class="bmix-l">${b(m.label)}</span>
              <span class="bmix-p">${free?`<span class="blur blur-num">${m.pct} %</span>`:`<span class="v-num">${m.pct} %</span>`}</span>
              <span class="bmix-n">${free?`<span class="blur blur-num">${m.n}</span>`:`<span class="v-num">${m.n}</span>`}</span>
            </div>`).join('')}
          </div>
        </div>
      </div>
      ${upsell}
    </section>

    <section class="bsec">
      <h4>${tk("Habe ich eine Chance?")}</h4>
      <div class="bhero bhero-${concClass}">
        <div class="bhero-val">${bnum(d.top3!=null ? d.top3+' %' : null)}</div>
        <div class="bhero-lbl">
          <span class="bhero-title">${free
            ? `<span class="blur">Die drei größten Gewinner holen ${d.top3} % aller Aufträge</span>`
            : `Die drei größten Gewinner holen <b>${d.top3} %</b> aller Aufträge`}</span>
          <span class="bhero-note">${free?`<span class="blur">${concNote}</span>`:concNote}</span>
        </div>
      </div>

      <div class="bscale">
        <div class="bscale-track">
          <span class="bs-zone bs-ok">${tk("offen")}</span>
          <span class="bs-zone bs-mid">${tk("gemischt")}</span>
          <span class="bs-zone bs-risk">${tk("konzentriert")}</span>
          ${free?'':`<span class="bs-mark" style="left:${Math.min(98,Math.max(2,d.top3))}%"><i></i><span class="bs-mark-l">${tk("dieser Käufer")}</span></span>`}
        </div>
        <div class="bscale-ends"><span>${tk("0 %, viele teilen sich die Aufträge")}</span><span>${tk("100 %, drei holen alles")}</span></div>
      </div>

      <div class="bstats bstats-2">
        <div class="bstat"><span class="bstat-k">${tk("Vergaben mit nur einem Bieter")}</span><span class="bstat-v">${bnum(d.single)}</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Bieter je Ausschreibung")}</span><span class="bstat-v">${bnum(d.avgBidders)}</span><span class="bstat-m">Ø</span></div>
        <div class="bstat"><span class="bstat-k">${tk("Verschiedene Gewinner")}</span><span class="bstat-v">${bnum(d.winners)}</span>
          <span class="bstat-m">${d.winners?`bei ${d.total} Vergaben`:''}</span></div>
      </div>

      <div class="bret">
        <span class="bret-k">${tk("Aufträge, die erneut an denselben Anbieter gehen")}</span>
        <span class="bret-v">${bnum(d.retention)}</span>
        ${retNote?`<span class="bret-note">${free?`<span class="blur">${retNote}</span>`:retNote}</span>`:''}
      </div>
      ${upsell}
    </section>

    <section class="bsec">
      <h4>${tk("Wen muss ich schlagen?")}</h4>
      <div class="bwinners">
        <span class="bwin-k">Die stärksten Wettbewerber — Anteil an allen ${d.total} Vergaben</span>
        <div class="bwin-list">
          ${d.topWinners.map(w=>`<div class="bwin-row">
            <span class="bwin-bar"><i style="width:${Math.min(100,w.pct*2)}%"></i></span>
            <span class="bwin-name">${b(w.n)}</span>
            <span class="bwin-p">${free?`<span class="blur blur-num">${w.pct} %</span>`:`<span class="v-num">${w.pct} %</span>`}</span>
            <span class="bwin-c">${free?`<span class="blur blur-num">${w.w}</span>`:`<span class="v-num">${w.w}</span>`} Siege</span>
          </div>`).join('')}
        </div>
      </div>
      <div class="bfeed">
        <div class="bfeed-row bfeed-head"><span>${tk("Zuletzt vergeben")}</span><span>${tk("Gewinner")}</span><span>${tk("Wert")}</span><span></span></div>
        ${d.recent.map(r=>{
          const inner = `<span class="bf-t"><span class="bf-date">${r.date}</span>${b(r.title)}${r.flag?`<span class="bf-flag" title="${esc(tk("Nur ein Bieter"))}">${r.flag}</span>`:''}</span>
          <span class="bf-w">${b(r.winner)}</span>
          <span class="bf-v ${r.value.includes('unbekannt')?'unk':''}">${free?`<span class="blur">${r.value}</span>`:r.value}</span>`;
          if(free) return `<div class="bfeed-row">${inner}</div>`;
          return r.lead
            ? `<div class="bfeed-row bfeed-link" data-openlead="${r.lead}" title="${esc(tk("Vergabe öffnen"))}">${inner}<span class="bf-go" aria-hidden="true">›</span></div>`
            : `<a class="bfeed-row bfeed-link" href="https://ted.europa.eu" target="_blank" rel="noopener" title="${esc(tk("Zuschlag auf TED ansehen"))}">${inner}<span class="bf-go bf-ext" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></span></a>`;
        }).join('')}
      </div>
      ${upsell}
    </section>

    </div>
    ${free?gateCard(tk("Käufer-Intelligenz"),tk("Wie aktiv diese Stelle vergibt, wie hart der Wettbewerb ist und wer sonst gewinnt, für jede Vergabestelle.")):''}
    </div>

    <div class="buyer-floor">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
      Volumen-Angaben sind Untergrenzen — nur für einen Teil der Vergaben ist ein Auftragswert veröffentlicht. ${d.below?`Diese Stelle vergibt auch unterschwellig (${d.below} Aufträge).`:''}
    </div>
  </div>`;
}

function renderGate(){
  return `<div class="dbody">
    <div class="gate">
      <svg class="lock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
        <rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>
      </svg>
      <h3>${tk("Drei Bewertungen in 30 Tagen sind aufgebraucht")}</h3>
      <p>${tk("Die Übersicht bleibt offen. Volumen, Timing und Auftraggeber siehst du weiterhin zu jedem Lead. Für Bewertung, Direktvergleich und Anforderungs-Check brauchst du den vollen Zugang.")}</p>
      <button class="cta">${tk("Zugang freischalten · 29 € / Monat")}</button>
      <span class="alt">${tk("Nächste freie Bewertung am 14. August")}</span>
    </div>
  </div>`;
}


/* ── Potenzial-Bereich: renderProfil (Prototyp, innerHTML→return) ── */
function renderProfil(){
  const d = BESTAND || PROFIL[profilStufe] || PROFIL.neu;
  const historie = d.siege>0, belastbar = d.siege>=5 && d.kunden>=3;
  const free = isFreeLimit();
  const n = v => `<span class="v-num">${v}</span>`;
  return `<div class="pwrap">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:var(--s4);flex-wrap:wrap">
      <div class="steck">
        <div class="steck-n">${userProfile&&userProfile.firma?userProfile.firma:'Euer Marktumfeld'}</div>
        <div class="steck-z">
          <span>${BRANCHEN[aktiveBranche]}</span><i>·</i>
          <span>${userProfile?(userProfile.regions?(userProfile.regionLabels||[]).join(' · '):'bundesweit'):'bundesweit'}</span><i>·</i>
          ${userProfile
            ? `<span class="steck-ok" title="${esc(tk("Profil aktiv, steuert Relevanz und Anforderungs-Check."))}">${tk("Profil aktiv")}</span>`
            : `<span class="steck-m" title="${esc(tk("Meldet euch an und bestätigt eure Firma, um euer Profil zu verbinden (Relevanz, Historie, eigene Aufträge)."))}">${tk("Profil noch nicht verbunden")}</span>`}
        </div>
      </div>
    </div>

    <div class="ptabs" role="tablist">
      <button class="ptab" data-ptab="chancen"  aria-selected="${potTab==='chancen'}">Chancen${
        potTab==='chancen'?'':''}</button>
      <button class="ptab" data-ptab="position" aria-selected="${potTab==='position'}">Position${
        free?`<span class="probadge probadge-lock">${tk("Pro")}</span>`:''}</button>
      <button class="ptab" data-ptab="profil"   aria-selected="${potTab==='profil'}">${tk("Profil")}</button>
    </div>

    ${potTab!=='chancen'?'':`
    <section class="sec">
      <h4>${tk("Wo könnt ihr gewinnen?")}</h4>
      ${historie&&d.kundenListe.length?`<div class="pblock ${free?'pb-lock':''}">
        <div class="pb-h"><span class="pb-t">Bei euren Kunden${free?`<span class="probadge probadge-lock">${tk("Pro")}</span>`:''}</span>
          <span class="pb-n">${d.kundenListe.reduce((a,k)=>a+k.offen,0)} ${tk("gerade offen")}</span></div>
        <p class="pb-x">${tk("Diese Stellen kennen euch bereits. Rechts steht, wie viele ihrer Vergaben gerade laufen.")}</p>
        ${d.kundenListe.map(k=>`<div class="pen"><span class="pen-n">${esc(k.n)}${
            k.offen?`<span class="pr-tag" style="margin-left:8px">${k.offen} ${tk("offen")}</span>`:''}</span>
          <span class="pen-s">${k.seit?tk("seit {j}",{j:k.seit}):''}${k.bindung?` · ${tk("Bindung")} ${tk(k.bindung)}`:''}</span>
          <span class="pen-v">${k.gewonnen} ${k.gewonnen===1?tk("Auftrag"):tk("Aufträge")}</span></div>`).join('')}
      </div>`:''}
      ${NACHBARN.length?`<div class="pblock ${free?'pb-lock':''}">
        <div class="pb-h"><span class="pb-t">In benachbarten Feldern${free?`<span class="probadge probadge-lock">${tk("Pro")}</span>`:''}</span></div>
        <p class="pb-x">${tk("Bereiche, die Firmen wie ihr häufig zusätzlich bedienen. Abgeleitet daraus, welche Felder dieselben Anbieter gemeinsam abdecken.")}</p>
        <div class="prow prow-h"><span>${tk("Feld")}</span><span>${tk("Nähe")}</span><span>${tk("Firmen")}</span></div>
        ${NACHBARN.map(x=>`<div class="prow"><span class="pr-n">${esc(x.n)}</span>
          <span class="pr-o"><span class="pr-tag ${x.naehe==='hoch'?'':'mut'}">${tk(x.naehe)}</span></span>
          <span class="pr-a">${x.firmen}</span></div>`).join('')}
      </div>`:''}
      <div class="pblock">
        <div class="pb-h"><span class="pb-t">${tk("In eurem Markt")}</span><span class="pb-n">${PMARKT.offen} offen</span></div>
        <p class="pb-x">${tk("Die aktivsten Vergabestellen in eurem Feld und euren Regionen. Unabhängig davon, ob ihr dort schon geboten habt.")}</p>
        <div class="prow prow-h"><span>${tk("Vergabestelle")}</span><span>${tk("Vergaben")}</span><span>${tk("offen")}</span></div>
        ${PMARKT.topStellen.map(v=>`<div class="prow"><span class="pr-n">${v.n}</span><span class="pr-a">${v.vergaben}</span>
          <span class="pr-o">${v.offen?`<span class="pr-tag">${v.offen}</span>`:'<span style="color:var(--ink-300)">—</span>'}</span></div>`).join('')}
      </div>
      <div class="pblock">
        <div class="pb-h"><span class="pb-t">${tk("Einstiegsfreundlich")}</span></div>
        <p class="pb-x">${tk("Offene Ausschreibungen mit kleinem Los und wenigen Bietern, dort ist der Sprung hinein am kürzesten.")}</p>
        <div class="prow prow-h"><span>${tk("Ausschreibung")}</span><span>${tk("Kleinstes Los")}</span><span>${tk("Bieter")}</span></div>
        ${PMARKT.einstieg.map(v=>`<div class="prow"><span class="pr-n">${v.n}</span><span class="pr-a">${v.wert}</span><span class="pr-a">${v.bieter||'—'}</span></div>`).join('')}
        <p class="pgap">${tk("Die Bieterzahl stammt aus vergleichbaren, bereits entschiedenen Vergaben derselben Stelle, bei laufenden Ausschreibungen hat noch niemand geboten.")}</p>
      </div>
    </section>`}
    ${potTab!=='position'?'':`
    <section class="sec ${free?'sec-lock':''}">
      <h4>${tk("Eure Position im Markt")}<span class="cov">${tk("Branche × Region, nach Anzahl")}</span></h4>
      ${free?`<div class="note-box" style="margin-bottom:var(--s3)"><b>${tk("Im Pro-Zugang enthalten.")}</b>${tk("Marktanteil und Rang rechnen wir aus allen Vergaben eures Feldes gegen eure Siege. Die Struktur siehst du, die Zahlen sind verdeckt.")}</div>`:''}
      <div class="pstats">
        <div class="pstat"><span class="pstat-k">${tk("Vergaben in eurem Feld")}</span><span class="pstat-v">${n(PMARKT.vergaben)}</span><span class="pstat-m">${tk("letzte 12 Monate")}</span></div>
        <div class="pstat"><span class="pstat-k">${tk("Davon von euch gewonnen")}</span><span class="pstat-v">${historie?n(d.siege):`<span class="pleer">${tk("keine")}</span>`}</span></div>
        <div class="pstat"><span class="pstat-k">${tk("Euer Anteil")}</span><span class="pstat-v">${d.anteil?n(d.anteil):'<span class="pleer">—</span>'}</span></div>
        <div class="pstat"><span class="pstat-k">${tk("Rang unter den Anbietern")}</span>
          <span class="pstat-v">${d.rang?n(d.rang+'.'):`<span class="pleer">${tk("zu wenige Siege")}</span>`}</span>
          ${d.rang?`<span class="pstat-m">von ${PMARKT.stellen} aktiven Anbietern</span>`:''}</div>
        <div class="pstat pstat-wide"><span class="pstat-k">${tk("Vergabestellen in eurem Feld")}</span><span class="pstat-v">${n(PMARKT.stellen)}</span>
          <span class="pstat-m">${historie?`bei ${d.kunden} davon habt ihr schon gewonnen`:tk("noch bei keiner davon aktiv")}</span></div>
      </div>
      <p class="pgap">${tk("Eine")}<b>${tk("Gewinnquote")}</b>${tk("können wir nicht ausweisen: Vergabestellen veröffentlichen den Gewinner, nicht die unterlegenen Bieter. Wir wissen, wie viele geboten haben, aber nicht, ob ihr dabei wart.")}</p>
    </section>`}

    ${potTab!=='profil'?'':`
    <section class="sec">
      <h4>${tk("Euer Profil")}<span class="cov">${tk("Grundlage für Relevanz und Anforderungs-Check")}</span></h4>

      <div class="pstats">
        <div class="pstat"><span class="pstat-k">${tk("Gewonnene Vergaben")}</span>
          <span class="pstat-v">${historie?n(d.siege):`<span class="pleer">${tk("noch keine")}</span>`}</span>
          ${historie?`<span class="pstat-m">seit ${d.seit}</span>`:''}</div>
        <div class="pstat"><span class="pstat-k">${tk("Auftraggeber")}</span>
          <span class="pstat-v">${historie?n(d.kunden):'<span class="pleer">—</span>'}</span></div>
        <div class="pstat"><span class="pstat-k">${tk("Typischer Auftragswert")}</span>
          <span class="pstat-v">${d.median?n(d.median):'<span class="pleer">—</span>'}</span>
          ${d.median?`<span class="pstat-m">${tk("Median")}</span>`:''}</div>
        <div class="pstat pstat-wide"><span class="pstat-k">${tk("Bekanntes Volumen")}</span>
          <span class="pstat-v">${d.volumen?n(d.volumen):'<span class="pleer">—</span>'}</span>
          ${d.volumen?`<span class="pstat-flag">${tk("Untergrenze, nur für rund zwei Drittel der Vergaben ist ein Wert veröffentlicht")}</span>`:''}</div>
      </div>

      ${historie && !belastbar?`<div class="note-box" style="margin-top:var(--s3)"><b>${tk("Dünne Grundlage.")}</b>
        Mit ${d.siege} ${d.siege===1?'Vergabe':'Vergaben'} bei ${d.kunden} ${d.kunden===1?'Auftraggeber':'Auftraggebern'}
        lässt sich noch kein Muster ablesen — ergänzt unten, was wir nicht sehen können.</div>`:''}
      ${!historie?`<div class="note-box" style="margin-top:var(--s3)">${tk("Wir finden unter eurem Namen noch keine gewonnene Vergabe.")}<b>${tk("Dann erklärt euer Profil selbst")}</b>${tk("Relevanz und Anforderungs-Check funktionieren auch ohne Historie.")}</div>`:''}

      <div class="ang">
        ${(()=>{
          const fmt = v => v==null ? null : (v>=1e6 ? (v/1e6).toFixed(1).replace('.',',')+' Mio' : Math.round(v).toLocaleString('de-DE'));
          if(userProfile){
            const felder = (userProfile.cpvLabels&&userProfile.cpvLabels.length)?userProfile.cpvLabels:['—'];
            const regs = userProfile.regions ? (userProfile.regionLabels||[]).join(' · ') : 'Bundesweit';
            const vmin = fmt(userProfile.volMin), vmax = fmt(userProfile.volMax);
            const vol = (vmin||vmax) ? `${vmin||'0'} – ${vmax||'beliebig'} €` : tk("keine Grenze");
            return `<div class="ang-sync">
              <div class="asy-h"><span class="asy-t">${tk("Eure Angaben")}<span class="asy-tag">${tk("erklärt")}</span></span>
                <button class="asy-edit" data-editprofil="1">${tk("Bearbeiten")}</button></div>
              <div class="asy-r"><span class="asy-k">${tk("Schwerpunkte")}</span>
                <span class="asy-v">${felder.map(f=>`<span class="asy-chip">${f}</span>`).join('')}</span></div>
              <div class="asy-r"><span class="asy-k">${tk("Regionen")}</span><span class="asy-v">${regs}</span></div>
              <div class="asy-r"><span class="asy-k">${tk("Auftragsgröße")}</span><span class="asy-v">${vol}</span></div>
              <p class="asy-x">${tk("Diese Angaben steuern Relevanz und Anforderungs-Check. Bearbeiten öffnet den Profil-Dialog.")}</p>
            </div>`;
          }
          return `<div class="note-box gap"><b>${tk("Noch kein Profil.")}</b>${tk("Richtet euer Firmenprofil ein. Es bestimmt, welche Ausschreibungen als relevant gelten, und speist den Anforderungs-Check.")}<div class="acts"><button data-editprofil="1">${tk("Profil einrichten")}</button></div></div>`;
        })()}

        ${angFeld('nachweise','Nachweise & Zertifikate',tk("Werden im Anforderungs-Check gegen die Forderungen geprüft."),[])}

        <div class="ang-f">
          <div class="ang-h"><span class="ang-t">${tk("Partnersuche")}</span>
            <span class="ang-x">${tk("Für Ausschreibungen, die man allein nicht ganz gewinnen kann.")}</span></div>
          <div class="ptoggle ${angaben.partner?'on':''}">
            <button class="pt-sw" data-partner aria-pressed="${!!angaben.partner}"><i></i></button>
            <div class="pt-m">
              <span class="pt-t">${angaben.partner?tk("Ihr seid sichtbar und seht andere"):'Ausgeschaltet'}</span>
              <span class="pt-x">${angaben.partner
                ? tk("Andere Firmen sehen euren Namen, eure Schwerpunkte, Regionen und Größenklasse. Was ihr euch anseht oder merkt, sieht niemand.")
                : tk("Eingeschaltet zeigen wir euch Firmen, die sich ebenfalls geöffnet haben, und ihr werdet für sie sichtbar. Nur zusammen, nicht einseitig.")}</span>
            </div>
          </div>
        </div>
      </div>

      <p class="pgap">${tk("Angaben von euch sind")}<b>${tk("nicht überprüft")}</b>${tk("wir kennzeichnen sie getrennt von dem, was wir aus euren Vergaben messen.")}</p>

      <button class="sec-link" data-editbestand="an">${historie?tk("Eure Verträge pflegen"):tk("Frühere Vergaben nachtragen")}
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
    </section>`}
  </div>`;
}

/* ── Brücke zu React ──────────────────────────────────────────────────────
   Die Filter-/Sortier-Logik (visible/sorted) liest modul-internen Zustand.
   React hält die UI-Wahrheit und schiebt sie vor jedem Render herein — so
   bleibt die Prototyp-Logik unverändert die einzige Quelle. */
function applyState(p){
  if(!p) return;
  if('sortKey' in p) sortKey = p.sortKey;
  if('sortDir' in p) sortDir = p.sortDir;
  if('aktiveBranche' in p) aktiveBranche = p.aktiveBranche;
  if('profilBranche' in p) profilBranche = p.profilBranche;
  if('searchTokens' in p) searchTokens = p.searchTokens;
  if('filters' in p) filters = p.filters;
  if('activeId' in p) activeId = p.activeId;
  if('activeTab' in p) activeTab = p.activeTab;
  if('aktiveRegion' in p) aktiveRegion = p.aktiveRegion;
  if('potTab' in p) potTab = p.potTab;
  if('accountLimit' in p) accountLimit = p.accountLimit;
  if('profilStufe' in p) profilStufe = p.profilStufe;
  if('offenerPicker' in p) offenerPicker = p.offenerPicker;
}
function getState(){
  return { sortKey, sortDir, aktiveBranche, profilBranche,
           searchTokens, filters, activeId };
}

// Echte Leads aus der Gold-Schicht in den Kern schieben (ersetzt den Demo-Seed).
// LEADS bleibt dieselbe Array-Referenz, die alle Closures lesen — nur der Inhalt wechselt.
function setLeads(arr){
  LEADS.length = 0;
  // Export liefert nur Codes → hier in die Anzeige-Sprache übersetzen (labels.js).
  for(const l of arr) LEADS.push(applyLabels(l));
  // Echtes Profil (aus Onboarding, kein branche-relatives Preset) → neue Leads sofort scoren.
  // Der Testsicht-Pfad scored ohnehin gleich über applyProfile im selben Render-Zyklus.
  if(userProfile && !activeProfile) scoreAll();
}

/* Alle geladenen Leads neu beschriften — Aufruf beim Sprachwechsel. Ohne das bleibt die
 * Liste in der Altsprache stehen, weil `applyLabels` seine Ergebnisse zwischenspeichert. */
function relabelLeads(){ for(const l of LEADS) applyLabels(l, true); }

// Eigener Vertragsbestand (aus user_contracts) — von React gesetzt, für „Eure Verträge bei X".
let userContracts = [];
function setUserContracts(arr){ userContracts = Array.isArray(arr) ? arr : []; if(userProfile) scoreAll(); }

// Echte Marktblöcke (Chancen-Tab) in PMARKT schieben — in place, damit renderProfil sie liest.
function setMarket(m){
  if(!m) return;
  for(const k of Object.keys(PMARKT)) delete PMARKT[k];
  Object.assign(PMARKT, m);
}

/* ── Test-Profile: Relevanz simulieren (Kleinbetrieb / Mittelstand / Großunternehmen) ──
   Relevanz hängt an einem Firmenprofil (CPV-Feld × Region × Volumen). Ohne Onboarding
   simulieren wir drei Größenklassen, um zu sehen, wie stark sich die Ergebnismenge
   fokussieren lässt — die Kernthese „wenige passende statt hunderter". */
/* Preset-Sichten (Testsicht). Sie sind KEINE Sonderlogik mehr, sondern erzeugen ein
 * echtes Profil — denselben Vertrag, den später das Onboarding füllt. `breadth`/`nachbar`
 * bestimmen, wie viele der häufigsten Feld-Segmente des Grundraums als Schwerpunkt bzw.
 * Nachbarfeld gelten (Stand-in für „im Onboarding gewählte Felder"). */
const PROFILES = {
  klein:  {label:'Kleinbetrieb',    sub:"Spezialist · lokal · kleine Aufträge",
           breadth:2,  nachbar:2, regions:['DE2'],                   volMin:0,      volMax:500000,  maxAlleine:300000,  buergschaft:100000},
  mittel: {label:'Mittelstand',     sub:"mehrere Felder · regional · mittlere Aufträge",
           breadth:4,  nachbar:3, regions:['DE1','DE2','DE7','DEA'], volMin:50000,  volMax:5000000, maxAlleine:2000000, buergschaft:500000},
  gross:  {label:"Großunternehmen", sub:"breit · bundesweit · Rahmenverträge",
           breadth:12, nachbar:6, regions:null,                      volMin:250000, volMax:1e13,    maxAlleine:5e7,     buergschaft:5e6},
};
function parseWert(w){
  if(!w || /offen/i.test(w)) return null;
  const mio = /mio/i.test(w);
  let s = String(w).replace(/[^\d.,]/g,'');
  if(mio){ s = s.replace(/\./g,'').replace(',','.'); const n=parseFloat(s); return isNaN(n)?null:n*1e6; }
  s = s.replace(/\./g,'').replace(',','.'); const n=parseFloat(s); return isNaN(n)?null:n;
}

// Das aktive Firmenprofil (echtes Objekt, nicht nur ein Preset-Key). null = ohne Onboarding.
let userProfile = null;
function setProfile(p){ userProfile = (p && hasProfile(p)) ? p : null; scoreAll(); }
function getProfile(){ return userProfile; }

/* Preset → echtes Profil. Die Feld-Segmente kommen aus dem aktuellen Grundraum,
 * damit die Testsicht ohne echte CPV-Auswahl funktioniert. */
function profileFromPreset(key){
  const pre = PROFILES[key];
  if(!pre) return null;
  const counts = {};
  for(const l of LEADS){ const c=String(l.cpv||'').slice(0,4); if(c) counts[c]=(counts[c]||0)+1; }
  const ranked = Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(e=>e[0]);
  const p = emptyProfile();
  p.firma = 'Testsicht: '+pre.label;
  p.entityConfidence = null;                  // Testsicht ist nicht belegt → kein ⚠-Hinweis
  p.cpvFields    = ranked.slice(0, pre.breadth);
  p.nachbarFields = ranked.slice(pre.breadth, pre.breadth + pre.nachbar);
  p.regions      = pre.regions;
  p.volMin       = pre.volMin;
  p.volMax       = pre.volMax;
  p.maxAlleine   = pre.maxAlleine;
  p.buergschaft  = pre.buergschaft;
  return p;
}

/* Relevanz je Los rechnen und die Ausschreibung die Relevanz ihres BESTEN Loses erben
 * lassen (#12). Los-CPV/Region sind belastbar (~99 % / 77 %), Los-Wert fast nie → Volumen
 * bleibt neutral auf Ausschreibungsebene. Nur bei ≥2 Losen mit eigener CPV greift das;
 * sonst (Ein-Los, Demo ohne Los-CPV) ist es die normale Lead-Ebene. */
const RELRANK = { hoch: 3, mittel: 2, niedrig: 1, na: 0 };
function scoreLeadPerLot(l, profile, v){
  const lots = (l.lose || []).filter(x => x && x.cpv);
  const leadM = matchLead(l, profile, v);
  if(lots.length < 2) return { m: leadM, bestLot: null };
  let best = null, bestM = leadM;
  for(const lot of lots){
    const nuts = lot.region || l.nuts;
    const pseudo = Object.assign({}, l, { cpv: lot.cpv, nuts, marktRegion: nuts ? true : l.marktRegion });
    const m = matchLead(pseudo, profile, v);
    if(RELRANK[m.relevanz] > RELRANK[bestM.relevanz]){ bestM = m; best = lot; }
  }
  // Erbt nur, wenn ein Los STRIKT besser passt als die Ausschreibungsebene.
  return best ? { m: bestM, bestLot: best } : { m: leadM, bestLot: null };
}

/* Alle Leads gegen das aktive Profil scoren — setzt relevanz, relWhy und das
 * volle match-Objekt (Blocker/Partner) für die Detail-Erklärung. */
function scoreAll(){
  if(!userProfile){ for(const l of LEADS){ l.relevanz='na'; l.passung=null; l.match=null; l.bestLot=null; l.eigen=false; l.eigenBestaetigt=false; } return; }
  const myId = userProfile.identityId || null;
  /* Die angehakten Einheiten aus dem Onboarding. Bis zum 2026-08-21 wurden sie NIRGENDS
     gelesen: gescort wurde allein gegen `identityId`, also gegen die ganze Gruppe. Der
     Screen „Gehören diese Einheiten zu euch?" war damit folgenlos — Abwählen nahm nichts
     weg, Dazuwählen gab nichts dazu. Jetzt zählt der Haken.
     Alte Profile tragen hier reine Namen (string), neue Objekte mit Beleglage. */
  const meineEinheiten = new Set((userProfile.confirmedEntities||[])
    .map(e => typeof e === 'string' ? e : (e && e.name))
    .filter(Boolean));
  // Buyer-Namen aus dem eigenen Vertragsbestand (für „eigen"-Match über Verträge)
  const myBuyers = (userContracts||[]).map(c=>String(c.buyer_name||'').toLowerCase()).filter(Boolean);
  for(const l of LEADS){
    const v = parseWert(l.volumen && l.volumen.wert);
    const { m, bestLot } = scoreLeadPerLot(l, userProfile, v);
    l.relevanz = m.relevanz;
    l.passung = m.passung;      // 0–100, Rangzahl zur Stufe; null ohne Profil
    l.match = m;
    l.bestLot = bestLot;   // {nr,titel,region,cpv} des passenden Loses, oder null
    l.relWhy = whyHtml(m);
    // „Eigen" (Verteidigungs-Sicht): der Amtsinhaber IST unsere Identität, ODER ein eigener
    // Vertrag passt zur Vergabestelle. Bei unsicherem Incumbent (conf<0.75) → „mutmaßlich".
    const inc = l.incumbent;
    /* Gruppentreffer allein genügt nicht mehr: die abgewählte Schwesterfirma ist nicht
       „eigen". Gemessen am 2026-08-21 findet der Incumbent-Name sein Mitglied in 9.991 von
       10.030 Fällen; die 39 Ausreisser (0,4 %) verlieren die Eigen-Markierung, was die
       vorsichtige Richtung ist. Leere Liste = Altprofil ohne Einheiten-Angabe → wie bisher
       die ganze Gruppe, sonst nähmen wir bestehenden Konten ihre Historie weg. */
    const incMine = !!(inc && myId && inc.groupId === myId
      && (meineEinheiten.size === 0 || meineEinheiten.has(inc.name)));
    const bn = String(l.buyer||'').toLowerCase();
    const contractMine = !!(bn && myBuyers.some(b=> b.includes(bn.slice(0,18)) || bn.includes(b.slice(0,18))));
    l.eigen = incMine || contractMine;
    l.eigenBestaetigt = incMine ? (inc.conf!=null && inc.conf>=0.75 ? true : null) : (contractMine ? true : false);
  }
}

// Testsicht-Umschalter: Preset-Key → echtes Profil → scoren.
let activeProfile = null;
function applyProfile(key){
  activeProfile = (key && PROFILES[key]) ? key : null;
  setProfile(activeProfile ? profileFromPreset(activeProfile) : null);
}

export { cpvLabel, relabelLeads, applyState, getState, setLeads, setMarket, setBestand, setNachbarn, setNetzZustand, toggleNetzLos, netzLoseVon, netzLose, setPlzGeo, setPlzLand, setUserContracts, applyProfile, setProfile, getProfile, PROFILES, parseWert, netzInteresse, netzFreigabe, offeneGruppen };
export {
  renderUebersicht, renderTeilnahme, renderAnalyse, renderMarkt, renderBuyer,
  renderTeam, renderGate, renderProfil, renderDocs, REGIONS,
};
export { angaben };
export {
  MEINE_FIRMA, LEADS, BRANCHEN, RAHMEN, RAHMEN_NACHWEIS, FACETS, ORTE, PLZ, PLACE_RADIUS,
  COLS, SRC_TEXT, WF, LVL, TOKICON, RADII, NETZ_FREI_MAX, STAR, ME,
  aufwandStufe, leadText, matchToken, fundstelle, hervorheben, hasToken, toggleToken,
  classifyQuery, val, bandMeter, wfPill, konkCell, chanceCap, istEigen, bieterLuecke,
  fristCell, visible, syncLocationColumn, sorted, cellHTML, tokenLabel, suggestList,
};

/* Land des Nutzers aus seinen Regionen — NUTS traegt es im Praefix („DE2", „AT3", „CH0").
 *
 * Gebraucht von der Strategie-Ansicht: deren Aggregate sind seit 2026-08-23 je Land
 * gerechnet, und ohne diese Ableitung bekaeme jeder Nutzer die deutschen. Ein eigener
 * Laenderwaehler waere die ehrlichere Loesung, aber solange die Regionen ohnehin
 * laendergebunden sind, ist ein zweiter Regler dieselbe Angabe zweimal.
 *
 * ⚠ Nicht jede Region traegt ein sauberes NUTS: gemessen fuehren 138 Schweizer Leads
 * einen Kantonskuerzel („ZH", „VD") statt „CH0…", und „BE" ist dort Bern, im NUTS-Raum
 * aber Belgien. Deshalb wird NUR gegen die drei bekannten Laender geprueft und sonst auf
 * DE zurueckgefallen — raten waere hier schlimmer als der Standard.
 */
const LAND_AUS_NUTS = { DE: 'DE', AT: 'AT', CH: 'CH' };
function nutzerLand() {
  const regionen = (userProfile && userProfile.regions) || [];
  for (const r of regionen) {
    const code = LAND_AUS_NUTS[String(r || '').slice(0, 2).toUpperCase()];
    if (code) return code;
  }
  return 'DE';
}
export { nutzerLand };
