# Build and Push the Stats API Container

This guide builds the Stats API image from the canonical source in `apps/tronbyt/stats-api/`, publishes it to GitHub Container Registry (GHCR), and updates Kubernetes to pull that published image.

> **Safety:** The build must not include credentials. Runtime credentials belong in Kubernetes Secrets. Never copy `.env` files, kubeconfig files, or Secret manifests into the image.

## Overview

- **Build context:** `apps/tronbyt/stats-api/`
- **Dockerfile:** `apps/tronbyt/stats-api/Dockerfile`
- **Image registry:** GitHub Container Registry (`ghcr.io`)
- **Target platform:** `linux/arm64` for the Raspberry Pi cluster (verify node architecture first)
- **Kubernetes workload:** `stats-api` Deployment and `aircraft-db` Job
- **Runtime Secrets:** `stats-api-secrets` in namespace `tronbyt`

## 1. Confirm the target nodes' architecture

From the MacBook, run:

```bash
kubectl --kubeconfig ~/.kube/rp5-master get nodes \
  -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture,OS:.status.nodeInfo.operatingSystem
```

Use the architecture reported by the node that runs the Stats API. If the nodes are `arm64`, build `linux/arm64`. Do not guess the target platform.

## 2. Confirm the source and Docker build context

From the repository root:

```bash
test -f apps/tronbyt/stats-api/Dockerfile
test -f apps/tronbyt/stats-api/stats_api.py
test -f apps/tronbyt/stats-api/build_aircraft_db.py
test -f apps/tronbyt/stats-api/requirements.txt
```

Each command should exit without an error. Build from `apps/tronbyt/stats-api/`, not the repository root, because the Dockerfile copies files from its build context.

## 3. Choose the GHCR image name

Replace `OWNER` with your GitHub user or organization that owns the repository:

```bash
export GHCR_IMAGE="ghcr.io/OWNER/homelab-stats-api"
```

Use a lowercase image/package name. Keep the owner and image name consistent for all later commands.

## 4. Authenticate Docker to GHCR

Create a GitHub Personal Access Token (classic) with `write:packages` permission (and `read:packages` if needed). Follow your organization's policies if applicable.

Log in without putting the token directly into shell history:

```bash
read -s "GHCR_TOKEN?GitHub token with package write permission: "
echo
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
unset GHCR_TOKEN
```

Replace `YOUR_GITHUB_USERNAME` with the account that owns or has permission to publish the package. Docker should report `Login Succeeded`.

## 5. Build and push a versioned image

Use a unique tag for each build. A Git commit SHA is ideal after the source is committed:

```bash
TAG="$(git rev-parse --short HEAD)"
```

If the repository does not have a commit yet, create a temporary test tag instead:

```bash
TAG="test-$(date +%Y%m%d-%H%M%S)"
```

Build and publish for the architecture confirmed in Step 1:

```bash
docker buildx create --name homelab-builder --use 2>/dev/null || docker buildx use homelab-builder

docker buildx build \
  --platform linux/arm64 \
  --tag "${GHCR_IMAGE}:${TAG}" \
  --push \
  apps/tronbyt/stats-api
```

If your target node architecture is not `arm64`, change `--platform` to match. The build context is the final argument.

The command should finish with a successful push. The version tag should identify this exact image; avoid deploying `latest` as your only reference.

## 6. Verify the published image

```bash
docker buildx imagetools inspect "${GHCR_IMAGE}:${TAG}"
```

Confirm the image exists and its platform matches the intended node architecture.

If the GHCR package is private, make sure the Kubernetes nodes can authenticate to pull it. For a public package, no image pull Secret is normally required.

## 7. Update the Kubernetes manifests

Edit both files:

- `apps/tronbyt/k8s/stats-api.yaml`
- `apps/tronbyt/k8s/aircraft-db-job.yaml`

Replace `image: stats-api:latest` with the exact versioned image:

```yaml
image: ghcr.io/OWNER/homelab-stats-api:TAG
imagePullPolicy: IfNotPresent
```

Replace `OWNER` and `TAG` with the values used in Steps 3 and 5. Make the same change in both resources. Do not add credentials to either manifest.

Before applying anything, render and inspect the configuration:

```bash
kubectl kustomize clusters/home > /tmp/homelab-rendered.yaml
grep -n -A2 -B2 'homelab-stats-api' /tmp/homelab-rendered.yaml
```

Confirm the rendered output contains the expected versioned image for both the Deployment and the aircraft database Job.

## 8. Deploy the updated Stats API

Apply the Stats API Deployment manifest to the intended cluster using its explicit kubeconfig:

```bash
kubectl --kubeconfig ~/.kube/rp5-master \
  apply -f apps/tronbyt/k8s/stats-api.yaml
```

Wait for rollout:

```bash
kubectl --kubeconfig ~/.kube/rp5-master \
  rollout status deployment/stats-api -n tronbyt --timeout=180s
```

Inspect the pod and logs if rollout fails:

```bash
kubectl --kubeconfig ~/.kube/rp5-master \
  get pods -n tronbyt -o wide

kubectl --kubeconfig ~/.kube/rp5-master \
  logs deployment/stats-api -n tronbyt --tail=100
```

The API requires the `stats-api-secrets` Secret in namespace `tronbyt`. The source code reads the Pi-hole and OpenSky values from environment variables, so missing keys will prevent startup.

## 9. Smoke-test the API

Find the Stats API pod and check its health endpoint:

```bash
kubectl --kubeconfig ~/.kube/rp5-master \
  get pods -n tronbyt -o wide
```

If the API is exposed on the node's host port 5000 as configured, test from the MacBook using the node address appropriate to your network:

```bash
curl --fail http://RASPBERRY_PI_NODE_IP:5000/health
```

Replace `RASPBERRY_PI_NODE_IP` with the correct current address. A successful response should indicate that the API is healthy. Avoid pasting any credential-bearing output into public issue trackers.

## 10. Optional: update the aircraft database Job

The Job uses the same image to run `build_aircraft_db.py`. After updating its manifest to the same published image, inspect the Job before applying it. Jobs may not rerun if a Job with the same name has already completed; use a deliberate versioned Job name or delete/recreate the existing Job only when you intend to run the database build again.

Do not run the database Job merely to test the API image unless you intend to rebuild or refresh the aircraft database.

## Troubleshooting

- **`no match for platform` / `exec format error`:** The image platform doesn't match the node architecture. Rebuild for the architecture reported by Kubernetes.
- **`unauthorized` while pulling:** Check GHCR package visibility and registry credentials. Private images require an image pull Secret in the workload namespace.
- **`ImagePullBackOff`:** Inspect pod events with `kubectl describe pod -n tronbyt POD_NAME`.
- **Pod starts and immediately exits:** Check logs and verify all required Secret keys exist in namespace `tronbyt`.
- **Changes don't appear:** Confirm the manifest references the new unique tag and the rollout used that tag.
- **Build can't find `stats_api.py`:** Ensure the build context is `apps/tronbyt/stats-api/` and that the canonical source file exists there.

## Important notes

- A successful build and push does not automatically update Kubernetes. The manifests must reference the published tag, and the workload must be updated.
- Keep the Pi cluster's kubeconfig explicit (`--kubeconfig ~/.kube/rp5-master`) so commands do not accidentally target the separate `minikube` context.
- For future GitOps, commit the image-tag change to Git and let Argo CD reconcile it rather than making manual cluster changes.
