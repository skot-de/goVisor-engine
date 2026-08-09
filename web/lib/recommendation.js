/* Feature #26 — Handlungsempfehlung je Lead. Zwei Kaskaden:
 *  A · Einordnung (A1–A6, Free, nur Metadaten)
 *  B · Handlungsempfehlung (B0–B9, Pro, braucht Unterlagen + Profil)
 * Kein Gesamtscore (AC1). Jede Bedingung einzeln erfüllbar, in einem Satz erklärbar. Reihenfolge
 * bindend, erste zutreffende Regel gewinnt. Alle Schwellen als Konstanten (AC1c, kalibrierbar §8).
 *
 * Framework-agnostisch: `recommend(lead, profile, ctx)` liefert reine Daten; das Rendering
 * (Liste/Detail) liegt beim Aufrufer. */

// ── Schwellen (§3.2, Ausgangswerte; kalibrierbar) ──
const T = {
  E2_hoch: 70, E2_mittel: 45,
  E3_incumbent_jung: 3,          // Jahre
  E3_wechsel_hoch: 40, E3_wechsel_tot: 15,  // % Segment-Wechselquote
  E4_mittel_ab: 150_000, E4_hoch_ab: 500_000,
  E4_grenz: 0.60,                // 60–99 % = grenzwertig
  E5_median_default: 10,         // Tage (§10 OP2)
  E9_min_faelle: 8, E9_guenstig: 3, E9_unguenstig: 7,
  KNAPP: 0.85,                   // Schwellenwert-Anforderung: 85–99 % = knapp verfehlt
  COVERAGE_MIN: 0.60,            // §3.9 Mindestabdeckung für Kaskade B
};

// Anker-Katalogschlüssel (nicht aus Stammdaten abgeleitet) — für die Abdeckung (§3.9).
const REQUIRED_KEYS = ["ausschluss_123_124", "sanktion_5k", "tariftreue", "berufshaftpflicht",
  "praequalifikation", "verbandsmitgliedschaft", "iso_9001", "iso_14001", "iso_27001", "scc"];

// Häufige Zertifikatsnamen aus Unterlagen → Profil-Attributschlüssel.
const CERT_MAP = [
  [/iso[\s-]*27001/i, "iso_27001"], [/iso[\s-]*9001/i, "iso_9001"], [/iso[\s-]*14001/i, "iso_14001"],
  [/\bscc\b|scp/i, "scc"], [/präqualif|praequalif|\bpq\b/i, "praequalifikation"],
  [/haftpflicht/i, "berufshaftpflicht"],
];

function parseEur(s) {
  if (s == null) return null;
  if (typeof s === "number") return s;
  const str = String(s);
  const m = str.match(/([\d.,]+)\s*(mio|mrd|k)?/i);
  if (!m) return null;
  let n = parseFloat(m[1].replace(/\./g, "").replace(",", "."));
  if (isNaN(n)) return null;
  const u = (m[2] || "").toLowerCase();
  if (u === "mio") n *= 1e6; else if (u === "mrd") n *= 1e9; else if (u === "k") n *= 1e3;
  return n;
}
const normName = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9äöüß ]/g, " ").replace(/\b(gmbh|ag|se|kg|co|ohg|mbh|und)\b/g, " ").replace(/\s+/g, " ").trim();

// ── Abdeckung des Eignungsprofils (§3.9) ──
function coverage(profile) {
  const attrs = (profile && profile.attributes) || {};
  const answered = REQUIRED_KEYS.filter((k) => {
    const a = attrs[k];
    return a && a.zustand !== "abgeleitet" && a.value != null && a.value !== "";
  }).length;
  return answered / REQUIRED_KEYS.length;
}

