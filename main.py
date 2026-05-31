import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from database import init_db, DB_PATH
from repository import SummaryRepository
from services.processor import start_processing_thread

load_dotenv()

app = Flask(__name__)
CORS(app)

db_path = os.environ.get("DATABASE_PATH", DB_PATH)
init_db(db_path)


@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.post("/api/v1/summaries")
def submit_filing():
    body = request.get_json(silent=True)
    if not body or not body.get("url"):
        return jsonify({"error": "Request body must contain a 'url' field."}), 400

    filing_url = body["url"].strip()
    if not filing_url.startswith("http"):
        return jsonify({"error": "Invalid URL."}), 400

    repo = SummaryRepository(db_path)
    summary = repo.create(filing_url=filing_url)
    start_processing_thread(summary_id=summary["id"], filing_url=filing_url, db_path=db_path)

    return jsonify({
        "id": summary["id"],
        "status": "pending",
        "message": f"Filing submitted (job ID: {summary['id']}). Poll GET /api/v1/summaries/{summary['id']} for status.",
    }), 202


@app.get("/api/v1/summaries")
def list_summaries():
    try:
        page = int(request.args.get("page", 1))
        page_size = min(int(request.args.get("page_size", 20)), 100)
    except ValueError:
        return jsonify({"error": "page and page_size must be integers."}), 400

    repo = SummaryRepository(db_path)
    items, total = repo.list_all(page=page, page_size=page_size)
    return jsonify({"items": items, "total": total, "page": page, "page_size": page_size})


@app.get("/api/v1/summaries/<int:summary_id>")
def get_summary(summary_id: int):
    repo = SummaryRepository(db_path)
    summary = repo.get_by_id(summary_id)
    if not summary:
        return jsonify({"error": f"Summary with id={summary_id} not found."}), 404
    return jsonify(summary)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
