import "server-only";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { verschluessele, entschluessele, KeinSchluessel } from "@/lib/blockCrypto";
import { textAusDatei, NichtLesbar } from "@/lib/fragebogenLesen";

export const runtime = "nodejs";          // Buffer + node:crypto fuer die Verschluesselung
export const maxDuration = 60;            // eine grosse PDF braucht Zeit zum Auslesen

/* Antwortauftrag — der Knopf (Funktion 1 der Go-live-Liste), Weboberflaechenseite.
 *
 * POST legt einen Auftrag ab, GET fragt ihn ab. Gerechnet wird NICHT hier, sondern in
 * `scripts/antwort_arbeiter.py`. Warum: die Geldwache sitzt in `llm.chat()` und nicht im
 * Aufrufer; eine Route, die selbst bei OpenRouter anklopft, umgeht Kontostand, Tagesbuch und
 * Deckel. Der naheliegende Weg waere `spawn python3` gewesen wie in `draft-check` — das ist
 * aber genau eine der Routen, die nicht serverless-faehig sind, und aus vier wuerden fuenf.
 * Entscheidung und Begruendung im Kopf von `supabase/0037_antwortauftrag.sql`.
 *
 * ⚠ ES KOMMT TEXT HEREIN, KEINE DATEI. Das ist dieselbe Form wie beim Bausteine-Import
 * (`/api/blocks-import`): der Nutzer fuegt den Fragenteil des Bogens ein. Eine Datei zu
 * verarbeiten braucht einen PDF-, DOCX- und XLSX-Leser, und den gibt es im Browser dieses
 * Projekts nicht (keine solche Abhaengigkeit in `web/package.json`, gepruefet 2026-10-04).
 * Das ist der naechste Schritt und ausdruecklich noch nicht dieser.
 */

/* ⚠ `bytea` reist als Hex-Zeichenkette — dieselbe Falle wie in `/api/blocks` und in
 * `govisor/blockcrypto.py`. Rohe Bytes landen als `{"0":72,…}` und sind beim naechsten
 * Entschluesseln Schrott; es faellt nicht beim Schreiben auf. */
const zuHex = (b: Buffer) => "\\x" + b.toString("hex");
const ausHex = (s: string) => Buffer.from(s.startsWith("\\x") ? s.slice(2) : s, "hex");

const MIN_TEXT = 40;
const MAX_TEXT = 400_000;        // wie `/api/blocks-import`

async function sitzung() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  return { sb, user };
}

/* Die Organisation dieses Menschen. ⚠ `user_profiles.id` IST die Auth-Kennung (0001), es gibt
 * dort kein `user_id` — dieselbe Form wie in der RLS von 0027. */
async function orgVon(sb: Awaited<ReturnType<typeof createClient>>, uid: string) {
  const { data } = await sb.from("user_profiles").select("org_id").eq("id", uid).limit(1);
  return (data?.[0]?.org_id as string | undefined) ?? null;
}

