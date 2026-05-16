# NAJAH-AI Platform v3
**Projets 8 & 9 combinés — Engagement étudiant + Éthique & Consentements**
Unité AI2S · UCA / HEEC · ENSA Marrakech

---

## Démarrage rapide

### 1. Prérequis
- Python 3.9+
- pip

### 2. Installation des dépendances
```bash
pip install flask flask-cors pandas
```

### 3. Lancement
```bash
cd najah_v3
python backend/app.py
```

Ouvrir : **http://localhost:5000**

## Démo
---
<img width="400" height="202" alt="Plateforme_Najah_v6 (1)" src="https://github.com/user-attachments/assets/f18e3734-ae3f-4c97-baa5-aa6f01701e2a" />

---

---
## Comptes de démonstration

| Rôle        | Email                          | Mot de passe |
|-------------|-------------------------------|--------------|
| Professeur  | zineb.achbarou@uca.ma         | prof12025    |
| Professeur  | fatima.berrada@uca.ma         | prof22025    |
| Professeur  | nadia.senhaji@uca.ma          | prof32025    |
| Étudiant    | karim.ouali1@etu.uca.ma       | stu12025     |
| Étudiant    | amine.ouali2@etu.uca.ma       | stu22025     |
| Étudiant    | nour.mekouar3@etu.uca.ma      | stu32025     |

---

## Pages disponibles

### Rôle Professeur
| Page                  | URL                          | Description                        |
|-----------------------|------------------------------|------------------------------------|
| Tableau de bord       | /dashboard_prof.html         | KPIs, graphiques, alertes          |
| Étudiants             | /etudiants.html              | Liste avec scores et filtres       |
| Détail étudiant       | /etudiant_detail.html?id=... | Profil complet + évolution         |
| Alertes               | /alertes.html                | Gestion des alertes d'engagement   |
| Consentements         | /consentements.html          | Vue globale des consentements      |
| Journal d'audit       | /audit.html                  | Traçabilité des accès              |
| Mon profil            | /profil.html                 | Informations du compte             |

### Rôle Étudiant
| Page                  | URL                          | Description                        |
|-----------------------|------------------------------|------------------------------------|
| Tableau de bord       | /dashboard_etu.html          | Score, évolution, consentements    |
| Mon engagement        | /mon_engagement.html         | Historique détaillé 12 semaines    |
| Mes consentements     | /mes_consentements.html      | Gestion RGPD personnelle           |
| Mon profil            | /profil.html                 | Informations du compte             |

---

## Architecture

```
najah_v3/
├── backend/
│   └── app.py              Flask API (auth, engagement, consentements, audit)
├── frontend/
│   ├── assets/
│   │   ├── css/main.css    Design system pastel
│   │   └── js/app.js       Utilitaires partagés, sidebar, icônes
│   └── pages/              Toutes les pages HTML
├── data/
│   ├── users_db.json       63 utilisateurs (3 profs + 60 étudiants)
│   ├── engagement.csv      720 lignes (60 étudiants × 12 semaines)
│   ├── alerts.csv          Alertes générées automatiquement
│   ├── consents.json       Consentements par étudiant
│   ├── courses.csv         6 cours
│   └── audit_log.jsonl     Journal d'audit
└── requirements.txt
```

---

## API Endpoints

| Méthode | Endpoint                      | Auth     | Description                     |
|---------|-------------------------------|----------|---------------------------------|
| POST    | /api/auth/login               | —        | Connexion                       |
| POST    | /api/auth/logout              | Oui      | Déconnexion                     |
| GET     | /api/auth/me                  | Oui      | Utilisateur courant             |
| GET     | /api/dashboard/prof           | Prof     | Stats tableau de bord prof      |
| GET     | /api/dashboard/etudiant       | Étudiant | Stats tableau de bord étudiant  |
| GET     | /api/students                 | Prof     | Liste étudiants filtrée         |
| GET     | /api/student/:id              | Oui      | Profil complet d'un étudiant    |
| GET     | /api/alerts                   | Prof     | Liste alertes                   |
| POST    | /api/alerts/:id/resolve       | Prof     | Résoudre une alerte             |
| GET     | /api/consent/:sid             | Oui      | Consentements d'un étudiant     |
| POST    | /api/consent/:sid             | Oui      | Mettre à jour un consentement   |
| GET     | /api/consents                 | Prof     | Tous les consentements          |
| GET     | /api/audit                    | Prof     | Journal d'audit                 |
| GET     | /api/courses                  | Oui      | Liste des cours                 |
