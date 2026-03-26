# Praxis — Patientendaten-App

Schnelle Erfassung und Analyse von Patientenkonsultationen.

## Projektstruktur

```
praxis-app/
├── main.py              # FastAPI Backend + API
├── requirements.txt     # Python-Abhängigkeiten
├── Procfile             # Startbefehl
├── railway.toml         # Deployment-Konfiguration
└── static/
    └── index.html       # Frontend (Single Page App)
```

---

## Lokaler Start (zum Testen)

**Voraussetzung:** Python 3.10+ installiert.

```bash
# 1. In den Projektordner wechseln
cd praxis-app

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. App starten
uvicorn main:app --reload

# 4. Browser öffnen
# → http://localhost:8000
```

---

## Deployment auf Railway (online, kostenlos)

### Einmalig einrichten

**1. GitHub-Konto erstellen** (falls noch keins): https://github.com

**2. Neues Repository anlegen:**
- Auf github.com → "New repository"
- Name z.B. `praxis-app`
- "Create repository"

**3. Projektdateien hochladen:**
```bash
cd praxis-app
git init
git add .
git commit -m "erste version"
git remote add origin https://github.com/DEIN-NAME/praxis-app.git
git push -u origin main
```

**4. Railway-Konto erstellen:** https://railway.app  
→ "Login with GitHub"

**5. Neues Projekt auf Railway:**
- "New Project" → "Deploy from GitHub repo"
- Dein Repository auswählen
- Railway erkennt `requirements.txt` und `Procfile` automatisch
- Nach ~1 Minute: App läuft unter einer URL wie `praxis-app-xyz.up.railway.app`

**6. Domain einrichten (optional):**
- Im Railway-Dashboard: Settings → Networking → Custom Domain
- Eigene Domain wie `praxis.meinename.de` eintragen

---

## Updates einspielen

```bash
git add .
git commit -m "änderungen"
git push
```
Railway deployed automatisch bei jedem Push.

---

## Datenbank

Die App verwendet **SQLite** — eine einfache Datei (`praxis.db`) ohne separaten Datenbankserver.

- Auf Railway wird die Datei im Container gespeichert.
- **Wichtig:** Bei Railway Free-Tier wird der Container gelegentlich neu gestartet, wobei die DB-Datei verloren gehen kann. Für dauerhafte Datenspeicherung empfiehlt sich ein Railway-Volume oder ein regelmäßiger CSV-Export.

### Volume auf Railway einrichten (empfohlen):
1. Railway Dashboard → dein Service → "Add Volume"
2. Mount Path: `/data`
3. In `railway.toml` Umgebungsvariable setzen: `DB_PATH=/data/praxis.db`

---

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| GET | `/api/konsultationen` | Alle Einträge |
| POST | `/api/konsultationen` | Neuer Eintrag |
| DELETE | `/api/konsultationen/{id}` | Eintrag löschen |
| GET | `/api/stats` | Auswertungsdaten |
| GET | `/api/export/csv` | CSV-Download |

API-Dokumentation (automatisch): `https://DEINE-URL/docs`
