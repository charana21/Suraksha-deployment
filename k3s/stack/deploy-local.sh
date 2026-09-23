#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/Crowd_Vision_Frontend"
BACKEND_DIR="$ROOT_DIR/crowd-backend"
K3S_DIR="$ROOT_DIR/k3s/stack"

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "Missing $BACKEND_DIR/.env" >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_DIR/.env" ]]; then
  echo "Missing $FRONTEND_DIR/.env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$FRONTEND_DIR/.env"
set +a

docker build \
  --build-arg "VITE_API_URL=${VITE_API_URL:-/api}" \
  -t crowdvision-frontend:local \
  "$FRONTEND_DIR"
docker save crowdvision-frontend:local | sudo k3s ctr -n k8s.io images import -

docker build -t crowdvision-backend:local "$BACKEND_DIR"
docker save crowdvision-backend:local | sudo k3s ctr -n k8s.io images import -

kubectl create namespace crowdvision --dry-run=client -o yaml | kubectl apply -f -
kubectl -n crowdvision create secret generic crowdvision-secrets \
  --from-env-file="$BACKEND_DIR/.env" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k "$K3S_DIR/overlays/local"