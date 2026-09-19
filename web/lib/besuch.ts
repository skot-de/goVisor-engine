"use client";

/* Wann war dieser Nutzer zuletzt in der Liste?
 *
 * ⚠ WARUM `localStorage` UND NICHT SUPABASE. „Seit deinem letzten Besuch" ist eine Frage
 * an das Geraet vor dem Nutzer, nicht an sein Konto: wer morgens am Buerorechner und
 * abends am Laptop sucht, will abends nicht hoeren, dass nichts neu ist. Dazu kommt ein
 * praktischer Grund — drei Migrationen (0021, 0022, 0023) liegen als Datei vor und sind
 * nicht angewandt; alles, was hier ueber Supabase liefe, waere heute wirkungslos und
 * WUERDE NICHTS MELDEN (die Client-Module fangen jeden Fehler ab). Der Besuchsstempel
 * funktioniert ohne Migration, ab sofort.
 *
 * ⚠ DER STEMPEL WIRD BEIM VERLASSEN GESETZT, NICHT BEIM ANKOMMEN. Wer ihn beim Laden
 * setzt, loescht die Antwort auf die Frage, die er gerade stellt: alles waere sofort
 * „nicht mehr neu". Deshalb liest die Seite den alten Wert und schreibt den neuen erst,
 * wenn der Besuch vorbei ist.
 */
const SCHLUESSEL = "govisor.besuch.v1";

/** Der Stand des VORIGEN Besuchs als `YYYY-MM-DD`, oder null beim allerersten Mal. */
export function letzterBesuch(): string | null {
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    if (!roh) return null;
    const d = JSON.parse(roh) as { am?: string };
    return typeof d.am === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d.am) ? d.am : null;
  } catch {
    return null;
  }
}

/** Diesen Besuch festhalten. Mehrfach aufzurufen ist unschaedlich. */
export function besuchMerken(): void {
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify({ am: new Date().toISOString().slice(0, 10) }));
  } catch {
    /* privater Modus, voller Speicher: dann gibt es eben keine Frischemarke */
  }
}

/** Beim allerersten Besuch gibt es kein „seit wann" — dann zaehlt dieses Fenster.
 *
 * ⚠ Ohne diesen Rueckfall waere die erste Sitzung die einzige ohne jede Marke, und das
 * ausgerechnet bei dem Nutzer, der die Liste noch nicht kennt. Sieben Tage, weil das dem
 * Takt entspricht, in dem Fristen laufen. */
export function stichtag(): string {
  const b = letzterBesuch();
  if (b) return b;
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}
