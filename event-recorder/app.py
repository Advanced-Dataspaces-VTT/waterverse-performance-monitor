from flask import Flask, request, jsonify
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import requests
import os
import uuid

app = Flask(__name__)

PUSHGATEWAY_HOST = os.getenv("PUSHGATEWAY_HOST", "localhost")
PUSHGATEWAY_PORT = os.getenv("PUSHGATEWAY_PORT", 8080)
HOSTNAME = os.getenv("HOSTNAME", "localhost")
JOB_NAME = "event_recorder"

event_store = {}

@app.route("/start", methods=["POST"])
def start_event():
    print("start_event")
    data = request.get_json()
    start_time = data.get("timestamp")
    event_id = str(uuid.uuid4())

    if not event_id or start_time is None:
        return jsonify({"error": "Missing required fields"}), 400
    push_event(event_id, start_time, "start")

    return jsonify({"uuid": event_id})


@app.route("/stop", methods=["POST"])
def stop_event():
    print("stop_event")
    data = request.get_json()
    event_id = data.get("uuid")
    stop_time = data.get("timestamp")

    if event_id is None or stop_time is None:
        return jsonify({"error": "Missing required fields"}), 400

    push_event(event_id, stop_time, "stop")

    return jsonify({"message": "Event recorded"}), 200

def push_event(event_id, timestamp, event_type):
    registry = CollectorRegistry()
    g = Gauge(
        'event_record',
        'Event timestamp',
        ['uuid', 'event_timestamp', 'type'],
        registry=registry
    )
    g.labels(uuid=event_id, event_timestamp=str(timestamp), type=event_type).set(timestamp)

    pushgateway_address = f"{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}"
    try:
        push_to_gateway(
            gateway=f"{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}",
            job="pushgateway",
            registry=registry,
            grouping_key={"instance": HOSTNAME}
        )
        print(f"Pushed event {event_id} at {timestamp} to Pushgateway")
    except Exception as e:
        print(f"Push failed: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
