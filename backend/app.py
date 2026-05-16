"""
NAJAH-AI Platform — Backend API v4
Projets 8 (Engagement) + 9 (Ethique & Consentements)
Base de donnees : SQLite
"""
import os, sys, json, hashlib, sqlite3, csv, io
import jwt as pyjwt
from datetime import datetime
from functools import wraps
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, session, send_from_directory, make_response
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_engine as ml

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.join(BASE_DIR, "..")
DATA_DIR     = os.path.join(ROOT_DIR, "data")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
DB_PATH      = os.path.join(DATA_DIR, "najah.db")

app = Flask(__name__)
app.secret_key = "NAJAH_AI2S_SECRET_2025"
JWT_SECRET = "NAJAH_JWT_2025_AI2S_UCA"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
CORS(app, supports_credentials=True,
     origins=["http://localhost:5000","http://127.0.0.1:5000"])

SALT = "NAJAH2025"
def hp(p): return hashlib.sha256(f"{SALT}{p}".encode()).hexdigest()[:16]


def get_current_user():
    """Vérifie le token JWT depuis le header Authorization ou la session Flask."""
    # Try JWT from Authorization header
    auth = request.headers.get("Authorization","")
    if auth.startswith("Bearer "):
        try:
            payload = pyjwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
            return payload
        except Exception:
            pass
    # Fallback to Flask session
    email = session.get("email")
    if email:
        return {"email": email, "user_id": session.get("user_id"), "role": session.get("role")}
    return None

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def qone(sql, params=()):
    with get_db() as conn:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None

