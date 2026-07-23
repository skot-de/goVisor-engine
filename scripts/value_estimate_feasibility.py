"""Ist der fehlende Wert schätzbar? Zell-Median (CPV×Laufzeit×Bieter) + Backoff,
5-fach kreuzvalidiert auf der BEWERTETEN Hälfte. Misst MdAPE + Band-Trefferquote."""
import duckdb
import numpy as np
import pandas as pd

S = "data/silver/DE"; G = "data/gold/DE"
def sg(t): return f"'{S}/{t}/*/*.parquet'"
MIN = 10
BANDS = [(0, 50e3, "<50k"), (50e3, 200e3, "50-200k"), (200e3, 1e6, "200k-1M"),
         (1e6, 5e6, "1-5M"), (5e6, 9e18, ">5M")]
def band(v):
    for lo, hi, lab in BANDS:
        if lo <= v < hi: return lab
    return "?"

con = duckdb.connect()
df = con.execute(f"""
    WITH dur AS (SELECT notice_id, max(duration_months) dm FROM {sg('lots')} WHERE duration_months>0 GROUP BY 1),
         tnd AS (SELECT notice_id, max(num_tenders) nt FROM {sg('awards')} WHERE num_tenders>0 GROUP BY 1)
    SELECT substr(n.cpv_main,1,4) cpv4, substr(n.cpv_main,1,2) cpv2,
           dc.branche, dur.dm, tnd.nt,
           q.final_value_clean * dd.factor_to_2020 AS val_real
    FROM {sg('notices')} n
    JOIN '{G}/quality.parquet' q ON q.notice_id=n.notice_id
    JOIN '{G}/dim_deflator.parquet' dd ON dd.year=n.year
    LEFT JOIN '{G}/dim_cpv.parquet' dc ON dc.division=substr(n.cpv_main,1,2)
    LEFT JOIN dur ON dur.notice_id=n.notice_id
    LEFT JOIN tnd ON tnd.notice_id=n.notice_id
    WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND q.final_value_clean IS NOT NULL
""").df()
con.close()

def dbucket(x):
    if pd.isna(x): return "d?"
    return "d<=12" if x <= 12 else "d13-36" if x <= 36 else "d37-60" if x <= 60 else "d>60"
def bbucket(x):
    if pd.isna(x): return "b?"
    return "b1" if x == 1 else "b2-3" if x <= 3 else "b4+"
df["db"] = df["dm"].apply(dbucket)
df["bb"] = df["nt"].apply(bbucket)
df["branche"] = df["branche"].fillna("?")
df = df[df["val_real"] > 0].reset_index(drop=True)
print(f"Bewertete CANs (real 2020): {len(df):,} | Median {df.val_real.median():,.0f} €")

def build(tr):
    lv = np.log(tr["val_real"])
    tr = tr.assign(lv=lv)
    return {
        "cell": tr.groupby(["cpv4", "db", "bb"]).lv.agg(["median", "count"]),
        "cpv4": tr.groupby("cpv4").lv.agg(["median", "count"]),
        "cpv2": tr.groupby("cpv2").lv.agg(["median", "count"]),
        "branche": tr.groupby("branche").lv.agg(["median", "count"]),
        "g": lv.median(),
    }
def predict(rows, m):
    out = []
    for _, r in rows.iterrows():
        for lvl, key in [("cell", (r.cpv4, r.db, r.bb)), ("cpv4", r.cpv4),
                         ("cpv2", r.cpv2), ("branche", r.branche)]:
            t = m[lvl]
            if key in t.index and t.loc[key, "count"] >= MIN:
                out.append(np.exp(t.loc[key, "median"])); break
        else:
            out.append(np.exp(m["g"]))
    return np.array(out)

rng = np.random.RandomState(42)
folds = np.array_split(rng.permutation(len(df)), 5)
df["pred"] = np.nan
for k in range(5):
    te = df.index.isin(folds[k])
    df.loc[te, "pred"] = predict(df[te], build(df[~te]))

ape = (np.abs(df["pred"] - df["val_real"]) / df["val_real"])
band_hit = (df["val_real"].apply(band) == df["pred"].apply(band)).mean()
# Baseline: globaler Median als Schätzung
base = df["val_real"].median()
ape_base = (np.abs(base - df["val_real"]) / df["val_real"])
band_hit_base = (df["val_real"].apply(band) == band(base)).mean()

print("\n=== KREUZVALIDIERTE SCHÄTZGENAUIGKEIT ===")
print(f"MdAPE (Median abs. %-Fehler)     Modell {ape.median()*100:>5.0f}%   | Baseline (globaler Median) {ape_base.median()*100:>5.0f}%")
print(f"Anteil Schätzung ±50% korrekt     Modell {(ape<=0.5).mean()*100:>5.0f}%   | Baseline {(ape_base<=0.5).mean()*100:>5.0f}%")
print(f"Band-Trefferquote (exakt)         Modell {band_hit*100:>5.0f}%   | Baseline {band_hit_base*100:>5.0f}%")
# Band ±1 (Nachbarband gilt als Treffer)
order = {lab: i for i, (_, _, lab) in enumerate(BANDS)}
band_near = (np.abs(df["val_real"].apply(lambda v: order[band(v)]) - df["pred"].apply(lambda v: order[band(v)])) <= 1).mean()
print(f"Band-Trefferquote (±1 Band)       Modell {band_near*100:>5.0f}%")
