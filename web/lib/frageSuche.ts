/**
 * Fragen statt Stichwörter — „zeig mir die Aufträge mit den niedrigsten Bietern".
 *
 * **Warum regelbasiert und nicht per Sprachmodell.** Nicht aus Sparsamkeit, sondern weil
 * eine Suche, die filtert, NACHVOLLZIEHBAR sein muss. Wer „wenig Bieter" eingibt und 2.430
 * statt 6.786 Ergebnissen sieht, muss erkennen können, WARUM — sonst ist das Ergebnis eine
 * Behauptung. Jede Absicht hier setzt deshalb genau einen benannten Filter, erzeugt ein
 * sichtbares Token mit Klartext und lässt sich mit einem Klick wieder entfernen.
 *
 * Ein Sprachmodell wäre für den langen Schwanz seltener Formulierungen die richtige zweite
 * Stufe. Es gehört aber HINTER diese hier, nicht davor: was regelbasiert eindeutig ist,
 * soll nicht von einem Modell geraten werden — gleiche Frage, gleiches Ergebnis, immer.
 *
 * **Was NICHT passiert: raten.** Erkennt keine Regel etwas, gibt `deuteFrage` `null` zurück
 * und die Suche verhält sich wie bisher (Volltext). Eine Frage halb zu verstehen und
 * stillschweigend einen Teil zu filtern wäre schlimmer als sie nicht zu verstehen.
 */
import type { Adv } from "@/components/explorer/FilterPanel";

export type Absicht = {
  /** Stabile Kennung — auch die Token-Kennung, damit dasselbe nicht zweimal greift. */
  id: string;
  /** Was im Token steht. Muss die WIRKUNG benennen, nicht die Frage wiederholen. */
  label: string;
  /** Filteränderung. Wird über den bestehenden Zustand gelegt, ersetzt ihn nicht. */
  adv?: Partial<Adv>;
  /** Sortierung, wenn die Frage eine Reihenfolge verlangt („niedrigste", „größte"). */
  sort?: { key: string; dir: 1 | -1 };
};

type Regel = { id: string; muster: RegExp; label: string; adv?: Partial<Adv>;
               sort?: { key: string; dir: 1 | -1 } };

/**
 * Die Regeln. Reihenfolge zählt: die erste passende gewinnt, deshalb steht Spezielles vor
 * Allgemeinem („kein Bieter" vor „wenig Bieter").
 *
 * Formulierungen stammen aus Svens eigener Frage und ihren naheliegenden Varianten. Wer
 * hier ergänzt, ergänzt eine Behauptung darüber, wie jemand fragt — im Zweifel lieber eine
 * Regel weniger und ehrlich in die Volltextsuche fallen.
 */
