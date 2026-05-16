"""
NAJAH-AI — Entraînement des modèles ML
  - RandomForestClassifier  : prédit le label d'engagement (Engagé / Modéré / À risque)
  - RandomForestRegressor   : prédit le score d'engagement (0-100)
  - IsolationForest         : détecte les anomalies comportementales

Lancer : python backend/train_models.py
"""
import os, json
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, mean_absolute_error

BASE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.join(BASE, "..")
DATA  = os.path.join(ROOT, "data")
MODEL = os.path.join(ROOT, "models")
os.makedirs(MODEL, exist_ok=True)

# ── 1. Chargement des données ─────────────────────────────────
print("Chargement des données…")
df = pd.read_csv(os.path.join(DATA, "engagement.csv"))

FEATURES = ["time_spent_min", "interactions", "quiz_score", "submissions", "logins", "week"]

# Validation des colonnes
for col in FEATURES + ["engagement_score", "engagement_label"]:
    assert col in df.columns, f"Colonne manquante: {col}"

X = df[FEATURES].values
y_label = df["engagement_label"].values
y_score = df["engagement_score"].values

# ── 2. Label encoder ─────────────────────────────────────────
le = LabelEncoder()
y_enc = le.fit_transform(y_label)
print(f"  Classes : {list(le.classes_)}")

# ── 3. Train/test split ──────────────────────────────────────
X_tr, X_te, yc_tr, yc_te, ys_tr, ys_te = train_test_split(
    X, y_enc, y_score, test_size=0.2, random_state=42, stratify=y_enc)

# ── 4. Classificateur (label engagement) ─────────────────────
print("\nEntraînement du classificateur (label)…")
clf = RandomForestClassifier(
    n_estimators=200, max_depth=10, min_samples_leaf=2,
    class_weight="balanced", random_state=42, n_jobs=-1)
clf.fit(X_tr, yc_tr)
y_pred = clf.predict(X_te)
print(classification_report(yc_te, y_pred, target_names=le.classes_))

# ── 5. Régresseur (score numérique) ──────────────────────────
print("Entraînement du régresseur (score)…")
reg = RandomForestRegressor(
    n_estimators=200, max_depth=10, min_samples_leaf=2,
    random_state=42, n_jobs=-1)
reg.fit(X_tr, ys_tr)
ys_pred = reg.predict(X_te)
mae = mean_absolute_error(ys_te, ys_pred)
print(f"  MAE score : {mae:.2f} pts")

# ── 6. Détecteur d'anomalies (Isolation Forest) ──────────────
print("\nEntraînement du détecteur d'anomalies…")
iso = IsolationForest(
    n_estimators=200, contamination=0.07,
    random_state=42, n_jobs=-1)
iso.fit(X)  # non supervisé — utilise tout le dataset

# Vérification : taux d'anomalies détectées
preds_iso = iso.predict(X)
anom_rate = (preds_iso == -1).mean()
print(f"  Taux d'anomalies détectées : {anom_rate*100:.1f}%")

# ── 7. Sauvegarde ─────────────────────────────────────────────
print("\nSauvegarde des modèles…")
joblib.dump(clf, os.path.join(MODEL, "clf_engagement.pkl"))
joblib.dump(reg, os.path.join(MODEL, "reg_score.pkl"))
joblib.dump(iso, os.path.join(MODEL, "iso_anomaly.pkl"))
joblib.dump(le,  os.path.join(MODEL, "label_encoder.pkl"))

meta = {
    "features":       FEATURES,
    "classes":        list(le.classes_),
    "clf_accuracy":   float((y_pred == yc_te).mean()),
    "reg_mae":        float(mae),
    "anomaly_rate":   float(anom_rate),
    "trained_on":     len(df),
    "feature_importance": {
        f: round(float(v), 4)
        for f, v in zip(FEATURES, clf.feature_importances_)
    }
}
with open(os.path.join(MODEL, "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

print("\nModèles sauvegardés dans models/")
print(f"  clf_engagement.pkl  — accuracy : {meta['clf_accuracy']*100:.1f}%")
print(f"  reg_score.pkl       — MAE      : {mae:.2f} pts")
print(f"  iso_anomaly.pkl     — taux     : {anom_rate*100:.1f}%")
print(f"  label_encoder.pkl")
print(f"  meta.json")
print("\nImportance des variables :")
for f, v in sorted(meta["feature_importance"].items(), key=lambda x: -x[1]):
    bar = "█" * int(v * 40)
    print(f"  {f:20s} {bar} {v:.3f}")
