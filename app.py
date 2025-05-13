from flask import Flask, render_template, request, jsonify, redirect
import json
import os
import pyodbc
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Path to store email metadata
METADATA_FILE = "static/special_offer_meta.json"

# Ensure metadata file exists
if not os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, "w") as f:
        json.dump({}, f)

# SQL connection config from .env
conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};" 
    f"SERVER={os.getenv('DB_HOST')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASS')}"
)
cursor = conn.cursor()

def fetch_all_special_offers():
    cursor.execute("""
        WITH LatestOffers AS (
            SELECT
                s.style_id,
                s.style AS product_code,
                COALESCE(NULLIF(s.LONG_DESCRPT, ''), s.DESCRIPTION) AS product_name,
                s.of7 AS bottle_size,
                MAX(b.price) AS price,
                MAX(b.qoh + b.qc) AS available,
                MAX(w.largepicture) AS image,
                'https://www.winehouse.com/shop/' + REPLACE(LTRIM(RTRIM(s.LONG_DESCRPT)), ' ', '-') + '-' + CAST(s.style_id AS VARCHAR) AS product_url
            FROM TB_STYLES s
            JOIN TB_SKUS sk ON sk.style_id = s.style_id
            JOIN TB_SKU_BUCKETS b ON b.sku_id = sk.SKU_ID
            LEFT JOIN web_all_products w ON w.style = s.style
            WHERE s.of20 = 'true'
            GROUP BY s.style_id, s.style, s.LONG_DESCRPT, s.DESCRIPTION, s.of7
        )
        SELECT * FROM LatestOffers
    """)

    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]

    with open(METADATA_FILE, "r") as f:
        meta = json.load(f)

    result = []
    for row in rows:
        item = dict(zip(columns, row))
        style_id = str(item["style_id"])
        if item.get("image"):
            item["image"] = f"https://www.winehouse.com/prodimages/{item['image']}"
        item["email_name"] = meta.get(style_id, {}).get("email_name", "")
        item["email_link"] = meta.get(style_id, {}).get("email_link", "")
        item["style_id"] = style_id  # Ensure style_id is always available for display
        item["product"] = item["product_code"]  # Rename for clarity in template
        item["name"] = item["product_name"]      # Rename for clarity in template
        result.append(item)
    return result

@app.route("/", methods=["GET"])
def index():
    offers = fetch_all_special_offers()
    return render_template("index.html", offers=offers)

@app.route("/add", methods=["POST"])
def add_offer():
    style_id = request.form.get("style_id")
    email_name = request.form.get("email_name")
    email_link = request.form.get("email_link")

    if not style_id or not email_name or not email_link:
        return redirect("/")

    with open(METADATA_FILE, "r") as f:
        meta = json.load(f)

    meta[style_id] = {
        "email_name": email_name,
        "email_link": email_link
    }

    with open(METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)

    return redirect("/")

@app.route("/delete/<style_id>")
def delete_offer(style_id):
    with open(METADATA_FILE, "r") as f:
        meta = json.load(f)
    if style_id in meta:
        del meta[style_id]
    with open(METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)
    return redirect("/")
    
@app.route("/special-offers")
def special_offers_page():
    offers = fetch_all_special_offers()
    # Only show items that have both an email name and email link set
    filtered = [o for o in offers if o.get("email_name") and o.get("email_link")]
    return render_template("special_offers.html", offers=filtered)

if __name__ == "__main__":
    app.run(debug=True, port=5001)