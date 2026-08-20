import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Landing } from "@/components/Landing";

/**
 * Die Wurzel. Angemeldet: direkt in die App. Sonst: die oeffentliche Startseite.
 *
 * Bis zum 2026-08-20 leitete `/` IMMER auf `/leads` — und weil die Leads eine Anmeldung
 * verlangen, landete jeder Fremde auf „Willkommen zurueck". Eine Anmeldemaske als erste
 * Antwort auf „was ist das?" ist keine Antwort.
 */
export const dynamic = "force-dynamic";   // haengt an der Sitzung, darf nicht statisch werden

export default async function Wurzel() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getUser();
  if (data?.user) redirect("/leads");
  return <Landing />;
}
