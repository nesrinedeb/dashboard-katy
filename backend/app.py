from flask import Flask, jsonify
from flask_cors import CORS
import requests
import csv
import io

app = Flask(__name__)
CORS(app)

GOOGLE_SHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRjwPUN21RUS6QX3hVUd7rP7t0MZ52hOVyMZNmRHdrR75gBD8FOtLnCcYwbS9GtvcDusIpliN0W-gzI/pub?output=csv&gid=792570627"

MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]

def parse_value(val):
    if not val or val.strip() == "":
        return 0
    v = val.strip()
    v = v.replace("€", "").replace("%", "")
    v = v.replace("\xa0", "").replace("\u202f", "").replace("\u00a0", "").replace("\u20ac", "")
    v = v.replace(" ", "").replace(",", ".")
    try:
        return float(v)
    except:
        return 0

def clean(s):
    return s.strip().lower() if s else ""

def fetch_csv():
    response = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=15)
    response.encoding = "utf-8"
    reader = csv.reader(io.StringIO(response.text))
    return [row for row in reader]

@app.route("/api/data")
def get_data():
    try:
        rows = fetch_csv()

        # Trouve la ligne header avec les mois
        mois_cols = {}
        for row in rows:
            for j, cell in enumerate(row):
                if "Janvier" in cell:
                    for k, c in enumerate(row):
                        c2 = c.strip()
                        if c2 in MOIS:
                            mois_cols[c2] = k
                    break
            if mois_cols:
                break

        def get_vals(row):
            return {m: parse_value(row[idx]) if idx < len(row) else 0 for m, idx in mois_cols.items()}

        data = {
            "equipe": {"goals": {}, "realise": {}, "pct": {}},
            "membres": {
                "Katy":    {"goals": {}, "realise": {}, "pct": {}},
                "Nesrine": {"goals": {}, "realise": {}, "pct": {}},
                "Julien":  {"goals": {}, "realise": {}, "pct": {}},
            }
        }

        for i, row in enumerate(rows):
            if len(row) < 3:
                continue

            c0 = clean(row[0])
            c1 = clean(row[1]) if len(row) > 1 else ""
            c2 = clean(row[2]) if len(row) > 2 else ""

            # ── ÉQUIPE ──
            # Ligne: ["", "Total Best MRR", "Team", "Goals", ...]
            if "total best mrr" in c1 or "total best mrr" in c2:
                if "goals" in c2 or "budget" in c2:
                    data["equipe"]["goals"] = get_vals(row)
                elif "réalis" in c2 or "realise" in c2:
                    data["equipe"]["realise"] = get_vals(row)
                elif "%" in c2 or "atteinte" in c2:
                    data["equipe"]["pct"] = get_vals(row)
                # Cherche aussi les lignes suivantes
                for nr in rows[i+1:i+4]:
                    if len(nr) < 3:
                        continue
                    nc2 = clean(nr[2]) if len(nr) > 2 else ""
                    nc1 = clean(nr[1]) if len(nr) > 1 else ""
                    if "goals" in nc2 or "budget" in nc2:
                        data["equipe"]["goals"] = get_vals(nr)
                    elif "réalis" in nc2 or "realise" in nc2 or "réalis" in nc1:
                        data["equipe"]["realise"] = get_vals(nr)
                    elif ("%" in nc2 or "atteinte" in nc2) and any(parse_value(nr[mois_cols[m]]) > 0 for m in MOIS if m in mois_cols and mois_cols[m] < len(nr)):
                        data["equipe"]["pct"] = get_vals(nr)

            # ── MEMBRES ──
            for nom in ["Katy", "Nesrine", "Julien"]:
                n = nom.lower()
                # Ligne type: ["", "", "Nesrine", "Goals", val, val, ...]
                # ou: ["", "", "Katy", "Réalisé", val, val, ...]
                if n in c1 or n in c2:
                    col_type = c2 if n in c1 else clean(row[3]) if len(row) > 3 else ""
                    vals = get_vals(row)
                    if "goals" in col_type or "budget" in col_type:
                        data["membres"][nom]["goals"] = vals
                    elif "réalis" in col_type or "realise" in col_type:
                        data["membres"][nom]["realise"] = vals
                    elif "%" in col_type or "atteinte" in col_type:
                        data["membres"][nom]["pct"] = vals
                    # Cherche lignes suivantes pour goals/réalisé/% du même membre
                    for nr in rows[i+1:i+4]:
                        if len(nr) < 3:
                            continue
                        nc1 = clean(nr[1]) if len(nr) > 1 else ""
                        nc2 = clean(nr[2]) if len(nr) > 2 else ""
                        nc3 = clean(nr[3]) if len(nr) > 3 else ""
                        # Stop si on change de membre
                        if any(other.lower() in nc1 or other.lower() in nc2 for other in ["Katy","Nesrine","Julien"] if other != nom):
                            break
                        if "goals" in nc2 or "budget" in nc2 or "goals" in nc3 or "budget" in nc3:
                            data["membres"][nom]["goals"] = get_vals(nr)
                        elif "réalis" in nc2 or "realise" in nc2 or "réalis" in nc3:
                            data["membres"][nom]["realise"] = get_vals(nr)
                        elif "%" in nc2 or "atteinte" in nc2 or "%" in nc3:
                            data["membres"][nom]["pct"] = get_vals(nr)

        # Calcule les % manquants
        for nom in ["Katy", "Nesrine", "Julien"]:
            if not data["membres"][nom]["pct"]:
                pct = {}
                for m in MOIS:
                    g = data["membres"][nom]["goals"].get(m, 0)
                    r = data["membres"][nom]["realise"].get(m, 0)
                    pct[m] = round(r / g * 100, 2) if g > 0 else 0
                data["membres"][nom]["pct"] = pct

        if not data["equipe"]["pct"]:
            pct = {}
            for m in MOIS:
                g = data["equipe"]["goals"].get(m, 0)
                r = data["equipe"]["realise"].get(m, 0)
                pct[m] = round(r / g * 100, 2) if g > 0 else 0
            data["equipe"]["pct"] = pct

        return jsonify({"success": True, "data": data, "mois": MOIS})

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/raw")
def get_raw():
    try:
        rows = fetch_csv()
        return jsonify({"rows": rows[:60]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Dashboard API - Team Katy"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
