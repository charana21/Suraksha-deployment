# CrowdVision K3s backend deployment

For a complete frontend, backend, MongoDB, and MediaMTX deployment, use
`k3s/stack/`. The manifests in this directory are the legacy backend-only
bundle.

K3s is a lightweight Kubernetes distribution, so it uses the standard Kubernetes
API manifests in this directory. These files are intentionally packaged under
`k3s/` to make the target platform clear.

These manifests deploy the backend and an internal MediaMTX service. They assume:

- the image is available as `registry.example.com/crowdvision/crowd-backend:latest`;
- the K3s cluster has an NVIDIA GPU node labeled `crowdvision/gpu=true`;
- the NVIDIA Container Toolkit and K3s GPU runtime are configured;
- MongoDB is reachable at the URI in `secret.yaml`; and
- model files are provisioned into `/app/data/weights` on the PVC.

## Before applying

1. Replace the image, hostname, MongoDB URI, notification credentials, and AWS credentials.
2. Create or provision the model files `yolov8m.pt` and `SHA_model.pth` in the PVC at `data/weights/`.
3. Create the TLS secret, or remove the TLS block until cert-manager is configured:

```bash
kubectl -n crowdvision create secret tls crowdvision-tls \
  --cert=fullchain.pem --key=privkey.pem
```

4. Update camera URLs to use the in-cluster MediaMTX DNS name, for example
   `rtsp://mediamtx:8554/cam_01`, or use the external camera URLs directly.

## Deploy

```bash
kubectl apply -k k3s/
kubectl -n crowdvision get pods -o wide
kubectl -n crowdvision logs deploy/crowdvision-backend -f
```

Verify the service before ingress:

```bash
kubectl -n crowdvision port-forward svc/crowdvision-backend 8080:80
curl http://127.0.0.1:8080/api/health/simple
curl http://127.0.0.1:8080/api/health
```

## Important production notes

- `secret.yaml` is a template and must not contain committed credentials. Prefer an external secret manager or Sealed Secrets.
- The backend uses `Recreate` and one replica because GPU model state and the default `ReadWriteOnce` PVC are node-local.
- Change `storageClassName` and increase storage for a production storage backend such as Longhorn.
- The default readiness probe reports failure when MongoDB or the requested GPU is unavailable.