"""
NAJAH-AI — Module d'inférence ML
Chargé une seule fois au démarrage de Flask.
"""
import os, json
import numpy as np
import joblib

BASE   = os.path.dirname(os.path.abspath(__file__))
MODEL  = os.path.join(BASE, "..", "models")

FEATURES = ["time_spent_min", "interactions", "quiz_score", "submissions", "logins", "week"]

# ── Chargement lazy ───────────────────────────────────────────
_clf = _reg = _iso = _le = None
_meta = {}

def _load():
    global _clf, _reg, _iso, _le, _meta
    if _clf is not None:
        return True
    try:
        _clf  = joblib.load(os.path.join(MODEL, "clf_engagement.pkl"))
        _reg  = joblib.load(os.path.join(MODEL, "reg_score.pkl"))
        _iso  = joblib.load(os.path.join(MODEL, "iso_anomaly.pkl"))
        _le   = joblib.load(os.path.join(MODEL, "label_encoder.pkl"))
        with open(os.path.join(MODEL, "meta.json")) as f:
            _meta = json.load(f)
        return True
    except FileNotFoundError:
        return False

def models_ready():
    return _load()

def get_meta():
    _load()
    return _meta

def predict_single(features: dict) -> dict:
    """
    Prédit pour un seul étudiant.
    features : dict avec les clés de FEATURES
    Retourne : score, label, anomaly, probabilities, confidence
    """
    if not _load():
        return {"error": "Modèles non entraînés. Lancez : python backend/train_models.py"}

    X = np.array([[features.get(f, 0) for f in FEATURES]], dtype=float)

    score     = float(np.clip(_reg.predict(X)[0], 0, 100))
    label_enc = int(_clf.predict(X)[0])
    label     = _le.inverse_transform([label_enc])[0]
    proba     = _clf.predict_proba(X)[0]
    iso_pred  = int(_iso.predict(X)[0])   # -1 = anomalie, 1 = normal
    anomaly   = iso_pred == -1
    iso_score = float(_iso.decision_function(X)[0])  # plus négatif = plus suspect

    proba_dict = {cls: round(float(p), 3) for cls, p in zip(_le.classes_, proba)}
    confidence = round(float(proba.max()), 3)

    return {
        "score":        round(score, 1),
        "label":        label,
        "anomaly":      anomaly,
        "anomaly_score": round(iso_score, 4),
        "probabilities": proba_dict,
        "confidence":    confidence,
    }

def predict_batch(rows: list) -> list:
    """
    rows : liste de dicts avec les clés FEATURES + student_id optionnel
    """
    if not _load():
        return []

    ids  = [r.get("student_id", i) for i, r in enumerate(rows)]
    X    = np.array([[r.get(f, 0) for f in FEATURES] for r in rows], dtype=float)

    scores    = np.clip(_reg.predict(X), 0, 100)
    labels    = _le.inverse_transform(_clf.predict(X))
    probas    = _clf.predict_proba(X)
    iso_preds = _iso.predict(X)
    iso_scores= _iso.decision_function(X)

    results = []
    for i, sid in enumerate(ids):
        proba_dict = {cls: round(float(p), 3) for cls, p in zip(_le.classes_, probas[i])}
        results.append({
            "student_id":    sid,
            "score":         round(float(scores[i]), 1),
            "label":         str(labels[i]),
            "anomaly":       bool(iso_preds[i] == -1),
            "anomaly_score": round(float(iso_scores[i]), 4),
            "probabilities": proba_dict,
            "confidence":    round(float(probas[i].max()), 3),
        })
    return results

def generate_alerts_from_predictions(predictions: list) -> list:
    """
    Génère des alertes automatiques à partir des prédictions.
    Règles :
      - score < 25 OU anomalie forte   → critique
      - score < 38 OU anomalie         → elevee
      - score < 50 ET confidence > 0.6 → normale
    """
    alerts = []
    for p in predictions:
        score     = p.get("score", 100)
        anomaly   = p.get("anomaly", False)
        iso_score = p.get("anomaly_score", 1.0)
        conf      = p.get("confidence", 0)
        sid       = p.get("student_id", "?")

        if score < 25 or (anomaly and iso_score < -0.15):
            severity = "critique"
            msg = "Score critique prédit par le modèle — intervention urgente recommandée"
        elif score < 38 or anomaly:
            severity = "elevee"
            msg = "Engagement faible détecté — suivi pédagogique conseillé"
        elif score < 50 and conf > 0.6:
            severity = "normale"
            msg = "Risque modéré détecté — à surveiller les prochaines semaines"
        else:
            continue  # pas d'alerte

        alerts.append({
            "student_id": sid,
            "severity":   severity,
            "message":    msg,
            "score":      score,
            "confidence": conf,
            "anomaly":    anomaly,
        })
    return alerts
