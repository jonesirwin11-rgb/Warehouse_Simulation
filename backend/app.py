from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from audit import StaticStackAudit
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_FOLDER = os.path.join(BASE_DIR, "dashboard", "static")
TEMPLATE_FOLDER = os.path.join(BASE_DIR, "dashboard", "templates")

app = Flask(__name__, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
CORS(app)  # Allow frontend to poll this API

@app.route('/')
def index():
    return render_template("index.html")

# ==========================================
# Phase 7 - Live Inventory Logic
# ==========================================
LIVE_INVENTORY_STATE = {
    "staged_boxes": 0,
    "truck_exit_events": 0,
    "staging_arrival_events": 0,
    "last_event": None,
    "last_audit": None
}

# In-memory deduplication of events
processed_event_ids = set()

audit_module = StaticStackAudit()

@app.route('/api/events', methods=['POST'])
def handle_event():
    event = request.json
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    quantity = event.get("quantity", 0)

    if not event_id or not event_type:
        return jsonify({"error": "Malformed event payload"}), 400

    # Phase 10: Deduplicate
    if event_id in processed_event_ids:
        print(f"[BACKEND] Ignored duplicate event {event_id}")
        return jsonify({"status": "duplicate_ignored"}), 200

    processed_event_ids.add(event_id)

    # Process counts based on the strict architectural rules
    if event_type == "STAGING_ARRIVAL_EVENT":
        LIVE_INVENTORY_STATE["staging_arrival_events"] += quantity
        LIVE_INVENTORY_STATE["staged_boxes"] += quantity
        print(f"[BACKEND] Staging count increased +{quantity} | Staged Total: {LIVE_INVENTORY_STATE['staged_boxes']}")
        
    elif event_type == "TRUCK_EXIT_EVENT":
        LIVE_INVENTORY_STATE["truck_exit_events"] += quantity
        print(f"[BACKEND] Truck Exit observed +{quantity} | Exited Total: {LIVE_INVENTORY_STATE['truck_exit_events']}")

    LIVE_INVENTORY_STATE["last_event"] = event_id
    
    return jsonify({"status": "success", "live_state": LIVE_INVENTORY_STATE}), 200


@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    return jsonify(LIVE_INVENTORY_STATE), 200


@app.route('/api/audit', methods=['POST'])
def trigger_audit():
    # 1. Run inference on the latest camera 2 frame
    estimation = audit_module.estimate_count()
    if "error" in estimation:
        return jsonify(estimation), 400

    # 2. Reconcile with Phase 10 Logic
    live_count = LIVE_INVENTORY_STATE["staged_boxes"]
    audit_count = estimation["estimated_count"]
    
    reconciliation_result = audit_module.reconcile(live_count, audit_count)
    reconciliation_result["confidence"] = estimation["confidence"]

    LIVE_INVENTORY_STATE["last_audit"] = reconciliation_result

    print(f"[AUDIT] Expected: {live_count} | Estimated: {audit_count} -> {reconciliation_result['status']}")

    return jsonify(reconciliation_result), 200


if __name__ == '__main__':
    # Phase 0: Make sure data directory exists for the latest_staging.jpg
    os.makedirs("data", exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
