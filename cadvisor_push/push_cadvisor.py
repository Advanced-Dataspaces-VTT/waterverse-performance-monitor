import yaml
import requests
import time
import os
import re
import sys

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

HOSTNAME = os.environ.get('HOSTNAME')
CADVISOR_METRICS_URL = os.environ.get('HOST')
PUSHGATEWAY_URL = os.environ.get('PUSHGW')
INTERVAL = int(os.environ.get('INTERVAL'))

def load_config():
    with open("/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    return config.get("allowed_metrics", [])

ALLOWED_METRICS = set(load_config())

def remove_timestamp(metric):
    return re.sub(r'\s\d+$', '', metric)

def filter_empty_labels(metric: str) -> str:
    """Remove empty labels."""
    metric = re.sub(r'([a-zA-Z0-9_-]+="",)', '', metric)
    return metric

def escape_prometheus_labels(metric: str) -> str:
    return re.sub(r'(["\\])', r'\\\1', metric)

def filter_metrics(metric_line):
    """Check if the metric should be included."""
    for allowed in ALLOWED_METRICS:
        if metric_line.startswith(allowed):
            return True
    return False

while True:
    count = 0
    failcount = 0
    print(f"scrape metrics from {CADVISOR_METRICS_URL}")
    try:
        response = requests.get(CADVISOR_METRICS_URL)
        if response.status_code == 200:
            if response.text.startswith("# HELP") or response.text.startswith("# TYPE"):
                metrics_lines = response.text.splitlines()
                filtered_metrics = []
                for line in metrics_lines:
                    if filter_metrics(line):
                        if not re.search(r' \S+$', line):
                            print(f"Skipping line with no value: {line}")
                        else:
                            line = remove_timestamp(line)
                            line = filter_empty_labels(line)
                            filtered_metrics.append(line)
                metrics_payload = '\n'.join(filtered_metrics) + '\n'
                print(f"payload: {metrics_payload}")
                push_url = f"{PUSHGATEWAY_URL}/instance/{HOSTNAME}"
                push_response = requests.post(
                    push_url,
                    data=metrics_payload.encode('utf-8'),
                    headers={'Content-Type': 'text/plain'}
                )
                if push_response.status_code == 200:
                    count = count + 1
                else:
                    failcount = failcount + 1
            else:
                print("Warning: Retrieved content is not valid Prometheus metrics!")
                print(response.text[:500])  # Print first 500 characters for debugging
        else:
            print(f"Failed to fetch metrics: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    # Push every 30 seconds
    print(f"{count} metrics pushed to {PUSHGATEWAY_URL} while {failcount} failed")
    time.sleep(INTERVAL)