// ── E-Größen aus dem Lead ableiten ──
function evaluate(lead, profile, ctx) {
  const attrs = (profile && profile.attributes) || {};
  const relBand = lead.match ? lead.match.relevanz : (lead.relevanz || "na");   // hoch/mittel/niedrig/na
  const E2 = relBand === "hoch" ? 75 : relBand === "mittel" ? 55 : relBand === "niedrig" ? 30 : null;

  // E3 Wettbewerbslage
  const inc = lead.incumbent || {};
  const incJahr = inc.seit ? parseInt(String(inc.seit).slice(0, 4), 10) : null;
  const incAlter = incJahr ? (new Date().getFullYear() - incJahr) : null;
  const wechsel = lead.wechsel;   // hoch/mittel/niedrig/na
  const erstvergabe = !inc.name && !(lead.kette && lead.kette.hat);
  let E3;
  if (erstvergabe || (incAlter != null && incAlter < T.E3_incumbent_jung) || wechsel === "hoch") E3 = "guenstig";
  else if (wechsel === "niedrig") E3 = "unguenstig";
  else E3 = "mittel";

  // E4 Aufwand ÷ Wert
  const anf = lead.anf || {};
  const nachweise = (anf.zertifikate || []).length + (anf.eignung || []).length;
  const aufStufe = (anf.buergschaft || nachweise >= 3) ? "hoch" : nachweise >= 1 ? "mittel" : "gering";
  const val = parseEur(lead.volumen && lead.volumen.wert);
  const valEcht = lead.volumen && (lead.volumen.src === "echt" || lead.volumen.src === "amtlich");
  const istRahmen = lead.contractKind === "framework" || lead.contractKind === "recurring" || lead.istRahmen;
  let E4;
  if (istRahmen) E4 = "rahmen";                     // §3.2b: Verhältnisprüfung entfällt
  else if (!valEcht || val == null) E4 = "unbekannt";
  else {
    const schwelle = aufStufe === "gering" ? 0 : aufStufe === "mittel" ? T.E4_mittel_ab : T.E4_hoch_ab;
    if (val >= schwelle) E4 = "angemessen";
    else if (val >= schwelle * T.E4_grenz) E4 = "grenzwertig";
    else E4 = "unverhaeltnismaessig";
  }

  // E5 Frist
  const fristTage = (lead.frist && typeof lead.frist.tage === "number") ? lead.frist.tage
    : (typeof lead.tage === "number" ? lead.tage : null);
  const median = T.E5_median_default;
  let E5;
  if (fristTage == null) E5 = "unbekannt";
  else if (fristTage >= median) E5 = "ausreichend";
  else if (fristTage >= median * 0.5) E5 = "knapp";
  else E5 = "unzureichend";

  // E6 Beziehung
  const ownBuyers = (ctx && ctx.ownBuyers) || [];
  const E6 = ownBuyers.some((b) => normName(b) && normName(lead.buyer).includes(normName(b))) ? "vorhanden" : "keine";

  // E7 Vertragsart
  const E7 = istRahmen ? "rahmen" : (lead.contractKind && lead.contractKind !== "other") ? "einzel" : "unbekannt";

  // E8 Vergabeart / istEigen
  const istEigen = !!(profile && profile.firma && inc.name && normName(inc.name) === normName(profile.firma));
  const E8 = istEigen ? "eigen" : erstvergabe ? "erstvergabe" : "folge_fremd";

  // E9 Bieterdichte
  const konk = lead.konk || {};
  const bieterMed = parseEur(konk.wert);   // konk.wert kann eine Zahl sein
  const E9 = (konk.stufe && konk.stufe !== "na" && bieterMed != null)
    ? (bieterMed <= T.E9_guenstig ? "guenstig" : bieterMed >= T.E9_unguenstig ? "unguenstig" : "mittel")
    : "unbekannt";

  // E10 Losstruktur
  const lose = lead.lose || [];
  const E10_teilbar = lose.length >= 2 && (relBand === "hoch" || relBand === "mittel");

  // E1 Pflichtanforderungen (Datenzustand)
  const reqCerts = [...(anf.zertifikate || []), ...(anf.eignung || [])].map(String);
  const hasDocs = reqCerts.length > 0 || anf.buergschaft != null;
  const datenzustand = hasDocs ? "B" : "A";
  let E1 = "unbekannt", E1_grund = null;
  if (hasDocs && reqCerts.length) {
    let verletzt = false, offen = false;
    for (const rc of reqCerts) {
      const hit = CERT_MAP.find(([re]) => re.test(rc));
      if (!hit) { offen = true; continue; }
      const a = attrs[hit[1]];
      if (a && a.zustand !== "abgeleitet") { if (a.value === false) { verletzt = true; E1_grund = rc; } }
      else offen = true;
    }
    E1 = verletzt ? "verletzt" : offen ? "unbekannt" : "erfuellt";
  }

  return { E1, E1_grund, E2, E2band: relBand, E3, E4, E4stufe: aufStufe, E5, E5tage: fristTage, E5median: median,
    E6, E7, E8, E9, E9med: bieterMed, E10_teilbar, loseN: lose.length, istEigen, istRahmen, val, valEcht,
    incumbent: inc, incAlter, wechsel, datenzustand };
}

