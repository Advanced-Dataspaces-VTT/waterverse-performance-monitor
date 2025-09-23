# Introduction
This is Prometheus performance metric tool to push metrics form Docker environment to main Prometheus server
For GPU measurements you need to install NVidia Container Toolkit

## Overview
This setup consists of two main services:
1. **cAdvisor**: Collects resource usage and performance metrics from Docker containers.
2. **cadvisor_push**: A custom Python-based service that fetches metrics from cAdvisor and pushes selected metrics to Prometheus Pushgateway.
3. **node_exporter**: Collects metrics from the host machine where docker and/or kubernetes are running 
4. **node_push**: pushes node exporter metrics dfined in config-node.yaml to Prometheus push gateway
5. **dcgm-exporter**: Collects metrics form NVidia Container Toolkit and provides access to Prometheus to those metrics
6. **gpu_push**: A custom Python-based service that fetches metrics from NVidia GPU monitor  and pushes selected metrics to Prometheus Pushgateway.
7. **event-recorder**: Event recorder that exposes REST API to record task start/stop events (NOTE this only needs to be in one place where the Prometheus is running)
8. **data-parser**: A Flask-based service that provides REST API endpoints to query and parse Prometheus metrics for specific events based on UUIDs, calculating metric deltas between start and stop timestamps.

## Quick Start
There is install script that creates docker-compose.yml file based on the user selection. E.g. if you only want to collect metrics from the host machine you can only include that 
service to docker-compose and not the others. Two things that you need to configure for in the script are:
1. **Push Gateway Host**: This is the host name with port (if other than 80 or 443) to push gateway. If the push gateway is behind reverse proxy, the proxy path needs to be included
2. **Hostname**: Name of the server from which you are pushing the metrics from. This is to identify the host in the Prometheus data

Launching the service is simple as this:
````bash
./install.sh
...
sudo docker compose up -d
````
Obviously you need to have docker engine and compose installed to use the install script system. Sudo may or may not be needed depending on how the Docker environment is setup at the host machine.

## Services Configuration

### 1. `cadvisor`
- **Image**: `gcr.io/cadvisor/cadvisor:latest`
- **Container Name**: `cadvisor`
- **Hostname**: `cadvisor`
- **Restart Policy**: `unless-stopped` (ensures it runs continuously unless manually stopped)
- **Ports**:
  - `8080:8080`: Exposes cAdvisor’s web UI and metrics endpoint on port 8080.
- **Volumes** (read-only):
  - `/` → `/rootfs`: Access to host filesystem.
  - `/var/run` → `/var/run`: Access to Docker runtime information.
  - `/sys` → `/sys`: Access to system statistics.
  - `/var/lib/docker/` → `/var/lib/docker/`: Access to Docker container data.
  - `/dev/disk/` → `/dev/disk/`: Access to disk statistics.
- **Devices**:
  - `/dev/kmsg`: Allows logging kernel messages.
- **Privileged Mode**: Enabled for better metric collection.

### 2. `dcgm-exporter`
- **Image**: `nvcr.io/nvidia/k8s/dcgm-exporter:latest`
- **Container Name**: `dcgm-exporter`
- **Hostname**: `dcgm-exporter`
- **Ports**:
  - `9400:9400`: Exposes cAdvisor’s web UI and metrics endpoint on port 8080.
- **cap_add**:
      - `SYS_ADMIN`: System Administration rights
- **gpus**: `all`: Give access to all GPU's in the system

### 3. `cadvisor_push`
- **Builds from**: `./cadvisor_push` directory (Dockerfile-based image build).
- **Container Name**: `cadvisor_push`
- **Hostname**: `cadvisor_push`
- **Environment Variables**:
  - `HOST`: `http://cadvisor:8080/metrics` (Fetch metrics from cAdvisor).
  - `PUSHGW`: `http://130.188.160.11:8080/metrics/job/pushgateway` (Push metrics to Prometheus Pushgateway).
  - `HOSTNAME`: Name or your server or instance. This will identify the machine at the prometheus data.
  - `INTERVAL`: `15` (Push metrics every 15 seconds).
