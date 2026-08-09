"use client";
import { createClient } from "./client";

/* #27 §8 — Nachweis-Uploads für Zertifikate. Privater Bucket „nachweise", profilgebunden
 * über den user-id-Pfadpräfix (RLS in supabase/0008_storage_nachweise.sql). Nie geteilte Ebene;
 * Zugriff nur über kurzlebige signierte URLs. */

const BUCKET = "nachweise";
const MAX_BYTES = 10 * 1024 * 1024;                     // 10 MB Obergrenze
const OK_TYPES = ["application/pdf", "image/png", "image/jpeg"];

const safe = (s: string) => s.normalize("NFKD").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 80);

export async function uploadNachweis(certId: string, file: File): Promise<{ ok: boolean; path?: string; error?: string }> {
  if (file.size > MAX_BYTES) return { ok: false, error: "Datei größer als 10 MB." };
  if (!OK_TYPES.includes(file.type)) return { ok: false, error: "Nur PDF, PNG oder JPG." };
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  const path = `${user.id}/${safe(certId)}/${safe(file.name)}`;
  const { error } = await sb.storage.from(BUCKET).upload(path, file, { upsert: true, contentType: file.type });
  return error ? { ok: false, error: error.message } : { ok: true, path };
}

// Kurzlebige signierte URL zum Ansehen (Standard 5 Minuten).
export async function signedNachweisUrl(path: string, seconds = 300): Promise<string | null> {
  const sb = createClient();
  const { data } = await sb.storage.from(BUCKET).createSignedUrl(path, seconds);
  return data?.signedUrl ?? null;
}

export async function removeNachweis(path: string): Promise<{ ok: boolean }> {
  const sb = createClient();
  const { error } = await sb.storage.from(BUCKET).remove([path]);
  return { ok: !error };
}
