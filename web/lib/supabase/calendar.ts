"use client";
import { createClient } from "./client";

/* iCal-Feed-Token je Nutzer (Ticket #16 §8.2). Legt bei Bedarf einen an, sonst gibt den
 * bestehenden zurück. No-op ohne Session. Der Token ist der geheime Schlüssel des Feeds —
 * die .ics-Route löst ihn server-seitig (Service-Role) zu user_watchlist auf. */
export async function getOrCreateCalendarFeed(): Promise<string | null> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return null;
    const { data } = await sb
      .from("user_calendar_feed").select("feed_token").eq("user_id", user.id).maybeSingle();
    if (data?.feed_token) return data.feed_token;
    const { data: created } = await sb
      .from("user_calendar_feed").insert({ user_id: user.id }).select("feed_token").single();
    return created?.feed_token ?? null;
  } catch {
    return null;
  }
}
