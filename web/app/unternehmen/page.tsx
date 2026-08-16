"use client";

import { useState } from "react";
import { UnternehmenView, type UnTab } from "@/components/unternehmen/UnternehmenView";
import { BereichsNav } from "@/components/explorer/BereichsNav";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";
import "./unternehmen.css";

// #27 Eignungsprofil — im gleichen Gerüst wie die Lead-Ansichten (Hauptnavigation links),
// nicht als Seite ohne Rückweg.
export default function UnternehmenPage() {
  const [tab, setTab] = useState<UnTab>("profil");
  return (
    <div className="app">
      <AppTop />
      {/* Die Abschnitte stehen in der Bereichsleiste — derselben Zeile, in der die
          Lead-Ansichten ihre Suchtoken und Bausteine seine Themen zeigen. Vorher lagen
          sie in der Kopfzeile und damit an einem Ort, den kein anderer Bereich benutzte. */}
      <div className="bereichsleiste">
        <BereichsNav
          aktiv={tab}
          onWechsel={(k) => setTab(k as UnTab)}
          gruppen={[{ punkte: [
            { key: "profil", label: "Eignungsprofil" },
            { key: "bilanz", label: "Unsere Bilanz" },
            { key: "chancen", label: "Chancen" },
          ] }]}
        />
      </div>
      <div className="body">
        <AppRail current="unternehmen" />
        <div className="main seitenmain">
          <UnternehmenView tab={tab} onTab={setTab} />
        </div>
      </div>
    </div>
  );
}
