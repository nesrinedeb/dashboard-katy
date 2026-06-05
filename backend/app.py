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
    for ch in ["€", "%", "\xa0", "\u202f", "\u00a0", "\u20ac"]:
        v = v.replace(ch, "")
    # Supprime les espaces (séparateurs de milliers: "1 144" -> "1144")
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

        # 1. Trouve la ligne des mois et leurs indices de colonnes
        mois_cols = {}
        for row in rows:
            for j, cell in enumerate(row):
                if cell.strip() == "Janvier":
                    for k, cc in enumerate(row):
                        cc_clean = cc.strip()
                        if cc_clean in MOIS:
                            mois_cols[cc_clean] = k
                    break
            if mois_cols:
                break

        def vals(row):
            return {m: parse_value(row[idx]) if idx < len(row) else 0
                    for m, idx in mois_cols.items()}

        data = {
            "equipe":  {"goals": zero(), "realise": zero(), "pct": zero()},
            "membres": {
                "Katy":    {"goals": zero(), "realise": zero(), "pct": zero()},
                "Nesrine": {"goals": zero(), "realise": zero(), "pct": zero()},
                "Julien":  {"goals": zero(), "realise": zero(), "pct": zero()},
            }
        }

        # 2. Parcours toutes les lignes
        for i, row in enumerate(rows):
            if not row:
                continue

            # Nettoie chaque cellule pour comparaison
            cells = [c.strip() for c in row]

            # ── ÉQUIPE ──
            # Ligne: ["", "Total Best MRR", "Team", "Goals", v1, v2...]
            if len(cells) > 3 and "Total Best MRR" in cells and "Team" in cells:
                idx = cells.index("Team")
                type_cell = cells[idx + 1] if idx + 1 < len(cells) else ""
                if "Goals" in type_cell or "Budget" in type_cell:
                    data["equipe"]["goals"] = vals(row)
                elif "Réalis" in type_cell:
                    data["equipe"]["realise"] = vals(row)
                elif "%" in type_cell or "Atteinte" in type_cell:
                    data["equipe"]["pct"] = vals(row)

            # Ligne suite équipe (Réalisé et % sont sur lignes séparées sans "Total Best MRR")
            # Format: ["", "", "", "Réalisé ", v1, v2...] ou ["", "", "", "%", v1, v2...]
            if len(cells) > 3 and cells[0] == "" and cells[1] == "" and cells[2] == "":
                type_cell = cells[3] if len(cells) > 3 else ""
                # Vérifie que c'est bien une ligne de données équipe (ligne juste après Total Best MRR)
                # en regardant si les valeurs correspondent à des montants d'équipe
                if "Réalis" in type_cell:
                    v = vals(row)
                    # Prend les valeurs les plus grandes comme étant l'équipe
                    if any(val > 500 for val in v.values()):
                        data["equipe"]["realise"] = v
                elif type_cell == "%" or "Atteinte" in type_cell:
                    data["equipe"]["pct"] = vals(row)

            # ── MEMBRES ──
            for nom in ["Katy", "Nesrine", "Julien"]:
                # Ligne: ["", "", "Katy", "Réalisé", v1, v2...] 
                # ou:    ["", "", "Nesrine", "Goals", v1, v2...]
                if nom in cells:
                    idx = cells.index(nom)
                    type_cell = cells[idx + 1] if idx + 1 < len(cells) else ""
                    if "Goals" in type_cell or "Budget" in type_cell:
                        data["membres"][nom]["goals"] = vals(row)
                    elif "Réalis" in type_cell:
                        data["membres"][nom]["realise"] = vals(row)
                    elif "%" in type_cell or "Atteinte" in type_cell:
                        data["membres"][nom]["pct"] = vals(row)
                    # Cherche les lignes suivantes pour goals/réalisé/%
                    for nr in rows[i+1:i+4]:
                        if not nr:
                            continue
                        nc = [c.strip() for c in nr]
                        # Stop si on tombe sur un autre membre
                        if any(other in nc for other in ["Katy","Nesrine","Julien"] if other != nom):
                            break
                        # Cherche le type dans les colonnes proches du nom
                        for k2, cell2 in enumerate(nc):
                            if "Goals" in cell2 or "Budget" in cell2:
                                if not data["membres"][nom]["goals"] or all(v == 0 for v in data["membres"][nom]["goals"].values()):
                                    data["membres"][nom]["goals"] = vals(nr)
                            elif "Réalis" in cell2:
                                if not data["membres"][nom]["realise"] or all(v == 0 for v in data["membres"][nom]["realise"].values()):
                                    data["membres"][nom]["realise"] = vals(nr)
                            elif cell2 == "%" or "Atteinte" in cell2:
                                if not data["membres"][nom]["pct"] or all(v == 0 for v in data["membres"][nom]["pct"].values()):
                                    data["membres"][nom]["pct"] = vals(nr)

        # 3. Calcule les % manquants
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
