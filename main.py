from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3, os, json
from datetime import datetime
from contextlib import contextmanager

app = FastAPI(title="Praxis API")
DB_PATH = os.environ.get("DB_PATH", "praxis.db")

VORSORGE = {'U1','U2','U3','U4','U5','U6','U7','U7a','U8','U9','U10','U11','J1','J2'}

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS konsultationen (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                datum            TEXT,
                alter_j          INTEGER DEFAULT 0,
                alter_m          INTEGER DEFAULT 0,
                alter_ges        INTEGER DEFAULT 0,
                dauer            INTEGER,
                grund            TEXT,
                diagnose_akut    TEXT,
                diagnose_dauer   TEXT,
                massnahmen       TEXT,
                begleitperson    TEXT DEFAULT '',
                mh               INTEGER DEFAULT 0,
                notizen          TEXT DEFAULT '',
                eltern_fragen    TEXT,
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        cols = [r[1] for r in db.execute("PRAGMA table_info(konsultationen)").fetchall()]
        migrations = [
            ("diagnose_akut",  "''"),
            ("diagnose_dauer", "''"),
            ("eltern_fragen",  "''"),
        ]
        for col, default in migrations:
            if col not in cols:
                db.execute(f"ALTER TABLE konsultationen ADD COLUMN {col} TEXT DEFAULT {default}")
        if "diagnose" in cols and "diagnose_akut" in cols:
            db.execute("UPDATE konsultationen SET diagnose_akut=diagnose WHERE diagnose_akut='' AND diagnose!=''")
        db.commit()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try: yield conn
    finally: conn.close()

class KonsultationIn(BaseModel):
    datum: Optional[str] = None
    alter_j: Optional[int] = 0
    alter_m: Optional[int] = 0
    alter_ges: Optional[int] = 0
    dauer: Optional[int] = None
    grund: Optional[List[str]] = []
    diagnose_akut: Optional[List[str]] = []
    diagnose_dauer: Optional[List[str]] = []
    massnahmen: Optional[List[str]] = []
    begleitperson: Optional[str] = ""
    mh: Optional[bool] = False
    notizen: Optional[str] = ""
    eltern_fragen: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

@app.get("/api/konsultationen")
def list_konsultationen(q: str = ""):
    with get_db() as db:
        if q:
            rows = db.execute(
                """SELECT * FROM konsultationen WHERE
                   grund LIKE ? OR diagnose_akut LIKE ? OR diagnose_dauer LIKE ?
                   OR notizen LIKE ? OR begleitperson LIKE ? OR eltern_fragen LIKE ?
                   ORDER BY id DESC""",
                tuple([f"%{q}%"] * 6)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM konsultationen ORDER BY id DESC").fetchall()
    return [_row_to_dict(r) for r in rows]

@app.post("/api/konsultationen", status_code=201)
def create_konsultation(k: KonsultationIn):
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO konsultationen
              (datum,alter_j,alter_m,alter_ges,dauer,grund,diagnose_akut,diagnose_dauer,
               massnahmen,begleitperson,mh,notizen,eltern_fragen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            k.datum or datetime.now().isoformat(timespec='minutes'),
            k.alter_j or 0, k.alter_m or 0, k.alter_ges or 0, k.dauer,
            json.dumps(k.grund or [], ensure_ascii=False),
            json.dumps(k.diagnose_akut or [], ensure_ascii=False),
            json.dumps(k.diagnose_dauer or [], ensure_ascii=False),
            json.dumps(k.massnahmen or [], ensure_ascii=False),
            k.begleitperson or "", 1 if k.mh else 0,
            k.notizen or "", k.eltern_fragen or ""
        ))
        db.commit()
        row = db.execute("SELECT * FROM konsultationen WHERE id=?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)

@app.put("/api/konsultationen/{entry_id}")
def update_konsultation(entry_id: int, k: KonsultationIn):
    with get_db() as db:
        if not db.execute("SELECT id FROM konsultationen WHERE id=?", (entry_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Nicht gefunden")
        db.execute("""
            UPDATE konsultationen SET
              datum=?,alter_j=?,alter_m=?,alter_ges=?,dauer=?,
              grund=?,diagnose_akut=?,diagnose_dauer=?,massnahmen=?,
              begleitperson=?,mh=?,notizen=?,eltern_fragen=?
            WHERE id=?
        """, (
            k.datum or datetime.now().isoformat(timespec='minutes'),
            k.alter_j or 0, k.alter_m or 0, k.alter_ges or 0, k.dauer,
            json.dumps(k.grund or [], ensure_ascii=False),
            json.dumps(k.diagnose_akut or [], ensure_ascii=False),
            json.dumps(k.diagnose_dauer or [], ensure_ascii=False),
            json.dumps(k.massnahmen or [], ensure_ascii=False),
            k.begleitperson or "", 1 if k.mh else 0,
            k.notizen or "", k.eltern_fragen or "",
            entry_id
        ))
        db.commit()
        row = db.execute("SELECT * FROM konsultationen WHERE id=?", (entry_id,)).fetchone()
    return _row_to_dict(row)

@app.delete("/api/konsultationen/{entry_id}", status_code=204)
def delete_konsultation(entry_id: int):
    with get_db() as db:
        result = db.execute("DELETE FROM konsultationen WHERE id=?", (entry_id,))
        db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Nicht gefunden")

@app.get("/api/stats")
def get_stats():
    with get_db() as db:
        rows = db.execute("SELECT * FROM konsultationen").fetchall()
    entries = [_row_to_dict(r) for r in rows]
    if not entries:
        return {"total":0,"avg_dauer":0,"mh_pct":0,"mh_count":0,
                "top_grund":None,"top_grund_count":0,
                "alter_dist":{},"grund_counts":{},"dauer_buckets":{},
                "vorsorge_count":0,"vorsorge_dist":{},"diag_akut_counts":{},
                "diag_dauer_counts":{},"mass_counts":{},"eltern_fragen_count":0}

    durations = [e["dauer"] for e in entries if e.get("dauer")]
    avg_dauer = round(sum(durations)/len(durations),1) if durations else 0
    mh_count = sum(1 for e in entries if e.get("mh"))

    grund_counts = {}
    for e in entries:
        for g in (e.get("grund") or []):
            grund_counts[g] = grund_counts.get(g,0)+1
    top_grund = max(grund_counts, key=grund_counts.get) if grund_counts else None

    # Vorsorge distribution
    vorsorge_dist = {}
    for e in entries:
        for g in (e.get("grund") or []):
            if g in VORSORGE:
                vorsorge_dist[g] = vorsorge_dist.get(g,0)+1
    vorsorge_order = ['U1','U2','U3','U4','U5','U6','U7','U7a','U8','U9','U10','U11','J1','J2']
    vorsorge_dist_sorted = {k: vorsorge_dist[k] for k in vorsorge_order if k in vorsorge_dist}

    # Age dist
    age_labels = ["< 1 J","1–2 J","2–4 J","4–6 J","6–9 J","9+ J"]
    alter_dist = {l:0 for l in age_labels}
    for e in entries:
        m = e.get("alter_ges",0) or 0
        if m<12: alter_dist["< 1 J"]+=1
        elif m<24: alter_dist["1–2 J"]+=1
        elif m<48: alter_dist["2–4 J"]+=1
        elif m<72: alter_dist["4–6 J"]+=1
        elif m<108: alter_dist["6–9 J"]+=1
        else: alter_dist["9+ J"]+=1

    # Dauer buckets
    dauer_buckets={"≤5 min":0,"6–10 min":0,"11–20 min":0,"21–30 min":0,">30 min":0}
    for e in entries:
        d=e.get("dauer")
        if not d: continue
        if d<=5: dauer_buckets["≤5 min"]+=1
        elif d<=10: dauer_buckets["6–10 min"]+=1
        elif d<=20: dauer_buckets["11–20 min"]+=1
        elif d<=30: dauer_buckets["21–30 min"]+=1
        else: dauer_buckets[">30 min"]+=1

    # Diagnose counts
    diag_akut_counts = {}
    diag_dauer_counts = {}
    for e in entries:
        for d in (e.get("diagnose_akut") or []):
            diag_akut_counts[d] = diag_akut_counts.get(d,0)+1
        for d in (e.get("diagnose_dauer") or []):
            diag_dauer_counts[d] = diag_dauer_counts.get(d,0)+1

    # Maßnahmen counts
    mass_counts = {}
    for e in entries:
        for m in (e.get("massnahmen") or []):
            mass_counts[m] = mass_counts.get(m,0)+1

    # Vorsorge-Fragen counts
    vorsorge_fragen_counts = {}
    for e in entries:
        for f in (e.get("vorsorge_fragen") or []):
            vorsorge_fragen_counts[f] = vorsorge_fragen_counts.get(f,0)+1

    return {
        "total": len(entries),
        "avg_dauer": avg_dauer,
        "mh_pct": round(mh_count/len(entries)*100),
        "mh_count": mh_count,
        "top_grund": top_grund,
        "top_grund_count": grund_counts.get(top_grund,0),
        "alter_dist": alter_dist,
        "grund_counts": dict(sorted(grund_counts.items(),key=lambda x:-x[1])[:10]),
        "dauer_buckets": dauer_buckets,
        "vorsorge_count": sum(vorsorge_dist.values()),
        "vorsorge_dist": vorsorge_dist_sorted,
        "diag_akut_counts": dict(sorted(diag_akut_counts.items(),key=lambda x:-x[1])[:10]),
        "diag_dauer_counts": dict(sorted(diag_dauer_counts.items(),key=lambda x:-x[1])[:10]),
        "mass_counts": dict(sorted(mass_counts.items(),key=lambda x:-x[1])[:10]),
        "vorsorge_fragen_counts": dict(sorted(vorsorge_fragen_counts.items(),key=lambda x:-x[1])[:10]),
    }

@app.get("/api/vorschlaege")
def get_vorschlaege():
    with get_db() as db:
        rows = db.execute("SELECT grund, diagnose_akut, diagnose_dauer, massnahmen, vorsorge_fragen FROM konsultationen").fetchall()
    gc, dac, ddc, mc, vfc = {}, {}, {}, {}, {}
    for row in rows:
        for val, counts in [(row[0],gc),(row[1],dac),(row[2],ddc),(row[3],mc),(row[4],vfc)]:
            if not val: continue
            try: items = json.loads(val)
            except: items = []
            for item in items:
                item=item.strip()
                if item: counts[item]=counts.get(item,0)+1
    srt = lambda d: [k for k,_ in sorted(d.items(),key=lambda x:-x[1])]
    return {
        "grund":            {"top":srt(gc)[:10],  "alle":srt(gc)},
        "diagnose_akut":    {"top":srt(dac)[:10], "alle":srt(dac)},
        "diagnose_dauer":   {"top":srt(ddc)[:10], "alle":srt(ddc)},
        "massnahmen":       {"top":srt(mc)[:10],  "alle":srt(mc)},
        "vorsorge_fragen":  {"top":srt(vfc)[:10], "alle":srt(vfc)},
    }

@app.get("/api/export/csv")
def export_csv():
    from fastapi.responses import StreamingResponse
    import io, csv
    with get_db() as db:
        rows = db.execute("SELECT * FROM konsultationen ORDER BY id").fetchall()
    entries = [_row_to_dict(r) for r in rows]
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["ID","Datum","Alter (J)","Alter (M)","Alter (Ges. Mo.)","Dauer (min)",
                     "Grund","Diagnose (akut)","Diagnose (Dauer)","Maßnahmen",
                     "Begleitperson","MH","Notizen","Eltern-Fragen"])
    for e in entries:
        writer.writerow([e["id"],e.get("datum",""),e.get("alter_j",0),e.get("alter_m",0),
            e.get("alter_ges",0),e.get("dauer",""),
            ", ".join(e.get("grund") or []),
            ", ".join(e.get("diagnose_akut") or []),
            ", ".join(e.get("diagnose_dauer") or []),
            ", ".join(e.get("massnahmen") or []),
            e.get("begleitperson",""),"Ja" if e.get("mh") else "Nein",
            e.get("notizen",""),e.get("eltern_fragen","")])
    output.seek(0)
    filename = f"praxis_export_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
        headers={"Content-Disposition":f"attachment; filename={filename}"})

def _row_to_dict(row):
    d = dict(row)
    for field in ("grund","diagnose_akut","diagnose_dauer","massnahmen"):
        if isinstance(d.get(field),str):
            try: d[field]=json.loads(d[field])
            except: d[field]=[]
        elif d.get(field) is None:
            d[field]=[]
    d["mh"]=bool(d.get("mh",0))
    if d.get("eltern_fragen") is None:
        d["eltern_fragen"]=""
    return d

@app.on_event("startup")
def startup():
    init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
