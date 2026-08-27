/**
 * Informationsdichte eines Leads — wie viel können wir über diese Vergabe sagen?
 *
 * **Warum es das gibt.** Wer in einer Liste klickt, trifft oft eine Vergabe, zu der wir
 * wenig sagen können. Ob das die Nutzer stört, wissen wir NICHT — und genau diese Frage
 * soll messbar werden, bevor wir ein Symbol dagegen bauen. Die Stufe wird deshalb bei
 * jedem Lead-Klick mitgeschrieben (`analytics.recordLeadClick`).
 *
 * **Warum keine Punktzahl.** Ein naives Zählen der vorhandenen Felder führt in die Irre:
 * einen Unterlagen-LINK haben die meisten, Lose viele — beides sagt nichts darüber, ob man
 * die Vergabe beurteilen kann. Eine Punktzahl hätte die eine wichtige Eigenschaft unter
 * fünf billigen begraben.
 *
 * ## ⚠ Was „reich" bis zum 2026-08-26 bedeutete, und warum das falsch war
 *
 * Die erste Fassung schloss aus dem VORHANDENSEIN von Anforderungen auf „Unterlagen
 * gelesen" — und zählte dabei `bindefristTage` und `buergschaft` mit. Die stammen aber
 * regelmässig aus eForms-Attributen, nicht aus Dokumenten. Gemessen am 2026-08-26:
 *
 *     als „reich" eingestuft            11.731
 *       davon mit Volltext bei uns       5.443
 *       davon OHNE Volltext              6.288   ← 54 %
 *         nur wegen Bindefrist/Bürgschaft 6.063
 *
 * Bei 54 % der „reichen" Leads war nie ein Dokument gelesen worden. Das ist keine
 * Kosmetik: die Stufe wird je Klick in `user_lead_interactions` und PostHog geschrieben,
 * und sie ist **nachträglich nicht rekonstruierbar** — die Dichte eines Leads ändert sich,
 * sobald seine Unterlagen ankommen. Jeder falsch verbuchte Klick bleibt falsch.
 *
 * Seit dem 2026-08-25 gibt es die Tatsache statt des Rückschlusses: `unterlagen.gelesen`
 * sagt, ob der Volltext bei uns liegt, `anf.quelle` sagt, woher der Inhalt stammt.
 *
 * Verteilung nach der Korrektur (2026-08-26, 43.542 Leads):
 *
 *     reich     5.359   12,3 %   Unterlagen gelesen UND ausgewertet
 *     mittel   15.299   35,1 %   Unterlagen da oder Angaben aus der Bekanntmachung
 *     duenn    22.884   52,6 %   nur Kopfdaten
 *
 * `merkmale()` gibt weiterhin zurück, was KONKRET vorliegt — inklusive der Herkunft.
 * „reich wegen Eignung aus Unterlagen" und „mittel wegen Bindefrist aus eForms" sind sehr
 * verschiedene Leads, und die spätere Frage „warum wurde geklickt" braucht den Unterschied.
 */

export type Dichte = "reich" | "mittel" | "duenn";

/**
 * Eingabe bewusst DURCHLÄSSIG. Die Lead-Objekte stammen aus JSON und tragen einen locker
 * gehaltenen Typ, der `anf`/`unterlagen` gar nicht deklariert. Hier eine enge Struktur zu
 * verlangen hiesse, am Aufrufort eine Typ-Zusicherung zu schreiben — und die behauptet
 * etwas, statt es zu prüfen. Also lieber hier prüfen, wo es hingehört.
 */
export type LeadArtig = Record<string, unknown> | null | undefined;

type Anf = {
  eignung?: unknown[]; zertifikate?: unknown[];
  bindefristTage?: number | null; buergschaft?: boolean | null;
  quelle?: string;
};

type Unterlagen = { gelesen?: boolean };