- **Volumes**:
  - `./config.yaml:/config.yaml`: Mounts a configuration file for additional settings.

### 4. `gpu_push`
- **Builds from**: `./gpu_push` directory (Dockerfile-based image build).
- **Container Name**: `gpu_push`
- **Hostname**: `gpu_push`
- **Environment Variables**:
  - `HOST`: `http://dcgm-exporter:9400/metrics` (Fetch metrics from cAdvisor).
  - `PUSHGW`: `http://130.188.160.11:8080/metrics/job/pushgateway` (Push metrics to Prometheus Pushgateway).
  - `HOSTNAME`: Name or your server or instance. This will identify the machine at the prometheus data.
  - `INTERVAL`: `15` (Push metrics every 15 seconds).
- **Volumes**:
  - `./config.yaml:/config.yaml`: Mounts a configuration file for additional settings.

### 5. `data-parser`
- **Image**: `karikolehmainen/data-parser:latest`
- **Container Name**: `data-parser`
- **Hostname**: `data-parser`
- **Environment Variables**:
  - `PROM_URL`: `http://waterverse.collab-cloud.eu:9090` (URL of the Prometheus server to query metrics from).
- **Ports**:
  - `8081:5000`: Exposes the data-parser REST API on port 8081 (mapped to 5000 inside the container).
- **Functionality**:
  - Provides a `/events` endpoint (GET) to retrieve all UUIDs from Prometheus.
  - Provides a `/event` endpoint (POST) to query and parse metrics for a specific UUID, calculating deltas between start and stop timestamps for specified metrics.

## How to Use
1. Ensure `docker-compose.yml` and the `cadvisor_push` directory with a `Dockerfile` are present.
2. (Optional) Modify `config.yaml` to filter/select specific metrics.
3. Start the services:
   ```sh
   docker-compose up -d
   ```
4. Access cAdvisor at `http://localhost:8080`.
5. Verify metrics in Pushgateway at `http://130.188.160.11:8080`.
6. Ensure Prometheus is scraping Pushgateway to retrieve metrics.

### Using the `data-parser` Service
1. **Retrieve UUIDs**:
   - Use the `/events` endpoint to get a list of all UUIDs stored in Prometheus:
     ```sh
     curl http://localhost:8081/events
     ```
   - This returns a JSON array of UUIDs available for querying.

2. **Query Metrics for an Event**:
   - Use the `/event` endpoint to query and parse metrics for a specific UUID. You need to provide a JSON payload specifying the UUID and the metrics to query, along with the fields to include in the response.
   - Example JSON payload for testing:
     ```json
     {
       "uuid": "f5d5447e-cdab-46b7-b235-bb4d03e5698c",
       "metrics": [
         {
           "metric": "container_cpu_usage_seconds_total",
           "fields": ["exported_instance", "name", "cpu", "values"]
         },
         {
           "metric": "container_memory_usage_bytes",
           "fields": ["exported_instance", "name", "values"]
         }
       ]
     }
     ```
   - Save the JSON payload to a file (e.g., `request.json`) and send it using `curl`:
     ```sh
     curl -X POST http://localhost:8081/event -H "Content-Type: application/json" -d @request.json
     ```
   - The response will include parsed metrics with their values and the delta (difference between the last and first value) for each metric, filtered to exclude zero deltas. The metrics are sorted by task name for clarity.

3. **Expected Response**:
   - The `/event` endpoint returns a JSON array of parsed metrics, each containing:
     - `metric`: The metric name (e.g., `container_cpu_usage_seconds_total`).
     - `task`: A string combining the specified fields (e.g., `exported_instance:name:cpu`).
     - `values`: A sorted list of timestamp-value pairs.
     - `delta`: The difference between the last and first value in the time range.
   - Example response (simplified):
     ```json
     [
       {
         "metric": "container_cpu_usage_seconds_total",
         "task": "instance1:container1:cpu0",
         "values": [{"timestamp": 1631234567.0, "value": 10.0}, {"timestamp": 1631234568.0, "value": 15.0}],
         "delta": 5.0
       },
       {
         "metric": "container_memory_usage_bytes",
         "task": "instance1:container1",
         "values": [{"timestamp": 1631234567.0, "value": 1048576.0}, {"timestamp": 1631234568.0, "value": 2097152.0}],
         "delta": 1048576.0
       }
     ]
     ```

