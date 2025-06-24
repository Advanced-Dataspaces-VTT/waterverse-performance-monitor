#!/bin/bash

set -e

echo "=== Monitoring Stack Installer ==="

read -p "Enter Pushgateway address (e.g. http://example.com:8080): " PUSHGW
read -p "Enter this machine's hostname: " HOSTNAME

echo "Select components to install:"
echo "1. cAdvisor + push"
echo "2. node-exporter + push"
echo "3. event-recorder"
echo "4. GPU monitoring"
echo "5. All"
read -p "Enter numbers separated by space (e.g. 1 2 3): " COMPONENTS

# Helper to check if component was selected
function selected() {
  [[ " $COMPONENTS " =~ " $1 " ]] || [[ $COMPONENTS == "5" ]]
}

echo "Generating docker-compose.yml..."

cat > docker-compose.yml <<EOF
version: '3.8'
services:
EOF

if selected 1; then
cat >> docker-compose.yml <<EOF
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    hostname: cadvisor
    restart: unless-stopped
    volumes:
      - "/:/rootfs:ro"
      - "/var/run:/var/run:ro"
      - "/sys:/sys:ro"
      - "/var/lib/docker/:/var/lib/docker:ro"
      - "/dev/disk/:/dev/disk:ro"
    devices:
      - "/dev/kmsg"
    privileged: true
  cadvisor_push:
    image: karikolehmainen/cadvisor_push:latest
    hostname: cadvisor_push
    container_name: cadvisor_push
    environment:
      HOST: http://cadvisor:8080/metrics
      PUSHGW: $PUSHGW/metrics/job/pushgateway
      HOSTNAME: $HOSTNAME
      INTERVAL: 15
    volumes:
      - "./config.yaml:/config.yaml"

EOF
fi

if selected 2; then
cat >> docker-compose.yml <<EOF
  node-exporter:
    image: quay.io/prometheus/node-exporter:latest
    container_name: node-exporter
    hostname: node-exporter
    restart: unless-stopped
    pid: host
    volumes:
      - /:/host:ro,rslave
    command:
      - '--path.rootfs=/host'
  node_push:
    image: karikolehmainen/node_push:latest
    hostname: node_push
    container_name: node_push
    environment:
      HOST: http://node-exporter:9100/metrics
      PUSHGW: $PUSHGW/metrics/job/pushgateway
      HOSTNAME: $HOSTNAME
      INTERVAL: 15
    volumes:
      - "./config-node.yaml:/config.yaml"

EOF
fi

if selected 3; then
cat >> docker-compose.yml <<EOF
  event-recorder:
    image: karikolehmainen/event-recorder:latest
    container_name: event-recorder
    ports:
      - "8081:5000"
    environment:
      PUSHGATEWAY_HOST: ${PUSHGW%:*}
      PUSHGATEWAY_PORT: ${PUSHGW##*:}
      HOSTNAME: $HOSTNAME

EOF
fi

if selected 4; then
cat >> docker-compose.yml <<EOF
  dcgm-exporter:
    image: nvcr.io/nvidia/k8s/dcgm-exporter:4.1.1-4.0.4-ubuntu22.04
    container_name: dcgm-exporter
    hostname: dcgm-exporter
    cap_add:
      - SYS_ADMIN
    runtime: nvidia
    restart: "always"
  gpu_push:
    image: karikolehmainen/gpu_push:latest
    hostname: gpu_push
    container_name: gpu_push
    environment:
      HOST: http://dcgm-exporter:9400/metrics
      PUSHGW: $PUSHGW/metrics/job/pushgateway
      HOSTNAME: $HOSTNAME
      INTERVAL: 15
    volumes:
      - "./config-gpu.yaml:/config.yaml"
EOF
fi

echo "Installation files generated."
echo "Run with: docker compose up -d"
