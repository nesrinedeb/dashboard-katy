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
    val = val.strip()
    val = val.replace("€", "").replace("%", "").replace("\xa0", "")
    val = val.replace("\u202f", "").replace(" ", "").replace("\u00a0", "")
    val = val.replace(",", ".")
    # Gère les espaces comme séparateurs de milliers (1 055 -> 1055)
    val = "".join(val.split())
    try:
        return float(val)
    except:
        return 0

def fetch_csv():
    response = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=15)
    response.encoding = "utf-8"
    reader = csv.reader(io.StringIO(response.text))
    rows = [row for row in reader]
    return rows

@app.route("/api/data")
def get_data():
    try:
        rows = fetch_csv()

        # On cherche les lignes clés par leur contenu
        data = {
            "equipe": {
                "goals":   dict.fromkeys(MOIS, 0),
                "realise": dict.fromkeys(MOIS, 0),
                "pct":     dict.fromkeys(MOIS, 0),
            },
            "membres": {
                "Katy":    {"goals": dict.fromkeys(MOIS, 0), "realise": dict.fromkeys(MOIS, 0), "pct": dict.fromkeys(MOIS, 0)},
                "Nesrine": {"goals": dict.fromkeys(MOIS, 0), "realise": dict.fromkeys(MOIS, 0), "pct": dict.fromkeys(MOIS, 0)},
                "Julien":  {"goals": dict.fromkeys(MOIS, 0), "realise": dict.fromkeys(MOIS, 0), "pct": dict.fromkeys(MOIS, 0)},
            },
            "raw_rows": []  # debug temporaire
        }

        # Trouve l'index des colonnes mois (ligne header)
        header_row_idx = None
        mois_cols = {}
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                if "Janvier" in cell or "janvier" in cell.lower():
                    header_row_idx = i
                    # Trouve les positions des mois
                    for k, c in enumerate(row):
                        c_clean = c.strip()
                        if c_clean in MOIS:
                            mois_cols[c_clean] = k
                    break
            if header_row_idx is not None:
                break

        # Ajoute les données brutes pour debug
        data["raw_rows"] = [row[:10] for row in rows[:50]]
        data["header_row"] = header_row_idx
        data["mois_cols"] = mois_cols

        def extract_mois_values(row, cols):
            result = {}
            for mois, idx in cols.items():
                result[mois] = parse_value(row[idx]) if idx < len(row) else 0
            return result

        # Parcourt toutes les lignes pour trouver les données
        current_member = None
        for i, row in enumerate(rows):
            if not row or len(row) < 3:
                continue

            # Cherche le nom dans les premières colonnes
            row_text = " ".join(row[:4]).lower()

            # Détection membre courant
            for nom in ["Katy", "Nesrine", "Julien"]:
                if nom.lower() in row[:3][0].lower() if row[0] else False:
                    current_member = nom
                elif nom.lower() in row[:3][1].lower() if len(row) > 1 and row[1] else False:
                    current_member = nom

            # Equipe - Total Best MRR
            if "total best mrr" in row_text and mois_cols:
                next_rows = rows[i:i+4]
                for nr in next_rows:
                    if not nr or len(nr) < 3:
                        continue
                    nr_text = " ".join(nr[:3]).lower()
                    if "réalis" in nr_text or "realise" in nr_text or "r\u00e9alis" in nr_text:
                        data["equipe"]["realise"] = extract_mois_values(nr, mois_cols)
                    elif "budget" in nr_text or "goals" in nr_text:
                        data["equipe"]["goals"] = extract_mois_values(nr, mois_cols)
                    elif "atteinte" in nr_text or "%" in nr_text:
                        data["equipe"]["pct"] = extract_mois_values(nr, mois_cols)

            # Membres individuels - cherche par nom
            for nom in ["Katy", "Nesrine", "Julien"]:
                if nom.lower() in row_text and mois_cols:
                    # Cherche dans les lignes suivantes
                    for nr in rows[i:i+5]:
                        if not nr or len(nr) < 3:
                            continue
                        nr_text = " ".join(nr[:4]).lower()
                        if ("réalis" in nr_text or "r\u00e9alis" in nr_text) and nom.lower() in nr_text:
                            data["membres"][nom]["realise"] = extract_mois_values(nr, mois_cols)
                        elif "budget" in nr_text and nom.lower() in nr_text:
                            data["membres"][nom]["goals"] = extract_mois_values(nr, mois_cols)
                        elif "atteinte" in nr_text and nom.lower() in nr_text:
                            data["membres"][nom]["pct"] = extract_mois_values(nr, mois_cols)

        return jsonify({"success": True, "data": data, "mois": MOIS})

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/raw")
def get_raw():
    """Route de debug pour voir le CSV brut"""
    try:
        rows = fetch_csv()
        return jsonify({"rows": [row for row in rows[:60]]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Dashboard API - Team Katy"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