### Using REST API's from Python script
Event-recorder and data-parser can be used together from Python script with relatively simply. Here is concise way of using the API's to record data from scripted test cases.
First order of business is define URLs where the API's are reachable. For instance:
```python
EVENT_URL  = "http://localhost:8080"
PARSER_URL = "http://localhost:8081"
```
Then you can add three simple wrappers to call the API's from the test. To record the start of test you can implement this kind of wrapper:
```python
def start_test():
    uuid = ""
    timestamp = int(time.time())
    payload = {
        "timestamp": timestamp
    }
    response = requests.post(f"{BASE_URL}/start", json=payload)
    print(f"[DEBUG] Raw response text: {response.text}")
    if response.status_code == 200:
        uuid = response.json().get("uuid")
        print(f"[START] Event UUID: {uuid}, Timestamp: {timestamp}")
        return uuid
    else:
        print(f"[START] Failed: {response.status_code} {response.text}")
        return None
```
Note that you need to save the UUID returned by start_test() so you can use in the stop test call and data parsing.
After routines are finished you can call stop_test with the UUID provided by the start_test wrapper
```python
def stop_test(uuid):
    timestamp = int(time.time())
    payload = {
        "uuid": uuid,
        "timestamp": timestamp
    }
    response = requests.post(f"{BASE_URL}/stop", json=payload)
    if response.status_code == 200:
        print(f"[STOP] Event UUID: {uuid}, Timestamp: {timestamp}")
    else:
        print(f"[STOP] Failed: {response.status_code} {response.text}")
```
This is the basic use, now the event record is stored in Prometheus database and can be retrieved later. 
Optionaly now you can also call the data-parser endopoint to retrieve the relevant metrics. For that you need to have metrics defined in JSON structure like this:
```json
{
  "metrics": [
    {
      "metric": "container_cpu_usage_seconds_total",
      "fields": ["exported_instance", "name", "cpu", "values"]
    },
    {
      "metric": "container_memory_usage_bytes",
      "fields": ["exported_instance", "name", "values"]
    }
  ]
}
```
You can then implement wrapper to print metrics from the test case like this:
```python
def print_analytics(uuid, metrics):
    payload = {
        "uuid": uuid,
        "metrics": metrics["metrics"] if isinstance(metrics, dict) and "metrics" in metrics else metrics
    }
    try:
        r = requests.post(f"{API_URL}/event", json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"Error calling /event endpoint: {e}")
        return
    except ValueError:
        print("Error decoding JSON response")
        return

    print("=========== ANALYTICS ===========")
    print(json.dumps(data, indent=2))
```
Before calling the print_analytics you should allow some time for Prometheus to absorb the metrics. There is some delay as metrics from distributed system are collected
using push gateway and Prometheus periodically scrapes the metrics from the gateway. Good rule of thumb is to allow at least 15 seconds before retriving metrics.

You can also store the metrics JSON to file and read it when calling the print_analytics wrapper. Like this:
```python
...
    stop_test(uuid)
    time.sleep(30) # Wait metrics to be absorbed into Prometheus
    with open("metrics.json", "r") as f:
        print_analytics(uuid, json.load(f))
...
```

## Troubleshooting
- Check logs for errors:
  ```sh
  docker logs cadvisor_push
  ```
- Verify that cAdvisor is running and exposing metrics:
  ```sh
  curl http://localhost:8080/metrics | head -n 20
  ```
- Ensure Prometheus is properly configured to scrape from Pushgateway.

## Notes
- The cAdvisor service runs with privileged mode to access all necessary system metrics.
- The `config.yaml` file can be used to limit which metrics are pushed to Pushgateway.
- The default push interval is set to 15 seconds, but it can be adjusted via the `INTERVAL` environment variable.

For more details, refer to the official cAdvisor and Prometheus Pushgateway documentation.


