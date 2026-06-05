from flask import Flask, jsonify
from flask_cors import CORS
import requests
import csv
import io

app = Flask(__name__)
CORS(app, origins=["*"])

GOOGLE_SHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRjwPUN21RUS6QX3hVUd7rP7t0MZ52hOVyMZNmRHdrR75gBD8FOtLnCcYwbS9GtvcDusIpliN0W-gzI/pub?output=csv&gid=792570627"
MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]
VERSION = "v8"

def parse_value(val):
    if not val or not val.strip() or val.strip() == "#REF!":
        return 0
    v = val.strip()
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

@app.route("/api/data")
def get_data():
    try:
        rows = fetch_csv()

        # 1. Trouve colonnes des mois
        mois_cols = {}
        for row in rows:
            for j, cell in enumerate(row):
                if cell.strip() == "Janvier":
                    for k, cc in enumerate(row):
                        if cc.strip() in MOIS:
                            mois_cols[cc.strip()] = k
                    break
            if mois_cols:
                break

        def vals(row):
            return {m: parse_value(row[idx]) if idx < len(row) else 0 for m, idx in mois_cols.items()}

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

        for i, row in enumerate(rows):
            if len(row) < 4:
                continue
            c1 = row[1].strip()
            c2 = row[2].strip()
            c3 = row[3].strip()

            # ÉQUIPE : première occurrence avec valeurs réelles (pas #REF!)
            if c1 == "Total Best MRR" and c2 == "Team" and c3 == "Goals":
                v = vals(row)
                if any(x > 0 for x in v.values()):
                    data["equipe"]["goals"] = v
                    if i+1 < len(rows): data["equipe"]["realise"] = vals(rows[i+1])
                    if i+2 < len(rows): data["equipe"]["pct"] = vals(rows[i+2])

            # KATY GOALS (ligne ajoutée manuellement)
            if c2 == "Katy" and "Goals" in c3:
                data["membres"]["Katy"]["goals"] = vals(row)

            # KATY RÉALISÉ
            if c2 == "Katy" and "Réalis" in c3:
                data["membres"]["Katy"]["realise"] = vals(row)
                if i+1 < len(rows) and rows[i+1][3].strip() == "%":
                    data["membres"]["Katy"]["pct"] = vals(rows[i+1])

            # NESRINE
            if c2 == "Nesrine" and "Goals" in c3:
                data["membres"]["Nesrine"]["goals"] = vals(row)
                if i+1 < len(rows): data["membres"]["Nesrine"]["realise"] = vals(rows[i+1])
                if i+2 < len(rows): data["membres"]["Nesrine"]["pct"] = vals(rows[i+2])

            # JULIEN
            if c2 == "Julien" and "Goals" in c3:
                data["membres"]["Julien"]["goals"] = vals(row)
                if i+1 < len(rows): data["membres"]["Julien"]["realise"] = vals(rows[i+1])
                if i+2 < len(rows): data["membres"]["Julien"]["pct"] = vals(rows[i+2])

        # Calcule % manquants
        for nom in ["Katy", "Nesrine", "Julien"]:
            if all(v == 0 for v in data["membres"][nom]["pct"].values()):
                data["membres"][nom]["pct"] = {
                    m: round(data["membres"][nom]["realise"].get(m, 0) /
                             data["membres"][nom]["goals"].get(m, 0) * 100, 2)
                    if data["membres"][nom]["goals"].get(m, 0) > 0 else 0
                    for m in MOIS
                }

        return jsonify({"success": True, "version": VERSION, "data": data, "mois": MOIS})

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
    return jsonify({"status": "ok", "message": "Dashboard API - Team Katy", "version": VERSION})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
