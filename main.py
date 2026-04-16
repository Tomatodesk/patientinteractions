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
                vorsorge_fragen  TEXT,
                begleitperson    TEXT DEFAULT '',
                mh               INTEGER DEFAULT 0,
                notizen          TEXT DEFAULT '',
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        cols = [r[1] for r in db.execute("PRAGMA table_info(konsultationen)").fetchall()]
        for col in ["diagnose_akut","diagnose_dauer","vorsorge_fragen","ebm_ziffern"]:
            if col not in cols:
                db.execute(f"ALTER TABLE konsultationen ADD COLUMN {col} TEXT DEFAULT ''")
        if "alter_d" not in cols:
            db.execute("ALTER TABLE konsultationen ADD COLUMN alter_d INTEGER DEFAULT 0")
        # migrate old field names
        if "diagnose" in cols and "diagnose_akut" in cols:
            db.execute("UPDATE konsultationen SET diagnose_akut=diagnose WHERE (diagnose_akut IS NULL OR diagnose_akut='') AND diagnose IS NOT NULL AND diagnose!=''")
        if "eltern_fragen" in cols and "vorsorge_fragen" in cols:
            db.execute("UPDATE konsultationen SET vorsorge_fragen=eltern_fragen WHERE (vorsorge_fragen IS NULL OR vorsorge_fragen='') AND eltern_fragen IS NOT NULL AND eltern_fragen!=''")
        db.commit()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try: yield conn
    finally: conn.close()

def _dumps(v): return json.dumps(v or [], ensure_ascii=False)
def _loads(v):
    if not v: return []
    try:
        r = json.loads(v)
        return r if isinstance(r, list) else [r]
    except: return [v] if v else []

def _row_to_dict(row):
    d = dict(row)
    for f in ("grund","diagnose_akut","diagnose_dauer","massnahmen","vorsorge_fragen","begleitperson","ebm_ziffern"):
        d[f] = _loads(d.get(f))
    d["mh"] = bool(d.get("mh", 0))
    return d

class KonsultationIn(BaseModel):
    datum: Optional[str] = None
    alter_j: Optional[int] = 0
    alter_m: Optional[int] = 0
    alter_d: Optional[int] = 0
    alter_ges: Optional[int] = 0
    dauer: Optional[int] = None
    grund: Optional[List[str]] = []
    diagnose_akut: Optional[List[str]] = []
    diagnose_dauer: Optional[List[str]] = []
    massnahmen: Optional[List[str]] = []
    vorsorge_fragen: Optional[List[str]] = []
    begleitperson: Optional[List[str]] = []
    ebm_ziffern: Optional[List[str]] = []
    mh: Optional[bool] = False
    notizen: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

@app.get("/api/konsultationen")
def list_konsultationen(q: str = "", sort: str = "datum_desc", von: str = "", bis: str = ""):
    order = {"datum_asc":"datum ASC","created_desc":"created_at DESC","created_asc":"created_at ASC"}.get(sort,"datum DESC")
    conditions, params = [], []
    if q:
        like = f"%{q}%"
        conditions.append("(datum LIKE ? OR grund LIKE ? OR diagnose_akut LIKE ? OR diagnose_dauer LIKE ? OR massnahmen LIKE ? OR notizen LIKE ? OR begleitperson LIKE ? OR vorsorge_fragen LIKE ? OR ebm_ziffern LIKE ?)")
        params.extend([like]*9)
    if von:
        conditions.append("datum >= ?")
        params.append(von)
    if bis:
        conditions.append("datum <= ?")
        params.append(bis + "T23:59")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as db:
        rows = db.execute(f"SELECT * FROM konsultationen {where} ORDER BY {order}", params).fetchall()
    return [_row_to_dict(r) for r in rows]

