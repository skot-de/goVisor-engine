"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  LEADS, BRANCHEN, COLS, applyState, relabelLeads, visible, sorted, syncLocationColumn,
  suggestList, classifyQuery, netzInteresse, netzFreigabe, offeneGruppen, angaben, setLeads, setMarket, setBestand,
  setNachbarn, setNetzZustand, toggleNetzLos, netzLoseVon, setPlzGeo, setPlzLand,
  setProfile, setUserContracts, parseWert, aufwandStufe,
} from "@/lib/explorerCore";
import { loadContracts } from "@/lib/supabase/contracts";
import { buildProfile, brancheFromProfile } from "@/lib/profileEngine";
import { FilterPanel, emptyAdv, advCount, type Adv, type Segment } from "./FilterPanel";
import { LeadTable } from "./LeadTable";
import { DetailPanel } from "./DetailPanel";
import { StrategieView, SEKTIONEN } from "./StrategieView";
import { BereichsNav } from "./BereichsNav";
import { deuteFrage } from "@/lib/frageSuche";
import { ExportMenu } from "./ExportMenu";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { currentUser, logout, loadProfile } from "@/lib/supabase/auth";
import { recordLeadClick, recordAnalysis } from "@/lib/analytics";
import { syncWatchlist, loadWatchlist, type MerkZeile } from "@/lib/supabase/watchlist";
import { Kalender } from "./Kalender";
import { Cockpit } from "./Cockpit";
import { getOrCreateCalendarFeed } from "@/lib/supabase/calendar";
import { useSprache } from "@/lib/i18n";
import { profilGeaendert } from "@/lib/useProfil";

type Profile = ReturnType<typeof buildProfile>;
const PROFILE_KEY = "govisor.profile.v1";
import { ColumnMenu, FilterBar, Suggestions, HeaderFilterPopover } from "./parts";
import { AppRail, AppTop, type RailId } from "./Rail";

type Lead = { id: string; branche?: string; merk?: unknown; [k: string]: unknown };
type Token = { type: string; value: string; label: string; radius?: number | null; coord?: number[];
  /** Nur bei Frage-Token: WELCHE Filterfelder diese Frage gesetzt hat. Ohne diese Notiz
   *  koennte das Entfernen des Tokens den Filter nicht zuruecknehmen — das Token waere
   *  weg und die Liste bliebe gefiltert. Genau die Sorte stiller Rest, die man erst
   *  bemerkt, wenn Zahlen nicht mehr zusammenpassen. */
  advKeys?: string[] };
type Filters = { ungesichtet: boolean; gemerkt: boolean; kandidaten: boolean; netz: boolean; relevant: boolean };
type View = "angriff" | "merkliste" | "netzwerk" | "potenzial";

// Mutabler Prototyp-Zustand, den React nicht als State hält (in-place mutiert):
// COLS-Reihenfolge/on, LEADS[].merk/status, netzInteresse. Ein Tick erzwingt Neuberechnung.
const CORE = LEADS as Lead[];
const ART_MATCH: Record<string, string> = {
  rahmen: "Rahmenvertrag", wiederkehrend: "Wiederkehrende Leistung", einzel: "Einzelauftrag",
};

// Erweiterte Filter (Filter-Panel) über die Kern-Auswahl legen. Unbekanntes schließt nichts
// aus (Wert). Zeithorizont zählt Vertragsende (endTage) bzw. Frist (tage). Region über
// Leistungsort (marktRegion) ODER Käufersitz (nuts) + bundesweit erbringbare.
function postFilter(rows: Lead[], a: Adv): Lead[] {
  if (advCount(a) === 0) return rows;
  const buyer = a.buyer.trim().toLowerCase();
  return rows.filter((l) => {
    if (a.staaten.length && !a.staaten.includes(String(l.land || "DE"))) return false;
    if (a.phases.length && !a.phases.includes(String(l.src))) return false;
    if (a.horizon != null) {
      const days = (l.endTage as number | null) ?? (l.tage as number | null);
      if (days == null || days < 0 || days / 30 > a.horizon) return false;
    }
    if (a.regions.length || a.nationwide) {
      const geo = String((a.regionAxis === "perf" ? l.marktRegion : l.nuts) || "");
      const landOk = a.regions.length > 0 && a.regions.some((r) => geo.startsWith(r));
      const natOk = a.nationwide && l.is_nationwide === true;
      if (!(landOk || natOk)) return false;
    }
    if (a.cpvFields.length && !a.cpvFields.includes(String(l.cpv || "").slice(0, 4))) return false;
    if (buyer && !String(l.buyer || "").toLowerCase().includes(buyer)) return false;
    if (a.leistung.length && !a.leistung.includes(String(l.naturKat))) return false;
    if (a.art.length && !a.art.some((k) => l.art === ART_MATCH[k])) return false;
    if (a.rahmen.length && !a.rahmen.includes(String(l.rahmen))) return false;
    if (a.hasDetail && !l.hasDetail) return false;
    if (a.unterlagen && !l.unterlagen) return false;
    if (a.valMin != null || a.valMax != null) {
      const v = parseWert((l.volumen as { wert?: string } | undefined)?.wert);
      if (v != null) {
        if (a.valMin != null && v < a.valMin) return false;
        if (a.valMax != null && v > a.valMax) return false;
      }
    }
    if (a.neu === "neu" && !l.neu) return false;
    if (a.neu === "folge" && l.neu) return false;
    if (a.wenigWettbewerb && (l.konk as { stufe?: string } | undefined)?.stufe !== "gering") return false;
    if (a.chance.length && !a.chance.includes(String(l.wechsel))) return false;
    if (a.relevanz.length && !a.relevanz.includes(String(l.relevanz))) return false;
    if (a.aufwand.length && !a.aufwand.includes(aufwandStufe(l).stufe)) return false;
    if (a.buergschaft !== "all") {
      const b = (l.aufwand as { buergschaft?: string } | undefined)?.buergschaft;
      if (a.buergschaft === "ja" && !(b && b !== "nein")) return false;
      if (a.buergschaft === "nein" && b !== "nein") return false;
    }
    if (a.multiLot && (((l.lose as unknown[] | undefined)?.length ?? 0) <= 1)) return false;
    return true;
  });
}

// URL-Slug ↔ interner Zustand. Slugs sind ENGLISCH/universell (wie der DB-Vertrag) — über alle
// Länder gleich; die sichtbaren Rail-Labels bleiben lokalisiert. watchlist/network sind Filter
// auf „angriff", strategy ist „potenzial".
const SLUG_VIEW: Record<string, View> = {
  leads: "angriff", watchlist: "angriff", network: "angriff", strategy: "potenzial",
};
function slugOf(v: View, f: { gemerkt: boolean; netz: boolean }): string {
  if (v === "potenzial") return "strategy";
  if (f.gemerkt) return "watchlist";
  if (f.netz) return "network";
  return "leads";
}

// Ticket #23 Checkliste: Abhak-Zustand je Lead persistieren + TOC-Fortschritt aktualisieren (DOM-only).
function clPersist(root: HTMLElement | null) {
  if (!root) return;
  const lead = root.dataset.clroot;
  const items = root.querySelectorAll<HTMLElement>(".item[data-clitem]");
  const state: Record<string, boolean> = {};
  let dn = 0;
  items.forEach((it) => { if (it.classList.contains("done")) { state[it.dataset.clitem || ""] = true; dn++; } });
  if (lead) { try { localStorage.setItem("govisor.checkstate." + lead, JSON.stringify(state)); } catch { /* voll */ } }
  const n = root.querySelector<HTMLElement>(".cl-doneN"); if (n) n.textContent = String(dn);
  const bar = root.querySelector<HTMLElement>(".cl-tprog");
  if (bar) bar.style.width = (items.length ? Math.round((dn / items.length) * 100) : 0) + "%";
}

