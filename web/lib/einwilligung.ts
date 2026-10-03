/**
 * Einwilligung in die Messung — gemeinsame Begriffe fuer Browser und Server.
 *
 * ZWEI STUFEN, nicht ein Schalter (s. 0036):
 *   Stufe 1, immer: cookielose Messung auf Grundlage berechtigten Interesses. Keine Kennung,
 *            keine Wiedererkennung. Beantwortet „wie viele Aufrufe, wie lange, woher grob".
 *   Stufe 2, nur mit Einwilligung: dauerhafte Besucherkennung, Zuordnung ueber Besuche
 *            hinweg, Kampagnen, voller Referrer, Browser und Geraet.
 *
 * ⚠ WARUM NICHT „ohne Einwilligung messen wir nichts". Das waere rechtlich bequemer und
 *   praktisch schlechter: die Mehrheit willigt nicht ein, und dann faellt genau die Zahl aus,
 *   um die es vor dem Start geht — wie viele Fremde ueberhaupt auf einer Landingpage landen.
 *   Stufe 1 braucht keine Einwilligung, weil sie niemanden wiedererkennbar macht.
 *
 * ⚠ WARUM NICHT „wir messen alles und fragen nicht". `besucher` ist ein
 *   Wiedererkennungsmerkmal und braucht nach § 25 TDDDG eine Einwilligung — unabhaengig
 *   davon, ob man es Cookie nennt oder in localStorage legt. Die Technik entscheidet das
 *   nicht, der Zweck tut es.
 */

/** Entscheidung des Besuchers. Fehlt das Cookie, ist noch nichts entschieden. */
export const EINWILLIGUNG_COOKIE = "gv_mess";
/** Dauerhafte Besucherkennung. Wird NUR gesetzt, wenn die Entscheidung „ja" lautet. */
export const BESUCHER_COOKIE = "gv_besucher";

/** 12 Monate. ⚠ Beide Cookies gleich lang: laeuft die Entscheidung vor der Kennung ab,
 *  wird erneut gefragt, obwohl die Kennung noch liegt — und eine Kennung ohne gueltige
 *  Einwilligung ist genau das, was nicht sein darf. */
export const COOKIE_TAGE = 365;

export type Entscheidung = "ja" | "nein" | null;

export function istJa(wert: string | undefined | null): boolean {
  return wert === "ja";
}

/** Entscheidung aus einem Cookie-Kopfzeilenwert lesen (Server) oder aus document.cookie. */
export function leseCookie(cookieZeile: string | undefined | null, name: string): string | null {
  if (!cookieZeile) return null;
  for (const teil of cookieZeile.split(";")) {
    const [k, ...rest] = teil.trim().split("=");
    if (k === name) return decodeURIComponent(rest.join("=")) || null;
  }
  return null;
}

/* ───────────────────────────────────────────────────────── Kampagnen aus der Adresse */

/**
 * `utm_*`-Felder aus einem Query-String ziehen.
 *
 * ⚠ EINE FESTE LISTE, NICHT DER GANZE QUERY-STRING. Der Query-String kann alles tragen —
 *   Einladungstoken, Mailadressen, Suchbegriffe. Nur diese fuenf Namen sind
 *   Kampagnenkennzeichnung und nichts sonst. Ein „wir speichern die Adresse mit" waere der
 *   bequeme Weg und wuerde irgendwann einen Token in die Telemetrie tragen.
 */
const UTM = ["utm_source", "utm_medium", "utm_campaign"] as const;

export type Kampagne = { utm_quelle?: string; utm_medium?: string; utm_kampagne?: string };

export function kampagneAus(suche: string | null | undefined): Kampagne {
  if (!suche) return {};
  let p: URLSearchParams;
  try { p = new URLSearchParams(suche.startsWith("?") ? suche.slice(1) : suche); }
  catch { return {}; }
  const kurz = (s: string | null) => (s ? s.slice(0, 120) : undefined);
  const k: Kampagne = {
    utm_quelle: kurz(p.get(UTM[0])),
    utm_medium: kurz(p.get(UTM[1])),
    utm_kampagne: kurz(p.get(UTM[2])),
  };
  // Leere Felder nicht mitschicken, damit die Tabelle nicht mit NULL-Zeilen voller
  // Platzhalter waechst.
  return Object.fromEntries(Object.entries(k).filter(([, v]) => v)) as Kampagne;
}

/* ───────────────────────────────────────────────── Browser und Geraet, grob */

/**
 * Grobe Klasse aus dem User-Agent. NUR mit Einwilligung zu verwenden.
 *
 * ⚠ GROB IST ABSICHT. Eine genaue Version plus Plattform plus Sprache ist ein
 *   Fingerabdruck, mit dem man einen Besucher auch ohne Cookie wiedererkennt. Fuer die
 *   Frage „bauen wir die Oberflaeche fuer die richtigen Geraete" genuegt die Klasse, und
 *   mehr zu speichern waere eine Preisgabe ohne Gegenwert.
 */
export function browserKlasse(ua: string | null | undefined): string | null {
  if (!ua) return null;
  const u = ua.toLowerCase();
  if (u.includes("edg/")) return "Edge";
  if (u.includes("opr/") || u.includes("opera")) return "Opera";
  if (u.includes("firefox")) return "Firefox";
  if (u.includes("chrome") || u.includes("chromium")) return "Chrome";
  if (u.includes("safari")) return "Safari";
  return "sonstiger";
}

export function geraeteKlasse(ua: string | null | undefined, viewportBreite?: number | null): string | null {
  const u = (ua || "").toLowerCase();
  if (u.includes("ipad") || u.includes("tablet")) return "Tablet";
  if (u.includes("mobile") || u.includes("iphone") || u.includes("android")) return "Mobil";
  if (u) return "Desktop";
  // ⚠ Rueckfall ohne User-Agent: die Fensterbreite. Sie steht schon in Stufe 1 und ist
  //   kein Personenbezug — deshalb funktioniert diese Einordnung auch ohne Einwilligung.
  if (typeof viewportBreite === "number" && viewportBreite > 0) {
    return viewportBreite < 768 ? "Mobil" : viewportBreite < 1024 ? "Tablet" : "Desktop";
  }
  return null;
}
