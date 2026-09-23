# CrowdVision K3s stack

This bundle deploys the frontend, API, and MediaMTX into K3s. MongoDB is
external and must be configured through `MONGODB_URI` in the Kubernetes Secret. The
frontend and API share one Traefik ingress: the frontend is available at `/` and
the API and WebSockets are available at `/api`. Build the frontend with its
default `VITE_API_URL=/api` so it always uses the current workstation address.

## Local K3s test

Install K3s, then run the local deployment script from the repository root:

```bash
./k3s/stack/deploy-local.sh
```

The script reads `crowd-backend/.env` into the Kubernetes Secret and uses
`Crowd_Vision_Frontend/.env` for the frontend's build-time `VITE_*` values. These
files must remain uncommitted. It builds and imports both local images into the
K3s containerd image store, then applies the local overlay.

For a manual deployment, create the non-committed secret from the backend env:

```bash
kubectl create namespace crowdvision --dry-run=client -o yaml | kubectl apply -f -
kubectl -n crowdvision create secret generic crowdvision-secrets \
  --from-env-file=crowd-backend/.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k k3s/stack/overlays/local
```

Copy `yolov8m.pt` and `SHA_model.pth` to the `crowdvision-data` volume before
starting a camera stream. Test the web application at `http://<k3s-node-ip>/`.

## GPU workstation deployment

The `workstation` overlay requests one NVIDIA GPU. Install the NVIDIA driver,
NVIDIA Container Toolkit, and the NVIDIA Kubernetes device plugin on the K3s
node first. Push the two images to the client-accessible registry, then replace
the `newName` and `newTag` values in `overlays/workstation/kustomization.yaml`.

Create `crowdvision-secrets` as above and apply:

```bash
kubectl apply -k overlays/workstation
kubectl -n crowdvision rollout status deploy/crowdvision-backend --timeout=10m
kubectl -n crowdvision rollout status deploy/crowdvision-frontend
```

For a client hostname and TLS, add a host and TLS block to `base/ingress.yaml`
or a client-specific overlay. For durable installations, replace
`local-path` in `base/pvc.yaml` with the site storage class, such as Longhorn or
NFS.

Do not use `overlays/production`; this repository provides `local` and
`workstation` overlays.

## Verification and operations

```bash
kubectl -n crowdvision get pods,svc,ingress
curl http://<k3s-node-ip>/api/health/simple
kubectl -n crowdvision logs deploy/crowdvision-backend -f
```

K3s normally ships Traefik. If it was disabled, install an ingress controller
or expose the frontend service through a `NodePort` service instead.