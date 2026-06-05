from flask import Flask, jsonify
from flask_cors import CORS
import requests
import csv
import io

app = Flask(__name__)
CORS(app, origins=["https://dashboard-katy-1.onrender.com"])

GOOGLE_SHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRjwPUN21RUS6QX3hVUd7rP7t0MZ52hOVyMZNmRHdrR75gBD8FOtLnCcYwbS9GtvcDusIpliN0W-gzI/pub?output=csv&gid=792570627"
MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]

def parse_value(val):
    if not val or not val.strip():
        return 0
    v = val.strip()
    for ch in ["€", "%", "\xa0", "\u202f", "\u00a0", "\u20ac", " "]:
        v = v.replace(ch, "")
    v = v.replace(",", ".")
    try:
        return float(v)
    except:
        return 0

def fetch_csv():
    r = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=15)
    r.encoding = "utf-8"
    return list(csv.reader(io.StringIO(r.text)))

def c(s):
    return (s or "").strip().lower()

@app.route("/api/data")
def get_data():
    try:
        rows = fetch_csv()

        # 1. Trouve les colonnes des mois
        mois_cols = {}
        for row in rows:
            for j, cell in enumerate(row):
                if "Janvier" in cell:
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

        # 2. Parcours ligne par ligne
        for i, row in enumerate(rows):
            if len(row) < 4:
                continue

            # Concatène les 5 premières cellules pour la recherche
            txt = " | ".join(c(row[k]) for k in range(min(5, len(row))))

            # ── ÉQUIPE (Total Best MRR) ──
            if "total best mrr" in txt:
                # La ligne courante peut avoir goals/réalisé/% en col 2 ou 3
                col_type = c(row[2]) + " " + c(row[3])
                if "goals" in col_type or "budget" in col_type:
                    data["equipe"]["goals"] = vals(row)
                elif "réalis" in col_type or "r\u00e9alis" in col_type:
                    data["equipe"]["realise"] = vals(row)
                elif "%" in col_type or "atteinte" in col_type:
                    data["equipe"]["pct"] = vals(row)

                # Cherche les 3 lignes suivantes pour compléter
                for nr in rows[i+1:i+4]:
                    if len(nr) < 3:
                        continue
                    nt = " | ".join(c(nr[k]) for k in range(min(5, len(nr))))
                    if "total best mrr" in nt:
                        continue
                    ntype = c(nr[2]) + " " + (c(nr[3]) if len(nr) > 3 else "")
                    if "goals" in ntype or "budget" in ntype:
                        data["equipe"]["goals"] = vals(nr)
                    elif "réalis" in ntype or "r\u00e9alis" in ntype:
                        data["equipe"]["realise"] = vals(nr)
                    elif "%" in ntype or "atteinte" in ntype:
                        data["equipe"]["pct"] = vals(nr)

            # ── MEMBRES ──
            for nom in ["Katy", "Nesrine", "Julien"]:
                n = nom.lower()
                # Le nom peut être en col 1, 2 ou 3
                nom_col = -1
                for k in range(min(4, len(row))):
                    if n in c(row[k]):
                        nom_col = k
                        break
                if nom_col == -1:
                    continue

                # Le type (Goals/Réalisé/%) est dans la colonne suivante
                type_col = nom_col + 1
                if type_col >= len(row):
                    continue
                col_type = c(row[type_col])

                if "goals" in col_type or "budget" in col_type:
                    data["membres"][nom]["goals"] = vals(row)
                elif "réalis" in col_type or "r\u00e9alis" in col_type:
                    data["membres"][nom]["realise"] = vals(row)
                elif "%" in col_type or "atteinte" in col_type:
                    data["membres"][nom]["pct"] = vals(row)
                else:
                    # Cherche dans les lignes suivantes
                    for nr in rows[i+1:i+4]:
                        if len(nr) < 3:
                            continue
                        # Stop si autre membre détecté
                        other_found = any(
                            other.lower() in c(nr[k])
                            for other in ["Katy","Nesrine","Julien"] if other != nom
                            for k in range(min(3, len(nr)))
                        )
                        if other_found:
                            break
                        ntype = c(nr[2]) + " " + (c(nr[3]) if len(nr) > 3 else "")
                        if "goals" in ntype or "budget" in ntype:
                            data["membres"][nom]["goals"] = vals(nr)
                        elif "réalis" in ntype or "r\u00e9alis" in ntype:
                            data["membres"][nom]["realise"] = vals(nr)
                        elif "%" in ntype or "atteinte" in ntype:
                            data["membres"][nom]["pct"] = vals(nr)

        # 3. Calcule les % manquants
        for nom in ["Katy", "Nesrine", "Julien"]:
            if all(v == 0 for v in data["membres"][nom]["pct"].values()):
                data["membres"][nom]["pct"] = {
                    m: round(data["membres"][nom]["realise"][m] / data["membres"][nom]["goals"][m] * 100, 2)
                    if data["membres"][nom]["goals"][m] > 0 else 0
                    for m in MOIS
                }
        if all(v == 0 for v in data["equipe"]["pct"].values()):
            data["equipe"]["pct"] = {
                m: round(data["equipe"]["realise"][m] / data["equipe"]["goals"][m] * 100, 2)
                if data["equipe"]["goals"][m] > 0 else 0
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
