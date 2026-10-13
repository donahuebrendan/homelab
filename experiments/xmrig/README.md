# Monero Mining on k3s — Setup Guide
## xmrig on RP5 Master | mining namespace

---

## Overview

- **Coin:** Monero (XMR) — best CPU-minable coin
- **Miner:** xmrig via `metal3d/xmrig` Docker image
- **Pool:** SupportXMR (`pool.supportxmr.com`)
- **Node:** RP5 master (pinned — 16GB RAM, faster CPU)
- **Pods:** 4 pods × 1GB RAM = 4GB total
- **Threads:** 1 thread per pod (RP5 has 4 cores — one per pod)
- **Namespace:** `mining`

---

## Step 1: Create a Monero Wallet

You need a wallet address to receive mining payouts.

**Option A: MyMonero (easiest, browser-based)**
1. Go to https://mymonero.com
2. Click "Create Account"
3. Save your 25-word seed phrase somewhere safe — this is your wallet
4. Copy your public wallet address (starts with `4`)

**Option B: Feather Wallet (desktop, more secure)**
1. Download from https://featherwallet.org
2. Create new wallet, save seed phrase
3. Copy your receiving address

Save your wallet address — you'll need it in Step 3.

---

## Step 2: Create the mining namespace

```bash
kubectl --kubeconfig ~/.kube/rp5-master create namespace mining
```

---

## Step 3: Create the xmrig config Secret

Store your wallet address as a Kubernetes Secret so it's not hardcoded in the manifest:

```bash
kubectl --kubeconfig ~/.kube/rp5-master create secret generic xmrig-config \
  --namespace mining \
  --from-literal=wallet=YOUR_WALLET_ADDRESS_HERE \
  --from-literal=pool=pool.supportxmr.com:443 \
  --from-literal=worker=rp5-cluster
```

Replace `YOUR_WALLET_ADDRESS_HERE` with your actual Monero wallet address.

Verify:
```bash
kubectl --kubeconfig ~/.kube/rp5-master get secret xmrig-config -n mining
```

---

## Step 4: Apply the Deployment

Save this as `xmrig.yaml`:

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xmrig
  namespace: mining
  labels:
    app: xmrig
spec:
  replicas: 4
  selector:
    matchLabels:
      app: xmrig
  template:
    metadata:
      labels:
        app: xmrig
    spec:
      # Pin to RP5 — faster CPU, 16GB RAM
      nodeSelector:
        kubernetes.io/hostname: rp5-master

      containers:
        - name: xmrig
          image: metal3d/xmrig:latest
          env:
            - name: POOL_URL
              valueFrom:
                secretKeyRef:
                  name: xmrig-config
                  key: pool
            - name: POOL_USER
              valueFrom:
                secretKeyRef:
                  name: xmrig-config
                  key: wallet
            - name: POOL_PASS
              valueFrom:
                secretKeyRef:
                  name: xmrig-config
                  key: worker
            - name: THREADS
              value: "1"         # 1 thread per pod, 4 pods = 4 threads = all cores
            - name: DONATE_LEVEL
              value: "1"         # 1% donation to xmrig devs (minimum)
          resources:
            requests:
              memory: "768Mi"
              cpu: "800m"
            limits:
              memory: "1Gi"
              cpu: "1000m"      # 1 full core per pod

      # Spread pods evenly (all on RP5 but different processes)
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: xmrig
```

Apply it:
```bash
kubectl --kubeconfig ~/.kube/rp5-master apply -f xmrig.yaml
```

Watch pods come up:
```bash
kubectl --kubeconfig ~/.kube/rp5-master get pods -n mining -w
```

All 4 should reach `Running` within ~30 seconds.

---

## Step 5: Verify Mining

Check logs of one pod to confirm it's hashing:
```bash
kubectl --kubeconfig ~/.kube/rp5-master logs -n mining -l app=xmrig --tail=20
```

You should see output like:
```
[2026-09-23 14:00:01.000]  net      use pool pool.supportxmr.com:443
[2026-09-23 14:00:02.000]  cpu      use 1 thread
[2026-09-23 14:00:05.000]  miner    speed 10s/60s/15m 120.5 120.0 n/a H/s
```

---

## Step 6: Monitor on SupportXMR

1. Go to https://supportxmr.com
2. Enter your wallet address in the search box
3. You'll see:
   - **Hashrate** — combined H/s from all 4 pods
   - **Shares** — valid shares submitted
   - **Balance** — XMR earned (tiny at first)
   - **Workers** — shows `rp5-cluster` as your worker

Note: It takes ~10 minutes for your worker to appear on the pool dashboard after first starting.

---

## Step 7: Expose xmrig API (for Tronbyt dashboard)

xmrig has a built-in HTTP API on port 3000. Expose it via a ClusterIP service so the stats-api can query it:

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: xmrig-api
  namespace: mining
spec:
  selector:
    app: xmrig
  ports:
    - protocol: TCP
      port: 3000
      targetPort: 3000
```

Apply:
```bash
kubectl --kubeconfig ~/.kube/rp5-master apply -f xmrig-svc.yaml
```

Test the API from RP5:
```bash
ssh pi@192.168.4.35
curl http://xmrig-api.mining.svc.cluster.local:3000/2/summary | jq .
```

This returns JSON with hashrate, shares, CPU info — everything we need for the Tronbyt dashboard.

---

## Expected Performance

| Component | Hashrate |
|-----------|----------|
| RP5 (4 pods × 1 thread) | ~400-600 H/s total |
| RP3 worker | not mining (saving for stats-api + tronbyt) |
| **Combined** | **~400-600 H/s** |

At current difficulty, expect **< $0.01/day** in XMR — this is purely for fun and learning.

---

## Useful Commands

```bash
# See all mining pods
kubectl --kubeconfig ~/.kube/rp5-master get pods -n mining

# Stream logs from all xmrig pods
kubectl --kubeconfig ~/.kube/rp5-master logs -n mining -l app=xmrig -f

# Check resource usage
kubectl --kubeconfig ~/.kube/rp5-master top pods -n mining

# Scale up (add more pods)
kubectl --kubeconfig ~/.kube/rp5-master scale deployment xmrig -n mining --replicas=6

# Scale down (reduce CPU load)
kubectl --kubeconfig ~/.kube/rp5-master scale deployment xmrig -n mining --replicas=2

# Stop mining entirely
kubectl --kubeconfig ~/.kube/rp5-master scale deployment xmrig -n mining --replicas=0

# Resume
kubectl --kubeconfig ~/.kube/rp5-master scale deployment xmrig -n mining --replicas=4
```

---

## Next Step: Tronbyt Mining Dashboard

Once mining is confirmed working, we'll add a `/mining` endpoint to stats-api that:
1. Queries the xmrig API across all pods
2. Aggregates total hashrate and shares
3. Queries SupportXMR pool API for balance and payout info

Then build a `mining.star` Pixlet app showing:
- Total H/s across cluster
- Shares found today
- XMR balance
- Estimated daily earnings
