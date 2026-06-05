# AutoPilot DevOps Agent — Project Memory

## What This Is
AutoPilot is an autonomous AI DevOps agent for Kubernetes + Jenkins with a React dashboard.
Built by Chetan.

## Stack
- Python Agent: FastAPI + kubernetes-client + anthropic SDK + asyncpg + redis + slack-bolt
- Node.js API: Express + TypeScript + pg + ioredis + ws
- React Dashboard: React 18 + Vite + TypeScript + Tailwind + Zustand + TanStack Query + Recharts
- Infra: PostgreSQL (NeonDB/local) + Redis + K8s on Oracle Cloud ARM64

## Critical Architecture Decisions
1. Python agent runs IN the K8s cluster with a ClusterRole binding
2. Jenkins runs as a pod: http://jenkins.jenkins.svc.cluster.local:8080
3. Redis is used for both queue (incident_queue list) and pub/sub (autopilot:events channel)
4. Node.js API is a READ-ONLY API — it does not write to K8s directly
5. All K8s mutations go through the Python agent

## Hard Rules (Never Break)
1. Never auto-fix kube-system (except CoreDNS/metrics-server restart)
2. Never delete PVCs, PersistentVolumes, or Secrets
3. Never create/modify RBAC resources
4. Never auto-fix CRITICAL severity — always require Slack approval
5. Never auto-fix if confidence < AI_CONFIDENCE_THRESHOLD
6. Never fix the autopilot-agent pod itself
7. Never retry Jenkins more than JENKINS_MAX_RETRIES times
8. All fix methods must be idempotent
9. All fix executions logged to DB before and after
10. If DRY_RUN=true: log and alert but never execute
11. Never delete Secrets
12. For selector mismatch: alert only, never auto-apply

## Environment
- Oracle Cloud VM, Ubuntu ARM64 (aarch64)
- K8s cluster with Jenkins as a pod in jenkins namespace
- App being monitored: 3-tier Node.js (React frontend, Express microservices, PostgreSQL + Redis)

## Key File Locations
- Python agent entry: agent/main.py
- Scan logic: agent/core/scanner.py
- Fix logic: agent/core/executor.py
- DB schema: agent/db/schema.sql
- Node API entry: api/src/index.ts
- Dashboard entry: dashboard/src/main.tsx
- K8s manifests: k8s/
