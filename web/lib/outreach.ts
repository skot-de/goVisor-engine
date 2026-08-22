import { loadDataFile, ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Vorberechnete Outreach-Landings (scripts/export_outreach.py), nach Token verschlüsselt.
 * Statisch + serverless-fähig — die Landing /t/<token> braucht kein Python im Deploy. */

/* Die Landing besteht aus BAUSTEINEN, nicht aus festen Feldern.
 *
 * Jeder Baustein hat sich im Generator selbst als belegt erwiesen, sonst wäre er nicht
 * hier. Die Oberfläche darf deshalb keinen bestimmten Baustein voraussetzen und keinen
 * durch einen Platzhalter ersetzen: fehlt einer, fehlt er, weil wir es für diese Firma
 * nicht wissen. Ein Ersatz an dieser Stelle wäre wieder das, was die alte Fassung tat.
 *
 * `art` je Zeile statt einer pauschalen Überschrift: nur Rahmen- und Wiederholungs-
 * verträge laufen im Wortsinn aus (gemessen 19,3 %); Bauleistungen werden fertig. */
export type Zahl = { wert: string | null; label: string };
export type Zeile = {
  titel: string; buyer: string; vol: string | null; ende: string | null;
  /** Rohdatum der Frist. Die Restlaufzeit wird beim ANZEIGEN gerechnet, nicht beim
   *  Erzeugen — sonst friert „noch 2 Tage" im statischen JSON ein. */
  endeISO?: string | null;
  art: "auslauf" | "fertigstellung" | "unklar";
};
export type Baustein = {
  id: string; staerke: number; titel: string;
  /** „was wir über euch wissen" vs. „was wir für euch finden". Trägt den Bogen der Seite. */
  gruppe?: "ueber_euch" | "fuer_euch";
  /** Kachel in der Kennzahlenleiste oder eigene Karte (nur die Vertragstabelle). */
  form?: "kpi" | "karte";
  zahlen?: Zahl[]; zeilen?: Zeile[]; namen?: string[];
  /** Schrittweise Eingrenzung auf die Firma. Beantwortet „wie viele genau fuer uns?". */
  trichter?: { n: number; label: string; hinweis?: string | null }[];
  /** Der Kettensatz ueber der Kette: „X sagt der Markt. Wir sagen Y …". */
  kette?: string | null;
  n_auslauf?: number; n_fertigstellung?: number;
  /** Ein Satz, der ohne Umgebung trägt. Speist den Kernbefund im Seitenkopf. */
  kern?: string | null;
  /** Die FOLGE des Befunds („fällt der grösste aus, fehlen 50 %"). Ohne sie ist der
   *  Befund eine Beobachtung, die der Empfänger längst kennt, und kein Grund zu handeln. */
  folge?: string | null;
  /** Anteil 0..1 für den Balken (nur wo eine Konzentration gemessen wurde). */
  anteil?: number;
  /** Schlussfolgerung aus der Tabelle, ersetzt die frühere Spalte „Art". */
  befund?: string | null;
  /** Fertig formulierter Hinweis auf das, was wir NICHT zeigen. Vom Generator,
   *  weil nur er weiss, ob ueberhaupt Zeilen dastehen. */
  verschwiegen_text?: string | null;
  /** Einordnung, wo kein Einzelwert veröffentlicht ist (CPV-Vergleichswert). */
  vergleich?: string | null;
  /** Was diese Zahlen NICHT abdecken. Pflichtfeld, kein Beiwerk. */
  grenze: string;
  /** Anschluss an einen Produktbereich (Strategie, Unternehmen, Planung). */
  bruecke: { produkt: string; text: string };
};
export type Landing = {
  id: string; name: string; stand: string;
  /** Die eine Aussage für den Seitenkopf, aus dem überraschendsten Baustein. */
  kern: string | null;
  bausteine: Baustein[];
  belegt: string[];
  /** Produktbereiche, in die diese Firma konkret führt. Gebündelt im Abschluss. */
  bereiche?: string[];
  /** Was die Zahlen fuer den Empfaenger bedeuten. Schliesst die HEUTE-Haelfte ab. */
  muster?: string | null;
  /** Zustellquittung: Hash der Adresse, an die wir den Link geschickt haben.
   *  Kein Ausweis — nur der Nachschlagewert fuer die Postfach-Pruefung. */
  zustellung?: { hash: string; am: string; domain: string | null } | null;
  /** Vorschlag fuer den warmen Onboarding-Weg. `null` heisst: wir wissen es nicht. */
  vorbelegung?: { branche: string | null; regionen: string[] } | null;
};


/* ⚠ Über `loadDataFile`, NICHT direkt von der Platte. Seit `web/data` nicht mehr in Git
   liegt, kommt die Datei auf einem Deployment aus dem Objektspeicher (`DATA_BASE_URL`).
   Ein direktes `readFile(process.cwd()/data/...)` findet dort NICHTS und liefert still
   einen leeren Bestand — die Oberfläche sähe aus, als gäbe es keine Daten. */
export async function loadLanding(token: string): Promise<Landing | null> {
  // Wie bei suppliers/firmaProfiles: kein ewiger Speicher mehr. Eine Instanz, die den
  // Outreach-Bestand bis zum Neustart festhält, zeigt frisch angeschriebenen Firmen ihre
  // Landing nicht — sie war beim Start noch nicht dabei.
  let alle = ausSpeicher<Record<string, Landing>>("outreach:geparst");
  if (!alle) {
    try {
      const roh = await loadDataFile("outreach.json");
      alle = inSpeicher("outreach:geparst", roh ? JSON.parse(roh) : {}, roh?.length ?? 0);
    } catch { alle = inSpeicher("outreach:geparst", {}, 0); }
  }
  return alle?.[token] ?? null;
}
