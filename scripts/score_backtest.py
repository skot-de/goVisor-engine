"""Kalibrierungs-Backtest des NEUEN Scores (echte contract_successions-Labels,
Merkmale Vertragsart × Branche × Bieter). 5-fach kreuzvalidiert. Vergleich zur
alten (nur Branche×Bieter) Basis über AUC/ECE/Brier."""
import duckdb
import numpy as np
import pandas as pd

MIN = 20
S = "data/silver/DE"; G = "data/gold/DE"
def sg(t): return f"'{S}/{t}/*/*.parquet'"

con = duckdb.connect()
KIND = """CASE
  WHEN lower(p.title) LIKE '%rahmen%' THEN 'rahmenvertrag'
  WHEN regexp_matches(lower(p.title),'wartung|pflege|lizenz|reinigung|bewirtschaft|unterhalt|betreib|betrieb|entsorgung|catering|bewachung|winterdienst|support|hosting|miete|leasing|verpflegung|instandhalt|dienstleistung|service|beratung|gala') THEN 'wiederkehrend'
  WHEN p.cpv_main LIKE '45%' AND regexp_matches(lower(p.title),'neubau|sanierung|umbau|abbruch|errichtung|rohbau|ausbau|modernisierung|fassad|dachsanierung|erweiterungsbau|anbau') THEN 'einmal_werk'
  WHEN p.cpv_main LIKE '45%' THEN 'werk_sonstig' ELSE 'sonstiges' END"""
df = con.execute(f"""
  WITH tnd AS (SELECT notice_id, max(num_tenders) nt FROM {sg('awards')} WHERE num_tenders>0 GROUP BY 1)
  SELECT {KIND} AS kind, coalesce(dc.branche,'?') branche, tnd.nt,
         (NOT cs.incumbent_retained)::INT AS displaced
  FROM '{G}/contract_successions.parquet' cs
  JOIN {sg('notices')} p ON p.notice_id=cs.predecessor
  LEFT JOIN '{G}/dim_cpv.parquet' dc ON dc.division=substr(p.cpv_main,1,2)
  LEFT JOIN tnd ON tnd.notice_id=cs.predecessor
  WHERE cs.incumbent_retained IS NOT NULL
""").df()
con.close()

def bucket(nt):
    if pd.isna(nt): return "unbekannt"
    return "einzel" if nt == 1 else "wenig" if nt <= 3 else "viel"
df["bucket"] = df["nt"].apply(bucket)
print(f"Echte Nachfolge-Trainingszeilen: {len(df):,} | Basisrate Verdrängung {df.displaced.mean():.3f}")

def train(tr):
    return (tr.groupby(["kind", "branche", "bucket"]).displaced.agg(["mean", "count"]),
            tr.groupby(["kind", "branche"]).displaced.agg(["mean", "count"]),
            tr.groupby("kind").displaced.agg(["mean", "count"]), tr.displaced.mean())
def predict(rows, m):
    kbb, kb, k, gm = m
    out = []
    for _, r in rows.iterrows():
        if (r.kind, r.branche, r.bucket) in kbb.index and kbb.loc[(r.kind, r.branche, r.bucket), "count"] >= MIN:
            out.append(kbb.loc[(r.kind, r.branche, r.bucket), "mean"])
        elif (r.kind, r.branche) in kb.index and kb.loc[(r.kind, r.branche), "count"] >= MIN:
            out.append(kb.loc[(r.kind, r.branche), "mean"])
        elif r.kind in k.index and k.loc[r.kind, "count"] >= MIN:
            out.append(k.loc[r.kind, "mean"])
        else:
            out.append(gm)
    return out

rng = np.random.RandomState(42)
folds = np.array_split(rng.permutation(len(df)), 5)
df = df.reset_index(drop=True); df["pred"] = np.nan
for kf in range(5):
    te = df.index.isin(folds[kf])
    df.loc[te, "pred"] = predict(df[te], train(df[~te]))

print("\n=== KALIBRIERUNG (out-of-sample) ===")
print(f"{'Bin':<12}{'n':>6}{'vorherges.':>12}{'tatsächl.':>11}{'Δ':>8}")
ece = 0.0
for lab, grp in df.groupby(pd.cut(df["pred"], [0, .5, .6, .7, .8, .9, 1.01], right=False), observed=True):
    if len(grp) == 0: continue
    pm, am = grp["pred"].mean(), grp["displaced"].mean()
    ece += len(grp) / len(df) * abs(pm - am)
    print(f"{str(lab):<12}{len(grp):>6}{pm:>12.3f}{am:>11.3f}{pm-am:>+8.3f}")
brier = ((df["pred"] - df["displaced"]) ** 2).mean()
base = df["displaced"].mean(); brier_b = ((base - df["displaced"]) ** 2).mean()
r = df["pred"].rank(); pos = df["displaced"] == 1
auc = (r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum())
print(f"\nECE {ece:.3f} | Brier {brier:.4f} vs Baseline {brier_b:.4f} ({100*(brier_b-brier)/brier_b:+.1f}%) | "
      f"AUC {auc:.3f}  (alt: AUC 0,659 / ECE 0,019)")
