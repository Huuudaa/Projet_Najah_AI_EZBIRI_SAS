"""
NAJAH-AI — Initialisation base de données SQLite
Lance : python backend/init_db.py
"""
import os, json, csv, hashlib, sqlite3
from datetime import datetime, timedelta
import random

BASE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.join(BASE, "..")
DATA  = os.path.join(ROOT, "data")
DB    = os.path.join(DATA, "najah.db")

random.seed(42)
SALT = "NAJAH2025"
def hp(p): return hashlib.sha256(f"{SALT}{p}".encode()).hexdigest()[:16]

def init_db():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE users (
        user_id     TEXT PRIMARY KEY,
        prenom      TEXT NOT NULL,
        nom         TEXT NOT NULL,
        email       TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        raw_password TEXT,
        role        TEXT NOT NULL CHECK(role IN ('professeur','etudiant')),
        filiere     TEXT,
        annee       INTEGER,
        specialite  TEXT,
        bureau      TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE engagement (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id  TEXT NOT NULL,
        week        INTEGER NOT NULL,
        time_spent_min  INTEGER DEFAULT 0,
        interactions    INTEGER DEFAULT 0,
        quiz_score      REAL DEFAULT 0,
        submissions     INTEGER DEFAULT 0,
        logins          INTEGER DEFAULT 0,
        engagement_score REAL DEFAULT 0,
        engagement_label TEXT DEFAULT 'Modéré',
        anomaly     INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(student_id) REFERENCES users(user_id),
        UNIQUE(student_id, week)
    );

    CREATE TABLE alerts (
        alert_id    TEXT PRIMARY KEY,
        student_id  TEXT NOT NULL,
        week        INTEGER NOT NULL,
        score       REAL,
        severity    TEXT CHECK(severity IN ('critique','elevee','normale')),
        message     TEXT,
        created_at  TEXT DEFAULT (datetime('now')),
        resolved    INTEGER DEFAULT 0,
        resolved_at TEXT,
        resolved_by TEXT,
        FOREIGN KEY(student_id) REFERENCES users(user_id)
    );

    CREATE TABLE consents (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id   TEXT NOT NULL,
        consent_type TEXT NOT NULL,
        given        INTEGER DEFAULT 0,
        date         TEXT,
        withdrawn_at TEXT,
        FOREIGN KEY(student_id) REFERENCES users(user_id),
        UNIQUE(student_id, consent_type)
    );

    CREATE TABLE audit_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts        TEXT DEFAULT (datetime('now')),
        actor     TEXT,
        action    TEXT,
        resource  TEXT,
        status    TEXT,
        detail    TEXT
    );

    CREATE TABLE courses (
        course_id TEXT PRIMARY KEY,
        title     TEXT NOT NULL,
        prof_id   TEXT,
        filiere   TEXT,
        credits   INTEGER
    );

    CREATE INDEX idx_eng_student ON engagement(student_id);
    CREATE INDEX idx_eng_week    ON engagement(week);
    CREATE INDEX idx_alerts_stu  ON alerts(student_id);
    CREATE INDEX idx_audit_ts    ON audit_log(ts);
    CREATE INDEX idx_cons_stu    ON consents(student_id);
    """)

    # ── Utilisateurs ─────────────────────────────────────────
    profs = [
        ("PROF001","Zineb","Achbarou","zineb.achbarou@uca.ma","prof12025","Informatique",None,"B201"),
        ("PROF002","Fatima","Berrada","fatima.berrada@uca.ma","prof22025","IA & Data",None,"B202"),
        ("PROF003","Nadia","Senhaji","nadia.senhaji@uca.ma","prof32025","Génie Logiciel",None,"B203"),
    ]
    for uid,pr,no,em,pwd,sp,_,bu in profs:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                  (uid,pr,no,em,hp(pwd),pwd,"professeur",sp,None,sp,bu))

    fnames = ["Karim","Amine","Nour","Sara","Youssef","Leila","Omar","Hind","Mehdi","Rania",
              "Tarik","Samira","Adil","Loubna","Hamza","Zineb","Khalid","Imane","Sami","Douae"]
    lnames = ["Ouali","Mekouar","Benbrahim","Tazi","Idrissi","Hajji","Ziani","Benali","Fassi","Rochdi"]
    filieres = ["Informatique","IA & Data","Génie Logiciel"]
    students = []
    for i in range(60):
        fn = fnames[i % len(fnames)]
        ln = lnames[i % len(lnames)]
        uid = f"ETU{i+1:03d}"
        em = f"{fn.lower()}.{ln.lower()}{i+1}@etu.uca.ma"
        pwd = f"stu{i+1}2025"
        fil = filieres[i % 3]
        ann = random.choice([3,4,5])
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                  (uid,fn,ln,em,hp(pwd),pwd,"etudiant",fil,ann,None,None))
        students.append({"user_id":uid,"prenom":fn,"nom":ln,"email":em,"filiere":fil,"annee":ann})

    # ── Engagement ───────────────────────────────────────────
    eng_rows = []
    for s in students:
        base = random.uniform(30, 85)
        for week in range(1, 13):
            score = max(0, min(100, base + random.uniform(-8,8) + week*random.uniform(-1,1.5)))
            ts = int(random.uniform(20, 180))
            inter = random.randint(0, 30)
            quiz = random.uniform(30, 100)
            subs = random.randint(0, 5)
            logins = random.randint(1, 14)
            anom = 1 if score < 25 or (ts < 20 and inter < 3) else 0
            lbl = "Engagé" if score >= 68 else ("Modéré" if score >= 38 else "À risque")
            eng_rows.append((s["user_id"], week, ts, inter, round(quiz,1), subs, logins,
                             round(score,1), lbl, anom))
    c.executemany("""INSERT INTO engagement
        (student_id,week,time_spent_min,interactions,quiz_score,submissions,logins,
         engagement_score,engagement_label,anomaly)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", eng_rows)

    # ── Alertes ──────────────────────────────────────────────
    alert_id = 1
    for sid, week, *_, score, lbl, anom in eng_rows:
        score_val = score
        if score_val < 25 or (anom and score_val < 35):
            sev = "critique"
            msg = "Score critique — intervention urgente recommandée"
        elif score_val < 38:
            sev = "elevee"
            msg = "Engagement faible — suivi pédagogique conseillé"
        else:
            continue
        resolved = random.choice([0,0,1])
        resolved_at = (datetime(2025,9,1)+timedelta(weeks=week+1)).strftime("%Y-%m-%d") if resolved else None
        c.execute("INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (f"ALT{alert_id:04d}", sid, week, score_val, sev, msg,
                   (datetime(2025,9,1)+timedelta(weeks=week)).strftime("%Y-%m-%d"),
                   resolved, resolved_at, "zineb.achbarou@uca.ma" if resolved else None))
        alert_id += 1

    # ── Consentements ─────────────────────────────────────────
    types = ["analytics","personalization","data_sharing"]
    for s in students:
        for ct in types:
            given = 1 if random.random() > 0.15 else 0
            date  = (datetime(2025,9,1)+timedelta(days=random.randint(0,30))).strftime("%Y-%m-%d")
            wdate = (datetime(2025,10,1)+timedelta(days=random.randint(0,30))).strftime("%Y-%m-%d") if not given else None
            c.execute("INSERT INTO consents (student_id,consent_type,given,date,withdrawn_at) VALUES (?,?,?,?,?)",
                      (s["user_id"], ct, given, date, wdate))

    # ── Cours ─────────────────────────────────────────────────
    courses = [
        ("CS101","Introduction à l'IA","PROF001","IA & Data",4),
        ("CS102","Machine Learning","PROF001","IA & Data",5),
        ("CS201","Algorithmique avancée","PROF002","Informatique",4),
        ("CS202","Bases de données","PROF002","Informatique",3),
        ("CS301","Génie logiciel","PROF003","Génie Logiciel",4),
        ("CS302","Architecture web","PROF003","Génie Logiciel",3),
    ]
    c.executemany("INSERT INTO courses VALUES (?,?,?,?,?)", courses)

    # ── Audit initial ─────────────────────────────────────────
    c.execute("INSERT INTO audit_log (actor,action,resource,status,detail) VALUES (?,?,?,?,?)",
              ("system","INIT","database","success","{}"))

    conn.commit()
    conn.close()

    n_eng = len(eng_rows)
    print(f"Base de données créée : {DB}")
    print(f"  Utilisateurs : {len(profs)+len(students)} (3 profs + {len(students)} étudiants)")
    print(f"  Engagement   : {n_eng} lignes")
    print(f"  Alertes      : {alert_id-1}")
    print(f"  Consentements: {len(students)*len(types)}")

if __name__ == "__main__":
    init_db()