export async function POST(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  let text = "", lead_id: string | null = null, dateiname: string | null = null, hinweis: string | undefined;

  if ((req.headers.get("content-type") || "").includes("multipart/form-data")) {
    /* Datei: wird HIER ausgelesen und danach verworfen. Gespeichert wird nur der Text, und der
     * verschluesselt. Begruendung und die Grenzen stehen in `lib/fragebogenLesen.ts`. */
    let datei: File | null = null;
    try {
      const form = await req.formData();
      const f = form.get("datei");
      datei = f instanceof File ? f : null;
      const l = form.get("lead_id");
      lead_id = l ? String(l).slice(0, 64) : null;
    } catch {
      return NextResponse.json({ error: "Datei nicht lesbar" }, { status: 400 });
    }
    if (!datei) return NextResponse.json({ error: "Keine Datei dabei" }, { status: 400 });
    /* ⚠ Die Grenze ist nicht nur Vorsicht, sondern das Hosting: eine Anfrage an eine
     * serverlose Funktion darf bei Vercel rund 4,5 MB gross sein. Ohne eigene Pruefung
     * bekaeme der Nutzer einen Plattformfehler ohne Erklaerung statt dieses Satzes. */
    if (datei.size > 4_000_000) {
      return NextResponse.json(
        { error: "Die Datei ist groesser als 4 MB. Bitte nur den Fragenteil hochladen." },
        { status: 413 });
    }
    dateiname = datei.name.slice(0, 200);
    try {
      const gelesen = await textAusDatei(new Uint8Array(await datei.arrayBuffer()), dateiname);
      text = gelesen.text;
      hinweis = gelesen.hinweis;
    } catch (e) {
      /* `NichtLesbar` traegt einen Satz, der fuer den Nutzer geschrieben ist (etwa der
       * Scan-Hinweis) — er wird durchgereicht und nicht durch eine eigene Formulierung ersetzt. */
      if (e instanceof NichtLesbar) {
        // Der Grund ins Protokoll, der Satz an den Menschen. Ohne das ist nicht zu klaeren,
        // warum eine Datei abgewiesen wurde, die anderswo durchlief.
        if (e.cause) console.error("[antwortauftrag] Datei:", e.message, "·", e.cause);
        return NextResponse.json({ error: e.message }, { status: 400 });
      }
      return NextResponse.json({ error: "Die Datei konnte nicht gelesen werden." }, { status: 400 });
    }
  } else {
    try {
      const b = await req.json();
      text = String(b.text || "");
      lead_id = b.lead_id ? String(b.lead_id).slice(0, 64) : null;
      dateiname = b.dateiname ? String(b.dateiname).slice(0, 200) : null;
    } catch {
      return NextResponse.json({ error: "Eingabe nicht lesbar" }, { status: 400 });
    }
  }
  if (text.trim().length < MIN_TEXT) {
    return NextResponse.json(
      { error: `Zu wenig Text (mindestens ${MIN_TEXT} Zeichen).` }, { status: 400 });
  }
  if (text.length > MAX_TEXT) text = text.slice(0, MAX_TEXT);

  const org_id = await orgVon(sb, user.id);
  if (!org_id) {
    return NextResponse.json({ error: "Keine Organisation hinterlegt." }, { status: 409 });
  }

  let fragebogen_encrypted: string;
  try {
    fragebogen_encrypted = zuHex(verschluessele(text));
  } catch (e) {
    /* ⚠ Fehlt der Schluessel, wird NICHT im Klartext gespeichert — es wird gar nicht
     * gespeichert. Dieselbe Entscheidung wie bei den Bausteinen: die Spalte heisst
     * `fragebogen_encrypted`, und niemand wuerde nachsehen. */
    if (e instanceof KeinSchluessel) {
      return NextResponse.json({ error: "Verschluesselung nicht eingerichtet." }, { status: 503 });
    }
    throw e;
  }

  const { data, error } = await sb.from("user_antwortauftrag")
    .insert({ org_id, profil_id: user.id, lead_id, dateiname, fragebogen_encrypted })
    .select("id, status, erstellt_at").limit(1);
  if (error) {
    /* ⚠ Die Datenbankmeldung NICHT durchreichen. Beim Sichttest stand im Gesicht des Nutzers
     * "Could not find the table 'public.user_antwortauftrag' in the schema cache" — fuer ihn
     * sinnlos, fuer einen Angreifer eine Auskunft ueber das Schema. Der Grund gehoert ins
     * Serverprotokoll, der Mensch bekommt einen Satz, mit dem er etwas anfangen kann. */
    console.error("[antwortauftrag] insert:", error.message);
    return NextResponse.json(
      { error: "Der Auftrag konnte nicht gespeichert werden. Bitte spaeter erneut versuchen." },
      { status: 500 });
  }

  return NextResponse.json({ auftrag: data?.[0] ?? null, hinweis });
}

export async function GET(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  const id = new URL(req.url).searchParams.get("id");

  /* Ohne `id`: die letzten Auftraege der Organisation, ohne Inhalte. Die Oberflaeche braucht
   * eine Liste, und `zaehlung` steht bewusst im Klartext in der Tabelle — so laesst sich der
   * Fortschritt zeigen, ohne jeden Auftrag zu entschluesseln. */
  if (!id) {
    const { data, error } = await sb.from("user_antwortauftrag")
      .select("id, status, dateiname, lead_id, zaehlung, fragen_gesamt, fehler, erstellt_at, fertig_at")
      .order("erstellt_at", { ascending: false }).limit(20);
    if (error) { console.error("[antwortauftrag] lesen:", error.message); return NextResponse.json({ error: "Die Auftraege konnten nicht geladen werden." }, { status: 500 }); }
    return NextResponse.json({ auftraege: data ?? [] });
  }

  /* ⚠ EINE Zeichenkette, nicht zusammengesetzt. Supabase leitet die Spaltentypen aus dem
   * Literal ab; ein `"a, " + "b"` kennt es nicht und macht daraus `GenericStringError` — die
   * Zeile ist dann zur Laufzeit richtig und beim Typpruefen falsch. Dieselbe Warnung steht in
   * `/api/blocks`, und ich bin trotzdem hineingelaufen. */
  const { data, error } = await sb.from("user_antwortauftrag")
    .select("id, status, dateiname, lead_id, zaehlung, fragen_gesamt, fehler, erstellt_at, fertig_at, ergebnis_encrypted")
    .eq("id", id).limit(1);
  if (error) { console.error("[antwortauftrag] lesen:", error.message); return NextResponse.json({ error: "Die Auftraege konnten nicht geladen werden." }, { status: 500 }); }

  const zeile = data?.[0];
  if (!zeile) return NextResponse.json({ error: "Nicht gefunden" }, { status: 404 });

  const { ergebnis_encrypted, ...offen } = zeile as Record<string, unknown>;
  if (zeile.status !== "fertig" || !ergebnis_encrypted) {
    return NextResponse.json({ auftrag: offen });
  }

  /* ⚠ Ein Ergebnis, das sich nicht entschluesseln laesst, darf NICHT als leeres Ergebnis
   * durchgehen. Das sahe aus wie „der Bogen gab nichts her" — und der Nutzer wuerde den
   * Auftrag wegwerfen statt den Fehler zu melden. */
  try {
    return NextResponse.json({
      auftrag: offen,
      ergebnis: JSON.parse(entschluessele(ausHex(String(ergebnis_encrypted)))),
    });
  } catch {
    return NextResponse.json(
      { auftrag: { ...offen, status: "fehler", fehler: "Ergebnis nicht entschluesselbar." } },
      { status: 500 });
  }
}