export function ExplorerShell({ initialSlug = "leads" }: { initialSlug?: string }) {
  const { t, lang, setLang } = useSprache();
  const [query, setQuery] = useState("");
  const [tokens, setTokens] = useState<Token[]>([]);
  const [filters, setFilters] = useState<Filters>({
    ungesichtet: false, gemerkt: initialSlug === "watchlist", kandidaten: false,
    netz: initialSlug === "network", relevant: false,
  });
  const [sortKey, setSortKey] = useState("frist");
  const [sortDir, setSortDir] = useState(1);
  const [awAlertOff, setAwAlertOff] = useState(false);   // #24 Zuschlag-Alert-Band ausgeblendet
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("uebersicht");
  const [mode, setMode] = useState<"browse" | "read" | "full">("browse");
  const [buyerDemo, setBuyerDemo] = useState("dbnetz");
  const [aktiveRegion, setAktiveRegion] = useState("ffm");
  const [potTab, setPotTab] = useState("chancen");
  // Ohne Onboarding: aspiring bidder (keine Firmen-Historie). Firmen-Blöcke im Chancen-Tab
  // bleiben leer, die Marktblöcke (Branche × Region) sind echt gefüllt.
  const [profilStufe, setProfilStufe] = useState("neu");
  const [offenerPicker, setOffenerPicker] = useState<string | null>(null);
  const [realProfile, setRealProfile] = useState<Profile | null>(null);   // echtes Profil aus Onboarding
  const router = useRouter();
  const [adv, setAdv] = useState<Adv>(emptyAdv);
  const [panelOpen, setPanelOpen] = useState(false);
  const accountLimit = false; // Pro; §9: kommt später aus dem echten Account-Status
  const [aktiveBranche, setAktiveBranche] = useState("it");
  // Der Strategie-Abschnitt liegt HIER, nicht in `StrategieView`: seine Navigation steht
  // in der Bereichsleiste, also ausserhalb jener Komponente.
  const [stratSektion, setStratSektion] = useState("pipeline");
  // Grundraum aus dem Profil (CPV) — nicht mehr hart „it". Fällt auf „it" zurück, solange kein Profil da ist.
  const profilBranche = brancheFromProfile(realProfile as unknown as Parameters<typeof brancheFromProfile>[0]) || "it";
  const brancheManual = useRef(false);   // true, sobald der Nutzer den Grundraum selbst umschaltet
  const [view, setView] = useState<View>(SLUG_VIEW[initialSlug] ?? "angriff");
  // #16 Verfahrenskalender — „Termine"-Modus in der Merkliste + iCal-Feed-URL
  const [kalMode, setKalMode] = useState(false);
  const [feedUrl, setFeedUrl] = useState<string | null>(null);

  // Popover-/Menü-Zustand
  const [colMenuOpen, setColMenuOpen] = useState(false);

  // Sprachwechsel: die geladenen Leads tragen zwischengespeicherte Labels (Phase, Leistung,
  // Wert-Herkunft). Ohne dieses Nachziehen bliebe die Liste in der Altsprache stehen —
  // die Oberflaeche wechselte, die Tabelle nicht. Kein Neuladen noetig.
  useEffect(() => { relabelLeads(); bump(); }, [lang]);
  const [headFilter, setHeadFilter] = useState<{ facet: string; rect: DOMRect } | null>(null);
  const [openRadius, setOpenRadius] = useState<number | null>(null);
  const [suggIdx, setSuggIdx] = useState(-1);
  const [tick, setTick] = useState(0);
  const bump = useCallback(() => setTick((n) => n + 1), []);
  const [branchenCounts, setBranchenCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const [userEmail, setUserEmail] = useState<string | null>(null);
  // Echter Zugangsstatus statt hartkodiertem „Pro"-Aufkleber (Free bis der Account etwas anderes sagt).
  const [plan, setPlan] = useState<"free" | "paid" | "cancelled">("free");
  const [planOpen, setPlanOpen] = useState(false);
  // Vorauswahl = das Produktversprechen („wir sortieren vor, ihr arbeitet nur das Sinnvolle ab").
  // Standard AN; ohne Profil wirkungslos, weil dann keine Relevanz berechnet werden kann.
  const [vorauswahl, setVorauswahl] = useState(true);
  // Immer nur EINE Phase in der Liste; die nächste wird als letzte Zeile angekündigt.
  // Aufgeklappte Phasen (kumulativ): 1 = nur „Jetzt bewerben". Ersetzen war falsch —
  // wer weiterklickte, verlor die erste Phase und fand ohne zweiten Klick nicht zurück.
  const [phasenOffen, setPhasenOffen] = useState(1);

  // Beim Start: eingeloggt? → Profil aus Supabase (autoritativ); sonst lokaler Fallback.
  useEffect(() => {
    (async () => {
      const u = await currentUser().catch(() => null);
      setUserEmail(u?.email ?? null);
      if (u) {
        // echten Zugangsstatus laden (Free bleibt der ehrliche Default, wenn nichts hinterlegt ist)
        import("@/lib/supabase/account").then(({ loadAccount }) => loadAccount())
          .then((a) => { const p = a?.plan; if (p === "paid" || p === "cancelled") setPlan(p); })
          .catch(() => {});
      }
      if (u) { loadContracts().then((cs) => { setUserContracts(cs); bump(); }).catch(() => {}); }
      const remote = u ? await loadProfile().catch(() => null) : null;
      if (remote) {
        setRealProfile(remote);
        try { localStorage.setItem(PROFILE_KEY, JSON.stringify(remote)); } catch { /* Quota */ }
        profilGeaendert();
        return;
      }
      try {
        const raw = localStorage.getItem(PROFILE_KEY);
        if (raw) setRealProfile(JSON.parse(raw));
      } catch { /* ungültig → ignorieren */ }
    })();
  }, []);

  // Nach dem Profil-Laden den Grundraum auf die eigene Branche stellen — sonst sieht ein Bau-Kunde
  // den IT-Default. Nur solange der Nutzer nicht selbst umgeschaltet hat.
  useEffect(() => {
    if (brancheManual.current) return;
    const b = brancheFromProfile(realProfile as unknown as Parameters<typeof brancheFromProfile>[0]);
    if (b) setAktiveBranche((cur) => (cur === b ? cur : b));
  }, [realProfile]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function abmelden() {
    await logout().catch(() => {});
    try { localStorage.removeItem(PROFILE_KEY); } catch { /* egal */ }
    setRealProfile(null); setUserEmail(null); brancheManual.current = false; setPlan("free");
    profilGeaendert();   // sonst behaelt der Kopf den Firmennamen des Abgemeldeten
    bump();
  }

  // Onboarding ist eine eigene Route (/onboarding, portiert aus dem v1.4-Design). Das
  // Profil kommt beim Zurücknavigieren über localStorage rein (Load-Effect beim Mount).

  // Echte Leads aus der Gold-Schicht laden — bei Mount und bei jedem Grundraum-Wechsel.
  // Deep-Link: ?lead=<id>&branche=<br>&tab=docs öffnet einen Lead direkt (z. B. eine analysierte
  // Unterlagen-Checkliste), ohne die Liste durchsuchen zu müssen. Einmalig beim Laden.
  const deepRef = useRef<{ lead: string; tab: string } | null>(null);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const lead = p.get("lead");
    if (!lead) return;
    deepRef.current = { lead, tab: p.get("tab") || "docs" };
    const br = p.get("branche");
    if (br) { brancheManual.current = true; setAktiveBranche(br); }   // expliziter Deep-Link gewinnt vor Profil-Ableitung
  }, []);

  // SUCHE VON EINER ANDEREN SEITE. Die eigenstaendigen Seiten (Unternehmen, Bausteine)
  // tragen dieselbe Suchleiste, haben aber keinen Listenzustand — sie schicken den Begriff
  // als `?q=` hierher. Ohne das waere die Leiste dort Zierde: sichtbar, aber wirkungslos,
  // und das ist schlimmer als keine Leiste.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (!q) return;
    const tok = classifyQuery(q) as Token | null;
    if (tok) setTokens((ts) => ts.some((x) => x.type === tok.type && x.value === tok.value)
      ? ts : [...ts, tok]);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    detailLoaded.current.clear();
    fetch(`/api/leads?branche=${aktiveBranche}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        if (Array.isArray(data)) { setLeads(data); setActiveId(null); }
        setLoading(false);
        bump();
        const dl = deepRef.current;
        if (dl && Array.isArray(data) && data.some((x: { id?: string }) => String(x.id) === dl.lead)) {
          deepRef.current = null;
          setTimeout(() => { openLead(dl.lead); setTimeout(() => setActiveTab(dl.tab), 0); }, 0);
        }
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [aktiveBranche, bump]);

  // Branchen-Zähler: bei aktiver Textsuche die Treffer je Branche ziehen (nicht die
  // Maximal-Totale) — "Hamm" zeigt im Menü dann z. B. Bau 0 / IT 6 statt 31.141 / 3.883.
  // Suchbegriffe = Live-Eingabe + committete Stichwort-Tokens. Debounced; ohne Suche → Totale.
  const textTokenKey = tokens.filter((tk) => tk.type === "text").map((tk) => tk.value).join(" ");
  // Aktiver Umkreis-Token (Stadt/PLZ mit Koordinate) → die Branchen-Zähler im Menü auf genau
  // diesen Ort+Radius beziehen (#27), statt globale Totale zu zeigen.
  const ortGeo = tokens.find(
    (tk) => tk.type === "ort" && Array.isArray((tk as { coord?: number[] }).coord),
  ) as { coord?: number[]; radius?: number } | undefined;
  const geoKey = ortGeo?.coord ? `${ortGeo.coord[0]},${ortGeo.coord[1]},${ortGeo.radius || 25}` : "";
  useEffect(() => {
    const raw = [query.trim(), textTokenKey].filter(Boolean).join(" ").trim();
    // Reine PLZ/Zahl ist eine Geo-Suche (kein Textmatch) → nicht als Textzähler werten,
    // sonst zeigte das Menü fälschlich 0 überall. Der Umkreis kommt separat als lat/lon/r.
    const q = (raw.length >= 2 && !/^\d{2,5}$/.test(raw)) ? raw : "";
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (geoKey) { const [la, lo, rr] = geoKey.split(","); params.set("lat", la); params.set("lon", lo); params.set("r", rr); }
    const qs = params.toString();
    const url = qs ? `/api/branchen?${qs}` : "/api/branchen";
    const id = setTimeout(() => {
      fetch(url).then((r) => r.json()).then(setBranchenCounts).catch(() => {});
    }, (q || geoKey) ? 220 : 0);
    return () => clearTimeout(id);
  }, [query, textTokenKey, geoKey]);

  // PLZ→Koordinate-Tabelle einmal laden (für die echte Umkreissuche). ~450 KB, cache-fähig.
  useEffect(() => {
    fetch("/api/plz-geo").then((r) => r.json()).then(setPlzGeo).catch(() => {});
  }, []);
  // Aktiver DACH-Länderfilter → getippte 4-stellige PLZ (CH/AT kollidieren) dorthin auflösen.
  useEffect(() => {
    setPlzLand(adv.staaten.length === 1 ? adv.staaten[0] : "");
  }, [adv.staaten]);

  // Echte Marktblöcke (Chancen-Tab) laden und bei Branchenwechsel in den Kern schieben.
  const marktRef = useRef<Record<string, unknown>>({});
  useEffect(() => {
    fetch("/api/markt").then((r) => r.json()).then((m) => {
      marktRef.current = m || {};
      setMarket(marktRef.current[aktiveBranche]);
      bump();
    }).catch(() => {});
  }, []); // einmal laden
  useEffect(() => {
    if (marktRef.current[aktiveBranche]) { setMarket(marktRef.current[aktiveBranche]); bump(); }
  }, [aktiveBranche, bump]);

  // Partnersuche: Zustand für den geöffneten Lead holen. Nur für Mehr-Los-Vergaben und nur
  // mit Konto — ohne eigene Meldung gibt der Endpunkt ohnehin nichts heraus (Regel 1 dort).
  useEffect(() => {
    if (!activeId || !userEmail) return;
    const l = CORE.find((x) => x.id === activeId) as (Lead & { lose?: unknown[] }) | undefined;
    if (!l || (l.lose?.length ?? 0) < 2) return;
    let abgebrochen = false;
    fetch(`/api/netz?leadId=${encodeURIComponent(activeId)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((z) => { if (!abgebrochen) { setNetzZustand(activeId, z); bump(); } })
      .catch(() => {});
    return () => { abgebrochen = true; };
  }, [activeId, userEmail, bump]);

  // Der eigene Bestand für „Position" und „Profil". Bis zum 2026-08-22 holte den niemand:
  // die Ansicht las nur die Leerstufe in `PROFIL`, und deshalb standen dort Nullen, obwohl
  // `/api/firma` das vorberechnete Profil der Identität längst ausliefert. Ohne bestätigte
  // Firma bleibt es bewusst leer — dann gibt es keinen Bestand, den wir zeigen dürften.
  // `Profile` ist `ReturnType<typeof buildProfile>` und kennt `identityId` nicht — das Feld
  // setzt erst das Onboarding auf das gespeicherte Profil. Gleiche Lage wie bei
  // `brancheFromProfile` weiter oben, deshalb hier derselbe enge Zugriff statt eines
  // aufgeweichten Typs.
  const identId = (realProfile as unknown as { identityId?: string } | null)?.identityId;
  useEffect(() => {
    const id = identId;
    if (!id) { setBestand(null); bump(); return; }
    fetch(`/api/firma?id=${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((fp) => { setBestand(fp && !fp.error ? fp : null); bump(); })
      .catch(() => { setBestand(null); bump(); });
  }, [identId, bump]);

  // Vom Nutzer gezogene Spaltenbreiten (px), je Spaltenschlüssel. Gehört später ins
  // gespeicherte Arbeitsplatz-Profil (Übergabenotiz §10, um „Breite" erweitert).
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const setColWidth = useCallback(
    (key: string, w: number) => setColWidths((m) => ({ ...m, [key]: Math.max(48, Math.round(w)) })),
    []
  );

  const searchRef = useRef<HTMLInputElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const detailLoaded = useRef<Set<string>>(new Set());

  // Inkrementelles Rendern: erst N Zeilen zeigen, beim Scrollen nachwachsen. Hält den DOM
  // klein (ein paar Hundert Zeilen) auch bei tausenden Leads — ohne feste Zeilenhöhe.
  const [renderCount, setRenderCount] = useState(200);
  function onTableScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 500) {
      setRenderCount((c) => c + 200);
    }
  }
  // Bei geänderter Filterung/Sortierung/Branche wieder oben anfangen.
  useEffect(() => { setRenderCount(200); }, [aktiveBranche, sortKey, sortDir, tokens, filters]);

  // Modus steuert die Split-Höhe (CSS: body[data-mode]). Beim Wechsel die per Drag
  // gesetzte Inline-Höhe entfernen, damit die Modus-Regel wieder greift.
  useEffect(() => {
    document.body.dataset.mode = activeId ? mode : "browse";
    // Marker fürs Layout: ohne gewählten Lead steht unten der Überblick, nicht ein
    // Detail — der bekommt per CSS mehr Höhe.
    if (activeId) document.body.dataset.lead = "";
    else delete document.body.dataset.lead;
    // Potenzial-Bereich blendet Tabelle/Detail aus und zeigt die profilview (CSS §area).
    if (view === "potenzial") document.body.dataset.area = "profil";
    else document.body.removeAttribute("data-area");
    if (mainRef.current) mainRef.current.style.gridTemplateRows = "";
  }, [activeId, mode, view]);

  function startDivider() {
    const main = mainRef.current;
    if (!main) return;
    main.classList.add("dragging");
    document.body.style.userSelect = "none";
    const move = (ev: MouseEvent) => {
      const r = main.getBoundingClientRect();
      const h = Math.min(Math.max(ev.clientY - r.top, 90), r.height - 120);
      main.style.gridTemplateRows = `${h}px 6px 1fr`;
    };
    const up = () => {
      main.classList.remove("dragging");
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  // React ist die Wahrheit → vor jeder Ableitung in den Kern schieben, dann dessen
  // unveränderte Filter-/Sortier-Logik nutzen.
  // Vollständige, gefilterte Liste INKLUSIVE Zuschläge — Basis für Zähler und das Zuschlags-Band.
  const alleRows: Lead[] = useMemo(() => {
    // Frage-Token gehoeren NICHT in die Volltextsuche. Sie haben ihre Wirkung schon
    // entfaltet (sie setzen einen Filter); als Suchtoken wuerde die Kernlogik zusaetzlich
    // nach der Zeichenfolge „wenig-bieter" im Titel suchen — und die gibt es nirgends.
    // Gemessen beim ersten Versuch: „0 von 0" statt 2.430.
    const suchToken = tokens.filter((t) => t.type !== "frage");
    applyState({ aktiveBranche, profilBranche, sortKey, sortDir, searchTokens: suchToken, filters });
    setProfile(realProfile);
    syncLocationColumn();
    return postFilter(sorted(visible()), adv);
  }, [aktiveBranche, sortKey, sortDir, tokens, filters, tick, realProfile, adv]);

  // Akquise zeigt, worauf man sich BEWERBEN kann. Erteilte Zuschläge (#24) sind Marktbeobachtung
  // (wer hat gewonnen → wer kauft jetzt zu) und würden hier oben stehen, weil sie nach
  // Zuschlagsdatum ganz vorn sortieren. Deshalb nur, wenn die Phase ausdrücklich gewählt ist.
  // `alleRows` behält sie — daraus speist sich das Zuschlags-Band.
  // Die Vorauswahl gilt nur für die Akquise — Merkliste/Netzwerk sind eigene Linsen.
  // Rail-Punkt ↔ interne Ansicht. Getrennt gehalten: die Rail spricht die Sprache des
  // Nutzers ("akquise"), die Shell ihre eigene ("angriff").
  const RAIL_VIEW: Record<string, View> = {
    akquise: "angriff", merkliste: "merkliste", netzwerk: "netzwerk", strategie: "potenzial",
  } as Record<string, View>;
  const aktiverRailPunkt: RailId =
    view === "potenzial" ? "strategie"
    : filters.gemerkt ? "merkliste" : filters.netz ? "netzwerk" : "akquise";

  const istAkquise = view === "angriff" && !filters.gemerkt && !filters.netz;
  // Die Vorauswahl sucht bewerbbare Ausschreibungen (src='f02'). Wer ausdrücklich EINE
  // Phase wählt, will etwas anderes sehen — dann muss sie schweigen, sonst filtert sie
  // die angeforderte Menge restlos weg. Das ist zweimal passiert: „Zuschläge ansehen"
  // und „Alle Ankündigungen ansehen" landeten beide auf einer leeren Tabelle.
  const eigenePhasenwahl = adv.phases.length > 0;
  const zuschlagsSicht = adv.phases.includes("award");

  /* Der Trichter als EINE Liste, die weiterreicht — nicht als Blockstapel.
   *
   * Sortiert nach „wann muss ich handeln", nicht nach Datenquelle. Deshalb liegen bald
   * auslaufende Verträge und Ankündigungen in DERSELBEN Phase: beides heißt „die
   * Ausschreibung kommt in den nächsten Monaten". Vorher standen Ankündigungen vor
   * Verträgen, die schon diesen Monat auslaufen — nach Herkunft sortiert, nicht nach Frist.
   *
   * Gemessen zur Belastbarkeit der Auslauf-Leads (Nachfolger nachweisbar, Ende ≥6 Mon her):
   *   echtes Enddatum   → Nachfolger kam im Median  +21 Tage danach  (gut zentriert)
   *   geschätztes Ende  → Nachfolger kam im Median −174 Tage DAVOR   (systematisch zu spät)
   * Deshalb zuerst die mit echtem Datum. 78 % der Auslauf-Leads haben eines.
   */
  const PHASEN = useMemo(() => {
    if (!realProfile || !istAkquise || eigenePhasenwahl || !vorauswahl) return null;
    const passt = (l: Lead) => l.relevanz === "hoch" || l.relevanz === "mittel";
    const keinBlocker = (l: Lead) => {
      const m = l.match as { blocker?: { art: string }[] } | undefined;
      return !m?.blocker?.some((b) => b.art === "buergschaft" || b.art === "ausschluss");
    };
    const frist = (l: Lead) => (l.frist as { tage?: number } | undefined)?.tage ?? (l.tage as number | null);
    const ende = (l: Lead) => (l.endTage as number | null);
    const echt = (l: Lead) => String((l.timing as { src?: string } | undefined)?.src ?? "") === "echt";
    const basis = alleRows.filter((l) => l.src !== "award" && keinBlocker(l));

    // Open House gehört nicht in „Jetzt bewerben": kein Wettbewerb, keine echte Frist —
    // ein Beitritt ist jederzeit möglich, es drängt nichts. In der Frist-Phase würde es
    // die echten Ausschreibungen verdrängen (bei Medizin 1.816 von 2.003).
    const offenesHaus = (l: Lead) => (l as { verfahren?: string }).verfahren === "open_house";
    const jetzt = basis.filter((l) => l.src === "f02" && l.relevanz === "hoch" && !offenesHaus(l)
      && typeof frist(l) === "number" && (frist(l) as number) >= 3
      && aufwandStufe(l).stufe !== "hoch");
    // „Bald" = Ausschreibung steht in den nächsten ~6 Monaten an: angekündigt ODER
    // laufender Vertrag, der demnächst endet. Echte Enddaten zuerst — sie treffen.
    const bald = basis.filter((l) => passt(l)
      && (l.src === "f01" || (l.src === "auslauf" && (ende(l) ?? -1) >= 0 && (ende(l) ?? 9e9) <= 183)))
      .sort((a, z) => (echt(z) ? 1 : 0) - (echt(a) ? 1 : 0) || ((ende(a) ?? 9e9) - (ende(z) ?? 9e9)));
    // Dritte Phase hat jetzt Inhalt: der Export liefert 24 Monate statt der 26 Tage, die
    // vorher durch den Ausliefer-Deckel übrig blieben (Bau: 953 Verträge im 1–2-Jahres-Fenster).
    const lang = basis.filter((l) => passt(l) && l.src === "auslauf" && (ende(l) ?? -1) > 183)
      .sort((a, z) => ((ende(a) ?? 9e9) - (ende(z) ?? 9e9)));

    // `titel`/`hinweis` bleiben hier DEUTSCH — sie sind die Übersetzungsschlüssel. Übersetzt
    // wird an der Render-Stelle (`t(PHASEN[i].titel)`); dieses useMemo hängt nicht an der
    // Sprache, hier übersetzt wäre sie bis zum nächsten Datenwechsel eingefroren.
    return [
      { key: "jetzt", titel: "Jetzt bewerben", hinweis: "Frist läuft, hier zählt Tempo", rows: jetzt },
      { key: "bald", titel: "Bahnt sich an", hinweis: "angekündigt oder Vertrag endet bald", rows: bald },
      { key: "offen", titel: "Jederzeit beitretbar", hinweis: "Open House. Kein Wettbewerb, keine Frist",
        rows: basis.filter((l) => passt(l) && offenesHaus(l)) },
      { key: "lang", titel: "Langfristig", hinweis: "Verträge, die in ein bis zwei Jahren auslaufen", rows: lang },
    ];
  }, [alleRows, realProfile, istAkquise, eigenePhasenwahl, vorauswahl]);

  const rows: Lead[] = useMemo(() => {
    if (PHASEN) return PHASEN.slice(0, phasenOffen).flatMap((p) => p.rows);
    const ohneAwards = adv.phases.includes("award") ? alleRows : alleRows.filter((l) => l.src !== "award");
    // Vorauswahl (gemessen an ENGIE/Cancom/Rosenbauer: 5.911→72, 3.974→23, 5.979→77):
    // Es bleibt, worauf man sich HEUTE sinnvoll bewerben kann —
    //   · echte Ausschreibung (keine Ankündigung, kein bloßes Vertragsende)
    //   · noch mindestens 3 Tage Zeit
    //   · Relevanz hoch (CPV-6-genau + Region + Volumen)
    //   · kein harter Blocker (Bürgschaft übersteigt Rahmen / bewusst ausgeschlossen)
    //   · Aufwand nicht „hoch" — unbekannter Aufwand fliegt NICHT raus (Unbekanntes schließt nie aus)
    // Ohne Profil ist die Relevanz für alles „na" → wir sortieren nicht vor, statt alles zu leeren.
    if (!vorauswahl || !realProfile || !istAkquise || eigenePhasenwahl) return ohneAwards;
    return ohneAwards.filter((l) => {
      if (l.src !== "f02") return false;
      const tage = (l.frist as { tage?: number } | undefined)?.tage ?? (l.tage as number | null);
      if (typeof tage !== "number" || tage < 3) return false;
      if (l.relevanz !== "hoch") return false;
      const m = l.match as { blocker?: { art: string }[] } | undefined;
      if (m?.blocker?.some((b) => b.art === "buergschaft" || b.art === "ausschluss")) return false;
      return aufwandStufe(l).stufe !== "hoch";
    });
  }, [alleRows, adv.phases, vorauswahl, realProfile, istAkquise, eigenePhasenwahl, PHASEN, phasenOffen]);

  const suggestions = useMemo(() => (query.trim() ? suggestList(query) : []), [query]);

  // CPV-Fachgebiete des Grundraums (Top-Segmente) für den Feinfilter im Panel.
  const cpvSegments = useMemo((): Segment[] => {
    const map: Record<string, { label: string; n: number }> = {};
    for (const l of CORE) {
      const c = String((l as { cpv?: string }).cpv || "").slice(0, 4);
      if (!c) continue;
      if (!map[c]) map[c] = { label: String((l as { cpvLabel?: string }).cpvLabel || c), n: 0 };
      map[c].n++;
    }
    return Object.entries(map)
      .map(([cpv4, v]) => ({ cpv4, label: v.label, n: v.n }))
      .sort((a, b) => b.n - a.n)
      .slice(0, 14);
  }, [aktiveBranche, tick]);

  // Aktive Token je Facette → „on"-Zustand des Kopf-Trichters
  const activeFacets = useMemo(() => {
    const m: Record<string, number> = {};
    tokens.forEach((tk) => { m[tk.type] = (m[tk.type] || 0) + 1; });
    return m;
  }, [tokens]);

  // ── Aktionen ──────────────────────────────────────────────────────────────
  const closeAllPops = useCallback(() => {
    // Das Sprachmenue schliesst sich selbst — es lebt seit 2026-08-16 in `AppTop`.
    setColMenuOpen(false); setHeadFilter(null); setOpenRadius(null);
  }, []);

  const autoSort = useRef(true);   // solange true: Sortierung wird automatisch verwaltet
  function handleSort(key: string) {
    autoSort.current = false;      // manuelle Sortierung → Auto-Umschaltung aus
    if (key === sortKey) setSortDir((d) => -d);
    else { setSortKey(key); setSortDir(1); }
  }

  // Kombiniertes Ranking (Ticket #1) als Default-Sort, sobald ein Profil aktiv ist (beste zuerst);
  // ohne Profil zurück auf Frist. Manuelle Sortierung schaltet das ab.
  useEffect(() => {
    if (!autoSort.current) return;
    // Erster Blick auf die Akquise = die Leads, die zuerst Arbeit verdienen: Relevanz × Chance ×
    // wenig Aufwand × genug Frist (topScore). Auch ohne Profil sinnvoll (dann ohne Relevanz-Anteil)
    // — die Alternative „nach Frist" stellt die fast abgelaufenen nach oben, also das Gegenteil.
    setSortKey("ranking");
    setSortDir(1);
  }, [realProfile]);

  // Verlauf-Protokoll (#30): Nutzeraktionen landen im Team-Tab „Verlauf" (l.log). Angehängt
  // (nicht vorangestellt), damit der Erst-Eintrag oben bleibt — wie in den Seed-Logs.
  function logEvent(l: (Lead & { log?: unknown[] }) | undefined, kind: string, text: string) {
    if (!l) return;
    (l.log = (l.log as unknown[]) || []).push({ kind, text, who: t("Du"), ts: t("gerade eben") });
  }
  function toggleStar(id: string) {
    const l = CORE.find((x) => x.id === id);
    if (l) {
      l.merk = l.merk ? null : "manuell";
      syncWatchlist(id, !!l.merk, { titel: l.titel as string, buyer: (l as { buyer?: string }).buyer });
      logEvent(l, "watch", l.merk ? t("Zur Merkliste hinzugefügt") : t("Von der Merkliste entfernt"));
    }
    bump();
  }

  /* Gemerkte Vorgänge, die es im Frontend-Export NICHT MEHR GIBT.
   *
   * ⚠ Sie sind der eigentliche Auslöser für die Ergebnisfrage. `export_web_leads.py` wirft
   * offene Ausschreibungen mit abgelaufener echter Frist heraus („nicht mehr biet-bar"), und
   * damit verschwand ein gemerkter Vorgang am Tag nach der Frist spurlos. Gemessen am
   * 2026-09-01: `frist.tage` wird im Frontend NIE negativ, das Minimum ist 0. Jede Bedingung
   * auf „< 0" ist deshalb toter Code — die Anzeige „abgelaufen" im Cockpit war es seit jeher.
   *
   * Was fehlt, kommt aus der Merkliste selbst, die seit heute Titel und Käufer mitführt. */
  const [verwaist, setVerwaist] = useState<MerkZeile[]>([]);
  useEffect(() => {
    let ab = false;
    loadWatchlist().then((zeilen) => {
      if (ab) return;
      const bekannt = new Set(CORE.map((l) => l.id));
      setVerwaist(zeilen.filter((z) => !bekannt.has(z.lead_id)));
    });
    return () => { ab = true; };
  }, [tick]);

  // ── Cockpit (#17) — Pipeline-/Ergebnis-Übergänge (client-seitig; #11-Meldung serverseitig) ──
  function ckApply(id: string) { const l = CORE.find((x) => x.id === id) as (Lead & { pipe?: string }) | undefined; if (l) l.pipe = "beworben"; bump(); }
  function ckStatus(id: string, s: string) { const l = CORE.find((x) => x.id === id) as (Lead & { pipe?: string }) | undefined; if (l) l.pipe = s; bump(); }
  function ckOutcome(id: string, o: "gewonnen" | "verloren") {
    const l = CORE.find((x) => x.id === id) as (Lead & { outcome?: string; cockpitProv?: string }) | undefined;
    if (l) { l.outcome = o; l.cockpitProv = "korrigiert"; } // Ergebnismeldung (#11) ist Nebenprodukt der Pflege
    bump();
  }
  function ckConfirm(id: string) { const l = CORE.find((x) => x.id === id) as (Lead & { cockpitProv?: string }) | undefined; if (l) l.cockpitProv = "bestaetigt"; bump(); }

  /* Ergebnismeldung nach abgelaufener Frist (Aktivierung C). ⚠ DIE ERSTE, DIE WIRKLICH
     SCHREIBT. Die Cockpit-Handler darueber aendern nur den Zustand im Browser; der Kommentar
     versprach „#11-Meldung serverseitig", und `reportOutcome` wurde von hier nie gerufen. Die
     Moat-Tabelle `user_outcomes` gibt es seit Ticket #11, sie war nur nicht angeschlossen.

     ⚠ Zuerst den fernen Stand, dann den lokalen: scheitert das Schreiben (keine Sitzung,
     Netz weg), soll die Oberflaeche NICHT so tun, als sei die Antwort angekommen. Eine
     Meldung, die niemand hat, ist schlimmer als eine, die nicht abgegeben wurde. */
  async function ckMitgeboten(id: string, mitgeboten: boolean, grund?: string) {
    const l = CORE.find((x) => x.id === id) as (Lead & {
      titel?: string; buyer?: string; volumen?: { wert?: string }; pipe?: string;
      outcome?: string; cockpitProv?: string }) | undefined;
    const { reportOutcome } = await import("@/lib/supabase/outcomes");
    const r = await reportOutcome({
      lead_id: id, applied: mitgeboten,
      dismiss_reason: mitgeboten ? null : (grund as never),
      titel: l?.titel ?? null, buyer_name: l?.buyer ?? null,
    });
    if (!r.ok) return;
    if (l) {
      // „Ja" fuehrt in die Pipeline (das Ergebnis kommt spaeter), „nein" schliesst den
      // Vorgang ab. Beides ist eine Angabe des Nutzers, also `korrigiert`, nicht `abgeleitet`.
      if (mitgeboten) l.pipe = "wartet"; else l.outcome = "verworfen";
      l.cockpitProv = "korrigiert";
    }
    bump();
  }

  // ── Lead-Detail öffnen/schließen/Tabs ──────────────────────────────────────
  function openLead(id: string) {
    const l = CORE.find((x) => x.id === id) as (Lead & { status?: string; beschreibung?: string; log?: unknown[] }) | undefined;
    if (l && l.status === "ungesichtet") l.status = "gesichtet";
    // Verlauf nie ganz leer: beim ERSTEN Öffnen einen Auftakt-Eintrag setzen (length-Guard → einmalig).
    if (l && (!l.log || (l.log as unknown[]).length === 0)) logEvent(l, "create", t("Lead in goVisor geöffnet"));
    setActiveId(id);
    setActiveTab("uebersicht");
    setMode("read");
    bump();
    // `l` mitgeben, nicht nur die Kennung: die Dichte muss im MOMENT des Klicks
    // festgehalten werden — sie aendert sich, sobald Unterlagen nachkommen.
    recordLeadClick(id, l);   // erster Detail-Klick, fuer die Historie (war einmal das Fee-Gate)
    // Schwere Felder (Beschreibung + Vergabestellen-Profil) einmalig nachladen.
    if (l && !detailLoaded.current.has(id)) {
      detailLoaded.current.add(id);
      fetch(`/api/lead-detail?branche=${aktiveBranche}&id=${encodeURIComponent(id)}`)
        .then((r) => r.json())
        .then((d) => { if (d && typeof d === "object" && !d.error) { Object.assign(l, d); bump(); } })
        .catch(() => detailLoaded.current.delete(id));
    }
  }
  function closeLead() {
    setActiveId(null);
    setMode("browse");
  }
  function setTab(k: string) {
    setActiveTab(k);
    setMode((m) => (m === "browse" ? "read" : m));
    // Klick auf „Bewertung" markiert den Lead als analysiert. Das war einmal das Gate der
    // Erfolgspraemie (§4); die ist gestrichen, der Klick bleibt als Fortschrittsspur nuetzlich.
    if (k === "analyse" && !accountLimit) {
      const l = CORE.find((x) => x.id === activeId) as (Lead & { status?: string; seen?: string }) | undefined;
      if (l) { l.status = "analysiert"; l.seen = "ANALYSIERT"; }
      if (activeId) recordAnalysis(activeId);   // erster Bewertungs-Klick, fuer die Historie
    }
    bump();
  }
  function setWf(k: string) {
    const l = CORE.find((x) => x.id === activeId) as (Lead & { userStatus?: string | null }) | undefined;
    if (!l) return;
    l.userStatus = l.userStatus === k ? null : k;
    const WFLABEL: Record<string, string> = { interessant: "Interessant", pruefung: "In Prüfung", fragen: "Offene Fragen", verworfen: "Verworfen" };
    logEvent(l, "status", l.userStatus
      ? t("Status → {status}", { status: t(WFLABEL[k] || k) })
      : t("Status zurückgesetzt"));
    bump();
  }
  function toggleExpand() { setMode((m) => (m === "full" ? "read" : "full")); }

  // Interaktionen im Tab-Körper (delegiert aus DetailPanel)
  /* Baustein aus der Checkliste übernehmen: lokal IMMER, auf dem Server wenn möglich.
   *
   * ⚠ Die Reihenfolge ist der Punkt. Lokal zuerst, ohne auf das Netz zu warten — sonst
   * hinge der Knopf, und wer nicht angemeldet ist, verlöre den Baustein ganz. Der Server
   * ist die Schicht darüber, nicht die Bedingung.
   *
   * Der Vermerk in der Verwendungshistorie (§9.3) entsteht dabei in derselben Anfrage:
   * ein Baustein, der aus der Checkliste eines Vorgangs kommt, ist in diesem Vorgang
   * verwendet worden. Das ist EIN Ereignis, nicht zwei. */
  function bausteinUebernehmen(theme: string, content: string, label: string,
                               leadId: string | null) {
    try {
      const lib = JSON.parse(localStorage.getItem("govisor.blocks") || "[]");
      lib.push({ theme: theme || "sonstiges", content, label: label || "",
        lead_id: leadId, saved_at: new Date().toISOString() });
      localStorage.setItem("govisor.blocks", JSON.stringify(lib));
    } catch { /* Speicher voll/blockiert → wenigstens kopiert */ }
    // Ohne Anmeldung antwortet die Middleware mit 401; das ist kein Fehlerfall, sondern
    // der lokale Betrieb. Deshalb still.
    fetch("/api/blocks", {
      method: "POST", headers: { "content-type": "application/json" },
      // Ohne Vorgang kein Verwendungsvermerk — ein Baustein ohne Herkunft ist keiner mit
      // falscher. Der Baustein selbst wird trotzdem gespeichert.
      body: JSON.stringify({ blocks: [{ theme: theme || "sonstiges", content,
        ...(leadId ? { lead_id: leadId } : {}), origin: "checkliste" }] }),
    }).catch(() => {});
  }

  /* ── Vorhandenen Baustein in einen Vorgang übernehmen (§9.3) ───────────────────────────
   *
   * Bis hierher konnte die Bibliothek nur WACHSEN: jeder Weg legte einen neuen Baustein an.
   * Das ist die Gegenrichtung — und erst sie macht die Verwendungshistorie zu dem, was sie
   * meint. Ein Baustein, der in fünf Vorgängen half, ist ein anderer als einer, der einmal
   * entstand.
   *
   * Die Liste wird EINMAL geholt und behalten: wer eine Checkliste durchgeht, tippt den
   * Knopf mehrfach, und jedes Mal 40 Bausteine neu zu laden wäre spürbar. */
  const bibliothekRef = useRef<{ id?: string; theme: string; content: string;
    verwendet?: number }[] | null>(null);

  async function bibliothek() {
    if (bibliothekRef.current) return bibliothekRef.current;
    let liste: { id?: string; theme: string; content: string; verwendet?: number }[] = [];
    try {
      const d = await (await fetch("/api/blocks")).json();
      if (Array.isArray(d.blocks)) liste = d.blocks;
    } catch { /* s. u. */ }
    // Ohne Anmeldung antwortet die Middleware mit 401 — dann gilt der lokale Bestand.
    // Er ist derselbe, nur ohne Kennung; die Verwendung lässt sich dann nicht vermerken.
    if (!liste.length) {
      try { liste = JSON.parse(localStorage.getItem("govisor.blocks") || "[]"); } catch { liste = []; }
    }
    bibliothekRef.current = liste;
    return liste;
  }

  function onBodyAction(action: string, value: string, el: HTMLElement) {
    switch (action) {
      case "anav": {
        document.getElementById("an-" + value)?.scrollIntoView({ behavior: "smooth", block: "start" });
        break;
      }
      case "openlead": openLead(value); break;
      // #24/#25: Firmenprofil des Zuschlags-Gewinners (eigene Seite) + Merken aus dem Zuschlag-Detail
      case "firma": if (value) window.location.href = "/firma?id=" + encodeURIComponent(value); break;
      case "merk": toggleStar(value); break;
      case "saveblock": {
        // §7.1 Kombi-Button: editierten Baustein (oder das Zitat) in die Zwischenablage kopieren
        // UND in die Bausteinbibliothek speichern (§9.1). Lokal (Ebene B) — die verschlüsselte
        // Supabase-Persistenz (profile_text_blocks) ist die Deploy-Schicht.
        let blk: { quote?: string; label?: string; theme?: string } = {};
        try { blk = JSON.parse(value); } catch { /* ignore */ }
        const ta = el.closest(".cl-item")?.querySelector<HTMLTextAreaElement>("textarea.cl-edit");
        const text = (ta?.value.trim()) || blk.quote || blk.label || "";
        if (text) {
          navigator.clipboard?.writeText(text).catch(() => {});
          bausteinUebernehmen(blk.theme || "sonstiges", text, blk.label || "", activeId);
        }
        const btn = el as HTMLButtonElement;
        const orig = btn.textContent;
        btn.classList.add("ok"); btn.textContent = t("Gespeichert ✓");
        setTimeout(() => { btn.classList.remove("ok"); btn.textContent = orig; }, 1500);
        break;
      }
      // ── Ticket #23 Checkliste (§7): Abhaken, Kombi-Button, Kopieren, TOC ──────────────────
      case "clchk": {
        const it = el.closest<HTMLElement>(".item");
        if (it) { it.classList.toggle("done"); clPersist(el.closest<HTMLElement>(".va-checklist")); }
        break;
      }
      case "clkombi": {
        let blk: { theme?: string; label?: string; quote?: string } = {};
        try { blk = JSON.parse(value); } catch { /* ignore */ }
        const it = el.closest<HTMLElement>(".item");
        const ta = it?.querySelector<HTMLTextAreaElement>("textarea.ta");
        const text = (ta?.value.trim()) || blk.quote || blk.label || "";
        if (text) {
          navigator.clipboard?.writeText(text).catch(() => {});
          bausteinUebernehmen(blk.theme || "sonstiges", text, blk.label || "", activeId);
        }
        if (it) { it.classList.add("done"); clPersist(el.closest<HTMLElement>(".va-checklist")); }
        break;
      }
      case "clnutzen": {
        let blk: { theme?: string; i?: number } = {};
        try { blk = JSON.parse(value); } catch { /* ignore */ }
        const it = el.closest<HTMLElement>(".item");
        const fuss = it?.querySelector<HTMLElement>(".blockfoot");
        if (!it || !fuss) break;
        const offen = it.querySelector(".cl-bib");
        if (offen) { offen.remove(); break; }        // zweiter Klick schliesst wieder

        const kasten = document.createElement("div");
        kasten.className = "cl-bib";
        kasten.textContent = t("Wird geladen …");
        fuss.after(kasten);
        bibliothek().then((alle) => {
          // Zum Thema passende zuerst, danach der Rest — nie NUR die passenden: eine leere
          // Liste erklaert nicht, ob die Bibliothek leer ist oder nur zu diesem Thema nichts
          // hat, und das sind zwei sehr verschiedene Lagen.
          const passend = alle.filter((b) => b.theme === blk.theme);
          const rest = alle.filter((b) => b.theme !== blk.theme);
          const zeigen = [...passend, ...rest].slice(0, 12);
          if (!zeigen.length) {
            kasten.textContent = t("Noch keine Bausteine in der Bibliothek.");
            return;
          }
          kasten.innerHTML = "";
          if (!passend.length) {
            const h = document.createElement("div");
            h.className = "cl-bib-h";
            h.textContent = t("Zu diesem Punkt noch nichts. Hier der übrige Bestand:");
            kasten.appendChild(h);
          }
          zeigen.forEach((b, k) => {
            const z = document.createElement("button");
            z.className = "cl-bib-z";
            z.dataset.clpick = String(alle.indexOf(b));
            const wie = b.verwendet ? ` · ${b.verwendet}×` : "";
            z.innerHTML = `<span class="cl-bib-t">${b.theme}${wie}</span>`
              + `<span class="cl-bib-x"></span>`;
            // Textinhalt NICHT ueber innerHTML: ein Baustein enthaelt fremden Text.
            z.querySelector(".cl-bib-x")!.textContent = b.content.slice(0, 160);
            if (passend.length && k === passend.length) z.classList.add("cl-bib-trenn");
            kasten.appendChild(z);
          });
        });
        break;
      }
      case "clpick": {
        const idx = Number(value);
        const it = el.closest<HTMLElement>(".item");
        const ta = it?.querySelector<HTMLTextAreaElement>("textarea.ta");
        const alle = bibliothekRef.current || [];
        const b = alle[idx];
        if (!b || !ta) break;
        ta.value = b.content;
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        it?.querySelector(".cl-bib")?.remove();
        // ⚠ Der Vermerk kommt NACH dem Einsetzen und blockiert es nicht. Ohne Kennung
        // (lokaler Bestand ohne Anmeldung) gibt es nichts zu vermerken — der Baustein steht
        // trotzdem im Feld.
        if (b.id && activeId) {
          fetch("/api/blocks/usage", {
            method: "POST", headers: { "content-type": "application/json" },
            body: JSON.stringify({ block_id: b.id, lead_id: activeId }),
          }).then(() => {
            // Die Zahl im Kasten stimmt sonst bis zum naechsten Laden nicht.
            b.verwendet = (b.verwendet || 0) + 1;
            const hist = it?.querySelector<HTMLElement>(".cl-hist");
            if (hist) hist.textContent = t("Übernommen · schon %n× verwendet")
              .replace("%n", String(b.verwendet));
          }).catch(() => {});
        }
        break;
      }
      case "clcopy": {
        const it = el.closest<HTMLElement>(".item");
        const ta = it?.querySelector<HTMLTextAreaElement>("textarea.ta");
        const q = it?.querySelector<HTMLElement>(".quote q");
        const text = (ta?.value.trim()) || q?.textContent || "";
        if (text) navigator.clipboard?.writeText(text).catch(() => {});
        const b = el as HTMLButtonElement; const o = b.textContent;
        b.textContent = t("Kopiert"); setTimeout(() => { b.textContent = o; }, 1200);
        break;
      }
      case "cljump": {
        const g = document.getElementById(value);
        if (g) { g.setAttribute("open", ""); g.scrollIntoView({ behavior: "smooth", block: "start" }); }
        break;
      }
      case "clcollapse": {
        const root = el.closest<HTMLElement>(".va-checklist");
        if (root) {
          const anyOpen = root.querySelector("details.grp[open]");
          root.querySelectorAll<HTMLDetailsElement>("details.grp").forEach((g) => {
            if (anyOpen) g.removeAttribute("open"); else g.setAttribute("open", "");
          });
          (el as HTMLElement).textContent = anyOpen ? t("Alle aufklappen") : t("Alle zuklappen");
        }
        break;
      }
      case "editprofil": router.push("/onboarding"); break;   // Profil-Tab → selbe Route wie der Topbar-Button
      case "region": setAktiveRegion(value); bump(); break;
      case "buyerdemo": setBuyerDemo(value); bump(); break;
      case "tonetz": case "netz": switchView("netzwerk"); break;
      case "buyerleads": {
        const l = CORE.find((x) => x.id === activeId) as (Lead & { buyer?: string; buyerShort?: string }) | undefined;
        const label = l?.buyer || value;
        setTokens((ts) => [...ts.filter((tk) => tk.type !== "buyer"), { type: "buyer", value, label }]);
        setMode("browse"); setActiveId(null);
        break;
      }
      case "grp": {
        const g = offeneGruppen as Set<string>;
        g.has(value) ? g.delete(value) : g.add(value);
        bump();
        break;
      }
      case "cmtsend": {
        const ta = el.closest(".detail")?.querySelector<HTMLTextAreaElement>("[data-cmt]");
        const body = ta?.value.trim();
        if (body) {
          const l = CORE.find((x) => x.id === activeId) as (Lead & { comments?: unknown[] }) | undefined;
          l?.comments?.push({ author: t("Du"), initials: "DK", ts: t("gerade eben"), body });
          logEvent(l, "analyze", t("Notiz für das Team ergänzt"));
          bump();
        }
        break;
      }
      case "uploaddocs": {
        // Vergabeunterlagen hochladen → Pipeline (index→signals→LLM) → Felder in den Lead mergen.
        const statusEl = el.closest(".detail")?.querySelector<HTMLElement>(`[data-upstatus="${value}"]`) || null;
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".zip,.pdf,.doc,.docx,.xls,.xlsx,.txt,.html";
        input.onchange = async () => {
          const file = input.files?.[0];
          if (!file) return;
          if (statusEl) statusEl.textContent = t("Lade hoch und analysiere … (kann bis ~30 s dauern)");
          const fd = new FormData();
          fd.append("file", file);
          const lb = (CORE.find((x) => x.id === value) as (Lead & { buyer?: string }) | undefined)?.buyer || "";
          try {
            const r = await fetch(`/api/lead-docs?id=${encodeURIComponent(value)}&buyer=${encodeURIComponent(lb)}`,
              { method: "POST", body: fd });
            const d = await r.json();
            if (!r.ok || d.error) { if (statusEl) statusEl.textContent = t("Fehler: {grund}", { grund: d.error || r.status }); return; }
            const l = CORE.find((x) => x.id === value) as (Lead & { log?: unknown[] }) | undefined;
            if (l) { Object.assign(l, d); logEvent(l, "analyze", t("Vergabeunterlagen hochgeladen & analysiert")); }
            // §5-4: Käufer nicht in den Unterlagen gefunden → Rückfrage (Analyse trotzdem gezeigt).
            const mm = (d as { leadMismatch?: { expected_buyer?: string } }).leadMismatch;
            // Tagesdeckel für hochgeladene Unterlagen erreicht: die Datei liegt bereits,
            // nur die Auswertung wartet. Das MUSS dastehen — sonst sieht der Nutzer einen
            // erfolgreichen Upload ohne Ergebnis und ohne Grund und lädt morgen erneut hoch.
            const wartet = (d as { lbAnalyseWartet?: boolean }).lbAnalyseWartet;
            const teile: string[] = [];
            if (mm) teile.push(`<span style="color:#b91c1c">${t("⚠ Diese Unterlagen erwähnen den Auftraggeber „{buyer}\" nicht, gehören sie wirklich zu diesem Lead? Die Analyse ist unten trotzdem angezeigt.", { buyer: (mm.expected_buyer || "").replace(/[<>&]/g, "") })}</span>`);
            if (wartet) teile.push(`<span style="color:#92400e">${t("Die Unterlagen sind gespeichert. Ausgewertet werden sie im nächsten Tageslauf ab 00:30 Uhr, weil das Auswertungskontingent für hochgeladene Unterlagen heute aufgebraucht ist. Sie müssen nichts noch einmal hochladen.")}</span>`);
            if (statusEl) statusEl.innerHTML = teile.join("<br>");
            bump();
          } catch {
            if (statusEl) statusEl.textContent = t("Upload fehlgeschlagen.");
          }
        };
        input.click();
        break;
      }
      case "ptab": setPotTab(value); break;
      case "pstufe": setProfilStufe(value); break;
      case "partner": {
        const a = angaben as { partner?: boolean };
        a.partner = !a.partner;
        if (!a.partner) { (netzInteresse as Set<string>).clear(); (netzFreigabe as Set<string>).clear(); }
        bump();
        break;
      }
      case "angset": {
        const [k, v] = value.split(":");
        const arr = (angaben as unknown as Record<string, string[]>)[k];
        if (arr && !arr.includes(v)) arr.push(v);
        setOffenerPicker(null);
        bump();
        break;
      }
      case "angrm": {
        const [k, v] = value.split(":");
        const rec = angaben as unknown as Record<string, string[]>;
        if (rec[k]) rec[k] = rec[k].filter((x) => x !== v);
        bump();
        break;
      }
      case "angadd": setOffenerPicker((p) => (p === value ? null : value)); bump(); break;
      case "editbestand": {
        // „Verträge pflegen" → zurück in die Liste im Bestand-Modus (vereinfacht: Liste zeigen)
        setView("angriff");
        setFilters((f) => ({ ...f, kandidaten: false }));
        break;
      }
      // ── Partnersuche ──────────────────────────────────────────────────────────────
      // Vor dem 2026-08-22 lief das rein im Speicher: `toggleNetz` schob eine ID in ein Set,
      // das beim Neuladen verschwand und das niemand sonst je sah. Jetzt geht jeder Schritt
      // an `/api/netz` und kommt mit dem Serverzustand samt Treffer zurück.
      case "netzlos": toggleNetzLos(value); bump(); break;
      case "netzint": netzMelden(value); break;
      case "netzfrei": netzFreigeben(value); break;
      default: break; // mark — Feinschliff
    }
  }
  async function netzSenden(id: string, feld: Record<string, unknown>) {
    try {
      const r = await fetch("/api/netz", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId: id, identityId: identId, ...feld }),
      });
      setNetzZustand(id, r.ok ? await r.json() : null);
    } catch { /* offline: Zustand bleibt, wie er war */ }
    bump();
  }
  /* Melden oder zurückziehen. Die angehakten Lose sind die eigentliche Angabe: ohne sie
     gäbe es keine Ergänzung, sondern nur zwei Firmen auf demselben Los. */
  function netzMelden(id: string) {
    if ((netzInteresse as Set<string>).has(id)) {
      fetch(`/api/netz?leadId=${encodeURIComponent(id)}`, { method: "DELETE" })
        .then(() => { setNetzZustand(id, null); bump(); }).catch(() => {});
      return;
    }
    const lose = netzLoseVon(id);
    if (!lose.length) return;      // der Knopf ist dann ohnehin gesperrt
    netzSenden(id, { lose });
  }
  function netzFreigeben(id: string) { netzSenden(id, { freigabe: true }); }
  function toggleNetz(id: string) { netzMelden(id); }
  function toggleOwn(id: string, ans: string) {
    const l = CORE.find((x) => x.id === id) as (Lead & { eigen?: boolean; eigenBestaetigt?: boolean }) | undefined;
    if (l) {
      l.eigenBestaetigt = ans === "ja";
      l.eigen = ans === "ja";
      if (ans !== "ja" && activeId === id) setActiveId(null);
    }
    bump();
  }
  function toggleCol(key: string) {
    const c = (COLS as { key: string; on: boolean; lock?: boolean; _userOff?: boolean }[]).find((x) => x.key === key);
    if (c && !c.lock) { c.on = !c.on; if (key === "region") c._userOff = !c.on; bump(); }
  }
  // Spalten umordnen (Prototyp-Verhalten: vor/nach dem Ziel je nach Cursorseite)
  function reorderCol(fromKey: string, toKey: string, after: boolean) {
    if (fromKey === toKey || toKey === "star") return;
    const cols = COLS as { key: string }[];
    const from = cols.findIndex((c) => c.key === fromKey);
    const moved = cols.splice(from, 1)[0];
    let to = cols.findIndex((c) => c.key === toKey);
    if (after) to++;
    cols.splice(to, 0, moved);
    bump();
  }

  // Such-Tokens
  function commitSearch(pick?: number | "raw") {
    // FRAGE VOR STICHWORT. Erkennt eine Regel eine Absicht („wenigste Bieter"), wird sie zu
    // einem Filter statt zu einem Volltext-Token — sonst suchte die Anwendung nach dem Wort
    // „Bieter" im Titel und faende nichts. Greift keine Regel, laeuft alles wie bisher.
    const absicht = typeof pick === "number" || suggIdx >= 0 ? null : deuteFrage(query);
    if (absicht) {
      if (tokens.some((x) => x.type === "frage" && x.value === absicht.id)) { setQuery(""); return; }
      const keys = Object.keys(absicht.adv || {});
      if (absicht.adv) setAdv((a) => ({ ...a, ...absicht.adv }));
      if (absicht.sort) { setSortKey(absicht.sort.key); setSortDir(absicht.sort.dir); autoSort.current = false; }
      setTokens((ts) => [...ts, { type: "frage", value: absicht.id, label: absicht.label, advKeys: keys }]);
      setQuery(""); setSuggIdx(-1);
      return;
    }
    let tok: Token | null = null;
    if (typeof pick === "number") tok = suggestions[pick] as Token;
    else if (pick === "raw") tok = classifyQuery(query) as Token;
    else if (suggIdx >= 0 && suggIdx < suggestions.length) tok = suggestions[suggIdx] as Token;
    else tok = classifyQuery(query) as Token;
    if (tok && !tokens.some((x) => x.type === tok!.type && x.value === tok!.value)) {
      // coord/radius mitnehmen — trägt die echte PLZ-Umkreissuche (sonst Token ohne Geo).
      setTokens((ts) => [...ts, { type: tok!.type, value: tok!.value, label: tok!.label,
        ...(tok!.coord ? { coord: tok!.coord } : {}), ...(tok!.radius ? { radius: tok!.radius } : {}) }]);
    }
    setQuery(""); setSuggIdx(-1);
  }
  function removeToken(i: number) {
    const weg = tokens[i];
    // Ein Frage-Token hat einen Filter GESETZT — beim Entfernen muss er zurueck auf den
    // Ausgangswert, nicht einfach stehenbleiben.
    if (weg?.advKeys?.length) {
      setAdv((a) => {
        const n = { ...a } as Record<string, unknown>;
        for (const k of weg.advKeys!) n[k] = (emptyAdv as unknown as Record<string, unknown>)[k];
        return n as Adv;
      });
    }
    setTokens((ts) => ts.filter((_, k) => k !== i));
  }
  function clearAll() {
    // Auch hier: die von Fragen gesetzten Filter muessen mit weg, sonst bleibt nach
    // „alles loeschen" eine unsichtbare Einschraenkung stehen.
    if (tokens.some((t) => t.advKeys?.length)) setAdv(emptyAdv);
    setTokens([]); setQuery("");
    setFilters((f) => ({ ...f, ungesichtet: false, gemerkt: false }));
  }
  function toggleFacetToken(name: string, v: string, label: string) {
    setTokens((ts) => {
      const i = ts.findIndex((tk) => tk.type === name && tk.value === v);
      return i >= 0 ? ts.filter((_, k) => k !== i) : [...ts, { type: name, value: v, label }];
    });
  }
  function togglePlace(region: string, label: string) {
    setTokens((ts) => {
      const i = ts.findIndex((tk) => tk.type === "ort" && tk.value === region);
      return i >= 0 ? ts.filter((_, k) => k !== i) : [...ts, { type: "ort", value: region, label }];
    });
  }
  function setRadius(i: number, km: number) {
    setTokens((ts) => ts.map((tk, k) => (k === i ? { ...tk, radius: km || null } : tk)));
    setOpenRadius(null);
  }

  // Rail-Sichten
  function switchView(next: View) {
    closeAllPops();
    setActiveId(null);
    const netzCol = (COLS as { key: string; on: boolean }[]).find((c) => c.key === "netz");
    if (next === "angriff") {
      setFilters((f) => ({ ...f, netz: false, gemerkt: false }));
      if (netzCol) netzCol.on = false;
    } else if (next === "merkliste") {
      setFilters((f) => ({ ...f, gemerkt: !f.gemerkt, netz: false }));
      if (netzCol) netzCol.on = false;
    } else if (next === "netzwerk") {
      setFilters((f) => ({ ...f, netz: !f.netz, gemerkt: false }));
      if (netzCol) netzCol.on = !filters.netz;
    } else {
      // Strategie ist keine Linse auf die Liste — die Linsen dürfen nicht mitwandern.
      setFilters((f) => ({ ...f, netz: false, gemerkt: false }));
      if (netzCol) netzCol.on = false;
    }
    const nextView: View = next === "merkliste" && filters.gemerkt ? "angriff" : next;
    setView(nextView);
    // URL spiegelt die Ansicht (bookmarkbar), ohne Next-Navigation → kein Remount.
    const nextFilters = {
      gemerkt: next === "merkliste" ? !filters.gemerkt : false,
      netz: next === "netzwerk" ? !filters.netz : false,
    };
    if (typeof window !== "undefined") {
      window.history.pushState(null, "", "/" + slugOf(nextView, nextFilters));
    }
    bump();
  }

  // Zurück/Vor im Browser → Ansicht aus der URL wiederherstellen.
  useEffect(() => {
    function onPop() {
      const slug = window.location.pathname.replace(/^\//, "").split("/")[0] || "leads";
      setView(SLUG_VIEW[slug] ?? "angriff");
      setFilters((f) => ({ ...f, gemerkt: slug === "watchlist", netz: slug === "network" }));
      const netzCol = (COLS as { key: string; on: boolean }[]).find((c) => c.key === "netz");
      if (netzCol) netzCol.on = slug === "network";
      bump();
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [bump]);

  function setBranche(k: string) { brancheManual.current = true; setAktiveBranche(k); setActiveId(null); }
  function resetBranche() { setAktiveBranche(profilBranche); setActiveId(null); }

  // Tastatur
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (e.key === "/" && !el.matches("input,textarea")) {
        e.preventDefault(); searchRef.current?.focus(); return;
      }
      if (el.matches("input,textarea")) return;
      if (e.key === "Escape" && activeId) { setActiveId(null); return; }
      if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
      if (!rows.length) return;
      e.preventDefault();
      const i = rows.findIndex((l) => l.id === activeId);
      const n = e.key === "ArrowDown" ? rows[Math.min(i + 1, rows.length - 1)] : rows[Math.max(i - 1, 0)];
      setActiveId(n.id);
      document.querySelector(`tr[data-id="${n.id}"]`)?.scrollIntoView({ block: "nearest" });
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rows, activeId]);

  // Klick außerhalb schließt Popovers
  useEffect(() => {
    function onDown(e: MouseEvent) {
      const ziel = e.target as HTMLElement;
      if (!ziel.closest(".colcfg")) setColMenuOpen(false);
      if (!ziel.closest(".has-filter") && !ziel.closest(".headpop")) setHeadFilter(null);
      if (!ziel.closest(".ftoken")) setOpenRadius(null);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function onSearchKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") { e.preventDefault(); setSuggIdx((i) => Math.min(i + 1, suggestions.length)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSuggIdx((i) => Math.max(i - 1, -1)); }
    else if (e.key === "Enter") { e.preventDefault(); commitSearch(); }
    else if (e.key === "Escape") { setQuery(""); (e.target as HTMLInputElement).blur(); }
    else if (e.key === "Backspace" && query === "" && tokens.length) {
      setTokens((ts) => ts.slice(0, -1));
    }
  }

  const branchen = BRANCHEN as Record<string, string>;
  const merkN = CORE.filter((l) => l.merk).length;

  return (
    <div className="app" data-view={view === "netzwerk" ? "angriff" : "angriff"}>
      {/* EINE Kopfzeile fuer die ganze Anwendung — dieselbe wie auf „Unternehmen",
          „Bausteine" und „Einstellungen". Bis 2026-08-16 hatte die Shell ihre eigene,
          und nur sie trug Profil und Sprachwahl; die uebrigen Seiten hatten beides nicht.
          Das war keine Gestaltungsentscheidung, sondern eine Folge davon, wo der Zustand
          lag. Jetzt kann keine Seite mehr abweichen, weil es nichts mehr gibt, wovon sie
          abweichen koennte.

          Was die Shell hineinreicht, ist nur, was IHR gehoert: ihre Suche (filtert die
          Tabelle, statt wie die Seitensuche wegzuspringen) und die Listen-Werkzeuge.
          In der Strategie-Ansicht faellt zweiteres weg — dort gibt es keine Tabelle, auf
          die Filter, Spalten oder Export wirken koennten. Sie standen dort trotzdem und
          der Export lieferte die Lead-Liste, die man gar nicht sah. */}
      <AppTop
        suche={
          <div className="searchwrap">
            <label className="tsearch">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.4-3.4" />
              </svg>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSuggIdx(-1); }}
                onKeyDown={onSearchKey}
                placeholder={t("Suchen. Ort, PLZ, Auftraggeber, Stichwort")}
                aria-label={t("Suchen")}
                autoComplete="off"
              />
              <kbd className="tkbd">/</kbd>
            </label>
            <Suggestions query={query} list={suggestions as never} suggIdx={suggIdx} onPick={commitSearch} />
          </div>
        }
        werkzeuge={view === "potenzial" ? null : (
          <>
            <div className="colcfg">
              <button className="colbtn" type="button" onClick={() => setPanelOpen(true)} title={t("Detailfilter")}>
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 5h18l-7 8v5l-4 2v-7L3 5Z" />
                </svg>
                {t("Filter")}{advCount(adv) ? <span className="filt-n">{advCount(adv)}</span> : null}
              </button>
            </div>
            <div className="colcfg">
              <button className="colbtn" type="button" onClick={() => setColMenuOpen((o) => !o)}>
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M3 5h18M3 12h18M3 19h18" />
                </svg>
                {t("Spalten")}
              </button>
              <ColumnMenu open={colMenuOpen} onToggleCol={toggleCol} />
            </div>
            <ExportMenu rows={rows} view={filters.relevant ? "passend" : "alle"} />
          </>
        )}
      />

      {/* BEREICHSLEISTE — die zweite Zeile des Rahmens, in JEDEM Bereich gleich hoch.
          Sie lag bis 2026-08-15 IM Kopf; dadurch war der Kopf hier 93 px hoch und auf
          „Unternehmen"/„Bausteine" nur 48. Beim Wechsel sprang der gesamte Inhalt um
          45 px — genau das, was sich uneinheitlich anfuehlte (gemessen, nicht geschaetzt).

          Sie mit Leerraum aufzufuellen waere die falsche Loesung gewesen. Stattdessen
          traegt die Leiste in jedem Bereich das, was dort oben hingehoert: hier die
          Suchtoken, im Unternehmen die Reiter. Gleiche Hoehe, gleicher Ort, anderer
          Inhalt — das ist ein Rahmen und keine Polsterung. */}
      {/* NUR BEI AKTIVER SUCHE. Vorher stand die Leiste immer da — und war im Normalfall
          leer (`<div class="filterbar empty">`), also 45 px Chrom ohne Aussage.
          Ein Sprung, den der Nutzer selbst ausloest (er sucht), ist lesbar; einer beim
          Bereichswechsel nicht. Nur den zweiten galt es zu beseitigen. */}
      {/* DIE ZWEITE ZEILE — in JEDEM Bereich vorhanden, gleich hoch, und in JEDEM mit
          Inhalt: hier Trefferzahl und Suchtoken, in der Strategie die neun Abschnitte, im
          Unternehmen seine drei, in Bausteinen die Themen.

          Sie stand frueher nur bei aktiver Suche, weil sie sonst leeres Chrom gewesen
          waere. Das galt, solange sie nur Suchtoken tragen konnte. Seit die Abschnitte
          aller Bereiche hier liegen, ist der Grund entfallen — und die feste Hoehe ist
          jetzt der Gewinn: beim Wechsel zwischen Bereichen springt nichts mehr. */}
      <div className="bereichsleiste">
        {view === "potenzial" ? (
          <BereichsNav
            aktiv={stratSektion}
            onWechsel={setStratSektion}
            gruppen={SEKTIONEN.map((g) => ({
              titel: g.group,
              punkte: g.items.map((i) => ({ key: i.key, label: i.label })),
            }))}
            hinweis={SEKTIONEN.flatMap((g) => g.items).find((i) => i.key === stratSektion)?.frage}
          />
        ) : (
          <>
            <span className="tcount">
              {/* Nenner auf DERSELBEN Grundmenge wie die Anzeige — in der
                  Zuschlags-Sicht sind das die Zuschläge, sonst die offenen. */}
              <b>{rows.length}</b> {t("von")} <span>{zuschlagsSicht ? alleRows.length : alleRows.filter((l) => l.src !== "award").length}</span>
            </span>
            {tokens.length > 0 ? (
              <FilterBar
                tokens={tokens}
                openRadius={openRadius}
                onRemove={removeToken}
                onClear={clearAll}
                onToggleRadius={(i) => setOpenRadius((r) => (r === i ? null : i))}
                onSetRadius={setRadius}
              />
            ) : null}
          </>
        )}
      </div>

      <div className="body">
        <AppRail
          current={aktiverRailPunkt}
          merkN={merkN}
          onSwitch={(id) => switchView(RAIL_VIEW[id])}
          plan={plan}
          userEmail={userEmail}
          onLogout={abmelden}
        />

        <div className="main" ref={mainRef}>
          {view === "potenzial" ? (
            <section className="profilview">
              <StrategieView
                potTab={potTab}
                profilStufe={profilStufe}
                offenerPicker={offenerPicker}
                aktiveBranche={aktiveBranche}
                accountLimit={accountLimit}
                tick={tick}
                aktiveSektion={stratSektion}
                onBodyAction={onBodyAction}
              />
            </section>
          ) : (
          <>
          <section className="tablewrap">
            {filters.gemerkt && (
              <div className="wl-toggle" role="tablist" aria-label={t("Merkliste-Ansicht")}>
                <button role="tab" aria-selected={!kalMode} className={!kalMode ? "on" : ""} onClick={() => setKalMode(false)}>{t("Cockpit")}</button>
                <button role="tab" aria-selected={kalMode} className={kalMode ? "on" : ""} onClick={() => setKalMode(true)}>{t("Termine")}</button>
              </div>
            )}
            {filters.gemerkt && kalMode ? (
              <Kalender
                rows={rows}
                onSelect={openLead}
                feedUrl={feedUrl}
                onSubscribe={async () => {
                  const token = await getOrCreateCalendarFeed();
                  if (token) setFeedUrl(`${window.location.origin}/api/calendar/${token}.ics`);
                }}
              />
            ) : filters.gemerkt ? (
              <div className="ckscroll">
                <Cockpit
                  rows={CORE.filter((l) => l.merk || (l as { pipe?: string }).pipe || (l as { outcome?: string }).outcome || (l.eigen && l.eigenBestaetigt !== false))}
                  onSelect={openLead}
                  onApply={ckApply}
                  onStatus={ckStatus}
                  onOutcome={ckOutcome}
                  onConfirm={ckConfirm}
                  onMitgeboten={ckMitgeboten}
                  verwaist={verwaist}
                />
              </div>
            ) : (
            <div className="tablescroll" onScroll={onTableScroll}>
              {(() => {
                // #24 Alert-Band (§4): frische Zuschläge (≤3 Tage) im aktuellen Feld — der eigentliche
                // Auslöser. Gebündelt, nicht je Einzelzuschlag; ausblendbar.
                if (awAlertOff) return null;
                type Aw = { ago?: number; winner?: string };
                const awOf = (l: Lead) => (l as { award?: Aw }).award;
                // WICHTIG: aus `alleRows` (inkl. Zuschläge), nicht aus `rows` — dort sind die
                // Zuschläge bewusst herausgefiltert, das Band würde sich sonst selbst abschalten.
                // „in eurem Feld" war gelogen: gezählt wurde der ganze Grundraum. Mit Profil
                // zählen wir nur, was auch zu euch passt — sonst meldet die App einem
                // Tiefbauer aus Sachsen-Anhalt Zuschläge aus ganz Deutschland.
                const fresh = alleRows.filter((l) =>
                  l.src === "award" && (awOf(l)?.ago ?? 99) <= 3
                  && (!realProfile || l.relevanz === "hoch" || l.relevanz === "mittel"));
                if (!fresh.length) return null;
                const winners = [...new Set(fresh.map((l) => awOf(l)?.winner).filter(Boolean))].slice(0, 2);
                return (
                  <div className="aw-alert">
                    <svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8" /><path d="M13.7 21a2 2 0 01-3.4 0" /></svg>
                    <div><b>{fresh.length === 1
                        ? (realProfile ? t("{n} neuer Zuschlag in eurem Feld", { n: fresh.length }) : t("{n} neuer Zuschlag im Grundraum", { n: fresh.length }))
                        : (realProfile ? t("{n} neue Zuschläge in eurem Feld", { n: fresh.length }) : t("{n} neue Zuschläge im Grundraum", { n: fresh.length }))}</b>
                      {winners.length ? ` — ${winners.join(` ${t("und")} `)}. ` : " — "}{t("Wer gerade gewonnen hat, kauft jetzt ein.")}</div>
                    {/* Zuschläge sind nicht mehr bewerbbar und stehen deshalb nicht in der Akquise-Liste.
                        Hier — wo sie angekündigt werden — führt ein Klick direkt zu ihnen. */}
                    <button className="aw-alert-go" onClick={() => setAdv((a) => ({ ...a, phases: ["award"] }))}>
                      {t("Zuschläge ansehen")}
                    </button>
                    <button className="aw-alert-x" onClick={() => setAwAlertOff(true)} aria-label={t("Ausblenden")}>✕</button>
                  </div>
                );
              })()}
              <LeadTable
                rows={rows}
                limit={renderCount}
                // Die Vorauswahl steht am ENDE der Liste: dort kommt man beim Lesen an, und
                // dort ist die Frage „ist das alles?" tatsächlich aktuell. Als Banner darüber
                // wurde sie weggeklickt, bevor man einen Lead gesehen hatte. Stilles Filtern
                // bleibt ausgeschlossen — die weggelassene Menge steht weiterhin da.
                fuss={
                  PHASEN ? (
                    /* Die Liste endet nie hart: die letzte Zeile reicht an die nächste Phase
                       weiter (oder zurück auf die erste). So sieht man immer nur eine
                       Handvoll Leads, weiß aber, was dahinter liegt. */
                    <div className="phasefuss">
                      {phasenOffen < PHASEN.length ? (
                        <button className="pf-next" onClick={() => setPhasenOffen(phasenOffen + 1)}>
                          <span className="pf-pfeil">▾</span>
                          <span className="pf-k">{t("Auch anzeigen")}</span>
                          <b>{t(PHASEN[phasenOffen].titel)}</b>
                          <span className="pf-n">{PHASEN[phasenOffen].rows.length}</span>
                          <span className="pf-h">{t(PHASEN[phasenOffen].hinweis)}</span>
                        </button>
                      ) : (
                        <button className="pf-next" onClick={() => setPhasenOffen(1)}>
                          <span className="pf-pfeil">▴</span>
                          <span className="pf-k">{t("Wieder einklappen")}</span>
                          <b>{t("nur {phase}", { phase: t(PHASEN[0].titel) })}</b>
                          <span className="pf-n">{PHASEN[0].rows.length}</span>
                        </button>
                      )}
                      <button className="pf-alle" onClick={() => setVorauswahl(false)}>
                        {t("Alle {n} Ausschreibungen des Grundraums", { n: alleRows.filter((l) => l.src !== "award").length.toLocaleString("de-DE") })}
                      </button>
                    </div>
                  ) : (
                  realProfile && istAkquise && !adv.phases.includes("award") ? (
                  <div className={`vor-band ${vorauswahl ? "" : "off"}`}>
                    {vorauswahl ? (
                      <>
                        {t("Das ist alles, was zu euch passt.")} <span className="vor-gr">{t("{n} Ausschreibungen im Grundraum {branche}", { n: alleRows.filter((l) => l.src !== "award").length.toLocaleString("de-DE"), branche: t((BRANCHEN as Record<string, string>)[aktiveBranche]) })}</span>
                        {/* Die Auswahl-Kriterien stehen jetzt in den Abschnitts-Zeilen der Liste,
                            wo sie gelten. Hier bleibt nur die Region — die sieht man sonst nirgends. */}
                        <span className="vor-x">
                          {(() => {
                            const p = realProfile as unknown as { regionLabels?: string[]; regions?: string[] } | null;
                            if (!p?.regions?.length) return null;
                            const wo = (p.regionLabels?.length ? p.regionLabels : p.regions).slice(0, 3).join(", ");
                            return t("gefiltert auf {wo}, aus euren Zuschlägen abgeleitet", { wo });
                          })()}
                        </span>
                        <button className="vor-btn" onClick={() => setVorauswahl(false)}>{t("Alle {n} anzeigen", { n: alleRows.filter((l) => l.src !== "award").length.toLocaleString("de-DE") })}</button>
                      </>
                    ) : (
                      <>
                        {t("Alle")} <b>{rows.length.toLocaleString("de-DE")}</b> {t("Ausschreibungen in {branche}", { branche: t((BRANCHEN as Record<string, string>)[aktiveBranche]) })}
                        <span className="vor-x">{t("ungefiltert, auch Ankündigungen und weniger passende")}</span>
                        <button className="vor-btn" onClick={() => setVorauswahl(true)}>{t("Wieder vorsortieren")}</button>
                      </>
                    )}
                  </div>
                  ) : null
                  )
                }
                sortKey={sortKey}
                sortDir={sortDir}
                activeId={activeId}
                activeFacets={activeFacets}
                onSort={handleSort}
                onSelect={openLead}
                onStar={toggleStar}
                onNetz={toggleNetz}
                onOwn={toggleOwn}
                onHeadFilter={(facet, rect) =>
                  setHeadFilter((h) => (h && h.facet === facet ? null : { facet, rect }))
                }
                onReorder={reorderCol}
                colWidths={colWidths}
                onResize={setColWidth}
              />
            </div>
            )}
          </section>

          <div className="divider" role="separator" aria-orientation="horizontal" onMouseDown={startDivider} />

          <section className="detail">
            <DetailPanel
              activeId={activeId}
              activeTab={activeTab}
              mode={mode}
              tick={tick}
              buyerDemo={buyerDemo}
              aktiveRegion={aktiveRegion}
              accountLimit={accountLimit}
              rows={rows}
              alle={alleRows}
              onGoto={(ziel) => {
                // Ein Klick im Überblick soll die Ansicht wirklich wechseln, nicht nur
                // etwas einfärben — deshalb dieselben Wege wie über die Rail.
                if (ziel === "netzwerk") return switchView("netzwerk");
                if (ziel === "strategie") return switchView("potenzial");
                /* Die Treffergüte ist der EINZIGE Ort, an dem eine offene Angabe direkt
                   gefüllt werden kann (`BetragInput`: Betrag eintippen, Enter). Der Hinweis
                   im Überblick führte bis zum 2026-09-01 auf `/unternehmen`, wo genau diese
                   zwei Felder nicht stehen. */
                if (ziel === "trefferguete") { switchView("potenzial"); setStratSektion("trefferguete"); return; }
                if (ziel === "award") return setAdv((a) => ({ ...a, phases: ["award"] }));
                if (ziel === "vorschau") return setPhasenOffen(2);
                // Zurück auf die erste Phase — der Weg, der aus dem Überblick fehlte.
                if (ziel === "jetzt") { setPhasenOffen(1); setActiveId(null); return; }
              }}
              onPickLead={openLead}
              onTab={setTab}
              onClose={closeLead}
              onExpand={toggleExpand}
              onWf={setWf}
              onStar={toggleStar}
              onBodyAction={onBodyAction}
            />
          </section>
          </>
          )}
        </div>
      </div>

      <FilterPanel
        open={panelOpen}
        adv={adv}
        resultCount={rows.length}
        branche={aktiveBranche}
        profilBranche={profilBranche}
        brancheCounts={branchenCounts}
        onSetBranche={setBranche}
        onResetBranche={resetBranche}
        segments={cpvSegments}
        onChange={setAdv}
        onClose={() => setPanelOpen(false)}
        onReset={() => setAdv(emptyAdv)}
      />

      {headFilter ? (
        <HeaderFilterPopover
          facet={headFilter.facet}
          rect={headFilter.rect}
          tokens={tokens}
          onToggleFacet={toggleFacetToken}
          onTogglePlace={togglePlace}
        />
      ) : null}
    </div>
  );
}
