# CrowdVision K3s stack

This bundle deploys the frontend, API, and MediaMTX into K3s. MongoDB is
external and must be configured through `MONGODB_URI` in the Kubernetes Secret. The
frontend and API share one Traefik ingress: the frontend is available at `/` and
the API and WebSockets are available at `/api`. Build the frontend with its
default `VITE_API_URL=/api` so it always uses the current workstation address.

## Local K3s test

Install K3s, then build and import both images into its containerd image store:

```bash
cd /path/to/Crowd_Vision_Frontend
docker build -t crowdvision-frontend:local .
docker save crowdvision-frontend:local | sudo k3s ctr images import -

cd /path/to/crowd-backend
docker build -t crowdvision-backend:local .
docker save crowdvision-backend:local | sudo k3s ctr images import -
```

Create the non-committed secret file and deploy the local overlay:

```bash
cd /path/to/crowd-backend/k3s/stack
cp secrets.example.env secrets.env
# Put the test MongoDB URI from the backend environment in `MONGODB_URI`.
kubectl create namespace crowdvision --dry-run=client -o yaml | kubectl apply -f -
kubectl -n crowdvision create secret generic crowdvision-secrets \
  --from-env-file=secrets.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k overlays/local
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