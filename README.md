# Introduction
This is Prometheus performance metric tool to push metrics form Docker environment to main Prometheus server

## Overview
This setup consists of two main services:

1. **cAdvisor**: Collects resource usage and performance metrics from Docker containers.
2. **cadvisor_push**: A custom Python-based service that fetches metrics from cAdvisor and pushes selected metrics to Prometheus Pushgateway.

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

### 2. `cadvisor_push`
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


