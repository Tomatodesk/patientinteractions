"""
CSV-Import für Praxis-Datenbank
Verwendung: python3 import_csv.py <pfad-zur-csv>
"""
import sys, csv, json, sqlite3, os

DB_PATH = os.environ.get("DB_PATH", "praxis.db")

def dumps(v): return json.dumps(v or [], ensure_ascii=False)

def parse_list(s):
    """Komma-separierter String → JSON-Array"""
    if not s or not s.strip():
        return dumps([])
    return dumps([x.strip() for x in s.split(",") if x.strip()])

def run(csv_path):
    if not os.path.exists(csv_path):
        print(f"Datei nicht gefunden: {csv_path}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Tabelle anlegen falls noch nicht vorhanden
    conn.execute("""
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

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    if not rows:
        print("CSV ist leer.")
        sys.exit(1)

    print(f"Spalten gefunden: {list(rows[0].keys())}")

    inserted = 0
    skipped = 0
    for row in rows:
        # Bestehende ID überspringen falls schon vorhanden
        existing_id = row.get("ID", "").strip()
        if existing_id:
            exists = conn.execute("SELECT id FROM konsultationen WHERE id=?", (existing_id,)).fetchone()
            if exists:
                skipped += 1
                continue

        mh_val = row.get("MH", "Nein").strip()
        mh = 1 if mh_val.lower() in ("ja", "1", "true") else 0

        alter_j = int(row.get("Alter (J)", 0) or 0)
        alter_m = int(row.get("Alter (M)", 0) or 0)
        alter_ges = int(row.get("Alter (Ges. Mo.)", 0) or 0) or (alter_j * 12 + alter_m)
        dauer = int(row.get("Dauer (min)", 10) or 10)

        conn.execute("""
            INSERT INTO konsultationen
              (datum, alter_j, alter_m, alter_ges, dauer,
               grund, diagnose_akut, diagnose_dauer, massnahmen,
               vorsorge_fragen, begleitperson, mh, notizen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            row.get("Datum", "").strip() or None,
            alter_j, alter_m, alter_ges, dauer,
            parse_list(row.get("Grund", "")),
            parse_list(row.get("Diagnose (akut)", "")),
            parse_list(row.get("Diagnose (Dauer)", "")),
            parse_list(row.get("Maßnahmen", "")),
            parse_list(row.get("Vorsorge-Fragen", "")),
            parse_list(row.get("Begleitperson", "")),
            mh,
            row.get("Notizen", "").strip(),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"✓ {inserted} Einträge importiert, {skipped} bereits vorhanden übersprungen.")
    print(f"  Datenbank: {os.path.abspath(DB_PATH)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung: python3 import_csv.py <pfad-zur-csv>")
        sys.exit(1)
    run(sys.argv[1])
