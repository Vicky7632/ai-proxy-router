# Local Kubernetes deployment

This guide covers only the manifests under `k8s/base/` on a local Docker
Desktop Kubernetes context. These resources are not a production deployment.
The instructions are provided for the operator to run; no Kubernetes commands
were executed while writing this documentation.

## Resources defined by the manifests

Expected namespace: `ai-proxy-router`.

| Workload / service | Image / type | Ports |
| --- | --- | --- |
| `frontend` Deployment / Service | `aiproxyrouter-frontend:k8s` / NodePort | Pod/service port 80, NodePort 30080 |
| `backend` Deployment / Service | `aiproxyrouter-backend:latest` / NodePort | Pod/service port 8000, NodePort 30081 |
| `postgres` Deployment / Service | `pgvector/pgvector:0.8.6-pg18` / ClusterIP | 5432 |
| `redis` Deployment / Service | `redis:7-alpine` / ClusterIP | 6379 |

Host addresses:

- Frontend: `http://localhost:30080`
- Backend: `http://localhost:30081`

In-cluster service names are `postgres:5432` and `redis:6379`, within the
namespace. The PostgreSQL Deployment mounts PVC `postgres-data` (2Gi,
`ReadWriteOnce`, `hostpath`) at `/var/lib/postgresql`. The Redis Deployment
mounts PVC `redis-data` (1Gi, `ReadWriteOnce`, `hostpath`) at `/data`; Redis
starts with append-only persistence enabled. Frontend and backend Deployments
do not mount persistent volumes.

The backend reads environment values through Secret
`ai-proxy-router-secrets`. The `k8s/base/` files reference these Secret keys
but do not define that Secret. It must already exist in the namespace:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
- `JWT_SECRET_KEY`

Never paste the values into a manifest, terminal transcript, or documentation.
Use the approved local secret-management process to provision the Secret.

## Build the local images

Run from the repository root. Docker Desktop shares its local image store with
its Kubernetes runtime; the manifests use `imagePullPolicy: IfNotPresent`.

```powershell
docker build -f .\Backend\DockerFile -t aiproxyrouter-backend:latest .\Backend
docker build --build-arg VITE_API_BASE_URL=http://localhost:30081 -t aiproxyrouter-frontend:k8s .\Frontend
```

The backend Dockerfile is named `Backend/DockerFile` (capital `F`). The
frontend Dockerfile runs the Vite production build. `VITE_API_BASE_URL` is
compiled into the JavaScript bundle during that build; setting a Kubernetes
container environment variable later does not change the already-built
frontend bundle. For the local cluster the browser must reach the API at
`http://localhost:30081`.

## Apply the base manifests

Before applying, verify the current kubectl context and ensure the referenced
Secret has been provisioned. The following applies only the checked-in base
files in dependency order; it does not delete PVCs or persistent data.

```powershell
kubectl config current-context
kubectl apply -f .\k8s\base\namespace.yaml
kubectl apply -f .\k8s\base\storage.yaml
kubectl apply -f .\k8s\base\data-services.yaml
kubectl apply -f .\k8s\base\backend.yaml
kubectl apply -f .\k8s\base\frontend.yaml
```

The deployment manifests expect Docker Desktop's local images. If updating an
existing cluster after rebuilding an image with the same tag, restart only
that application Deployment so its Pod is recreated from the local image:

```powershell
kubectl -n ai-proxy-router rollout restart deployment/backend
kubectl -n ai-proxy-router rollout status deployment/backend --timeout=180s

kubectl -n ai-proxy-router rollout restart deployment/frontend
kubectl -n ai-proxy-router rollout status deployment/frontend --timeout=180s
```

Only run the restart corresponding to the image you rebuilt. These commands
do not alter PostgreSQL or Redis PVCs.

## Read-only inspection

```powershell
kubectl config current-context
kubectl -n ai-proxy-router get deployments -o wide
kubectl -n ai-proxy-router get pods -o wide
kubectl -n ai-proxy-router get services -o wide
kubectl -n ai-proxy-router get endpoints
kubectl -n ai-proxy-router get pvc
kubectl -n ai-proxy-router rollout status deployment/frontend
kubectl -n ai-proxy-router rollout status deployment/backend
```

Inspect application logs without requesting Secret contents:

```powershell
kubectl -n ai-proxy-router logs deployment/backend --tail=100
kubectl -n ai-proxy-router logs deployment/frontend --tail=100
```

Avoid commands that print Secret values. Do not delete namespaces, PVCs,
volumes, or data services as a troubleshooting step.

## Troubleshooting

### NodePort does not respond

1. Confirm `kubectl config current-context` is `docker-desktop`.
2. Check the relevant Deployment and Pod are ready with the inspection
   commands above.
3. Check `frontend` has NodePort 30080 and `backend` has NodePort 30081 using
   `kubectl -n ai-proxy-router get services -o wide`.
4. Check Service endpoints exist and target ready Pods.
5. Probe the backend root from PowerShell:

   ```powershell
   Invoke-WebRequest -Uri http://localhost:30081/ -UseBasicParsing
   ```

   The backend root response is `{"message":"AI proxy router running"}`.

### Frontend reports an API connectivity error

- Inspect the actual failing request in browser DevTools Network; do not infer
  that the root endpoint is the failing request.
- Confirm the served frontend image was built with
  `VITE_API_BASE_URL=http://localhost:30081`. Vite embeds this value during
  `npm run build`.
- After changing that build argument, rebuild the frontend image, then restart
  and verify only the frontend Deployment.
- Check CORS configuration: the backend allows the single
  `FRONTEND_ORIGIN` value with credentials. The base backend manifest sets it
  to `http://localhost:30080`.

### Image changes are not visible

- Verify the exact image tag matches `k8s/base/frontend.yaml` or
  `k8s/base/backend.yaml`.
- Docker Desktop's cluster uses `IfNotPresent`; build into the local Docker
  Desktop image store, and restart only the matching application Deployment.
- Wait for `kubectl rollout status` to report success. Then check the new Pod
  image and age with `kubectl -n ai-proxy-router get pods -o wide`.

### Missing configuration / Secret reference

- The manifests require a Secret named `ai-proxy-router-secrets` in
  `ai-proxy-router`; the base files do not create it.
- Check its existence without printing values:

  ```powershell
  kubectl -n ai-proxy-router get secret ai-proxy-router-secrets
  ```

- Ensure the keys listed in the resources table have been provisioned using
  your local secret-management procedure.

### PVC or data-service issue

- Use `kubectl -n ai-proxy-router get pvc,pods,services` and backend/data
  service logs to diagnose readiness.
- PVCs `postgres-data` and `redis-data` hold state. Never delete or recreate
  them as a routine restart or image-update operation.