def qall(sql, params=()):
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def qexec(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid

def audit(actor, action, resource, status, detail=None):
    try:
        qexec("INSERT INTO audit_log (actor,action,resource,status,detail) VALUES (?,?,?,?,?)",
              (actor, action, resource, status, json.dumps(detail or {})))
    except Exception:
        pass

def require_auth(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            if role and user.get("role") != role:
                return jsonify({"error": "Insufficient permissions"}), 403
            # Sync session for audit logging
            session["email"]   = user.get("email")
            session["user_id"] = user.get("user_id")
            session["role"]    = user.get("role")
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Static files
@app.route("/")
def root():
    return send_from_directory(os.path.join(FRONTEND_DIR,"pages"), "login.html")

@app.route("/<path:filename>")
def static_files(filename):
    pages = os.path.join(FRONTEND_DIR,"pages")
    if os.path.isfile(os.path.join(pages, filename)):
        return send_from_directory(pages, filename)
    if os.path.isfile(os.path.join(FRONTEND_DIR, filename)):
        return send_from_directory(FRONTEND_DIR, filename)
    return "Not found", 404

# AUTH
@app.route("/api/auth/login", methods=["POST"])
def login():
    data  = request.get_json() or {}
    email = data.get("email","").strip().lower()
    pwd   = data.get("password","").strip()
    if not email or not pwd:
        return jsonify({"error": "Champs requis"}), 400
    user = qone("SELECT * FROM users WHERE email=?", (email,))
    if not user:
        audit(email,"LOGIN","auth","denied"); return jsonify({"error":"Identifiants invalides"}), 401
    if pwd != user.get("raw_password","") and hp(pwd) != user.get("password",""):
        audit(email,"LOGIN","auth","denied"); return jsonify({"error":"Identifiants invalides"}), 401
    session["email"]   = email
    session["user_id"] = user["user_id"]
    session["role"]    = user["role"]
    # JWT token for reliable cross-request auth
    token = pyjwt.encode({
        "email": email, "user_id": user["user_id"], "role": user["role"],
        "prenom": user["prenom"], "nom": user["nom"]
    }, JWT_SECRET, algorithm="HS256")
    audit(email,"LOGIN","auth","success",{"role":user["role"]})
    return jsonify({"success":True,"user_id":user["user_id"],"role":user["role"],
                    "prenom":user["prenom"],"nom":user["nom"],"email":email,"token":token})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    audit(session.get("email","anon"),"LOGOUT","auth","success")
    session.clear(); return jsonify({"success":True})

@app.route("/api/auth/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user: return jsonify({"authenticated":False}), 401
    email = user.get("email")
    u = qone("SELECT * FROM users WHERE email=?", (email,))
    if not u: return jsonify({"authenticated":False}), 401
    return jsonify({"authenticated":True,"email":email,
                    "user_id":u["user_id"],"role":u["role"],
                    "prenom":u["prenom"],"nom":u["nom"],
                    "filiere":u.get("filiere",""),"annee":u.get("annee",""),
                    "specialite":u.get("specialite",""),"bureau":u.get("bureau","")})

# DASHBOARDS
@app.route("/api/dashboard/prof", methods=["GET"])
@require_auth("professeur")
def dashboard_prof():
    last_week = qone("SELECT MAX(week) as w FROM engagement")["w"] or 1
    stats = qone("""SELECT COUNT(DISTINCT student_id) as total,
        SUM(CASE WHEN engagement_label='Engage' THEN 1 ELSE 0 END) as engages,
        SUM(CASE WHEN engagement_label='Modere' THEN 1 ELSE 0 END) as moderes,
        SUM(CASE WHEN engagement_label='A risque' THEN 1 ELSE 0 END) as a_risque,
        ROUND(AVG(engagement_score),1) as score_moyen, SUM(anomaly) as anomalies
        FROM engagement WHERE week=?""", (last_week,))
    # Re-query with proper labels
    stats2 = qone("""SELECT COUNT(DISTINCT student_id) as total,
        SUM(CASE WHEN engagement_label='Engage' THEN 1 ELSE 0 END) as engages,
        ROUND(AVG(engagement_score),1) as score_moyen, SUM(anomaly) as anomalies
        FROM engagement WHERE week=?""", (last_week,))
    distrib = qall("""SELECT engagement_label, COUNT(*) as cnt FROM engagement
        WHERE week=? GROUP BY engagement_label""", (last_week,))
    d = {r["engagement_label"]:r["cnt"] for r in distrib}
    alerts = qone("""SELECT COUNT(*) as total,
        SUM(CASE WHEN severity='critique' THEN 1 ELSE 0 END) as critiques,
        SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) as non_resolues FROM alerts""")
    eth = qone("SELECT COUNT(*) as total, SUM(given) as actifs FROM consents")
    evo = qall("""SELECT week, ROUND(AVG(engagement_score),1) as score_moyen,
        SUM(CASE WHEN engagement_label='Engage' THEN 1 ELSE 0 END) as engages,
        SUM(CASE WHEN engagement_label='Modere' THEN 1 ELSE 0 END) as moderes,
        SUM(CASE WHEN engagement_label='A risque' THEN 1 ELSE 0 END) as a_risque
        FROM engagement GROUP BY week ORDER BY week""")
    # fix encoded labels
    label_fix = lambda s: s.replace("Engage","Engagé").replace("Modere","Modéré").replace("A risque","À risque") if s else s
    for row in evo:
        row["engages"]  = row.get("engages",0)
        row["moderes"]  = row.get("moderes",0)
        row["a_risque"] = row.get("a_risque",0)
    audit(session["email"],"READ","dashboard_prof","success")
    return jsonify({
        "engagement":{"total":stats2["total"],"semaine":last_week,
                      "engages":d.get("Engagé",0),"moderes":d.get("Modéré",0),
                      "a_risque":d.get("À risque",0),
                      "score_moyen":stats2["score_moyen"],"anomalies":stats2["anomalies"]},
        "alertes":  alerts,
        "ethique":  {"total":eth["total"],"actifs":eth["actifs"],
                     "taux":round(eth["actifs"]/eth["total"]*100,1) if eth["total"] else 0},
        "evolution":evo
    })

@app.route("/api/dashboard/etudiant", methods=["GET"])
@require_auth("etudiant")
def dashboard_etudiant():
    sid = session["user_id"]
    last_week = qone("SELECT MAX(week) as w FROM engagement WHERE student_id=?", (sid,))
    if not last_week: return jsonify({"error":"No data"}), 404
    lw = last_week["w"]
    row = qone("SELECT * FROM engagement WHERE student_id=? AND week=?", (sid, lw))
    if not row: return jsonify({"error":"No data"}), 404
    evo = qall("SELECT week, engagement_score as score, time_spent_min as time, interactions FROM engagement WHERE student_id=? ORDER BY week", (sid,))
    audit(session["email"],"READ","dashboard_etudiant","success")
    # Normalize field names for frontend consistency
    normalized = {
        "score_actuel":   row.get("engagement_score"),
        "label":          row.get("engagement_label"),
        "week":           row.get("week"),
        "time_spent":     row.get("time_spent_min"),
        "interactions":   row.get("interactions"),
        "quiz_score":     row.get("quiz_score"),
        "submissions":    row.get("submissions"),
        "logins":         row.get("logins"),
        "anomaly":        bool(row.get("anomaly", 0)),
        "evolution":      evo
    }
    return jsonify(normalized)

# ETUDIANTS
@app.route("/api/students", methods=["GET"])
@require_auth("professeur")
def get_students():
    lw  = qone("SELECT MAX(week) as w FROM engagement")["w"] or 1
    q   = request.args.get("q","").lower()
    fil = request.args.get("filiere","")
    lbl = request.args.get("label","")
    sql = """SELECT u.user_id, u.prenom, u.nom, u.email, u.filiere, u.annee,
             e.engagement_score as score, e.engagement_label as label, e.anomaly,
             (SELECT COUNT(*) FROM consents c WHERE c.student_id=u.user_id AND c.given=1) as consent_count
             FROM users u JOIN engagement e ON e.student_id=u.user_id AND e.week=?
             WHERE u.role='etudiant'"""
    params = [lw]
    if fil: sql += " AND u.filiere=?"; params.append(fil)
    if lbl: sql += " AND e.engagement_label=?"; params.append(lbl)
    sql += " ORDER BY e.engagement_score ASC"
    rows = qall(sql, params)
    if q: rows = [r for r in rows if q in (r["prenom"]+r["nom"]+r["email"]).lower()]
    for r in rows:
        r["consent"] = r["consent_count"] > 0
        r["student_id"] = r["user_id"]  # alias for frontend
    audit(session["email"],"READ","students_list","success")
    return jsonify(rows)

@app.route("/api/student/<sid>", methods=["GET"])
@require_auth()
def get_student(sid):
    if session.get("role")=="etudiant" and session.get("user_id")!=sid:
        return jsonify({"error":"Forbidden"}), 403
    u = qone("SELECT * FROM users WHERE user_id=?", (sid,))
    if not u: return jsonify({"error":"Not found"}), 404
    evo_raw = qall("SELECT * FROM engagement WHERE student_id=? ORDER BY week", (sid,))
    evo = [{
        "week":         r["week"],
        "score":        r["engagement_score"],
        "label":        r["engagement_label"],
        "time":         r["time_spent_min"],
        "interactions": r["interactions"],
        "quiz":         r["quiz_score"],
        "submissions":  r["submissions"],
        "logins":       r["logins"],
        "anomaly":      bool(r["anomaly"]),
    } for r in evo_raw]
    cons = qall("SELECT consent_type, given, date, withdrawn_at FROM consents WHERE student_id=?", (sid,))
    last = evo_raw[-1] if evo_raw else {}
    consents_dict = {r["consent_type"]:{"given":bool(r["given"]),"date":r["date"],"withdrawn_at":r["withdrawn_at"]} for r in cons}
    # Recommandations
    recs = []
    if last:
        score = last.get("engagement_score", 100)
        if score < 38:
            recs.append({"niveau":"urgent","texte":"Organiser un entretien pédagogique individuel."})
            recs.append({"niveau":"urgent","texte":"Proposer des sessions de tutorat personnalisé."})
        if last.get("time_spent_min",60) < 30:
            recs.append({"niveau":"moyen","texte":"Encourager une connexion régulière (objectif : 45 min/semaine)."})
        if last.get("interactions",5) < 5:
            recs.append({"niveau":"moyen","texte":"Stimuler la participation via quiz interactifs et forums."})
        if last.get("quiz_score",70) < 50:
            recs.append({"niveau":"moyen","texte":"Proposer des exercices de révision adaptés au niveau."})
        if last.get("submissions",1) == 0:
            recs.append({"niveau":"urgent","texte":"Vérifier l'accès aux devoirs — aucun travail remis."})
        if score >= 68 and last.get("quiz_score",0) >= 70:
            recs.append({"niveau":"ok","texte":"Engagement excellent. Proposer des ressources avancées."})
        if not recs:
            recs.append({"niveau":"ok","texte":"Engagement satisfaisant. Maintenir le rythme actuel."})
    safe_u = {k:v for k,v in u.items() if k not in ["password","raw_password"]}
    audit(session["email"],"READ",f"student/{sid}","success")
    return jsonify({**safe_u,"score_actuel":last.get("engagement_score"),
                    "label":last.get("engagement_label"),"anomaly":bool(last.get("anomaly",0)),
                    "consents":consents_dict,"evolution":evo,"recommandations":recs})

# ALERTES
@app.route("/api/alerts", methods=["GET"])
@require_auth("professeur")
def get_alerts():
    sev = request.args.get("severity","")
    res = request.args.get("resolved","")
    sql = "SELECT a.*, u.prenom, u.nom, u.email FROM alerts a LEFT JOIN users u ON u.user_id=a.student_id WHERE 1=1"
    params = []
    if sev: sql += " AND a.severity=?"; params.append(sev)
    if res != "": sql += " AND a.resolved=?"; params.append(int(res))
    sql += " ORDER BY a.created_at DESC LIMIT 200"
    rows = qall(sql, params)
    audit(session["email"],"READ","alerts","success")
    return jsonify(rows)

@app.route("/api/alerts/<alert_id>/resolve", methods=["POST"])
@require_auth("professeur")
def resolve_alert(alert_id):
    qexec("UPDATE alerts SET resolved=1, resolved_at=datetime('now'), resolved_by=? WHERE alert_id=?",
          (session["email"], alert_id))
    audit(session["email"],"UPDATE",f"alert/{alert_id}","resolved")
    return jsonify({"success":True})

# CONSENTEMENTS
@app.route("/api/consent/<sid>", methods=["GET"])
@require_auth()
def get_consent(sid):
    if session.get("role")=="etudiant" and session.get("user_id")!=sid:
        return jsonify({"error":"Forbidden"}), 403
    rows = qall("SELECT consent_type, given, date, withdrawn_at FROM consents WHERE student_id=?", (sid,))
    result = {r["consent_type"]:{"given":bool(r["given"]),"date":r["date"],"withdrawn_at":r["withdrawn_at"]} for r in rows}
    audit(session["email"],"READ",f"consent/{sid}","success")
    return jsonify(result)

@app.route("/api/consent/<sid>", methods=["POST"])
@require_auth()
def update_consent(sid):
    if session.get("role")=="etudiant" and session.get("user_id")!=sid:
        return jsonify({"error":"Forbidden"}), 403
    data = request.get_json() or {}
    ctype = data.get("type"); given = data.get("given")
    if not ctype or given is None: return jsonify({"error":"type and given required"}), 400
    now = datetime.now().strftime("%Y-%m-%d")
    qexec("""INSERT INTO consents (student_id,consent_type,given,date,withdrawn_at) VALUES (?,?,?,?,?)
             ON CONFLICT(student_id,consent_type) DO UPDATE SET given=excluded.given,
             date=excluded.date, withdrawn_at=excluded.withdrawn_at""",
          (sid, ctype, int(given), now, None if given else now))
    audit(session["email"],"CONSENT_GIVEN" if given else "CONSENT_WITHDRAWN",f"consent/{sid}/{ctype}","success")
    return jsonify({"success":True})

@app.route("/api/consents", methods=["GET"])
@require_auth("professeur")
def list_consents():
    rows = qall("""SELECT u.user_id as student_id, u.prenom, u.nom, u.email,
        c.consent_type, c.given, c.date, c.withdrawn_at
        FROM users u LEFT JOIN consents c ON c.student_id=u.user_id
        WHERE u.role='etudiant' ORDER BY u.nom, u.prenom""")
    grouped = {}
    for r in rows:
        sid = r["student_id"]
        if sid not in grouped:
            grouped[sid] = {"student_id":sid,"prenom":r["prenom"],"nom":r["nom"],"email":r["email"],"consents":{}}
        if r["consent_type"]:
            grouped[sid]["consents"][r["consent_type"]] = {"given":bool(r["given"]),"date":r["date"],"withdrawn_at":r["withdrawn_at"]}
    result = list(grouped.values())
    for s in result:
        vals = list(s["consents"].values())
        s["all_given"] = all(v["given"] for v in vals) if vals else False
        s["any_given"] = any(v["given"] for v in vals) if vals else False
    audit(session["email"],"READ","consents_list","success")
    return jsonify(result)

# RGPD
@app.route("/api/student/<sid>/delete", methods=["DELETE"])
@require_auth("professeur")
def delete_student_data(sid):
    user = qone("SELECT * FROM users WHERE user_id=? AND role='etudiant'", (sid,))
    if not user: return jsonify({"error":"Etudiant introuvable"}), 404
    with get_db() as conn:
        conn.execute("DELETE FROM engagement WHERE student_id=?", (sid,))
        conn.execute("DELETE FROM alerts WHERE student_id=?", (sid,))
        conn.execute("DELETE FROM consents WHERE student_id=?", (sid,))
        conn.execute("DELETE FROM users WHERE user_id=?", (sid,))
        conn.commit()
    audit(session["email"],"DELETE",f"student/{sid}","success",{"email":user["email"]})
    return jsonify({"success":True,"message":f"Donnees de {user['prenom']} {user['nom']} supprimees (RGPD Art.17)."})

@app.route("/api/student/<sid>/export", methods=["GET"])
@require_auth()
def export_student_data(sid):
    if session.get("role")=="etudiant" and session.get("user_id")!=sid:
        return jsonify({"error":"Forbidden"}), 403
    user = qone("SELECT * FROM users WHERE user_id=?", (sid,))
    if not user: return jsonify({"error":"Not found"}), 404
    eng  = qall("SELECT * FROM engagement WHERE student_id=? ORDER BY week", (sid,))
    cons = qall("SELECT * FROM consents WHERE student_id=?", (sid,))
    data = {"export_date":datetime.now().isoformat(),
            "rgpd":"Article 20 - Droit a la portabilite",
            "profile":{k:v for k,v in user.items() if k not in ["password","raw_password"]},
            "engagement":eng, "consents":cons}
    audit(session["email"],"EXPORT",f"student/{sid}","success")
    resp = make_response(json.dumps(data, ensure_ascii=False, indent=2))
    resp.headers["Content-Type"] = "application/json"
    resp.headers["Content-Disposition"] = f'attachment; filename="donnees_{sid}.json"'
    return resp

@app.route("/api/engagement/export", methods=["GET"])
@require_auth("professeur")
def export_engagement_csv():
    rows = qall("SELECT student_id,week,time_spent_min,interactions,quiz_score,submissions,logins,engagement_score,engagement_label,anomaly FROM engagement ORDER BY student_id,week")
    out = io.StringIO()
    if rows:
        w = csv.DictWriter(out, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=engagement_export.csv"
    audit(session["email"],"EXPORT","engagement_csv","success")
    return resp

# AUDIT
@app.route("/api/audit", methods=["GET"])
@require_auth("professeur")
def get_audit():
    rows = qall("SELECT * FROM audit_log ORDER BY ts DESC LIMIT 300")
    return jsonify(rows)

# COURSES
@app.route("/api/courses", methods=["GET"])
@require_auth()
def get_courses():
    if session.get("role")=="etudiant":
        u = qone("SELECT filiere FROM users WHERE user_id=?", (session["user_id"],))
        rows = qall("SELECT * FROM courses WHERE filiere=?", (u["filiere"],)) if u else []
    else:
        rows = qall("SELECT * FROM courses")
    return jsonify(rows)

# ML
@app.route("/api/ml/status", methods=["GET"])
@require_auth()
def ml_status():
    ready = ml.models_ready()
    return jsonify({"ready":ready,"meta":ml.get_meta() if ready else {}})

@app.route("/api/ml/predict", methods=["POST"])
@require_auth()
def ml_predict():
    data = request.get_json() or {}
    result = ml.predict_single(data)
    if "error" in result: return jsonify(result), 503
    audit(session["email"],"ML_PREDICT","predict","success")
    return jsonify(result)

@app.route("/api/ml/predict/student/<sid>", methods=["GET"])
@require_auth()
def ml_predict_student(sid):
    if session.get("role")=="etudiant" and session.get("user_id")!=sid:
        return jsonify({"error":"Forbidden"}), 403
    rows = qall("SELECT * FROM engagement WHERE student_id=? ORDER BY week DESC LIMIT 3", (sid,))
    if not rows: return jsonify({"error":"No data"}), 404
    features = {
        "time_spent_min": float(np.mean([r["time_spent_min"] for r in rows])),
        "interactions":   float(np.mean([r["interactions"] for r in rows])),
        "quiz_score":     float(np.mean([r["quiz_score"] for r in rows])),
        "submissions":    float(np.mean([r["submissions"] for r in rows])),
        "logins":         float(np.mean([r["logins"] for r in rows])),
        "week":           float(rows[0]["week"]),
    }
    result = ml.predict_single(features)
    if "error" in result: return jsonify(result), 503
    result["student_id"] = sid; result["features_used"] = features
    audit(session["email"],"ML_PREDICT",f"student/{sid}","success")
    return jsonify(result)

@app.route("/api/ml/scan", methods=["POST"])
@require_auth("professeur")
def ml_scan_all():
    lw = qone("SELECT MAX(week) as w FROM engagement")["w"] or 1
    rows = qall("SELECT * FROM engagement WHERE week=?", (lw,))
    if not rows: return jsonify({"error":"Pas de donnees"}), 404
    predictions = ml.predict_batch(rows)
    if not predictions: return jsonify({"error":"Modeles non disponibles"}), 503
    with get_db() as conn:
        for p in predictions:
            conn.execute("UPDATE engagement SET engagement_score=?,engagement_label=?,anomaly=? WHERE student_id=? AND week=?",
                         (p["score"],p["label"],int(p["anomaly"]),p["student_id"],lw))
        conn.commit()
    auto = ml.generate_alerts_from_predictions(predictions)
    last_n = qone("SELECT COUNT(*) as n FROM alerts")["n"]
    for i, a in enumerate(auto):
        try:
            qexec("INSERT INTO alerts (alert_id,student_id,week,score,severity,message) VALUES (?,?,?,?,?,?)",
                  (f"ALT{last_n+i+1:04d}",a["student_id"],lw,a["score"],a["severity"],
                   a["message"]+f" (confiance {int(a['confidence']*100)}%)"))
        except Exception:
            pass
    dist = {}
    for p in predictions: dist[p["label"]] = dist.get(p["label"],0)+1
    sev = {"critique":0,"elevee":0,"normale":0}
    for a in auto: sev[a["severity"]] = sev.get(a["severity"],0)+1
    sev["ok"] = len(predictions)-len(auto)
    audit(session["email"],"ML_SCAN","scan_all","success",{"week":lw,"alerts":len(auto)})
    return jsonify({"week_analysed":lw,"students_scanned":len(predictions),
                    "alerts_generated":len(auto),"distribution":dist,
                    "severity_summary":sev,"predictions":predictions[:10],
                    "model_meta":ml.get_meta()})

@app.route("/api/ml/metrics", methods=["GET"])
@require_auth("professeur")
def ml_metrics():
    df   = pd.read_sql("SELECT * FROM engagement", get_db())
    last = df[df["week"]==df["week"].max()]
    cols = ["time_spent_min","interactions","quiz_score","submissions","logins"]
    corr = {c:round(float(df[c].corr(df["engagement_score"])),3) for c in cols if c in df}
    trend = {int(k):float(v) for k,v in df.groupby("week")["engagement_score"].mean().round(1).to_dict().items()}
    dist  = last["engagement_label"].value_counts().to_dict()
    return jsonify({"model_meta":ml.get_meta(),"correlations":corr,
                    "weekly_trend":trend,"current_distribution":dist,
                    "total_records":len(df),"students":int(df["student_id"].nunique()),
                    "weeks":int(df["week"].max())})

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","platform":"NAJAH-AI","version":"4.0","db":"sqlite"})

if __name__ == "__main__":
    os.chdir(ROOT_DIR)
    if not os.path.exists(DB_PATH):
        print("Base manquante — lancez : python backend/init_db.py")
    print("NAJAH-AI Platform v4 -> http://localhost:5000")
    app.run(debug=True, port=5000)
