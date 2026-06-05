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

        # 1. Trouve les colonnes des mois
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

        # 2. Trouve la ligne "Total Best MRR / Team / Goals" (première occurrence sans #REF!)
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row]
            if "Total Best MRR" in cells and "Team" in cells and "Goals" in cells:
                # Vérifie que ce ne sont pas des #REF!
                if parse_value(row[mois_cols["Janvier"]]) > 0 or parse_value(row[mois_cols["Février"]]) > 0:
                    data["equipe"]["goals"] = vals(row)
                    if i+1 < len(rows): data["equipe"]["realise"] = vals(rows[i+1])
                    if i+2 < len(rows): data["equipe"]["pct"] = vals(rows[i+2])
                    break

        # 3. Trouve chaque membre par son nom en colonne 2
        #    puis lit les lignes suivantes jusqu'au prochain membre
        MEMBRES = ["Katy", "Nesrine", "Julien"]
        
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row]
            if len(cells) < 4:
                continue
            
            nom = cells[2] if len(cells) > 2 else ""
            type_cel = cells[3] if len(cells) > 3 else ""
            
            if nom in MEMBRES:
                # Ligne courante : peut être Goals ou Réalisé directement
                if "Réalis" in type_cel:
                    data["membres"][nom]["realise"] = vals(row)
                    # Ligne suivante peut être %
                    if i+1 < len(rows):
                        nc = [c.strip() for c in rows[i+1]]
                        if len(nc) > 3 and nc[3] == "%":
                            data["membres"][nom]["pct"] = vals(rows[i+1])
                            
                elif "Goals" in type_cel or "Budget" in type_cel:
                    data["membres"][nom]["goals"] = vals(row)
                    # Cherche Réalisé et % dans les lignes suivantes
                    for j in range(i+1, min(i+4, len(rows))):
                        nr = rows[j]
                        nc = [c.strip() for c in nr]
                        if len(nc) < 4:
                            continue
                        # Stop si on trouve un autre membre
                        if nc[2] in MEMBRES and nc[2] != nom:
                            break
                        if "Réalis" in nc[3]:
                            data["membres"][nom]["realise"] = vals(nr)
                        elif nc[3] == "%":
                            data["membres"][nom]["pct"] = vals(nr)

        # 4. Calcule les % manquants
        for nom in MEMBRES:
            if all(v == 0 for v in data["membres"][nom]["pct"].values()):
                data["membres"][nom]["pct"] = {
                    m: round(data["membres"][nom]["realise"].get(m, 0) /
                             data["membres"][nom]["goals"].get(m, 0) * 100, 2)
                    if data["membres"][nom]["goals"].get(m, 0) > 0 else 0
                    for m in MOIS
                }
        if all(v == 0 for v in data["equipe"]["pct"].values()):
            data["equipe"]["pct"] = {
                m: round(data["equipe"]["realise"].get(m, 0) /
                         data["equipe"]["goals"].get(m, 0) * 100, 2)
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
