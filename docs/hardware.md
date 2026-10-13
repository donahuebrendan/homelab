# Homelab Hardware

This document records the physical hardware used by the homelab and the role each device currently plays. It intentionally omits exact LAN IP addresses and credentials so it can live in a public Git repository.

## Core hardware

| Device | Hostname / identity | Current role | Notes |
|---|---|---|---|
| Raspberry Pi 5 | `rp5-master` | k3s control-plane node | Primary cluster node. Runs cluster workloads that are pinned to the Pi 5, including Pi-hole. |
| Raspberry Pi 3 | `raspberrypi` | k3s worker node | Runs workloads that are pinned to the worker, including the Tronbyt server and Stats API. |
| Tidbyt display | Network-connected display | Homelab dashboard | Displays custom Pixlet apps that consume data from the Stats API. |
| MacBook Air | Development machine | Administration and development | Used for SSH, `kubectl`, Kustomize, and k9s. The Pi cluster uses a dedicated kubeconfig at `~/.kube/rp5-master`; do not make the Pi cluster the default Kubernetes context. |
| eero network | Home LAN | Network and DHCP reservations | Provides the home network and reserved addresses for the Raspberry Pi nodes. |
| Netgear 5-port Ethernet switch | Wired network | Ethernet connectivity | Added to support wired connections between the homelab devices and the home network. |

## Software and operating-system notes

- **Kubernetes distribution:** k3s.
- **Configuration management:** Kustomize manifests in `clusters/home` and `apps/`.
- **Raspberry Pi 5 OS:** Debian 13 (Trixie), ARM64. The system was reported as Debian 13.7 in October 2026.
- **Container and cluster administration:** `kubectl`, SSH, and k9s from the MacBook Air.
- **Display applications:** Pixlet `.star` apps hosted through Tronbyt.
- **Stats API:** Flask API providing endpoints used by display applications, including system stats, tides, national debt, fantasy football, Pi-hole metrics, and aircraft data.

## Network conventions

- The Raspberry Pi nodes use DHCP reservations on the home network.
- Both Ethernet and Wi-Fi have been used during network changes. The Raspberry Pi 3 has intentionally retained its Wi-Fi address for compatibility with an existing service.
- Keep actual IP addresses, credentials, kubeconfig files, and other private network details in local configuration or a private password manager rather than this public document.
- When administering the Pi cluster, use the dedicated kubeconfig explicitly:

  ```bash
  kubectl --kubeconfig ~/.kube/rp5-master get nodes
  ```

  This avoids accidentally sending commands to the separate local `minikube` context.

## Additional hardware / future projects

### Digilent Nexys 4 DDR

An older Digilent Nexys 4 DDR FPGA development board is available for a future project. It is not currently part of the k3s cluster and is not managed by the active Kubernetes configuration.

## Maintenance checklist

When hardware changes, update this document with:

- Device model and hostname
- Intended role
- Operating system or firmware, where relevant
- Network connection type (wired or Wi-Fi)
- Any dependencies that other services rely on

Avoid adding passwords, API keys, private SSH keys, or full kubeconfig contents to this file.
