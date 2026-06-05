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

        # 2. Cherche chaque ligne par son contenu exact
        # D'après le CSV brut, voici la structure :
        # Ligne equipe goals:   cells[1]="Total Best MRR", cells[2]="Team", cells[3]="Goals"
        # Ligne equipe realise: cells[3]="Réalisé " (avec espace), cells[1]="" cells[2]=""
        # Ligne equipe %:       cells[3]="%"
        # Ligne Katy realise:   cells[2]="Katy", cells[3]="Réalisé"
        # Ligne Nesrine goals:  cells[2]="Nesrine", cells[3]="Goals"
        # Ligne Nesrine realise: cells[2]="", cells[3]="Réalisé" (ligne APRES Nesrine Goals)
        # Ligne Julien goals:   cells[2]="Julien", cells[3]="Goals"
        # Ligne Julien realise: cells[2]="", cells[3]="Réalisé" (ligne APRES Julien Goals)

        equipe_goals_row = None

        for i, row in enumerate(rows):
            if len(row) < 4:
                continue
            c1 = row[1].strip()
            c2 = row[2].strip()
            c3 = row[3].strip()

            # ÉQUIPE GOALS : "Total Best MRR" + "Team" + "Goals"
            if c1 == "Total Best MRR" and c2 == "Team" and c3 == "Goals":
                # Vérifie que les valeurs ne sont pas #REF!
                test_val = parse_value(row[mois_cols["Janvier"]]) if "Janvier" in mois_cols else 0
                test_val2 = parse_value(row[mois_cols["Février"]]) if "Février" in mois_cols else 0
                if test_val > 0 or test_val2 > 0:
                    equipe_goals_row = i
                    data["equipe"]["goals"] = vals(row)

            # ÉQUIPE RÉALISÉ : ligne juste après equipe goals
            if equipe_goals_row is not None and i == equipe_goals_row + 1:
                data["equipe"]["realise"] = vals(row)

            # ÉQUIPE % : ligne juste après equipe réalisé
            if equipe_goals_row is not None and i == equipe_goals_row + 2:
                data["equipe"]["pct"] = vals(row)

            # KATY RÉALISÉ : cells[2]="Katy", cells[3]="Réalisé"
            if c2 == "Katy" and "Réalis" in c3:
                data["membres"]["Katy"]["realise"] = vals(row)
                # Ligne suivante = %
                if i+1 < len(rows) and len(rows[i+1]) > 3:
                    nc3 = rows[i+1][3].strip()
                    if nc3 == "%":
                        data["membres"]["Katy"]["pct"] = vals(rows[i+1])

            # NESRINE GOALS : cells[2]="Nesrine", cells[3]="Goals"
            if c2 == "Nesrine" and ("Goals" in c3 or "Budget" in c3):
                data["membres"]["Nesrine"]["goals"] = vals(row)
                # Ligne i+1 = Réalisé
                if i+1 < len(rows) and len(rows[i+1]) > 3:
                    if "Réalis" in rows[i+1][3]:
                        data["membres"]["Nesrine"]["realise"] = vals(rows[i+1])
                # Ligne i+2 = %
                if i+2 < len(rows) and len(rows[i+2]) > 3:
                    if rows[i+2][3].strip() == "%":
                        data["membres"]["Nesrine"]["pct"] = vals(rows[i+2])

            # JULIEN GOALS : cells[2]="Julien", cells[3]="Goals"
            if c2 == "Julien" and ("Goals" in c3 or "Budget" in c3):
                data["membres"]["Julien"]["goals"] = vals(row)
                # Ligne i+1 = Réalisé
                if i+1 < len(rows) and len(rows[i+1]) > 3:
                    if "Réalis" in rows[i+1][3]:
                        data["membres"]["Julien"]["realise"] = vals(rows[i+1])
                # Ligne i+2 = %
                if i+2 < len(rows) and len(rows[i+2]) > 3:
                    if rows[i+2][3].strip() == "%":
                        data["membres"]["Julien"]["pct"] = vals(rows[i+2])

            # KATY GOALS : pas de ligne Goals explicite pour Katy
            # On déduit depuis l'objectif équipe et les autres
            # Mais on peut chercher une ligne avec goals pour Katy si elle existe

        # 3. Goals Katy = pas dans le CSV directement, on utilise l'objectif individuel
        # D'après le CSV, Katy n'a pas de ligne Goals propre dans le premier bloc
        # On va chercher dans le second bloc ou calculer
        # Pour l'instant, si goals Katy = 0, on met les goals équipe / 3 comme approximation
        # MAIS d'abord cherchons si une ligne Katy + Goals existe ailleurs
        for i, row in enumerate(rows):
            if len(row) < 4:
                continue
            c2 = row[2].strip()
            c3 = row[3].strip()
            if c2 == "Katy" and ("Goals" in c3 or "Budget" in c3):
                data["membres"]["Katy"]["goals"] = vals(row)
                break

        # 4. Calcule les % manquants
        for nom in ["Katy", "Nesrine", "Julien"]:
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
