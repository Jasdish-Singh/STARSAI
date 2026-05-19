"""Quick EDA — what does the data tell us?"""
import pandas as pd, numpy as np

ROOT = __file__ = __import__('pathlib').Path(__file__).parent.parent
scores = pd.read_parquet(ROOT / "data/scores/scores.parquet")
feat = pd.read_parquet(ROOT / "data/gold/stop_features.parquet")

print("=== SCORE DISTRIBUTION ===")
print(f"Mean: {scores['t_ntsi_score'].mean():.1f}, Median: {scores['t_ntsi_score'].median():.1f}")
print(f"Std: {scores['t_ntsi_score'].std():.1f}")
print(f"Q1: {scores['t_ntsi_score'].quantile(0.25):.1f}, Q3: {scores['t_ntsi_score'].quantile(0.75):.1f}")
print(f"Skew: {scores['t_ntsi_score'].skew():.2f}\n")

print("=== FACTOR CORRELATIONS WITH COMPOSITE ===")
factor_cols = [c for c in scores.columns if c.startswith("f_")]
for c in sorted(factor_cols, key=lambda x: -scores[x].corr(scores["t_ntsi_score"])):
    r = scores[c].corr(scores["t_ntsi_score"])
    print(f"  {c:25s}: r={r:+.3f}")

print("\n=== BOTTOM 10% vs TOP 10% — FACTOR GAPS ===")
bottom = scores[scores["t_ntsi_score"] <= scores["t_ntsi_score"].quantile(0.10)]
top = scores[scores["t_ntsi_score"] >= scores["t_ntsi_score"].quantile(0.90)]
for c in factor_cols:
    gap = top[c].mean() - bottom[c].mean()
    print(f"  {c:25s}: bottom10={bottom[c].mean():.1f}  top10={top[c].mean():.1f}  gap={gap:+.1f}")

print("\n=== RAW FEATURES — BOTTOM vs TOP 10% ===")
cols = ["lights_50m","crime_count_500m","pois_150m","food_drink_150m",
        "buildings_50m","lit_yes_100m","disorder_count_200m"]
for c in cols:
    if c in feat.columns:
        print(f"  {c:25s}: bottom10={feat.loc[bottom.index,c].mean():6.1f}  top10={feat.loc[top.index,c].mean():6.1f}")

print("\n=== CRIME ===")
c = feat["crime_count_500m"]
zc = (c == 0).sum()
print(f"  Zero crime in 500m: {zc}/{len(feat)} ({zc/len(feat)*100:.1f}%)")
print(f"  Non-zero: mean={c[c>0].mean():.1f} median={c[c>0].median():.0f} max={c.max():.0f}")

print("\n=== LIGHTING ===")
l = feat["lights_50m"]
print(f"  Mean: {l.mean():.1f}  Median: {l.median():.0f}  Zero-lights: {(l==0).sum()} ({(l==0).sum()/len(feat)*100:.1f}%)")

print("\n=== POIS ===")
p = feat["pois_150m"]
print(f"  Mean: {p.mean():.1f}  Median: {p.median():.0f}  Zero: {(p==0).sum()} ({(p==0).sum()/len(feat)*100:.1f}%)")

print("\n=== LIT WAYS ===")
lw = feat["lit_yes_100m"]
print(f"  Mean: {lw.mean():.1f}  Median: {lw.median():.0f}  Zero: {(lw==0).sum()} ({(lw==0).sum()/len(feat)*100:.1f}%)")

print("\n=== 311 DISORDER ===")
d = feat["disorder_count_200m"]
print(f"  Mean: {d.mean():.1f}  Median: {d.median():.0f}  Zero: {(d==0).sum()} ({(d==0).sum()/len(feat)*100:.1f}%)")
print(f"  High (>5): {(d>5).sum()}  Max: {d.max():.0f}")

print("\n=== WORST 10 STOPS ===")
worst = scores.nsmallest(10, "t_ntsi_score")
for _, r in worst.iterrows():
    print(f"  {r['t_ntsi_score']:5.1f} | L{r['f_lighting']:4.0f} C{r['f_crime']:4.0f} E{r['f_eyes_on_street']:4.0f} I{r['f_isolation']:4.0f} D{r['f_disorder_311']:4.0f} | {r['stop_name'][:50]}")

print("\n=== BEST 10 STOPS ===")
best = scores.nlargest(10, "t_ntsi_score")
for _, r in best.iterrows():
    print(f"  {r['t_ntsi_score']:5.1f} | L{r['f_lighting']:4.0f} C{r['f_crime']:4.0f} E{r['f_eyes_on_street']:4.0f} I{r['f_isolation']:4.0f} D{r['f_disorder_311']:4.0f} | {r['stop_name'][:50]}")

print("\n=== STORY: WHAT DRIVES BAD SCORES ===")
# Which factor pulls the bottom 10% down hardest?
for c in factor_cols:
    bottom_gap = scores[c].median() - bottom[c].median()
    if bottom_gap > 0:
        print(f"  {c}: bottom10 median {bottom_gap:.1f} pts below overall median")

print("\n=== CRIME vs EYES ON STREET: JOINT ===")
# Are low-crime + high-POI stops safer than low-crime + low-POI?
feat_idx = scores.copy()
feat_idx["crime_bin"] = pd.qcut(feat["crime_count_500m"], 3, labels=["low","med","high"])
feat_idx["poi_bin"] = pd.qcut(feat["pois_150m"], 3, labels=["low","med","high"])
pivot = feat_idx.pivot_table(values="t_ntsi_score", index="crime_bin", columns="poi_bin", aggfunc="mean")
print(pivot.to_string())
