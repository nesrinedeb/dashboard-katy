from flask import Flask, jsonify
from flask_cors import CORS
import requests
import csv
import io

app = Flask(__name__)
CORS(app, origins=["*"])

GOOGLE_SHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRjwPUN21RUS6QX3hVUd7rP7t0MZ52hOVyMZNmRHdrR75gBD8FOtLnCcYwbS9GtvcDusIpliN0W-gzI/pub?output=csv&gid=792570627"
MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]

def parse_value(val):
    if not val or not val.strip():
        return 0
    v = val.strip()
    if v == "#REF!":
        return 0
    for ch in ["€", "%", "\xa0", "\u202f", "\u00a0", "\u20ac"]:
        v = v.replace(ch, "")
    v = v.replace(" ", "").replace(",", ".")
    try:
        return float(v)
    except:
        return 0

def fetch_csv():
    r = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=15)
    r.encoding = "utf-8"
    return list(csv.reader(io.StringIO(r.text)))

def zero():
    return {m: 0 for m in MOIS}

@app.route("/api/data")
def get_data():
    try:
        rows = fetch_csv()

        # Trouve la ligne des mois (contient "Janvier")
        mois_row_idx = None
        mois_cols = {}
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                if cell.strip() == "Janvier":
                    mois_row_idx = i
                    for k, cc in enumerate(row):
                        if cc.strip() in MOIS:
                            mois_cols[cc.strip()] = k
                    break
            if mois_row_idx is not None:
                break

        def vals(row):
            return {m: parse_value(row[idx]) if idx < len(row) else 0
                    for m, idx in mois_cols.items()}

        def zero():
            return {m: 0 for m in MOIS}

        data = {
            "equipe":  {"goals": zero(), "realise": zero(), "pct": zero()},
            "membres": {
                "Katy":    {"goals": zero(), "realise": zero(), "pct": zero()},
                "Nesrine": {"goals": zero(), "realise": zero(), "pct": zero()},
                "Julien":  {"goals": zero(), "realise": zero(), "pct": zero()},
            }
        }

        # Cherche le bloc principal "Total Best MRR / Team"
        # C'est le PREMIER bloc (pas les #REF! du second)
        first_block_found = False

        for i, row in enumerate(rows):
            cells = [c.strip() for c in row]
            if len(cells) < 4:
                continue

            # ── ÉQUIPE : premier "Total Best MRR" avec "Team" ──
            if not first_block_found and "Total Best MRR" in cells and "Team" in cells and "Goals" in cells:
                first_block_found = True
                # Ligne courante = Goals
                data["equipe"]["goals"] = vals(row)
                # Ligne i+1 = Réalisé
                if i+1 < len(rows):
                    data["equipe"]["realise"] = vals(rows[i+1])
                # Ligne i+2 = %
                if i+2 < len(rows):
                    data["equipe"]["pct"] = vals(rows[i+2])

            # ── MEMBRES : cherche par nom en colonne 2 (index 2) ──
            if len(cells) > 3:
                nom_cell = cells[2]
                type_cell = cells[3]

                if nom_cell in ["Katy", "Nesrine", "Julien"]:
                    nom = nom_cell
                    if "Goals" in type_cell or "Budget" in type_cell:
                        data["membres"][nom]["goals"] = vals(row)
                        # Ligne suivante = Réalisé
                        if i+1 < len(rows):
                            nr = [c.strip() for c in rows[i+1]]
                            if len(nr) > 3 and "Réalis" in nr[3]:
                                data["membres"][nom]["realise"] = vals(rows[i+1])
                        # Ligne i+2 = %
                        if i+2 < len(rows):
                            nr2 = [c.strip() for c in rows[i+2]]
                            if len(nr2) > 3 and "%" in nr2[3]:
                                data["membres"][nom]["pct"] = vals(rows[i+2])

                    elif "Réalis" in type_cell:
                        data["membres"][nom]["realise"] = vals(row)
                        # Ligne suivante = %
                        if i+1 < len(rows):
                            nr = [c.strip() for c in rows[i+1]]
                            if len(nr) > 3 and "%" in nr[3]:
                                data["membres"][nom]["pct"] = vals(rows[i+1])

        # Calcule les % manquants
        for nom in ["Katy", "Nesrine", "Julien"]:
            if all(v == 0 for v in data["membres"][nom]["pct"].values()):
                data["membres"][nom]["pct"] = {
                    m: round(data["membres"][nom]["realise"].get(m, 0) /
                             data["membres"][nom]["goals"].get(m, 1) * 100, 2)
                    if data["membres"][nom]["goals"].get(m, 0) > 0 else 0
                    for m in MOIS
                }
        if all(v == 0 for v in data["equipe"]["pct"].values()):
            data["equipe"]["pct"] = {
                m: round(data["equipe"]["realise"].get(m, 0) /
                         data["equipe"]["goals"].get(m, 1) * 100, 2)
                if data["equipe"]["goals"].get(m, 0) > 0 else 0
                for m in MOIS
            }

        return jsonify({"success": True, "data": data, "mois": MOIS})

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/raw")
def get_raw():
    try:
        return jsonify({"rows": fetch_csv()[:60]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Dashboard API - Team Katy"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
