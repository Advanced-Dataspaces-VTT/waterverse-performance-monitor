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