const REGELN: Regel[] = [
  {
    id: "wenig-bieter",
    // „niedrigste bieter", „wenigste bieter", „wenig wettbewerb", „nur ein bieter",
    // „kaum konkurrenz", „am wenigsten bieter in der vergangenheit"
    muster: /(wenig|wenigste|niedrigst|geringst|kaum|nur ein|einzig)\w*\s+(bieter|wettbewerb|konkurrenz|angebote)/i,
    label: "wenigste Bieter (zuletzt ≤ 3)",
    adv: { wenigWettbewerb: true },
    // Aufsteigend nach Wettbewerbsstufe: gering (1) zuerst — das ist die Frage.
    sort: { key: "konk", dir: 1 },
  },
  {
    id: "wenig-bieter-kurz",
    muster: /\b(single.?bid|ein.?bieter|bieterarm)\b/i,
    label: "wenigste Bieter (zuletzt ≤ 3)",
    adv: { wenigWettbewerb: true },
    sort: { key: "konk", dir: 1 },
  },
  {
    id: "neuvergabe",
    muster: /(neuvergabe|kein\w*\s+(amtsinhaber|incumbent|vorgänger)|erstmalig|zum ersten mal)/i,
    label: "Neuvergabe (kein Amtsinhaber)",
    adv: { neu: "neu" },
  },
  {
    id: "rahmen",
    muster: /rahmen(vertr|vereinbar|abkommen)/i,
    label: "nur Rahmenverträge",
    adv: { art: ["rahmen"] },
  },
  {
    id: "mit-unterlagen",
    muster: /(mit|inkl\w*)\s+(vergabe)?unterlagen|unterlagen (da|vorhanden|verfügbar)/i,
    label: "nur mit Vergabeunterlagen",
    adv: { unterlagen: true },
  },
  {
    id: "wenig-aufwand",
    muster: /(wenig|gering|niedrig)\w*\s+aufwand|(einfach|schnell)\w*\s+(zu )?(bieten|angebot)/i,
    label: "geringer Angebotsaufwand",
    adv: { aufwand: ["niedrig"] },
  },
  {
    id: "gute-chance",
    muster: /(gute|hohe|beste)\w*\s+(chance|wechselchance|aussicht)/i,
    label: "hohe Wechsel-Chance",
    adv: { chance: ["hoch"] },
  },
  {
    id: "bald",
    muster: /(läuft|laeuft|läuft bald|bald)\s*(aus|ab)|(nächst|naechst)\w*\s+(woche|monat)|dringend|kurzfristig/i,
    label: "Frist in den nächsten 3 Monaten",
    adv: { horizon: 3 },
  },
];

/** Zahl mit Einheit aus „über 1 Mio", „ab 500k", „mehr als 250.000 €". */
const WERT = /(?:über|ueber|ab|mehr als|mindestens|>)\s*([\d.,]+)\s*(mio|mio\.|millionen|k|tsd|tausend)?/i;

function wertAbsicht(text: string): Absicht | null {
  const m = WERT.exec(text);
  if (!m || !/(wert|volumen|auftrag|€|eur|mio|millionen)/i.test(text)) return null;
  const zahl = parseFloat(m[1].replace(/\./g, "").replace(",", "."));
  if (!isFinite(zahl) || zahl <= 0) return null;
  const einheit = (m[2] || "").toLowerCase();
  const faktor = /mio|millionen/.test(einheit) ? 1e6 : /k|tsd|tausend/.test(einheit) ? 1e3 : 1;
  const min = Math.round(zahl * faktor);
  return {
    id: `wert-min-${min}`,
    label: `Wert ab ${min.toLocaleString("de-DE")} €`,
    adv: { valMin: min },
  };
}

/**
 * Text → Absicht, oder `null`, wenn keine Regel greift.
 *
 * `null` ist ein vollwertiges Ergebnis, kein Fehler: die Suche fällt dann auf ihr bisheriges
 * Verhalten zurück (Ort/PLZ/Volltext). Nur so bleibt „Berlin" eine Ortssuche und wird nicht
 * von einer übereifrigen Regel eingefangen.
 */
export function deuteFrage(text: string): Absicht | null {
  const t = (text || "").trim();
  // Unter vier Zeichen ist nichts eine Frage — „Bau", „IT", „5xx" gehören in die Volltextsuche.
  if (t.length < 4) return null;
  for (const r of REGELN) {
    if (r.muster.test(t)) return { id: r.id, label: r.label, adv: r.adv, sort: r.sort };
  }
  return wertAbsicht(t);
}

/**
 * Beispiele für die Vorschlagsliste — sie sind der einzige Weg, auf dem jemand erfährt,
 * dass die Suche das überhaupt kann. Eine Fähigkeit, die man erraten muss, hat niemand.
 */
export const BEISPIELFRAGEN = [
  "Aufträge mit den wenigsten Bietern",
  "Neuvergaben ohne Amtsinhaber",
  "Rahmenverträge mit Unterlagen",
  "läuft bald aus",
  "Wert über 1 Mio",
];
