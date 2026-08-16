import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { istAdmin } from "@/lib/admin";
import { cookies } from "next/headers";

/**
 * „Wer bin ich" — angemeldet? Admin?
 *
 * **Warum diese Route NICHT hinter der Sperre liegt.** Die erste Fassung lag unter
 * `/api/intern/` und wurde damit von der Middleware mitgesperrt. Sie konnte deshalb nur
 * „ja" sagen (200) oder schweigen (404) — und bei „schweigen" wusste niemand, ob die
 * Sitzung fehlt, die Adresse nicht passt oder die Sperre klemmt. Genau dieser Fall trat
 * am 2026-08-16 ein: der Menüeintrag blieb aus, und es gab keine Möglichkeit zu sehen,
 * woran es lag.
 *
 * **Was sie preisgibt: nur Auskunft über den Fragenden selbst.** Keine Adressliste, keine
 * fremden Konten. Ein angemeldeter Nutzer erfährt, ob ER Admin ist — was er ohnehin daran
 * sähe, ob der Menüeintrag erscheint.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  let email: string | null = null;
  let fehler: string | null = null;
  try {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    email = data.user?.email ?? null;
    fehler = error?.message ?? null;
  } catch (e) {
    fehler = String((e as Error).message ?? e).slice(0, 120);
  }

  // DIAGNOSE, bewusst ohne Inhalte: nur die ANZAHL der Supabase-Cookies. Sie unterscheidet
  // die beiden Faelle, die von aussen gleich aussehen:
  //   0 Cookies  → der Browser sendet nichts (Anmeldung, Domain oder Cookie-Regel)
  //  >0 Cookies  → sie kommen an, aber `getUser()` erkennt sie nicht (Schluessel/Bibliothek)
  // Ohne diese Unterscheidung raet man zwischen zwei ganz verschiedenen Ursachen.
  let sbCookies = 0;
  try {
    const store = await cookies();
    sbCookies = store.getAll().filter((c) => /^sb-|^supabase/.test(c.name)).length;
  } catch { /* ausserhalb einer Anfrage nicht lesbar */ }

  return NextResponse.json(
    { angemeldet: !!email, admin: istAdmin(email), sbCookies, fehler },
    { headers: { "cache-control": "no-store" } },
  );
}