// ── Kaskade A · Einordnung (§3.3 A) ──
export function einordnung(e) {
  if (e.E8 === "eigen") return { label: "BESTANDSVERTRAG", cls: "blau", gruende: ["läuft aus — Folgeausschreibung"] };
  if (e.E2 != null && e.E2 < T.E2_mittel) return { label: "GERINGE PASSUNG", cls: "gedaempft", gruende: [`Passung ${e.E2band}`] };
  if (e.E5 === "unzureichend") return { label: "FRIST ZU KNAPP", cls: "gedaempft", gruende: [`nur ${e.E5tage} Tage`] };
  if (e.E2 != null && e.E2 >= T.E2_hoch && e.E3 === "guenstig") return { label: "HOHE PASSUNG", cls: "gruen", gruende: ["hohe Passung", "Amtsinhaber angreifbar"] };
  if (e.E2 != null && e.E2 >= T.E2_hoch) return { label: "HOHE PASSUNG", cls: "gruen", gruende: ["hohe Passung"] };
  return { label: "PASSUNG MITTEL", cls: "neutral", gruende: [] };
}

// ── Kaskade B · Handlungsempfehlung (§3.3 B) ──
export function handlungsempfehlung(e, partnerMoeglich) {
  if (e.E8 === "eigen") return { label: "VERTEIDIGEN", cls: "blau", gruende: ["euer Bestandsvertrag läuft aus"], schritt: "Verteidigungsangebot vorbereiten" };

  if (e.E1 === "verletzt") {
    if (partnerMoeglich) return { label: "NOCH ZU KLÄREN", cls: "neutral", frage: `${e.E1_grund || "Eine Anforderung"} fehlt — über eine Bietergemeinschaft abdeckbar?`, gruende: ["Pflichtanforderung fehlt"], schritt: "Partner suchen" };
    return { label: "NICHT BEWERBEN", cls: "gedaempft", gruende: [`Pflichtanforderung nicht erfüllt${e.E1_grund ? ": " + e.E1_grund : ""}`], schritt: "Lead verwerfen" };
  }
  if (e.E5 === "unzureichend") return { label: "NICHT BEWERBEN", cls: "gedaempft", gruende: ["Frist reicht für den Aufwand nicht"], schritt: "Lead verwerfen" };
  if (e.E2 != null && e.E2 < T.E2_mittel) return { label: "NICHT BEWERBEN", cls: "gedaempft", gruende: ["geringe Passung zum Profil"], schritt: "Lead verwerfen" };
  if (e.E4 === "unverhaeltnismaessig") {
    if (e.E10_teilbar) return { label: "NOCH ZU KLÄREN", cls: "neutral", frage: "Aufwand hoch fürs Gesamtvolumen — Bewerbung auf ein einzelnes Los prüfen?", gruende: ["Aufwand/Wert unausgewogen"], schritt: "Einzel-Los prüfen" };
    return { label: "NICHT BEWERBEN", cls: "gedaempft", gruende: ["Aufwand steht nicht im Verhältnis zum Auftragswert"], schritt: "Lead verwerfen" };
  }
  if (e.E1 === "unbekannt") {
    const frage = e.E1_grund ? `Erfüllt ihr: ${e.E1_grund}? Eine Angabe genügt.` : "Deckt euer Profil die geforderten Nachweise? Angaben ergänzen.";
    return { label: "NOCH ZU KLÄREN", cls: "neutral", frage, gruende: ["offene Pflichtanforderung"], schritt: "Angabe ergänzen" };
  }

  // E1 erfüllt → Abwägung über {E3, E4, E5, E9}
  const unguenstig = [];
  if (e.E3 === "unguenstig") unguenstig.push({ k: "E3", t: "Amtsinhaber fest gebunden — Verdrängung unwahrscheinlich" });
  if (e.E4 === "unverhaeltnismaessig") unguenstig.push({ k: "E4", t: "Aufwand unverhältnismäßig" });
  if (e.E5 === "knapp") unguenstig.push({ k: "E5", t: `Frist knapp (${e.E5tage} T, Median ${e.E5median})` });
  if (e.E9 === "unguenstig") unguenstig.push({ k: "E9", t: `starkes Feld (Median ${e.E9med} Bieter)` });

  const guenstig = e.E2 >= T.E2_hoch && e.E3 === "guenstig" && (e.E4 === "angemessen" || e.E4 === "rahmen") && e.E5 === "ausreichend" && e.E9 !== "unguenstig";
  if (guenstig) {
    const g = ["alle Kriterien erfüllt"];
    if (e.E3 === "guenstig") g.push("Amtsinhaber schwach");
    if (e.E6 === "vorhanden") g.push("bekannte Stelle");
    return { label: "BEWERBEN", cls: "gruen", gruende: g.slice(0, 3), schritt: "Unterlagen in der Checkliste abarbeiten" };
  }
  if (unguenstig.length === 1) return { label: "NOCH ZU KLÄREN", cls: "neutral", frage: unguenstig[0].t, gruende: [unguenstig[0].t], schritt: "abwägen" };
  if (unguenstig.length >= 2) return { label: "NICHT BEWERBEN", cls: "gedaempft", gruende: unguenstig.map((u) => u.t), schritt: "Lead verwerfen" };
  return { label: "NOCH ZU KLÄREN", cls: "neutral", frage: "Rahmenbedingungen prüfen.", gruende: [], schritt: "abwägen" };
}

