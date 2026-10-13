# Raspberry Pi Homelab

A Kubernetes homelab running on Raspberry Pi hardware, managed with k3s and organized with Kustomize.

## Hardware

- Raspberry Pi 5 — k3s control-plane node
- Raspberry Pi 3 — worker node
- Tronbyt display for custom Pixlet applications

## Applications

| Application | Purpose |
|---|---|
| Tronbyt | Hosts the display and custom Pixlet apps |
| Stats API | Provides system stats, tides, US national debt, fantasy football standings, Pi-hole stats, and aircraft data |
| Pi-hole | Network-wide DNS filtering |
| XMRig | Experimental mining workload |

## Repository structure

```text
apps/
  mining/       # Mining workload manifests
  pihole/       # Pi-hole manifests
  tronbyt/
    k8s/        # Tronbyt and API workloads
    pixlet/     # Display applications
    stats-api/  # API source and Docker image build
clusters/
  home/         # Combined home-cluster Kustomize configuration
```

## Kubernetes configuration

Render the full home-cluster configuration:

```bash
kubectl kustomize clusters/home
```

Apply it to the home cluster explicitly:

```bash
kubectl --kubeconfig ~/.kube/rp5-master \
  apply -k clusters/home
```

Review the rendered manifests before applying changes.

## Secrets

Credentials are stored in Kubernetes Secrets, not committed as plaintext manifests. The required Secrets must exist in the appropriate namespaces before deploying workloads.

- `pihole-secret` in `pihole`
- `stats-api-secrets` in `tronbyt`

Do not commit credentials, kubeconfig files, rendered Secret manifests, or local environment files.

## Container images

The Stats API and aircraft database Job currently reference `stats-api:latest`. The image must be built and available on the appropriate Kubernetes node before those workloads can run with `imagePullPolicy: Never`.

A future improvement is to publish versioned images to GitHub Container Registry and use Argo CD for GitOps deployment.