function objVon<T>(l: LeadArtig, feld: string): T {
  const v = (l as Record<string, unknown> | null)?.[feld];
  return (v && typeof v === "object" ? v : {}) as T;
}

const anfVon = (l: LeadArtig) => objVon<Anf>(l, "anf");

/**
 * Liegt der Volltext der Vergabeunterlagen bei UNS? Tatsache aus dem Export, kein
 * Rückschluss. Entsteht in `scripts/export_web_leads.py:_unterlagen`.
 */
function volltextDa(l: LeadArtig): boolean {
  return objVon<Unterlagen>(l, "unterlagen").gelesen === true;
}

/**
 * Stammt der Inhalt der Anforderungen aus den UNTERLAGEN — oder aus der Bekanntmachung?
 *
 * `anf.quelle` setzt der Export auf „unterlagen", sobald die Dokumentanalyse Eignung oder
 * Bürgschaft geliefert hat. Zertifikate gibt es ausschliesslich von dort, deshalb zählen
 * sie ebenfalls: ohne sie fiele ein Lead durch, dessen Analyse nur Zertifikate ergab.
 */
function inhaltAusUnterlagen(l: LeadArtig): boolean {
  const a = anfVon(l);
  return a.quelle === "unterlagen" || Boolean(a.zertifikate?.length);
}

/** Trägt die Bekanntmachung selbst genug für eine erste Einschätzung? */
function bekanntmachungTraegt(l: LeadArtig): boolean {
  const a = anfVon(l);
  return Boolean(
    a.eignung?.length || a.bindefristTage || a.buergschaft ||
    (l as Record<string, unknown> | null)?.hasDetail ||
    ((l as Record<string, unknown> | null)?.frist && (l as Record<string, unknown> | null)?.lose),
  );
}

export function dichte(l: LeadArtig): Dichte {
  if (!l) return "duenn";
  // REICH: die Unterlagen liegen vor UND die Auswertung hat daraus etwas gemacht. Nur das
  // trägt Checkliste, Eignungsabgleich und Aufwandsschätzung — also das, wofür man das
  // Produkt benutzt. Beide Bedingungen zusammen: Volltext ohne Auswertung hilft niemandem,
  // und Anforderungen ohne Volltext stammen aus der Bekanntmachung.
  if (volltextDa(l) && inhaltAusUnterlagen(l)) return "reich";
  // MITTEL: entweder liegen die Unterlagen vor und die Auswertung steht noch aus, oder die
  // Bekanntmachung trägt genug für eine erste Einschätzung.
  if (volltextDa(l) || bekanntmachungTraegt(l)) return "mittel";
  return "duenn";
}

/**
 * Was konkret vorliegt — für Tooltips und für die Auswertung.
 *
 * Eine Stufe allein wäre für die spätere Frage „warum wurde geklickt/nicht geklickt" zu
 * grob. ⚠ Seit dem 2026-08-26 steht die HERKUNFT dabei (`quelle:unterlagen` bzw.
 * `quelle:eforms`); ohne sie liessen sich die beiden Fälle im Nachhinein nicht trennen,
 * und genau diese Verwechslung war der Anlass für den Umbau.
 */
export function merkmale(l: LeadArtig): string[] {
  if (!l) return [];
  const a = anfVon(l);
  const r = l as Record<string, unknown>;
  const m: string[] = [];
  if (volltextDa(l)) m.push("volltext");
  if (a.eignung?.length) m.push("eignung");
  if (a.zertifikate?.length) m.push("zertifikate");
  if (a.bindefristTage) m.push("bindefrist");
  if (a.buergschaft) m.push("buergschaft");
  if (r.hasDetail) m.push("beschreibung");
  if (r.lose) m.push("lose");
  if (r.frist) m.push("frist");
  if (a.eignung?.length || a.zertifikate?.length || a.bindefristTage || a.buergschaft) {
    m.push(inhaltAusUnterlagen(l) ? "quelle:unterlagen" : "quelle:eforms");
  }
  return m;
}