// ── Zusätze (§3.4), max. 2 in der Liste, feste Rangfolge ──
function zusaetze(e, partnerMoeglich) {
  const z = [];
  if (partnerMoeglich && e.E1 === "verletzt") z.push({ k: "partner", t: "mit Partner möglich" });
  if (e.E10_teilbar) z.push({ k: "los", t: `Einzel-Los möglich (${e.loseN} Lose)` });
  if (e.E5 === "knapp") z.push({ k: "frist", t: "Frist knapp" });
  if (e.E9 !== "unbekannt") z.push({ k: "bieter", t: `Median ${e.E9med} Bieter` });
  if (e.istRahmen) z.push({ k: "rahmen", t: "Rahmenvertrag — Nennwert ist Schätzgrenze" });
  if (e.E8 === "erstvergabe") z.push({ k: "erst", t: "Erstvergabe — kein Amtsinhaber" });
  if (e.E6 === "vorhanden") z.push({ k: "stelle", t: "bekannte Stelle" });
  return z;
}

/* Öffentliche API. `profile` = Engine-Profil (+ #27 attributes), `ctx` = {ownBuyers, tier}. */
export function recommend(lead, profile, ctx) {
  ctx = ctx || {};
  const hatProfil = !!(profile && profile.cpvFields && profile.cpvFields.length);
  const e = evaluate(lead, profile, ctx);
  const cov = coverage(profile);
  const a = einordnung(e);

  // §3.9 Kaltstart: unter Mindestabdeckung KEINE Empfehlung (Kaskade B ausgesetzt), nur Einordnung.
  // Ebenso Zustand A (keine Unterlagen) → keine Empfehlung möglich.
  const partnerMoeglich = e.E1 === "verletzt" && e.loseN >= 2;   // teilbare Lücke (§3.4)
  let b = null, gesperrt = null;
  if (!hatProfil) gesperrt = "kein_profil";
  else if (e.datenzustand === "A") gesperrt = "keine_unterlagen";
  else if (cov < T.COVERAGE_MIN) gesperrt = "kaltstart";
  else b = handlungsempfehlung(e, partnerMoeglich);

  return {
    zustand: e.datenzustand, coverage: cov, evals: e,
    einordnung: a,
    empfehlung: b, gesperrt,
    zusaetze: zusaetze(e, partnerMoeglich).slice(0, 2),
    zusaetze_alle: zusaetze(e, partnerMoeglich),
  };
}

// Begründungskette fürs Detail (§4.2) — {E, label, zustand, quelle}.
export function begruendungskette(e) {
  return [
    { E: "E1", label: "Pflichtanforderungen", zustand: e.E1, quelle: e.datenzustand === "A" ? "keine Unterlagen" : "Unterlagen + Profil" },
    { E: "E2", label: "Relevanz", zustand: e.E2 == null ? "unbekannt" : `${e.E2} — ${e.E2band}`, quelle: "CPV · Region · Volumen" },
    { E: "E3", label: "Wettbewerbslage", zustand: e.E3 + (e.incAlter != null ? ` (Amtsinhaber ${e.incAlter} J.)` : e.E8 === "erstvergabe" ? " (Erstvergabe)" : ""), quelle: "incumbent · Wechselquote" },
    { E: "E4", label: "Aufwand/Wert", zustand: e.E4 + ` (Aufwand ${e.E4stufe})`, quelle: "#18 · Auftragswert" },
    { E: "E5", label: "Frist", zustand: e.E5tage == null ? "unbekannt" : `${e.E5tage} T · Median ${e.E5median}`, quelle: "Angebotsfrist" },
    { E: "E6", label: "Beziehung", zustand: e.E6, quelle: "eigene Zuschläge bei der Stelle" },
    { E: "E7", label: "Vertragsart", zustand: e.E7, quelle: "contract_kind" },
    { E: "E8", label: "Vergabeart", zustand: e.E8, quelle: "award_tender_link" },
    { E: "E9", label: "Bieterdichte", zustand: e.E9 === "unbekannt" ? "unbekannt (Fallzahl <8)" : `Median ${e.E9med}`, quelle: "vergleichbare Verfahren" },
    { E: "E10", label: "Losstruktur", zustand: e.loseN >= 2 ? `${e.loseN} Lose${e.E10_teilbar ? " · teilbar" : ""}` : "ein Los", quelle: "lead_lot" },
  ];
}
