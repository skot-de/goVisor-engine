import { NextResponse, type NextRequest } from "next/server";
import type { EmailOtpType } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";

/**
 * Rückkehr aus einer Anmelde-Mail: Magic Link, Passwort-Wiederherstellung, Einladung,
 * Bestätigung der Adresse.
 *
 * **Warum es das vorher nicht gab und was das kostete.** Die App kannte ausschliesslich
 * E-Mail plus Passwort. Supabase kann Magic Link und Recovery seit jeher, nur landete jede
 * dieser Mails auf einer Adresse, die den Token nie einlöste. Sven am 2026-08-18, nachdem
 * er weder mit Magic Link noch mit Wiederherstellung hineinkam: genau dieser Fall. Wer sein
 * Passwort nicht kennt, kam bis hier gar nicht mehr in sein Konto.
 *
 * **Zwei Formen, und die zweite ist die wichtigere.**
 *
 *   `?code=…`        PKCE. Der Prüfschlüssel liegt im Browser, der die Mail ANGEFORDERT hat.
 *                    Funktioniert nur dort, dafür ist es der sichere Normalweg.
 *   `?token_hash=…`  Einmal-Token ohne Prüfschlüssel. Das ist die Form, die aus dem
 *                    Supabase-Dashboard erzeugte Links tragen, und die einzige, die auch
 *                    dann noch trägt, wenn die Mail auf einem anderen Gerät geöffnet wird.
 *
 * Beide werden bedient, `token_hash` zuerst: liegt er an, ist PKCE ohnehin aussichtslos.
 *
 * **Der Fehlerfall führt zum Login, nicht ins Leere.** Ein abgelaufener Link ist der
 * Normalfall, nicht die Ausnahme (Supabase-Vorgabe: eine Stunde). Ihn mit einer nackten
 * Fehlerseite zu beantworten hiesse, den Nutzer im selben Zustand zurückzulassen wie vorher.
 */
export const dynamic = "force-dynamic";

// Nur die Typen, die wir selbst verschicken. Ein ungeprüfter `type` aus der URL ginge
// unbesehen an Supabase weiter, und die Liste dessen, was dabei entstehen kann, waechst mit
// jeder Bibliotheksversion, ohne dass es hier jemandem auffiele.
const TYPEN = new Set<EmailOtpType>(["magiclink", "recovery", "invite", "email", "email_change", "signup"]);

/** Nur seiteneigene Ziele. `//fremde.de` ist ein gueltiger Pfadanfang und landet woanders. */
function sicheresZiel(roh: string | null): string {
  if (!roh || !roh.startsWith("/") || roh.startsWith("//")) return "/leads";
  return roh;
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const weiter = sicheresZiel(url.searchParams.get("next"));
  const supabase = await createClient();

  const tokenHash = url.searchParams.get("token_hash");
  const typ = url.searchParams.get("type") as EmailOtpType | null;
  const code = url.searchParams.get("code");

  let fehler: string | null;
  if (tokenHash && typ && TYPEN.has(typ)) {
    fehler = (await supabase.auth.verifyOtp({ type: typ, token_hash: tokenHash })).error?.message ?? null;
  } else if (code) {
    fehler = (await supabase.auth.exchangeCodeForSession(code)).error?.message ?? null;
  } else {
    // Supabase haengt bei abgelaufenen Links seine eigene Begruendung an die URL. Sie ist
    // brauchbarer als alles, was wir hier erfinden koennten.
    fehler = url.searchParams.get("error_description") ?? "Der Link enthält keinen Anmeldecode.";
  }

  if (fehler) {
    const ziel = new URL("/login", request.url);
    ziel.searchParams.set("fehler", fehler);
    return NextResponse.redirect(ziel);
  }

  const antwort = NextResponse.redirect(new URL(weiter, request.url));

  // VORHANG: live liegt die App hinter der Coming-Soon-Sperre. Ohne diese Zeile käme man
  // per Mail zwar herein und stünde danach vor einer schwarzen Seite. Ein eingelöster
  // Supabase-Einmal-Token ist ein stärkerer Nachweis als die Kenntnis des geheimen Pfades,
  // der denselben Vorhang öffnet. FAIL-CLOSED bleibt: ohne gesetztes `ZUGANG_PFAD` gibt es
  // diesen Weg nicht, und was der Nutzer danach sieht, entscheidet weiterhin seine Sitzung.
  const zugang = process.env.ZUGANG_PFAD ?? "";
  if (zugang) {
    antwort.cookies.set("gv_vorhang", zugang, {
      httpOnly: true, sameSite: "lax", secure: true, path: "/", maxAge: 60 * 60 * 24 * 30,
    });
  }
  return antwort;
}