@app.post("/api/konsultationen", status_code=201)
def create_konsultation(k: KonsultationIn):
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO konsultationen
              (datum,alter_j,alter_m,alter_d,alter_ges,dauer,grund,diagnose_akut,diagnose_dauer,massnahmen,vorsorge_fragen,begleitperson,ebm_ziffern,mh,notizen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            k.datum or datetime.now().isoformat(timespec='minutes'),
            k.alter_j or 0, k.alter_m or 0, k.alter_d or 0, k.alter_ges or 0, k.dauer,
            _dumps(k.grund), _dumps(k.diagnose_akut), _dumps(k.diagnose_dauer),
            _dumps(k.massnahmen), _dumps(k.vorsorge_fragen), _dumps(k.begleitperson),
            _dumps(k.ebm_ziffern), 1 if k.mh else 0, k.notizen or ""
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
              datum=?,alter_j=?,alter_m=?,alter_d=?,alter_ges=?,dauer=?,
              grund=?,diagnose_akut=?,diagnose_dauer=?,massnahmen=?,vorsorge_fragen=?,begleitperson=?,ebm_ziffern=?,mh=?,notizen=?
            WHERE id=?
        """, (
            k.datum or datetime.now().isoformat(timespec='minutes'),
            k.alter_j or 0, k.alter_m or 0, k.alter_d or 0, k.alter_ges or 0, k.dauer,
            _dumps(k.grund), _dumps(k.diagnose_akut), _dumps(k.diagnose_dauer),
            _dumps(k.massnahmen), _dumps(k.vorsorge_fragen), _dumps(k.begleitperson),
            _dumps(k.ebm_ziffern), 1 if k.mh else 0, k.notizen or "", entry_id
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
        return {"total":0,"avg_dauer":0,"mh_pct":0,"mh_count":0,"top_grund":None,"top_grund_count":0,
                "alter_dist":{},"grund_counts":{},"dauer_buckets":{},"massnahmen_counts":{},
                "diag_akut_counts":{},"diag_dauer_counts":{},"elternfragen_counts":{},
                "begleitperson_counts":{},"wochentag_dist":{},"ebm_counts":{}}
    durations = [e["dauer"] for e in entries if e.get("dauer")]
    avg_dauer = round(sum(durations)/len(durations),1) if durations else 0
    mh_count = sum(1 for e in entries if e.get("mh"))
    def count_field(field, limit=12):
        counts = {}
        for e in entries:
            for v in (e.get(field) or []):
                counts[v] = counts.get(v,0)+1
        return dict(sorted(counts.items(), key=lambda x:-x[1])[:limit])
    grund_counts = count_field("grund")
    top_grund = max(grund_counts, key=grund_counts.get) if grund_counts else None
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
    dauer_buckets={"≤5 min":0,"6–10 min":0,"11–20 min":0,"21–30 min":0,">30 min":0}
    for e in entries:
        d=e.get("dauer")
        if not d: continue
        if d<=5: dauer_buckets["≤5 min"]+=1
        elif d<=10: dauer_buckets["6–10 min"]+=1
        elif d<=20: dauer_buckets["11–20 min"]+=1
        elif d<=30: dauer_buckets["21–30 min"]+=1
        else: dauer_buckets[">30 min"]+=1
    wt_labels = ["Mo","Di","Mi","Do","Fr","Sa","So"]
    wochentag_dist = {l:0 for l in wt_labels}
    # count entries per calendar date, then average by weekday over days with entries
    entries_per_date = {}
    for e in entries:
        try:
            d = datetime.fromisoformat(e["datum"]).date()
            entries_per_date[d] = entries_per_date.get(d, 0) + 1
        except: pass
    wt_day_counts = [[] for _ in range(7)]
    for d, cnt in entries_per_date.items():
        wt_day_counts[d.weekday()].append(cnt)
    for i, label in enumerate(wt_labels):
        days = wt_day_counts[i]
        wochentag_dist[label] = round(sum(days)/len(days), 1) if days else 0
    # begleitperson: flatten and count
    begl_counts = count_field("begleitperson", 8)
    return {
        "total":len(entries),"avg_dauer":avg_dauer,
        "mh_pct":round(mh_count/len(entries)*100),"mh_count":mh_count,
        "top_grund":top_grund,"top_grund_count":grund_counts.get(top_grund,0),
        "alter_dist":alter_dist,"grund_counts":grund_counts,"dauer_buckets":dauer_buckets,
        "diag_akut_counts":count_field("diagnose_akut"),
        "diag_dauer_counts":count_field("diagnose_dauer"),
        "massnahmen_counts":count_field("massnahmen"),
        "elternfragen_counts":count_field("vorsorge_fragen"),
        "begleitperson_counts":begl_counts,
        "wochentag_dist":wochentag_dist,
        "ebm_counts":count_field("ebm_ziffern"),
    }

@app.get("/api/vorschlaege")
def get_vorschlaege():
    with get_db() as db:
        rows = db.execute("SELECT grund,diagnose_akut,diagnose_dauer,massnahmen,vorsorge_fragen,ebm_ziffern FROM konsultationen").fetchall()
    gc,dac,ddc,mc,vfc,ec = {},{},{},{},{},{}
    for row in rows:
        for val,counts in [(row[0],gc),(row[1],dac),(row[2],ddc),(row[3],mc),(row[4],vfc),(row[5],ec)]:
            for item in _loads(val):
                item=item.strip()
                if item: counts[item]=counts.get(item,0)+1
    srt = lambda d: [k for k,_ in sorted(d.items(),key=lambda x:-x[1])]
    return {
        "grund":           {"top":srt(gc)[:10],  "alle":srt(gc)},
        "diagnose_akut":   {"top":srt(dac)[:10], "alle":srt(dac)},
        "diagnose_dauer":  {"top":srt(ddc)[:10], "alle":srt(ddc)},
        "massnahmen":      {"top":srt(mc)[:10],  "alle":srt(mc)},
        "vorsorge_fragen": {"top":srt(vfc)[:10], "alle":srt(vfc)},
        "ebm_ziffern":     {"top":srt(ec)[:10],  "alle":srt(ec)},
    }

@app.get("/api/vorschlaege/kontext")
def get_vorschlaege_kontext(grund: str = ""):
    if not grund:
        return {"diagnose_akut":{"top":[],"alle":[]},"diagnose_dauer":{"top":[],"alle":[]},"massnahmen":{"top":[],"alle":[]}}
    gruende = {g.strip() for g in grund.split(",") if g.strip()}
    with get_db() as db:
        rows = db.execute("SELECT grund,diagnose_akut,diagnose_dauer,massnahmen FROM konsultationen").fetchall()
    dac,ddc,mc = {},{},{}
    for row in rows:
        if not set(_loads(row[0])).intersection(gruende):
            continue
        for item in _loads(row[1]):
            item=item.strip()
            if item: dac[item]=dac.get(item,0)+1
        for item in _loads(row[2]):
            item=item.strip()
            if item: ddc[item]=ddc.get(item,0)+1
        for item in _loads(row[3]):
            item=item.strip()
            if item: mc[item]=mc.get(item,0)+1
    srt = lambda d: [k for k,_ in sorted(d.items(),key=lambda x:-x[1])]
    return {
        "diagnose_akut":  {"top":srt(dac)[:10],"alle":srt(dac)},
        "diagnose_dauer": {"top":srt(ddc)[:10],"alle":srt(ddc)},
        "massnahmen":     {"top":srt(mc)[:10], "alle":srt(mc)},
    }

@app.get("/api/vorschlaege/ebm-kontext")
def get_vorschlaege_ebm_kontext(grund: str = "", diagnose_akut: str = "", diagnose_dauer: str = "", massnahmen: str = ""):
    ctx_sets = []
    if grund:       ctx_sets.append(({g.strip() for g in grund.split(",") if g.strip()}, "grund"))
    if diagnose_akut:  ctx_sets.append(({g.strip() for g in diagnose_akut.split(",") if g.strip()}, "diagnose_akut"))
    if diagnose_dauer: ctx_sets.append(({g.strip() for g in diagnose_dauer.split(",") if g.strip()}, "diagnose_dauer"))
    if massnahmen:     ctx_sets.append(({g.strip() for g in massnahmen.split(",") if g.strip()}, "massnahmen"))
    if not ctx_sets:
        return {"ebm_ziffern": {"top": [], "alle": []}}
    with get_db() as db:
        rows = db.execute("SELECT grund,diagnose_akut,diagnose_dauer,massnahmen,ebm_ziffern FROM konsultationen").fetchall()
    ec = {}
    for row in rows:
        row_data = {"grund": set(_loads(row[0])), "diagnose_akut": set(_loads(row[1])),
                    "diagnose_dauer": set(_loads(row[2])), "massnahmen": set(_loads(row[3]))}
        match = any(row_data[field].intersection(vals) for vals, field in ctx_sets)
        if not match: continue
        for item in _loads(row[4]):
            item = item.strip()
            if item: ec[item] = ec.get(item, 0) + 1
    srt = lambda d: [k for k, _ in sorted(d.items(), key=lambda x: -x[1])]
    return {"ebm_ziffern": {"top": srt(ec)[:10], "alle": srt(ec)}}

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
    writer.writerow(["ID","Datum","Alter (J)","Alter (M)","Alter (Tage)","Alter (Ges. Mo.)","Dauer (min)",
                     "Grund","Diagnose (akut)","Diagnose (Dauer)","Maßnahmen","Elternfragen","Begleitperson","EBM-Ziffern","MH","Notizen"])
    for e in entries:
        writer.writerow([e["id"],e.get("datum",""),e.get("alter_j",0),e.get("alter_m",0),
            e.get("alter_d",0),e.get("alter_ges",0),e.get("dauer",""),
            ", ".join(e.get("grund") or []),
            ", ".join(e.get("diagnose_akut") or []),
            ", ".join(e.get("diagnose_dauer") or []),
            ", ".join(e.get("massnahmen") or []),
            ", ".join(e.get("vorsorge_fragen") or []),
            ", ".join(e.get("begleitperson") or []),
            ", ".join(e.get("ebm_ziffern") or []),
            "Ja" if e.get("mh") else "Nein",
            e.get("notizen","")])
    output.seek(0)
    filename = f"praxis_export_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
        headers={"Content-Disposition":f"attachment; filename={filename}"})

@app.on_event("startup")
def startup():
    init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
