#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io docker-compose-v2 python3 ca-certificates
install -d -m 0755 /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"}}
EOF
systemctl enable docker
systemctl restart docker
if ! swapon --show=NAME --noheadings | grep -q /swapfile; then
  if [ ! -e /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
fi
if ! grep -q '^/swapfile ' /etc/fstab; then
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
install -d -o ubuntu -g ubuntu -m 0750 /opt/capstone-traffic
install -d -m 0700 /var/lib/capstone-traffic /var/backups/capstone-traffic
timedatectl set-timezone UTC
touch /var/lib/capstone-traffic/bootstrap-complete
