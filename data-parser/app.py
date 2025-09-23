from flask import Flask, request, jsonify
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from datetime import datetime, timezone, timedelta
import requests
import os
import uuid

app = Flask(__name__)

PROM_URL = os.getenv("PROM_URL", "http://localhost:9090")


@app.route("/events", methods=["GET"])
def endpoint_events():
    uuids = get_all_uuids()
    return jsonify(uuids)

@app.route("/event", methods=["POST"])
def endpoint_getevent():
    data = request.get_json()
    uuid = data.get("uuid")
    print(f"endpoint_getevent {data}")
    metrics = data.get("metrics")

    if uuid is None or metrics is None:
        return jsonify({"error": "Missing required fields"}), 400
    skip_zeros = True

    start_ts = query_event_backwards(uuid, "start", 720, step="5s")
    stop_ts = query_event_backwards(uuid, "stop", 720, step="5s")

    if not start_ts or not stop_ts or stop_ts <= start_ts:
        return jsonify({"error": f"Could not find valid start/stop timestamps for UUID {uuid}"}), 400

    metric_values = query_metrics_for_event(metrics, start_ts, stop_ts)

    filtered_metrics = [
        metric for metric in metric_values
        if metric.get("name") is not None and metric.get("exported_instance") is not None
    ]


    task_dict = {}
    for metric_info in metrics:
        metric_name = metric_info["metric"]
        fields_order = [f for f in metric_info["fields"] if f != "values"]

        for metric in filtered_metrics:
            if metric.get("metric") and metric["metric"] != metric_name:
                #print(metric["metric"])
                continue

            task_parts = [str(metric.get(f, "")) for f in fields_order]
            task_name = ":".join(task_parts)
            # Use a tuple (metric_name, task_name) as the key
            dict_key = (metric_name, task_name)

            values = [{"timestamp": ts, "value": val} for ts, val in metric.get("values", [])]

            if dict_key in task_dict:
                task_dict[dict_key].extend(values)
            else:
                task_dict[dict_key] = values
    parsed_metrics = []
    for (metric_name, task_name), vals in task_dict.items():
        # Sort by timestamp
        vals_sorted = sorted(vals, key=lambda x: x["timestamp"])

        # Compute delta
        if vals_sorted:
            delta = vals_sorted[-1]["value"] - vals_sorted[0]["value"]
        else:
            delta = None  # handle empty values

        parsed_metrics.append({
            "metric": metric_name,
            "task": task_name,
            "values": vals_sorted,
            "delta": delta
        })
    print("UUID,duration,metric,instance,value")
    parsed_metrics.sort(key=lambda x: x["task"])
    if skip_zeros:
        parsed_metrics = [m for m in parsed_metrics if m["delta"] != 0]

    return parsed_metrics, 200

def get_all_uuids():
    url = f"{PROM_URL}/api/v1/label/uuid/values"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])

def query_event_backwards(uuid, ev_type, window_minutes=10, max_hours=960, step="60s"):
    """
    Queries Prometheus for a specific event type for a UUID,
    scanning backwards in time in chunks of window_minutes until a value is found
    or max_hours is reached.
    """
    now = datetime.now(timezone.utc)
    end_ts = int(now.timestamp())
    start_ts = end_ts - window_minutes * 60
    max_lookback = int((now - timedelta(hours=max_hours)).timestamp())

    while end_ts > max_lookback:
        q_url = f"{PROM_URL.rstrip('/')}/api/v1/query_range"
        query = f'event_record{{uuid="{uuid}", type="{ev_type}"}}'
        params = {
            "query": query,
            "start": start_ts,
            "end": end_ts,
            "step": step
        }
        r = requests.get(q_url, params=params, timeout=30)
        r.raise_for_status()
        results = r.json().get("data", {}).get("result", [])
        if results:
            type = results[0]["metric"].get("type")
            if (type == ev_type):
                ts_str = results[0]["values"][0][1]
                if ts_str:
                    return int(ts_str)
        # move 10 minutes back
        end_ts = start_ts
        start_ts = max(start_ts - window_minutes * 60, max_lookback)
    return None

def query_metrics_for_event(metrics_config, start_ts, stop_ts):
    """
    Query Prometheus for all metrics between start and stop timestamps.
    Returns a list of dicts with only the requested fields.
    """
    all_metrics = []

    for metric_info in metrics_config:
        metric_name = metric_info["metric"]
        keep_fields = set(metric_info["fields"])

        q_url = f"{PROM_URL.rstrip('/')}/api/v1/query_range"
        params = {
            "query": metric_name,
            "start": start_ts,
            "end": stop_ts,
            "step": "1s"
        }
        r = requests.get(q_url, params=params, timeout=30)
        r.raise_for_status()
        results = r.json().get("data", {}).get("result", [])

        for series in results:
            metric_entry = {}
            metric_labels = series.get("metric", {})
            metric_entry["metric"] = metric_name
            # Keep only requested fields
            for field in keep_fields:
                if field in metric_labels:
                    metric_entry[field] = metric_labels[field]

            # Always add values if requested
            if "values" in keep_fields:
                values = []
                for ts, val in series.get("values", []):
                    try:
                        values.append((float(ts), float(val)))
                    except:
                        continue
                metric_entry["values"] = values

            all_metrics.append(metric_entry)

    return all_metrics


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
