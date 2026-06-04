from flask import Flask, jsonify
from flask_cors import CORS
import requests
import csv
import io

app = Flask(__name__)
CORS(app)

# ⚠️ Remplace ce lien par ton lien CSV Google Sheets
GOOGLE_SHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRjwPUN21RUS6QX3hVUd7rP7t0MZ52hOVyMZNmRHdrR75gBD8FOtLnCcYwbS9GtvcDusIpliN0W-gzI/pub?output=csv"

MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]

def parse_value(val):
    """Convertit une valeur string en float (gère €, %, virgules)"""
    if not val or val.strip() == "":
        return 0
    val = val.strip().replace("€", "").replace("%", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(val)
    except:
        return 0

def fetch_and_parse():
    response = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=10)
    response.encoding = "utf-8"
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    return rows

@app.route("/api/data")
def get_data():
    try:
        rows = fetch_and_parse()

        data = {
            "equipe": {"goals": {}, "realise": {}, "pct": {}},
            "membres": {
                "Katy":    {"realise": {}, "goals": {}, "pct": {}, "produits": {}},
                "Nesrine": {"realise": {}, "goals": {}, "pct": {}, "produits": {}},
                "Julien":  {"realise": {}, "goals": {}, "pct": {}, "produits": {}}
            }
        }

        current_member = None
        PRODUITS = ["Pack Local", "Mini to Classic", "Boost'in", "Shoot'in", "Autres", "Seeble", "Site Web"]

        for row in rows:
            if len(row) < 3:
                continue

            col0 = row[0].strip() if row[0] else ""
            col1 = row[1].strip() if len(row) > 1 else ""
            col2 = row[2].strip() if len(row) > 2 else ""

            # Détection section équipe
            if col1 == "Team":
                if col2 == "Goals":
                    for i, mois in enumerate(MOIS):
                        data["equipe"]["goals"][mois] = parse_value(row[3+i]) if len(row) > 3+i else 0
                elif col2 == "Réalisé":
                    for i, mois in enumerate(MOIS):
                        data["equipe"]["realise"][mois] = parse_value(row[3+i]) if len(row) > 3+i else 0
                elif col2 == "%":
                    for i, mois in enumerate(MOIS):
                        data["equipe"]["pct"][mois] = parse_value(row[3+i]) if len(row) > 3+i else 0

            # Détection membres (résumé)
            elif col1 in ["Katy", "Nesrine", "Julien"]:
                current_member = col1
                if col2 == "Réalisé":
                    for i, mois in enumerate(MOIS):
                        data["membres"][col1]["realise"][mois] = parse_value(row[3+i]) if len(row) > 3+i else 0
                elif col2 == "Goals":
                    for i, mois in enumerate(MOIS):
                        data["membres"][col1]["goals"][mois] = parse_value(row[3+i]) if len(row) > 3+i else 0
                elif col2 == "%":
                    for i, mois in enumerate(MOIS):
                        data["membres"][col1]["pct"][mois] = parse_value(row[3+i]) if len(row) > 3+i else 0

            # Suite des lignes d'un membre (Goals / % sur lignes suivantes)
            elif col0 in ["Katy", "Nesrine", "Julien"]:
                current_member = col0
                if col1 == "Réalisé":
                    for i, mois in enumerate(MOIS):
                        data["membres"][col0]["realise"][mois] = parse_value(row[2+i]) if len(row) > 2+i else 0
                elif col1 == "Goals":
                    for i, mois in enumerate(MOIS):
                        data["membres"][col0]["goals"][mois] = parse_value(row[2+i]) if len(row) > 2+i else 0
                elif col1 == "%":
                    for i, mois in enumerate(MOIS):
                        data["membres"][col0]["pct"][mois] = parse_value(row[2+i]) if len(row) > 2+i else 0

            # Produits par membre
            elif current_member and col1 in PRODUITS:
                produit = col1
                if produit not in data["membres"][current_member]["produits"]:
                    data["membres"][current_member]["produits"][produit] = {}
                for i, mois in enumerate(MOIS):
                    data["membres"][current_member]["produits"][produit][mois] = parse_value(row[2+i]) if len(row) > 2+i else 0

        return jsonify({"success": True, "data": data, "mois": MOIS})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Dashboard API - Team Katy"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
