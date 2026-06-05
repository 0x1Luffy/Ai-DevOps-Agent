# AutoPilot DevOps Agent — Complete Build Prompt
## For Claude Code | Full Stack: Python Agent + Node.js API + React Dashboard
### Version 3.0 — Full Production Coverage: All Known K8s + Jenkins Failure Scenarios

---

## MISSION

Build **AutoPilot DevOps Agent** — a production-grade autonomous AI DevOps platform with three components:

1. **Python Agent** — Scans K8s cluster, diagnoses with Claude AI, auto-fixes issues, integrates with Jenkins
2. **Node.js/Express API** — Backend API that serves data to the frontend dashboard
3. **React Dashboard** — Real-time visualization of cluster health, incidents, fixes, and Jenkins pipelines

This is a REAL deployable system. No placeholders. No TODOs. Every file fully implemented.

**Developer context:**
- Name: Raj, Hexaware Technologies
- Comfort zone: Node.js, React, Express, PostgreSQL, Redis
- Environment: Oracle Cloud VM (Ubuntu ARM64), Kubernetes cluster, Jenkins deployed as a pod inside the same K8s cluster
- Application being monitored: 3-tier Node.js microservices (React frontend, Node.js/Express microservices, PostgreSQL + Redis)
- Existing stack: PostgreSQL (NeonDB/local), Redis, Docker Compose, Node.js

---

## SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                           │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   Python    │    │   Jenkins   │    │  Your 3-Tier App    │ │
│  │   Agent     │───▶│   (Pod)     │    │  frontend/backend/  │ │
│  │  (Pod)      │    │             │    │  db microservices   │ │
│  └──────┬──────┘    └──────┬──────┘    └─────────────────────┘ │
│         │ watches          │ webhooks                           │
│         ▼                  ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Redis (Queue + PubSub)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │ writes incidents/fixes
         ▼
┌─────────────────┐       ┌─────────────────────────────────────┐
│   PostgreSQL    │◀──────│     Node.js/Express API             │
│   (NeonDB)      │       │     (serves dashboard data)         │
└─────────────────┘       └──────────────┬──────────────────────┘
                                         │ REST + WebSocket
                                         ▼
                          ┌──────────────────────────────────────┐
                          │     React Dashboard                  │
                          │  (Vite + TypeScript + Tailwind)      │
                          └──────────────────────────────────────┘
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                     Slack Bot      GitHub API      Email SMTP
```

---

## COMPLETE PROJECT STRUCTURE

```
autopilot-devops-agent/
│
├── CLAUDE.md                          ← Project memory (described at end of prompt)
├── README.md
├── .env.example
├── docker-compose.yml                 ← All services for local dev
│
├── agent/                             ← Python autonomous agent
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                        ← Entry point, starts all schedulers + FastAPI
│   ├── config/
│   │   ├── settings.py                ← Pydantic BaseSettings (reads .env)
│   │   └── prompts/
│   │       ├── k8s_diagnosis.py       ← Claude system prompt for K8s issues
│   │       └── jenkins_diagnosis.py   ← Claude system prompt for Jenkins logs
│   ├── core/
│   │   ├── scanner.py                 ← K8s cluster scanner
│   │   ├── diagnoser.py               ← Claude AI diagnosis engine
│   │   ├── executor.py                ← Auto-fix executor
│   │   ├── feedback_loop.py           ← Post-fix verification
│   │   └── learning.py                ← Fix pattern success tracking
│   ├── integrations/
│   │   ├── jenkins.py                 ← Jenkins REST API + pipeline intelligence
│   │   ├── slack.py                   ← Slack Bolt: alerts + approval workflow + bot
│   │   ├── github.py                  ← Open issues + PR comments on failures
│   │   └── email.py                   ← SMTP escalation emails
│   ├── watchers/
│   │   ├── drift_detector.py          ← Config drift vs GitOps desired state
│   │   ├── expiry_watcher.py          ← TLS cert + Secret expiry alerts
│   │   └── resource_advisor.py        ← CPU/memory right-sizing weekly report
│   ├── api/
│   │   ├── main.py                    ← FastAPI app (webhooks only)
│   │   └── routes/
│   │       ├── jenkins_webhook.py     ← POST /webhooks/jenkins
│   │       ├── slack_webhook.py       ← POST /webhooks/slack
│   │       └── health_gate.py         ← GET /cluster/health-gate
│   └── db/
│       ├── connection.py              ← asyncpg pool
│       ├── migrations.py              ← Run all migrations on startup
│       ├── schema.sql                 ← All table definitions
│       └── repos/
│           ├── incidents.py
│           ├── fixes.py
│           ├── jenkins.py
│           └── patterns.py
│
├── api/                               ← Node.js/Express dashboard API
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts                   ← Express app entry, WS server
│   │   ├── config.ts                  ← Config from env
│   │   ├── db/
│   │   │   └── client.ts              ← pg Pool connection
│   │   ├── routes/
│   │   │   ├── incidents.ts           ← GET /api/incidents
│   │   │   ├── fixes.ts               ← GET /api/fixes, POST /api/fixes/:id/approve
│   │   │   ├── jenkins.ts             ← GET /api/jenkins/incidents
│   │   │   ├── cluster.ts             ← GET /api/cluster/health, GET /api/cluster/nodes
│   │   │   ├── dashboard.ts           ← GET /api/dashboard/summary
│   │   │   └── metrics.ts             ← GET /api/metrics/trends
│   │   ├── websocket/
│   │   │   └── broadcaster.ts         ← Broadcasts Redis pub/sub to WS clients
│   │   └── middleware/
│   │       ├── auth.ts                ← Simple API key auth
│   │       └── errorHandler.ts
│   └── tests/
│       └── routes.test.ts
│
├── dashboard/                         ← React frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types/
│       │   ├── incident.ts
│       │   ├── fix.ts
│       │   ├── jenkins.ts
│       │   └── cluster.ts
│       ├── api/
│       │   └── client.ts              ← Axios instance + all API calls
│       ├── hooks/
│       │   ├── useWebSocket.ts        ← Real-time updates hook
│       │   ├── useIncidents.ts
│       │   ├── useClusterHealth.ts
│       │   └── useDashboard.ts
│       ├── store/
│       │   └── index.ts               ← Zustand global state
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx
│       │   │   ├── Header.tsx
│       │   │   └── Layout.tsx
│       │   ├── dashboard/
│       │   │   ├── ClusterHealthScore.tsx
│       │   │   ├── IncidentSummaryCards.tsx
│       │   │   ├── ActivityFeed.tsx
│       │   │   └── JenkinsPipelineStatus.tsx
│       │   ├── incidents/
│       │   │   ├── IncidentTable.tsx
│       │   │   ├── IncidentDetailDrawer.tsx
│       │   │   ├── IncidentTimeline.tsx
│       │   │   └── SeverityBadge.tsx
│       │   ├── fixes/
│       │   │   ├── FixStepsViewer.tsx
│       │   │   ├── FixApprovalModal.tsx
│       │   │   └── FixHistoryTable.tsx
│       │   ├── cluster/
│       │   │   ├── NodeGrid.tsx
│       │   │   ├── NamespaceHealth.tsx
│       │   │   ├── PodStatusGrid.tsx
│       │   │   └── ResourceUsageBar.tsx
│       │   ├── jenkins/
│       │   │   ├── PipelineCard.tsx
│       │   │   ├── BuildHistory.tsx
│       │   │   └── FailureClassificationBadge.tsx
│       │   └── shared/
│       │       ├── StatusDot.tsx
│       │       ├── ConfidenceMeter.tsx
│       │       ├── CopyButton.tsx
│       │       └── EmptyState.tsx
│       └── pages/
│           ├── DashboardPage.tsx      ← Main overview
│           ├── IncidentsPage.tsx      ← All incidents with filters
│           ├── IncidentDetailPage.tsx ← Full incident detail + timeline
│           ├── ClusterPage.tsx        ← Nodes, namespaces, pods
│           ├── JenkinsPage.tsx        ← Pipeline health + build history
│           ├── FixHistoryPage.tsx     ← All fixes with success rates
│           └── SettingsPage.tsx       ← Agent config toggles (dry-run, etc.)
│
└── k8s/
    ├── namespace.yaml
    ├── serviceaccount.yaml
    ├── clusterrole.yaml
    ├── clusterrolebinding.yaml
    ├── agent-deployment.yaml
    ├── api-deployment.yaml
    ├── dashboard-deployment.yaml
    ├── services.yaml
    ├── configmap.yaml
    └── secrets-template.yaml
```

---

## COMPONENT 1: PYTHON AGENT (Full Specification)

### agent/core/scanner.py

Scan every 30 seconds via APScheduler. Also use `kubernetes.watch.Watch()` for real-time streaming.

**Namespaces:** Read from env `TARGET_NAMESPACES` (default: `default,production,staging`)

**Resources to scan and what to check:**

```
PODS:
  - phase: Pending > 5 min → PENDING_TOO_LONG
  - containerStatuses[].state.waiting.reason:
      CrashLoopBackOff → CRASH_LOOP (severity: HIGH)
      ImagePullBackOff → IMAGE_PULL_FAIL (severity: HIGH)
      ErrImagePull → IMAGE_PULL_FAIL (severity: HIGH)
      CreateContainerConfigError → CONFIG_ERROR (severity: HIGH)
      CreateContainerError → CONTAINER_CREATE_ERROR (severity: HIGH)
  - containerStatuses[].state.terminated.exitCode:
      137 → OOM_KILLED (severity: HIGH)
      1 → APP_CRASH (severity: MEDIUM)
      126, 127 → ENTRYPOINT_ERROR (severity: HIGH)
  - initContainerStatuses[].state — check init container failures
  - restartCount > 5 → HIGH_RESTART_COUNT (severity: MEDIUM)
  - conditions[Ready=False] with reason → NOT_READY

DEPLOYMENTS:
  - availableReplicas < desiredReplicas → REPLICA_MISMATCH (severity: MEDIUM-HIGH)
  - conditions[Available=False] → UNAVAILABLE
  - conditions[Progressing=False with DeadlineExceeded] → ROLLOUT_STUCK (severity: HIGH)
  - paused=true for > 30 min → DEPLOYMENT_PAUSED (severity: LOW)

NODES:
  - conditions[Ready=False] → NODE_NOT_READY (severity: CRITICAL)
  - conditions[MemoryPressure=True] → NODE_MEMORY_PRESSURE (severity: HIGH)
  - conditions[DiskPressure=True] → NODE_DISK_PRESSURE (severity: HIGH)
  - conditions[PIDPressure=True] → NODE_PID_PRESSURE (severity: HIGH)
  - allocatable CPU/memory < 10% remaining → NODE_RESOURCE_EXHAUSTED (severity: HIGH)

SERVICES:
  - subsets/endpoints empty (no ready addresses) → NO_ENDPOINTS (severity: HIGH)
  - selector matches 0 pods → SELECTOR_MISMATCH (severity: HIGH)

PERSISTENT VOLUME CLAIMS:
  - phase=Pending > 5 min → PVC_PENDING (severity: MEDIUM)
  - phase=Lost → PVC_LOST (severity: CRITICAL)

RESOURCE QUOTAS:
  - used/hard > 90% for any resource → QUOTA_NEAR_LIMIT (severity: MEDIUM)
  - used/hard = 100% → QUOTA_EXCEEDED (severity: HIGH) — this causes Pending pods

HORIZONTAL POD AUTOSCALERS:
  - conditions[AbleToScale=False] → HPA_SCALE_BLOCKED (severity: MEDIUM)
  - currentReplicas = maxReplicas for > 15 min → HPA_AT_MAX (severity: MEDIUM)
  - ScalingActive=False (metrics server issue) → METRICS_SERVER_ISSUE (severity: MEDIUM)
```

**Context collection per incident:**
- Pod logs: last 100 lines via `read_namespaced_pod_log`
- K8s events: `list_namespaced_event` filtered to the resource, last 10 events
- For pods: also collect logs from init containers if they failed
- For deployments: collect ReplicaSet events and last 3 revision annotations
- For nodes: collect system events
- Node resource usage: `top_node` if metrics-server available (catch failure gracefully)

**Deduplication:** Before emitting incident, check DB: is there an `open` or `fixing` incident for this exact `resource_type + resource_name + namespace + problem_type`? If yes, skip. Re-emit only after previous incident is `fixed` or `resolved`.

**Emit to Redis:** Push incident as JSON to Redis list `autopilot:incident_queue` using `LPUSH`.

### agent/core/diagnoser.py

```python
async def diagnose(incident: IncidentEvent) -> DiagnosisResult
```

- Pop from Redis queue, call Claude API
- Model: `claude-sonnet-4-20250514`
- Use system prompt from `config/prompts/k8s_diagnosis.py`
- Build user message with ALL collected context (logs, events, spec, node state)
- Parse response as strict JSON — if parse fails, retry once with: "Your previous response was not valid JSON. Return only the JSON object."
- Save full prompt + response to `incidents` table (for debugging and auditing)

**Auto-fix gate — proceed to executor ONLY if ALL conditions true:**
1. `confidence >= AI_CONFIDENCE_THRESHOLD` (default 85)
2. `autoFixable == true`
3. `severity not in [CRITICAL]`
4. namespace is NOT `kube-system` (except CoreDNS)
5. `ENABLE_AUTO_FIX == true`
6. `DRY_RUN == false`
7. Resource name is NOT the autopilot-agent itself

**If gate fails:** Set incident status to `needs_approval`, call `slack.send_approval_request(incident, diagnosis)`

### agent/core/executor.py

**Complete fix action matrix:**

```python
# FIX: CrashLoopBackOff
# Strategy: Analyze logs for root cause type
# If bad env var → patch deployment env from nearest ConfigMap match
# If OOM → patch_resource_limits (increase memory 50%)
# If app code crash → NOT auto-fixable, escalate
# Always: rolling restart via patch annotation

# FIX: ImagePullBackOff
# Get deployment revision history: apps_v1.list_namespaced_replica_set filtered by deployment
# Find last successful revision (annotation: deployment.kubernetes.io/revision)
# Extract image from that ReplicaSet spec
# Patch deployment with last known good image
# Add bad image tag to ConfigMap blacklist: autopilot-image-blacklist

# FIX: OOMKilled
# Read current memory limit from container spec
# New limit = current * 1.5, capped at 2Gi
# Patch deployment resource limits
# Add annotation: autopilot.io/oom-fix-applied=timestamp

# FIX: PENDING_TOO_LONG (resource shortage)
# Check ResourceQuota for namespace — if quota exceeded: alert, cannot auto-fix quota
# Check node allocatable resources
# If HPA exists: patch HPA maxReplicas + 2
# If no HPA: alert about resource shortage with node capacity details

# FIX: ROLLOUT_STUCK
# Check if it's been stuck > 10 min (from condition lastUpdateTime)
# kubectl rollout undo: patch deployment with last-applied-configuration annotation
# Add bad revision to ConfigMap: autopilot-bad-revisions

# FIX: NO_ENDPOINTS / SELECTOR_MISMATCH
# Get all pods in namespace with any labels
# Find pods whose labels partially match service selector
# Suggest corrected selector (DO NOT auto-apply selector fixes — too risky)
# Send to Slack for human approval with exact kubectl command

# FIX: NODE_MEMORY_PRESSURE / NODE_DISK_PRESSURE
# Cordon the node: patch node spec.unschedulable = true
# List pods on that node, evict non-daemonset pods gracefully
# Alert Slack CRITICAL with node name and pressure type

# FIX: METRICS_SERVER_ISSUE
# List pods in kube-system with label k8s-app=metrics-server
# Delete each pod (triggers restart via ReplicaSet)
# Wait 30s, verify HPA conditions recover

# FIX: PVC_PENDING
# Get StorageClass from PVC spec
# Check if StorageClass exists in cluster
# Alert with diagnosis: StorageClass missing vs provisioner issue vs capacity

# FIX: CONFIG_ERROR (CreateContainerConfigError)
# Usually missing Secret or ConfigMap
# Parse events for exact missing resource name
# Alert with: "ConfigMap 'xyz' referenced by pod does not exist" + creation template

# FIX: HPA_AT_MAX
# Alert that service is at max capacity
# Include: current replicas, CPU/memory usage %, recommendation to increase maxReplicas
# Provide exact kubectl command for human to run

# FIX: QUOTA_EXCEEDED
# Alert with quota breakdown table
# Provide kubectl command to increase quota
# Flag which pods are stuck due to this quota

async def patch_deployment(namespace: str, name: str, patch: dict) -> FixResult
async def rollout_undo(namespace: str, name: str) -> FixResult
async def delete_pod(namespace: str, name: str) -> FixResult
async def patch_service(namespace: str, name: str, patch: dict) -> FixResult
async def scale_hpa(namespace: str, name: str, max_replicas: int) -> FixResult
async def patch_resource_limits(namespace: str, deployment_name: str, container_name: str, memory_mi: int) -> FixResult
async def cordon_node(node_name: str) -> FixResult
async def evict_pods_from_node(node_name: str) -> FixResult
async def restart_deployment(namespace: str, name: str) -> FixResult  # patches annotation
async def add_to_image_blacklist(image: str) -> FixResult
async def restart_metrics_server() -> FixResult
```

**ALL methods must:**
- Log action to `fix_executions` table BEFORE executing with status `executing`
- Update `fix_executions` with result AFTER
- Be idempotent (check current state before applying)
- Return `FixResult(success: bool, message: str, action_taken: str)`
- Schedule `feedback_loop.verify_fix()` 2 minutes after successful execution

### agent/integrations/jenkins.py

**Jenkins is deployed as a pod in the same cluster. URL: `http://jenkins.jenkins.svc.cluster.local:8080`**

**Webhook handler (POST /webhooks/jenkins):**
```
Payload format (Generic Webhook Trigger plugin):
{
  "name": "microservice-deploy-pipeline",
  "build": {
    "number": 42,
    "phase": "FINALIZED",
    "status": "FAILURE",
    "url": "job/microservice-deploy-pipeline/42/",
    "full_url": "http://jenkins.../job/.../42/",
    "scm": {
      "branch": "main",
      "commit": "abc123"
    }
  }
}
```

**On FAILURE event:**
1. Fetch console log: `GET {JENKINS_URL}/job/{name}/{number}/consoleText` (Basic auth: user:token)
2. Fetch build info: `GET {JENKINS_URL}/job/{name}/{number}/api/json` for branch, duration, cause
3. Get Jenkins crumb for CSRF: `GET {JENKINS_URL}/crumbIssuer/api/json`
4. Truncate console log to last 300 lines
5. Send to Claude with `jenkins_diagnosis.py` system prompt
6. Parse response strictly as JSON

**Node.js specific failure detection — Claude must identify:**
- `npm ERR! code ERESOLVE` → peer dependency conflict (not retriable, needs manual fix)
- `npm ERR! 404` → package not found on registry (check spelling, retry once)
- `npm audit found X vulnerabilities` with `--audit-level=high` fail → open GitHub issue with vuln list
- `jest: command not found` → devDependencies not installed in prod context
- `Cannot find module` → missing dependency, not in package.json
- `ENOENT no such file or directory` in Docker build → wrong Dockerfile COPY path
- `error: failed to push some refs` → Docker registry auth failure (retry)
- `kubectl: error: the server doesn't have a resource type` → wrong k8s API version in manifests
- `Error from server (AlreadyExists)` → old k8s resource not cleaned up
- `ImagePullBackOff` seen in kubectl apply output → wrong image tag in manifest
- `Liveness probe failed` shortly after deploy → new version has health endpoint issue

**Action decision table:**
```
FLAKY_NETWORK          → retry (max 2), exponential backoff 30s/60s
NPM_REGISTRY_TIMEOUT   → retry (max 2)
DOCKER_PUSH_FAIL       → retry (max 2)
NPM_PEER_DEP_CONFLICT  → open GitHub issue, Slack alert, NO retry
NPM_AUDIT_FAIL         → open GitHub issue with vuln details, block deploy
TEST_FAILURE           → open GitHub issue with failing test names, Slack alert
KUBECTL_APPLY_FAIL     → open GitHub PR comment with diagnosis, Slack alert
MISSING_SECRET         → CRITICAL Slack alert, page escalation email, NO retry
DOCKER_BUILD_FAIL      → analyze Dockerfile error, open GitHub issue, NO retry
BUILD_OOM              → Slack alert with memory recommendation, NO retry
PERMISSION_DENIED      → CRITICAL Slack alert, NO retry
```

**Retry execution:**
```python
async def retry_build(job_name: str, build_number: int, crumb: str) -> bool:
    # POST {JENKINS_URL}/job/{job_name}/build
    # Include crumb in header: Jenkins-Crumb: {crumb}
    # Wait 5s, verify new build started by checking lastBuild.number > build_number
```

**Pre-deploy health gate:**
```
GET /cluster/health-gate

Response:
{
  "status": "HEALTHY" | "DEGRADED" | "UNHEALTHY",
  "score": 0-100,
  "issues": [{"type": "...", "detail": "...", "severity": "..."}],
  "recommendation": "Safe to deploy" | "Deploy with caution" | "Do not deploy",
  "checks": {
    "nodes_ready": {"score": 40, "details": "3/3 nodes ready"},
    "pod_health": {"score": 30, "details": "2 pods in CrashLoop in production"},
    "pvc_health": {"score": 15, "details": "All PVCs bound"},
    "recent_incidents": {"score": 10, "details": "4 incidents in last hour"}
  }
}
```

Score breakdown:
- Nodes: 40 pts. All ready = 40. Each NotReady = -15.
- Pod health: 30 pts. 0 crash/OOM in last 10 min = 30. Each crash = -5.
- PVC health: 15 pts. All bound = 15. Each unbound = -8.
- Recent incidents: 15 pts. 0 open incidents = 15. Each open = -3.
- Score < 60 = UNHEALTHY (block deploy). 60-79 = DEGRADED. 80+ = HEALTHY.

### agent/integrations/slack.py

**Use Slack Bolt SDK for Python (slack_bolt)**

**Alert message (non-approval, informational):**
```
Severity emoji: LOW=ℹ️ MEDIUM=⚠️ HIGH=🚨 CRITICAL=🔴

Format:
{emoji} {SEVERITY} INCIDENT — {resource_name}
─────────────────────────────────────
📍 Namespace: {namespace}
🔍 Root Cause: {rootCause}
📊 AI Confidence: {confidence}%
⏱ Detected: {timestamp}
🔧 Auto-fix applied: {fix action taken}
✅ Status: {fixed/still_broken/escalated}
```

**Approval message (HIGH severity, needs human):**
Use Slack Block Kit with:
- Header block: incident title
- Section block: root cause + confidence
- Section block: current state (what's broken)
- Section block: proposed fix in code block (exact kubectl commands)
- Section block: risk assessment
- Actions block: two buttons
  - "✅ Approve Fix" (action_id: approve_fix, value: {incident_id})
  - "❌ Skip — Handle Manually" (action_id: skip_fix, value: {incident_id})

**Approval button handler:**
```python
@app.action("approve_fix")
async def handle_approve(ack, body, say):
    # ack() immediately (Slack requires < 3s)
    # Extract incident_id from body.actions[0].value
    # Update Slack message: replace buttons with "⏳ Executing fix..."
    # Run executor.execute_fix_plan(incident_id)
    # Update Slack message with result: ✅ Fixed or ❌ Failed
```

**Slack Bot commands (@autopilot mention handler):**
```
status                    → cluster health summary (score + top issues)
status {namespace}        → namespace-specific health
rollback {service}        → sends approval message for rollout undo
logs {pod-name}           → last 50 lines of pod logs
incidents today           → table of today's incidents from DB
approve {incident-id}     → approves pending fix (same as button click)
dry-run on                → sets DRY_RUN=true in runtime config
dry-run off               → sets DRY_RUN=false in runtime config
help                      → lists all commands
```

### agent/watchers/drift_detector.py

- APScheduler every 5 minutes
- On successful Jenkins deploy: call `record_desired_state(namespace, deployment_name, spec)`
  - Snapshot: image tags, replica count, env var names (not values), resource limits, labels
  - Store in `desired_state` table
- Every 5 min: compare live state vs stored desired state for all watched deployments
- Drift types to detect:
  - Image tag changed (someone did `kubectl set image` manually)
  - Replica count changed (someone scaled manually)
  - Env var added/removed (someone did `kubectl edit`)
  - Resource limits changed
- On drift detected: Slack alert with exact diff
- If `DRIFT_AUTO_CORRECT=true`: patch back to desired state + log it

### agent/watchers/expiry_watcher.py

- APScheduler every 6 hours
- Scan all Secrets type=`kubernetes.io/tls` across all watched namespaces
- Base64 decode `tls.crt`, parse with Python `cryptography` library
- Extract `not_valid_after` datetime
- Days remaining = (not_valid_after - now).days
- Alert levels: <= 30 days = WARNING Slack, <= 7 days = CRITICAL Slack + email
- Store findings in `incidents` table with problem_type=`TLS_CERT_EXPIRY`
- Also scan Secrets with annotation `autopilot.io/expiry-date` for API tokens

---

## COMPONENT 2: NODE.JS/EXPRESS DASHBOARD API (Full Specification)

**Stack:** Node.js 20 + Express + TypeScript + pg (node-postgres) + ws (WebSocket) + Redis (ioredis)

### api/src/index.ts

- Express app on port 3001
- WebSocket server (ws library) on same port via server upgrade
- On startup: connect to PostgreSQL, connect to Redis, subscribe to `autopilot:events` pub/sub channel
- Redis pub/sub: whenever Python agent publishes an event, broadcast to all connected WebSocket clients
- Mount all routers under `/api`
- CORS: allow dashboard origin from env `DASHBOARD_URL`
- Simple API key auth middleware: check `Authorization: Bearer {API_KEY}` header. Key from env `API_KEY`.

### api/src/routes/incidents.ts

```
GET /api/incidents
  Query params: namespace, severity, status, problem_type, page, limit, from_date, to_date
  Returns: { incidents: Incident[], total: number, page: number, totalPages: number }

GET /api/incidents/:id
  Returns full incident with:
  - all incident fields
  - related fix_executions
  - timeline array (sorted events from detected to resolved)

GET /api/incidents/stats
  Returns: { total, open, fixing, fixed, by_severity: {}, by_problem_type: {}, avg_resolution_time_minutes }
```

### api/src/routes/fixes.ts

```
GET /api/fixes
  Query params: result, from_date, to_date, page, limit
  Returns: { fixes: FixExecution[], total, successRate }

GET /api/fixes/patterns
  Returns: fix_patterns table with success_rate, ordered by usage count desc

POST /api/fixes/:incident_id/approve
  Body: { approver: string }
  Publishes approval event to Redis → Python agent picks it up
  Returns: { approved: true, message: "Fix queued for execution" }
```

### api/src/routes/cluster.ts

```
GET /api/cluster/health
  Calls Python agent's health-gate endpoint, caches result 30s
  Returns health gate response

GET /api/cluster/nodes
  Proxies to Python agent which reads live K8s data
  Returns: node list with status, resource usage, conditions, pod count

GET /api/cluster/namespaces
  Returns: per-namespace health summary from DB incidents table
```

### api/src/routes/jenkins.ts

```
GET /api/jenkins/incidents
  Query params: job_name, resolved, from_date, page, limit
  Returns: { incidents: JenkinsIncident[], total, failuresByType: {} }

GET /api/jenkins/pipeline-health
  Returns: per-job success rate from jenkins_incidents table
  { jobs: [{ name, successRate, lastBuild, totalBuilds, commonFailureType }] }
```

### api/src/routes/dashboard.ts

```
GET /api/dashboard/summary
  Returns single aggregated object:
  {
    clusterHealthScore: number,
    clusterStatus: "HEALTHY" | "DEGRADED" | "UNHEALTHY",
    openIncidents: number,
    criticalIncidents: number,
    fixedLast24h: number,
    fixSuccessRate: number,        // last 7 days
    activeApprovals: number,       // incidents in 'needs_approval' status
    jenkinsFailures24h: number,
    topProblems: [{ type, count }],
    recentActivity: Activity[],    // last 10 events across all tables
    incidentTrend: [{ date, count }]  // last 7 days
  }
```

### api/src/routes/metrics.ts

```
GET /api/metrics/trends
  Query: days (default 7)
  Returns: {
    incidentsByDay: [{ date, count, by_severity: {} }],
    fixSuccessByDay: [{ date, successRate }],
    mttr: [{ date, avgMinutes }],  // mean time to resolve
    topNamespaces: [{ namespace, incidentCount }]
  }
```

### api/src/websocket/broadcaster.ts

- Subscribe to Redis channel `autopilot:events`
- Events published by Python agent: `{ type: "new_incident" | "fix_applied" | "fix_verified" | "jenkins_failure" | "approval_needed", data: {...} }`
- Broadcast to ALL connected WS clients as JSON
- WS clients send `{ type: "subscribe", channels: ["incidents", "cluster", "jenkins"] }` to filter events
- Heartbeat: ping every 30s, close connection if no pong in 10s

**Python agent must publish to Redis after every significant event:**
```python
await redis.publish("autopilot:events", json.dumps({
    "type": "new_incident",
    "data": { "id": "...", "severity": "HIGH", "resource": "...", "namespace": "..." }
}))
```

---

## COMPONENT 3: REACT DASHBOARD (Full Specification)

**Stack:** React 18 + TypeScript + Vite + Tailwind CSS + React Router v6 + Zustand + Recharts + React Query (TanStack Query) + shadcn/ui components

**Design system:**
- Dark theme (bg-gray-950 base, bg-gray-900 cards, bg-gray-800 borders)
- Status colors: RED = critical/error, ORANGE = high/warning, YELLOW = medium, GREEN = healthy/fixed, BLUE = info/low
- Font: Inter (Google Fonts)
- No external UI component library beyond shadcn/ui — build clean, minimal, professional

### Page: DashboardPage.tsx (route: /)

Layout: 2-column grid top, then full-width sections

**Top row — 4 stat cards:**
- Cluster Health Score: large circular progress ring (0-100), color changes red/yellow/green
- Open Incidents: count with severity breakdown mini-bar
- Fixed Last 24h: count with fix success rate %
- Pending Approvals: count with pulsing badge if > 0

**Middle row — 2 columns:**
Left: `IncidentSummaryCards` — last 5 open incidents as compact cards. Each shows: severity badge, resource name, problem type, time ago, confidence %. Click → navigate to incident detail.

Right: `JenkinsPipelineStatus` — last 5 pipeline builds. Each shows: pipeline name, build number, branch, status (pass/fail), duration, failure type badge if failed.

**Bottom row — full width:**
`ActivityFeed` — real-time feed of all events via WebSocket. Each entry: timestamp, icon (🔍 detected / 🔧 fixing / ✅ fixed / 🚨 escalated / 🔄 retried), description. New entries slide in from top with animation. Show last 20 entries, auto-scroll.

**Live indicator:** Green pulsing dot in header "Live" when WebSocket connected. Grey "Reconnecting..." when disconnected.

### Page: IncidentsPage.tsx (route: /incidents)

**Filters bar:**
- Namespace dropdown (populated from API)
- Severity multi-select: CRITICAL, HIGH, MEDIUM, LOW
- Status multi-select: open, fixing, fixed, needs_approval, manual, escalated
- Problem type dropdown
- Date range picker
- Search by resource name

**Table columns:**
Severity | Resource Name | Namespace | Problem Type | Detected | Status | Confidence | Actions

**Row details:**
- Severity: colored badge (CRITICAL=red, HIGH=orange, MEDIUM=yellow, LOW=blue)
- Status: colored status badge with icon
- Confidence: mini progress bar (red < 70, yellow < 85, green >= 85)
- Actions: "View Details" button

**Clicking a row:** Opens `IncidentDetailDrawer` from right side (slide-in panel, not new page — unless user clicks "Open Full Page")

### Component: IncidentDetailDrawer.tsx

Full incident detail in a right-side drawer (width: 600px).

**Sections:**

**Header:** Severity badge, resource name, namespace, problem type, time detected

**Root Cause (AI Analysis):**
```
Card with Claude AI icon
Root Cause: {rootCause text}
Confidence: [===-----] 72%
Severity: HIGH
Auto-fixable: Yes / No
Prevention Tip: {preventionTip}
```

**Fix Timeline:**
Vertical timeline showing all events for this incident in chronological order:
```
🔍 14:23:01  Detected — CrashLoopBackOff on payment-service
🤖 14:23:04  AI Diagnosed — OOM issue, confidence 91%
⏳ 14:23:04  Awaiting Approval — Slack message sent
✅ 14:25:33  Approved — by @raj.kumar in Slack
🔧 14:25:34  Fix Applied — Memory limit increased 256Mi → 384Mi
⏳ 14:27:34  Verifying — checking pod health...
✅ 14:28:01  Verified Fixed — pod running healthy
```
Each timeline item: icon, timestamp, title, description, expandable details

**Fix Steps Applied:**
If a fix was executed, show each step as a numbered card:
```
Step 1: patch_deployment
Command: kubectl patch deployment payment-service -n production \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"payment",
  "resources":{"limits":{"memory":"384Mi"}}}]}}}}'
Status: ✅ Success
```
Each command has a copy button.

**Raw K8s Context (collapsible):**
JSON viewer showing the raw pod/deployment spec that was captured at incident time. Syntax highlighted, collapsible tree.

**AI Prompt/Response (collapsible, for debugging):**
Show the exact prompt sent to Claude and exact response received.

### Page: IncidentsPage → IncidentDetailPage.tsx (route: /incidents/:id)

Same content as drawer but full page layout, with back button.

### Page: ClusterPage.tsx (route: /cluster)

**Top: Health Gate Card**
Big card showing current cluster health gate: status (HEALTHY/DEGRADED/UNHEALTHY), score, breakdown of each check category as progress bars, list of current issues.

**Node Grid (NodeGrid.tsx):**
Grid of node cards (one per node). Each card shows:
- Node name, role (control-plane / worker)
- Status indicator: green dot (Ready) / red dot (NotReady)
- CPU usage bar: used/allocatable
- Memory usage bar: used/allocatable
- Pod count: running/capacity
- Conditions: show warning badges for any non-normal conditions
- Taints (if any)

**Namespace Health (NamespaceHealth.tsx):**
Table: Namespace | Running Pods | Failing Pods | Open Incidents | Resource Quota Usage | Status
Color-code rows by health.

**Pod Status Grid (PodStatusGrid.tsx):**
Filter by namespace.
Grid of pod cards, color-coded by status:
- Green: Running + Ready
- Orange: Running + not Ready
- Red: CrashLoopBackOff / Error
- Yellow: Pending
- Grey: Terminating
Each card: pod name, namespace, status, restart count, age.
Click pod card → show last 50 lines of logs in a modal with copy button.

### Page: JenkinsPage.tsx (route: /jenkins)

**Pipeline Health Overview:**
Table of all Jenkins jobs seen in the last 30 days:
Job Name | Last Build | Branch | Status | Success Rate (7d) | Common Failure | Avg Duration

**Build History:**
Timeline/table of recent builds across all jobs:
Build # | Job | Branch | Status | Duration | Failure Type | Action Taken | Time

**Failure Distribution Chart:**
Pie/donut chart (Recharts) showing breakdown of failure types in last 7 days.

**Auto-Retry Stats:**
Card showing: Total retries initiated | Retry success rate | Retries saved vs manual intervention

### Page: FixHistoryPage.tsx (route: /fixes)

**Fix Patterns Table:**
Problem Type | Fix Action | Success Count | Failure Count | Success Rate | Last Used
Sorted by usage count desc. Success rate shown as colored percentage.

**Fix Execution History:**
Table: Time | Incident | Action | Executed By | Result | Verified Status | Details
Filter: result (success/failed), executed_by (auto/human)

**Fix Success Rate Chart:**
Line chart (Recharts) showing fix success rate trend over last 30 days.

### Page: SettingsPage.tsx (route: /settings)

**Agent Configuration:**
Toggle switches (read from API, POST changes back):
- Enable Auto-Fix (ENABLE_AUTO_FIX)
- Dry Run Mode (DRY_RUN) — warning banner when enabled
- Drift Auto-Correct (DRIFT_AUTO_CORRECT)

**Threshold Settings:**
- AI Confidence Threshold: slider 50-100 (default 85)
- Scan Interval: dropdown 15s / 30s / 60s
- Post-Fix Verify Delay: dropdown 1min / 2min / 5min
- Slack Approval Timeout: number input (minutes)

**Watched Namespaces:**
Multi-select tag input for TARGET_NAMESPACES

**Hard Rules Display (read-only):**
List of the 10 hard rules that are always enforced, displayed as info cards. Not editable.

### dashboard/src/hooks/useWebSocket.ts

```typescript
// Connects to ws://api:3001
// Auto-reconnects with exponential backoff (1s, 2s, 4s, 8s, max 30s)
// Returns: { connected, lastMessage, subscribe(channels) }
// On new message: updates Zustand store
// Exports: useWebSocket() hook
```

### dashboard/src/store/index.ts (Zustand)

```typescript
interface AppStore {
  // Dashboard summary
  summary: DashboardSummary | null
  setSummary: (s: DashboardSummary) => void

  // Real-time activity feed
  activityFeed: ActivityEvent[]
  addActivity: (event: ActivityEvent) => void  // prepend, keep max 50

  // Live incident updates from WS
  liveIncidentUpdates: Map<string, Partial<Incident>>
  updateIncident: (id: string, update: Partial<Incident>) => void

  // WS connection state
  wsConnected: boolean
  setWsConnected: (v: boolean) => void

  // Settings
  agentConfig: AgentConfig | null
  setAgentConfig: (c: AgentConfig) => void
}
```

---

## DATABASE SCHEMA (PostgreSQL) — IMPLEMENT ALL OF THIS

```sql
-- schema.sql (full file, applied by db/migrations.py on startup)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  resource_type VARCHAR(50) NOT NULL,
  resource_name VARCHAR(255) NOT NULL,
  namespace VARCHAR(100) NOT NULL,
  problem_type VARCHAR(100) NOT NULL,
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  root_cause TEXT,
  confidence INTEGER CHECK (confidence BETWEEN 0 AND 100),
  auto_fixable BOOLEAN DEFAULT FALSE,
  fix_plan JSONB,
  prevention_tip TEXT,
  estimated_recovery VARCHAR(100),
  related_resources JSONB,
  status VARCHAR(30) DEFAULT 'open' CHECK (status IN (
    'open','diagnosing','needs_approval','fixing','fixed','still_broken','escalated','manual','skipped'
  )),
  resolved_at TIMESTAMPTZ,
  slack_message_ts VARCHAR(100),
  slack_channel VARCHAR(100),
  claude_prompt TEXT,
  claude_response TEXT,
  full_context JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fix_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
  executed_at TIMESTAMPTZ DEFAULT NOW(),
  fix_action VARCHAR(100) NOT NULL,
  fix_params JSONB,
  fix_description TEXT,
  kubectl_commands TEXT[],
  executed_by VARCHAR(50) DEFAULT 'auto',
  approver_slack_id VARCHAR(100),
  result VARCHAR(30) CHECK (result IN ('success','failed','partial','skipped')),
  verification_status VARCHAR(30) CHECK (verification_status IN ('fixed','still_broken','degraded','pending','skipped')),
  verified_at TIMESTAMPTZ,
  error_message TEXT,
  execution_duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS jenkins_incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  job_name VARCHAR(255) NOT NULL,
  build_number INTEGER,
  branch VARCHAR(255),
  commit_sha VARCHAR(100),
  failure_type VARCHAR(100),
  failing_stage VARCHAR(255),
  failing_line TEXT,
  ai_diagnosis JSONB,
  action_taken VARCHAR(100),
  retry_count INTEGER DEFAULT 0,
  resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMPTZ,
  github_issue_url VARCHAR(500),
  build_duration_seconds INTEGER,
  console_log_snippet TEXT
);

CREATE TABLE IF NOT EXISTS fix_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  problem_pattern VARCHAR(100) NOT NULL,
  fix_action VARCHAR(100) NOT NULL,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  last_used TIMESTAMPTZ,
  UNIQUE(problem_pattern, fix_action)
);

CREATE TABLE IF NOT EXISTS desired_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recorded_at TIMESTAMPTZ DEFAULT NOW(),
  resource_type VARCHAR(50) NOT NULL,
  resource_name VARCHAR(255) NOT NULL,
  namespace VARCHAR(100) NOT NULL,
  spec_snapshot JSONB NOT NULL,
  image_tags JSONB,
  env_var_keys TEXT[],
  resource_limits JSONB,
  replica_count INTEGER,
  recorded_by VARCHAR(100) DEFAULT 'jenkins',
  UNIQUE(resource_type, resource_name, namespace)
);

CREATE TABLE IF NOT EXISTS drift_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  resource_type VARCHAR(50),
  resource_name VARCHAR(255),
  namespace VARCHAR(100),
  drift_type VARCHAR(100),
  old_value JSONB,
  new_value JSONB,
  auto_corrected BOOLEAN DEFAULT FALSE,
  corrected_at TIMESTAMPTZ
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_namespace ON incidents(namespace);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_detected_at ON incidents(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_fix_executions_incident_id ON fix_executions(incident_id);
CREATE INDEX IF NOT EXISTS idx_jenkins_incidents_job_name ON jenkins_incidents(job_name);
CREATE INDEX IF NOT EXISTS idx_jenkins_incidents_detected_at ON jenkins_incidents(detected_at DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER incidents_updated_at
  BEFORE UPDATE ON incidents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

---

## ENVIRONMENT VARIABLES

```env
# ── KUBERNETES ──────────────────────────────
K8S_IN_CLUSTER=true
TARGET_NAMESPACES=default,production,staging
KUBECONFIG=/root/.kube/config

# ── CLAUDE AI ───────────────────────────────
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-20250514
AI_CONFIDENCE_THRESHOLD=85

# ── DATABASE ────────────────────────────────
DATABASE_URL=postgresql://user:pass@postgres:5432/autopilot

# ── REDIS ───────────────────────────────────
REDIS_URL=redis://redis:6379

# ── JENKINS ─────────────────────────────────
JENKINS_URL=http://jenkins.jenkins.svc.cluster.local:8080
JENKINS_USER=admin
JENKINS_TOKEN=
JENKINS_WEBHOOK_SECRET=
JENKINS_MAX_RETRIES=2

# ── SLACK ───────────────────────────────────
SLACK_BOT_TOKEN=xoxb-
SLACK_SIGNING_SECRET=
SLACK_ALERT_CHANNEL=#devops-alerts
SLACK_APPROVAL_CHANNEL=#devops-approvals
SLACK_APPROVAL_TIMEOUT_MINUTES=30

# ── GITHUB ──────────────────────────────────
GITHUB_TOKEN=ghp_
GITHUB_REPO=org/repo-name

# ── EMAIL ───────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
ESCALATION_EMAIL=raj@hexaware.com

# ── AGENT BEHAVIOUR ─────────────────────────
SCAN_INTERVAL_SECONDS=30
POST_FIX_VERIFY_DELAY_SECONDS=120
ENABLE_AUTO_FIX=true
DRY_RUN=false
DRIFT_AUTO_CORRECT=false

# ── NODE.JS API ─────────────────────────────
API_PORT=3001
API_KEY=change-me-in-production
DASHBOARD_URL=http://localhost:5173

# ── REACT DASHBOARD ─────────────────────────
VITE_API_URL=http://localhost:3001
VITE_WS_URL=ws://localhost:3001
```

---

## DOCKER COMPOSE (local dev, all services)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment: { POSTGRES_DB: autopilot, POSTGRES_USER: autopilot, POSTGRES_PASSWORD: autopilot }
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autopilot"]
      interval: 5s

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  agent:
    build: ./agent
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    volumes:
      - ~/.kube:/root/.kube:ro  # for local dev outside cluster
    ports:
      - "8000:8000"   # FastAPI webhooks

  api:
    build: ./api
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    ports:
      - "3001:3001"

  dashboard:
    build: ./dashboard
    env_file: .env
    depends_on:
      - api
    ports:
      - "5173:80"
```

---

## KUBERNETES MANIFESTS

### k8s/clusterrole.yaml — GRANT ALL REQUIRED PERMISSIONS

```yaml
rules:
# Full read across cluster
- apiGroups: [""] 
  resources: [pods, pods/log, pods/exec, pods/eviction, services, endpoints, 
              nodes, configmaps, persistentvolumeclaims, resourcequotas, 
              namespaces, events, secrets]
  verbs: [get, list, watch]
- apiGroups: [apps]
  resources: [deployments, replicasets, statefulsets, daemonsets]
  verbs: [get, list, watch, patch, update]
# Write for auto-fix actions
- apiGroups: [""]
  resources: [pods]
  verbs: [delete]
- apiGroups: [""]
  resources: [nodes]
  verbs: [patch, update]   # for cordon
- apiGroups: [""]
  resources: [configmaps]
  verbs: [create, patch, update]   # for blacklist configmaps
- apiGroups: [apps]
  resources: [deployments]
  verbs: [patch, update]
- apiGroups: [autoscaling]
  resources: [horizontalpodautoscalers]
  verbs: [get, list, watch, patch, update]
- apiGroups: [networking.k8s.io]
  resources: [ingresses]
  verbs: [get, list, watch]
# Policy for eviction
- apiGroups: [policy]
  resources: [poddisruptionbudgets]
  verbs: [get, list]
```

---

## HARD RULES — NEVER VIOLATE

1. NEVER auto-fix anything in `kube-system` (except metrics-server and CoreDNS pods — delete only to trigger restart)
2. NEVER delete PVCs, PersistentVolumes, or Secrets
3. NEVER create or modify RBAC resources
4. NEVER auto-fix if severity = CRITICAL — always require Slack approval
5. NEVER auto-fix if confidence < AI_CONFIDENCE_THRESHOLD
6. NEVER fix the `autopilot-agent` pod/deployment itself
7. NEVER retry Jenkins pipeline more than JENKINS_MAX_RETRIES times (default 2)
8. ALL fix methods must be idempotent
9. ALL fix executions must be logged to DB before and after
10. If DRY_RUN=true: log everything, alert everything, execute NOTHING
11. NEVER delete Secrets (even if they appear to be causing issues)
12. For selector mismatch fixes: ALERT only, never auto-apply

---

## CLAUDE AI PROMPTS — EXACT CONTENT

### config/prompts/k8s_diagnosis.py

```python
K8S_SYSTEM_PROMPT = """You are AutoPilot, a senior Kubernetes SRE AI with 10 years of production experience.
You receive structured data about a Kubernetes incident including pod logs, events, resource specs, and node state.

Return ONLY a single valid JSON object. No markdown backticks. No text before or after the JSON.

RULES:
- autoFixable MUST be false for: data loss risk, security issues, RBAC, PVC deletion, kube-system (except CoreDNS/metrics-server restart), CRITICAL severity
- confidence is your true certainty (0-100). Never exceed 95. Be conservative.
- fixPlan actions must ONLY use: patch_deployment, rollout_undo, delete_pod, patch_service, scale_hpa, restart_daemonset, patch_resource_limits, cordon_node, restart_metrics_server, add_image_to_blacklist
- Each fixPlan step must include the exact params object needed to execute it
- preventionTip must be specific to THIS incident, not generic advice
- If root cause is unclear from provided data, say so honestly and lower confidence

RESPONSE FORMAT:
{
  "rootCause": "Clear 1-2 sentence explanation of what went wrong and why",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "autoFixable": true|false,
  "confidence": 0-100,
  "fixPlan": [
    {
      "action": "action_name",
      "params": {},
      "description": "human-readable description of this step",
      "kubectl_equivalent": "exact kubectl command a human would run"
    }
  ],
  "preventionTip": "specific prevention advice",
  "estimatedRecovery": "e.g. '2-3 minutes after fix applied'",
  "relatedResources": ["other resource names that may be affected"],
  "notAutoFixableReason": "if autoFixable=false, explain why"
}"""
```

### config/prompts/jenkins_diagnosis.py

```python
JENKINS_SYSTEM_PROMPT = """You are AutoPilot, a CI/CD expert AI specializing in Node.js microservice pipelines.
You receive a Jenkins pipeline console log for a Node.js application build.

Return ONLY a single valid JSON object. No markdown. No text before or after JSON.

FAILURE TYPES (pick exactly one):
FLAKY_NETWORK, NPM_PEER_DEP_CONFLICT, NPM_REGISTRY_TIMEOUT, NPM_AUDIT_FAIL,
DOCKER_BUILD_FAIL, DOCKER_PUSH_FAIL, TEST_FAILURE, KUBECTL_APPLY_FAIL,
BUILD_OOM, MISSING_SECRET, PERMISSION_DENIED, TIMEOUT, LIVENESS_PROBE_FAIL,
UNKNOWN

AUTO-RETRIABLE (max 2 retries): FLAKY_NETWORK, NPM_REGISTRY_TIMEOUT, DOCKER_PUSH_FAIL, TIMEOUT
NOT RETRIABLE: NPM_PEER_DEP_CONFLICT, NPM_AUDIT_FAIL, TEST_FAILURE, KUBECTL_APPLY_FAIL,
              BUILD_OOM, MISSING_SECRET, PERMISSION_DENIED, LIVENESS_PROBE_FAIL, DOCKER_BUILD_FAIL

RESPONSE FORMAT:
{
  "failureType": "...",
  "failingStage": "exact pipeline stage name",
  "failingLine": "the exact console line that caused failure",
  "rootCause": "clear explanation of what failed and why",
  "autoRetriable": true|false,
  "suggestedFix": "specific fix steps if not retriable",
  "githubIssueTitle": "concise issue title",
  "githubIssueBody": "## Root Cause\n...\n\n## Failing Stage\n...\n\n## Console Output\n```\n{relevant lines}\n```\n\n## Suggested Fix\n...",
  "shouldBlockDeploy": true|false,
  "urgency": "LOW|MEDIUM|HIGH|CRITICAL"
}"""
```

---

## BUILD ORDER FOR CLAUDE CODE

Build files in EXACTLY this order (dependency order, no broken imports):

**Phase 1 — Foundation**
1. `agent/requirements.txt`
2. `agent/config/settings.py`
3. `agent/db/schema.sql`
4. `agent/db/connection.py`
5. `agent/db/migrations.py`
6. `agent/db/repos/incidents.py`
7. `agent/db/repos/fixes.py`
8. `agent/db/repos/jenkins.py`
9. `agent/db/repos/patterns.py`

**Phase 2 — Agent Core**
10. `agent/config/prompts/k8s_diagnosis.py`
11. `agent/config/prompts/jenkins_diagnosis.py`
12. `agent/core/scanner.py`
13. `agent/core/diagnoser.py`
14. `agent/core/executor.py`
15. `agent/core/feedback_loop.py`
16. `agent/core/learning.py`

**Phase 3 — Integrations**
17. `agent/integrations/slack.py`
18. `agent/integrations/jenkins.py`
19. `agent/integrations/github.py`
20. `agent/integrations/email.py`

**Phase 4 — Watchers**
21. `agent/watchers/drift_detector.py`
22. `agent/watchers/expiry_watcher.py`
23. `agent/watchers/resource_advisor.py`

**Phase 5 — Agent API**
24. `agent/api/routes/jenkins_webhook.py`
25. `agent/api/routes/slack_webhook.py`
26. `agent/api/routes/health_gate.py`
27. `agent/api/main.py`
28. `agent/main.py`
29. `agent/Dockerfile`

**Phase 6 — Node.js API**
30. `api/package.json` (dependencies: express, pg, ioredis, ws, cors, typescript, ts-node)
31. `api/tsconfig.json`
32. `api/src/config.ts`
33. `api/src/db/client.ts`
34. `api/src/middleware/auth.ts`
35. `api/src/middleware/errorHandler.ts`
36. `api/src/routes/incidents.ts`
37. `api/src/routes/fixes.ts`
38. `api/src/routes/cluster.ts`
39. `api/src/routes/jenkins.ts`
40. `api/src/routes/dashboard.ts`
41. `api/src/routes/metrics.ts`
42. `api/src/websocket/broadcaster.ts`
43. `api/src/index.ts`
44. `api/Dockerfile`

**Phase 7 — React Dashboard**
45. `dashboard/package.json` (dependencies: react, react-dom, react-router-dom, zustand, @tanstack/react-query, axios, recharts, lucide-react, tailwindcss, vite)
46. `dashboard/vite.config.ts`
47. `dashboard/tailwind.config.ts`
48. `dashboard/tsconfig.json`
49. `dashboard/src/types/*.ts` (all 4 type files)
50. `dashboard/src/api/client.ts`
51. `dashboard/src/hooks/useWebSocket.ts`
52. `dashboard/src/hooks/useIncidents.ts`
53. `dashboard/src/hooks/useClusterHealth.ts`
54. `dashboard/src/hooks/useDashboard.ts`
55. `dashboard/src/store/index.ts`
56. `dashboard/src/components/shared/*.tsx` (all 4)
57. `dashboard/src/components/layout/*.tsx` (all 3)
58. `dashboard/src/components/dashboard/*.tsx` (all 4)
59. `dashboard/src/components/incidents/*.tsx` (all 4)
60. `dashboard/src/components/fixes/*.tsx` (all 3)
61. `dashboard/src/components/cluster/*.tsx` (all 4)
62. `dashboard/src/components/jenkins/*.tsx` (all 3)
63. `dashboard/src/pages/*.tsx` (all 7)
64. `dashboard/src/App.tsx`
65. `dashboard/src/main.tsx`
66. `dashboard/index.html`
67. `dashboard/Dockerfile`

**Phase 8 — Infrastructure**
68. `k8s/namespace.yaml`
69. `k8s/serviceaccount.yaml`
70. `k8s/clusterrole.yaml`
71. `k8s/clusterrolebinding.yaml`
72. `k8s/agent-deployment.yaml`
73. `k8s/api-deployment.yaml`
74. `k8s/dashboard-deployment.yaml`
75. `k8s/services.yaml`
76. `k8s/configmap.yaml`
77. `k8s/secrets-template.yaml`

**Phase 9 — Supporting files**
78. `docker-compose.yml`
79. `.env.example`
80. `README.md`
81. `CLAUDE.md`

---

## CODE QUALITY REQUIREMENTS

**Python (agent):**
- Full type hints on every function
- Docstrings on every class and public method
- Use `structlog` for structured JSON logging
- Async everywhere that touches I/O
- Exception handling: NEVER crash the main scanner loop
  - Each scan cycle is try/except, log error, continue
  - Each fix attempt is try/except, log to DB, escalate to Slack on failure
- Pydantic models for all data structures (IncidentEvent, DiagnosisResult, FixResult)

**Node.js API:**
- TypeScript strict mode
- Input validation on all routes (use zod or express-validator)
- Proper error responses: `{ error: string, code: string }`
- All DB queries must use parameterized queries (no string interpolation)
- All routes must have try/catch with next(error) pattern

**React:**
- TypeScript strict mode
- No `any` types
- All API calls through React Query (useQuery/useMutation)
- Loading states and error states on every data-fetching component
- Responsive: works on 1280px+ screens minimum
- No inline styles — Tailwind only
- All icons from lucide-react

---

## EXTENDED K8S COVERAGE — ALL MISSING PRODUCTION SCENARIOS

Add all of the following to `agent/core/scanner.py` detection logic and `agent/core/executor.py` fix matrix. These are REQUIRED, not optional.

### K8s Extended Detection and Fixes

#### EVICTED PODS
- Detection: pod.status.reason == "Evicted" — these do NOT show as CrashLoopBackOff. They silently pile up.
- Scanner: list all pods in all watched namespaces, filter phase=Failed AND reason=Evicted
- Root cause extraction: pod.status.message contains eviction reason (e.g. "The node was low on resource: memory")
- Fix: delete evicted pods (they are already dead, just taking up namespace quota slots)
- Action: `delete_pod` for each evicted pod
- After fix: check if underlying node pressure caused them — link to any open NODE_MEMORY_PRESSURE incident
- Severity: MEDIUM (LOW if < 3 evicted, HIGH if > 10 evicted in same namespace)

#### PODS STUCK IN TERMINATING
- Detection: pod.metadata.deletionTimestamp is set AND pod has been in that state > 5 minutes
- This blocks rollouts — new pods can't start if old ones won't die
- Root cause: usually a finalizer that can't complete, or a node that went NotReady mid-delete
- Fix strategy:
  - Check if pod's node is Ready — if node NotReady, that's why pod can't terminate
  - Check pod finalizers: if finalizers exist and node is NotReady → force delete
  - Force delete command: `kubectl delete pod {name} --grace-period=0 --force`
  - In Python: patch pod metadata.finalizers = [] then delete
- autoFixable: true if stuck > 10 minutes AND (node is NotReady OR no finalizers blocking)
- autoFixable: false if pod has custom finalizers (unknown what they do) — alert instead
- Severity: HIGH if it's blocking a deployment rollout, MEDIUM otherwise

#### POD DISRUPTION BUDGET BLOCKING ROLLOUT
- Detection:
  - Deployment has a rollout in progress (check ReplicaSet annotations)
  - ReplicaSet conditions contain "cannot disrupt" or PDB-related message
  - Check: `list_namespaced_pod_disruption_budget` — compare minAvailable/maxUnavailable vs current available pods
- Root cause: PDB says "keep at least N pods available" but only exactly N pods exist — can't take any down
- Fix: NOT auto-fixable — patching PDB is risky
- Action: Slack alert with exact diagnosis:
  "PDB '{pdb_name}' requires minAvailable={n} but deployment only has {n} pods. 
   Either scale up deployment to {n+2} first, or temporarily patch PDB.
   kubectl patch pdb {pdb_name} -n {ns} -p '{\"spec\":{\"minAvailable\":{n-1}}}'"
- Severity: HIGH (blocks deploy)

#### INGRESS FAILURES
- Detection: scan all Ingress resources every 60 seconds
  - Check ingress.status.loadBalancer.ingress — if empty for > 5 min: INGRESS_NO_LB
  - Check ingress annotations for nginx/traefik class — if ingress controller pods not running: INGRESS_CONTROLLER_DOWN
  - Check ingress rules: if backend service doesn't exist: INGRESS_BACKEND_MISSING
  - Check TLS secret referenced in ingress.spec.tls — if secret missing or expired: INGRESS_TLS_INVALID
- Fix for INGRESS_CONTROLLER_DOWN:
  - Find ingress controller deployment (label: app.kubernetes.io/name=ingress-nginx OR app=traefik)
  - Check its pod status — if CrashLoop, treat as standard pod fix
  - If deployment has 0 replicas: patch replicas to 1 (alert, don't auto-fix)
- Fix for INGRESS_BACKEND_MISSING: alert with missing service name
- Fix for INGRESS_TLS_INVALID: alert, link to cert-manager if present
- Severity: CRITICAL for INGRESS_CONTROLLER_DOWN (entire cluster ingress broken)

#### CERT-MANAGER FAILURES
- Detection: scan Certificate resources (cert-manager.io/v1 Certificate)
  - Check certificate.status.conditions[Ready=False]
  - Check certificate.status.notAfter — if expired
  - Check CertificateRequest resources for failed ACME challenges
- If cert-manager CRDs don't exist: skip silently (cert-manager not installed)
- Root causes:
  - ACME challenge failed (HTTP-01: ingress not reachable, DNS-01: DNS propagation)
  - Rate limited by Let's Encrypt
  - Wrong secret name referenced
- Fix: NOT auto-fixable — cert issuance is complex
- Action: detailed Slack alert with:
  - Certificate name, namespace, domain
  - Exact failure reason from status.conditions[0].message
  - Days until/since expiry
  - Commands to manually trigger renewal: `kubectl annotate certificate {name} cert-manager.io/issuer-kind=`
- Severity: HIGH if expiring < 7 days, CRITICAL if already expired

#### DNS RESOLUTION FAILURES (inter-service)
- Detection: two signals
  1. Pod logs contain: "getaddrinfo ENOTFOUND", "dial tcp: lookup", "could not resolve host", "DNS lookup failed"
  2. CoreDNS pods in kube-system: check for high error rate in CoreDNS logs or pod restarts
- Scanner: when diagnosing CrashLoop or app crash, ALSO scan logs for DNS error strings
- Root causes:
  - CoreDNS pods OOMKilled or crashlooping
  - Service name typo in app config (e.g. "user-service" vs "userservice")
  - Cross-namespace DNS not using FQDN (e.g. should be "user-service.production.svc.cluster.local")
  - ndots config misconfigured
- Fix for CoreDNS down:
  - Delete CoreDNS pods (they restart via Deployment): `restart_deployment("kube-system", "coredns")`
  - This IS the one kube-system auto-fix allowed
- Fix for app DNS config: alert with correct FQDN format
- Severity: HIGH (multiple services likely affected)

#### NETWORK POLICY BLOCKING TRAFFIC
- Detection: challenging — infer from pattern:
  - Pod is Running+Ready, Service has endpoints, but another pod can't reach it
  - Pod logs show "connection refused" or "connection timed out" to another service
  - Check: are NetworkPolicy resources present in the namespace?
  - If NetworkPolicy exists AND pod-to-pod call is failing: flag as potential NETWORK_POLICY_BLOCK
- Fix: NOT auto-fixable — modifying NetworkPolicy is security-sensitive
- Action: Slack alert with:
  - Source pod, destination service, error from logs
  - List of existing NetworkPolicy resources in namespace
  - Guidance: "Check if NetworkPolicy '{policy_name}' allows traffic from {source_labels} to {dest_labels}"
- Severity: HIGH

#### CONTAINER RUNTIME ERRORS (ContainerCreating stuck)
- Detection: pod.status.phase == Pending AND containerStatuses[0].state.waiting.reason == "ContainerCreating" for > 3 minutes
  - Check events for: "failed to create containerd task", "rpc error: code = Unknown", "failed to pull and unpack image"
  - Distinct from ImagePullBackOff — image may be pulled but container runtime failing
- Root causes:
  - containerd/CRI socket issue on specific node
  - Image layers corrupted in node cache
  - Volume mount failing (even if PVC is Bound)
  - Init process crashing before container starts
- Fix:
  - Identify which node the pod is scheduled on
  - Check if other pods on same node have ContainerCreating issues — if yes: node-level issue
  - If isolated to one pod: delete pod to reschedule to different node
  - If node-level: cordon node + alert
- Severity: HIGH if multiple pods affected, MEDIUM if single pod

#### STATEFULSET FAILURES
- Detection: scan StatefulSets in watched namespaces
  - Check: readyReplicas < replicas
  - Check: updateRevision != currentRevision AND update stuck > 10 min
  - StatefulSets update pods in ORDER (pod-0, pod-1...) unlike Deployments
  - If pod-0 is failing, pod-1 will never update — detect this specific pattern
- Root cause: StatefulSet pod failures block the entire update chain
- Fix: same as Deployment pod fixes (CrashLoop, OOM etc) but add context about ordered update impact
- Special case: if a StatefulSet pod has a PVC that's stuck, the pod will never start — alert with PVC details
- Severity: HIGH (StatefulSets usually = databases/Redis = data layer)

#### JOB AND CRONJOB FAILURES
- Detection: scan Jobs and CronJobs every 60 seconds
  - Job: check status.failed > 0, check status.conditions[Failed=True]
  - CronJob: check lastScheduleTime — if CronJob schedule should have run but lastSuccessfulTime is old
  - Check for CronJob with spec.suspend=true accidentally (was it meant to be suspended?)
- Root causes:
  - DB migration job failed (most common in Node.js 3-tier apps)
  - Scheduled cleanup job failing
  - Job backoffLimit exceeded
- Fix: NOT auto-retriable (jobs usually run migrations — retrying blindly is dangerous)
- Action: Slack HIGH alert with:
  - Job name, namespace, failure reason from pod logs
  - Number of retries attempted vs backoffLimit
  - "This may be a failed DB migration. Check logs before retrying."
- Severity: HIGH for migration jobs (detectable by name containing "migrate" or "migration"), MEDIUM for others

#### RBAC/PERMISSION ERRORS IN APPLICATION
- Detection: pod logs contain "User cannot", "forbidden", "403 Forbidden", "does not have permission", "is not allowed to"
  - Specifically for K8s API calls from within pods (apps using in-cluster K8s client)
- Root cause: Pod's ServiceAccount lacks required RBAC permissions
- Fix: NOT auto-fixable (adding RBAC is security-sensitive)
- Action: Slack alert with:
  - Exact forbidden action from log
  - Pod name, ServiceAccount name
  - Suggested Role/ClusterRole rule to add
  - "kubectl auth can-i {verb} {resource} --as=system:serviceaccount:{ns}:{sa}"
- Severity: MEDIUM-HIGH

#### DOCKERHUB/REGISTRY RATE LIMITING
- Detection: ImagePullBackOff where events contain "429 Too Many Requests" or "toomanyrequests"
  - Different from standard ImagePullBackOff (bad tag) — fix is different
- Root cause: DockerHub anonymous pull limit (100 pulls/6h per IP) hit by cluster
- Fix: NOT standard image tag rollback — that won't help
- Action: Slack alert with:
  - Which pods affected
  - "This is DockerHub rate limiting, not a bad image. Solutions:
     1. Add Docker Hub credentials as imagePullSecret
     2. Use a registry mirror (configure in containerd)
     3. Wait 6 hours for rate limit reset"
  - Exact command to create imagePullSecret
- Severity: HIGH if multiple pods affected (cluster-wide problem)

#### NODE RESOURCE EXHAUSTION (allocatable near zero)
- Detection: for each node, calculate:
  - allocatable_cpu - sum of all pod CPU requests on that node
  - allocatable_memory - sum of all pod memory requests on that node
  - If remaining < 10%: NODE_RESOURCE_NEARLY_FULL
  - If remaining < 2%: NODE_RESOURCE_EXHAUSTED (causes all new pods to be Pending)
- Different from NODE_MEMORY_PRESSURE (which is actual usage) — this is about *requested* resources
- Fix: NOT auto-fixable (can't add nodes automatically)
- Action: Slack alert with table showing:
  - Node name, CPU: used/allocatable (%), Memory: used/allocatable (%)
  - Top 5 resource-consuming pods on that node
  - Recommendation: add nodes OR identify over-provisioned pods
- Severity: HIGH

#### LIVENESS PROBE KILLING HEALTHY PODS (probe misconfiguration)
- Detection:
  - Pod has high restart count (> 5) BUT logs show application starting fine
  - Events show: "Liveness probe failed" repeatedly
  - Pod gets killed AFTER it starts (not during startup) — different from startup failure
  - Check probe timing: if initialDelaySeconds is too low for a Node.js app
- Root cause: probe fires before Node.js app has finished initializing (Node.js apps can take 10-30s to start)
- Fix:
  - If initialDelaySeconds < 30 for a Node.js app: patch to 30 (safe default)
  - If timeoutSeconds < 5: patch to 5
  - Patch: update deployment probe settings
- autoFixable: true if simple timing issue, false if endpoint itself is broken
- Severity: MEDIUM

---

## EXTENDED JENKINS COVERAGE — ALL MISSING PRODUCTION SCENARIOS

Add all of the following to `agent/integrations/jenkins.py`.

### Jenkins Extended Failure Types and Handling

Add these to the failure type enum and handling logic:

#### JENKINS_AGENT_OFFLINE / AGENT_OOM
- Detection in console log:
  - "Agent is not connected", "Connection was broken", "Remote call on channel failed"
  - "java.lang.OutOfMemoryError" in agent process (not app build)
  - "hudson.remoting.ChannelClosedException"
- Root cause: Jenkins Kubernetes plugin failed to provision build agent pod, OR agent pod ran OOM
- Fix:
  - Check Jenkins agent pod in jenkins namespace: `kubectl get pods -n jenkins -l jenkins=slave`
  - If agent pod is OOMKilled: record this, alert with memory increase recommendation for Jenkins agent pod
  - Auto-retry: YES (max 2) — agent will get a fresh pod
  - Also alert: "Consider increasing Jenkins agent pod memory limit in jenkins/agent-pod-template"
- Severity: MEDIUM

#### JENKINS_WORKSPACE_DIRTY
- Detection in console log:
  - "ENOENT: no such file or directory" on files that should always exist
  - "error: Your local changes would be overwritten by checkout"
  - Build passes locally but fails on Jenkins consistently with file-not-found errors
  - "Cannot lock ref" in git operations
- Root cause: Stale workspace from previous builds (Jenkins reuses workspace by default)
- Fix: auto-retry with clean workspace
  - Trigger build with parameter `clean=true` if pipeline supports it
  - OR: call `POST {JENKINS_URL}/job/{name}/doWipeOutWorkspace` before retry
- Auto-retry: YES (max 1, clean workspace first)
- Add to GitHub issue if clean-workspace retry also fails: "Workspace issue persists after clean"

#### SCM_CHECKOUT_FAILURE
- Detection in console log:
  - "ERROR: Error cloning remote repo", "Could not read from remote repository"
  - "SSH host key verification failed"
  - "remote: Repository not found"
  - "API rate limit exceeded" (GitHub)
  - "fatal: unable to access": SSL/network issue to GitHub
- Root causes (distinguish in AI diagnosis):
  - GitHub rate limiting → wait and retry
  - SSH key expired → alert, no retry
  - Repo moved/renamed → alert, no retry
  - Network timeout → retry
- Fix:
  - GitHub rate limit or network timeout: auto-retry after 60s (max 1)
  - SSH key / repo issues: CRITICAL Slack alert, no retry
- Severity: HIGH (entire pipeline fails before any stage runs)

#### SHARED_LIBRARY_FAILURE
- Detection in console log:
  - "No such DSL method", "unable to resolve class", "WorkflowScript"
  - "@Library" in Jenkinsfile — library load errors appear BEFORE any stage
  - "Could not find matching library", "library version not found"
- Root cause: Jenkins shared library version pinned to a branch/tag that no longer exists, OR breaking change in shared library
- Fix: NOT auto-fixable
- Action: Slack CRITICAL alert:
  - "Jenkins shared library failed to load. This blocks ALL pipeline stages."
  - Extract library name and version from error
  - "Check @Library annotation in Jenkinsfile and verify library repo/branch exists"
- Severity: CRITICAL (zero stages run)

#### PARALLEL_STAGE_FAILURE
- Detection in console log:
  - Multiple "parallel" blocks, one sub-branch shows failure
  - Console shows interleaved output from parallel branches — must parse carefully
  - Pattern: look for "Failed in branch {name}" or individual branch failure messages
- Root cause: one parallel branch fails, Jenkins may report wrong overall stage
- Fix: re-run AI diagnosis with specific instruction to identify WHICH parallel branch failed
- In GitHub issue: report the specific failing branch, not just "parallel stages failed"
- Auto-retry: depends on underlying failure type of the failing branch

#### DOCKER_IN_DOCKER_FAILURE
- Detection in console log:
  - "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
  - "permission denied while trying to connect to the Docker daemon socket"
  - "docker: command not found" (in a pod that should have Docker)
- Root cause: Jenkins pod running in K8s doesn't have Docker socket mounted, OR DinD sidecar not running
- Fix: NOT auto-fixable (requires K8s pod template change)
- Action: Slack HIGH alert:
  - "Jenkins build agent cannot access Docker. This is a pod configuration issue."
  - "Check Jenkins kubernetes plugin pod template: ensure docker socket volume mount or DinD sidecar"
  - Provide exact pod template YAML snippet to fix
- Severity: HIGH

#### PIPELINE_TIMEOUT
- Detection: "Timeout has been exceeded", "FlowInterruptedException", "Cancelling nested steps due to timeout"
  - Different from network timeouts WITHIN steps
  - This is the pipeline-level timeout block firing
- Root cause: build took longer than `timeout(time: X, unit: 'MINUTES')` allows
- Sub-classify:
  - If npm install step was running when timeout hit: dependency resolution too slow
  - If test step: tests hanging (common in Node.js with unresolved promises)
  - If docker build: large image layers
  - If kubectl rollout: deployment taking too long
- Fix by sub-type:
  - npm install timeout → retry with `--prefer-offline` flag suggestion, open GitHub issue
  - Test timeout → flag specific test file that was running, open GitHub issue
  - kubectl rollout timeout → check cluster health gate, open GitHub issue
- Auto-retry: NO for pipeline timeout (will just timeout again)

#### POST_BUILD_ACTION_FAILURE
- Detection: all stages show SUCCESS but overall build = FAILURE
  - Console shows failure AFTER "Finished: ..." stage messages
  - Common in post{} blocks: archiveArtifacts, junit, publishHTML, notifications
- Root cause: post-build steps failing (archiving, test result publishing, notifications)
  - This should NOT block the deploy if app actually deployed successfully
- Fix: detect this pattern specifically
  - If failure is ONLY in post{} block AND deployment stage succeeded: mark as WARNING not FAILURE
  - Alert: "Build marked failed due to post-build action only. Application may have deployed successfully."
  - Open GitHub issue to fix the post-build action
- Severity: LOW-MEDIUM (app may be fine)

#### CREDENTIALS_BINDING_FAILURE
- Detection in console log:
  - "CredentialsNotFoundException", "No credentials found with id"
  - "ERROR: credentials {id} not found"
  - withCredentials block failing
- Root cause: credential ID in Jenkinsfile references a credential that was deleted, renamed, or never created
- Fix: NOT auto-fixable (cannot create credentials automatically)
- Action: Slack CRITICAL alert:
  - "Jenkins credential '{id}' referenced in pipeline does not exist"
  - "Go to Jenkins → Manage Jenkins → Credentials and create credential with ID: {id}"
  - Extract exact credential ID from error
- Severity: CRITICAL (no retry — will keep failing)
- Do NOT log credential values anywhere

#### NODE_VERSION_MISMATCH
- Detection in console log:
  - "The engine 'node' is incompatible with this module", "requires node >= {version}"
  - "SyntaxError: Unexpected token" on valid modern JS (old Node version)
  - "node: /lib/aarch64-linux-gnu/libc.so.6: version GLIBC_2.28 not found" (ARM64 Node issue — relevant for Oracle ARM VM)
  - `.nvmrc` or `engines` field in package.json mismatch with Jenkins agent Node version
- Root cause: Jenkins agent pod using wrong Node.js version
- Fix: NOT auto-fixable (requires agent pod template change)
- Action: Slack HIGH alert with:
  - Required Node version (from error or package.json engines field)
  - Current Node version (parse from console: "node --version" output)
  - "Update Jenkins agent pod template to use node:{required_version} image"
- Severity: HIGH
- Special note: ARM64 compatibility — Oracle Cloud uses ARM. If GLIBC error: node image must be arm64 variant

#### NPM_CI_LOCK_MISMATCH
- Detection in console log:
  - "npm ci can only install packages when your package.json and package-lock.json are in sync"
  - "Missing: {package}@{version} from lock file"
- Root cause: developer ran `npm install` and committed package.json changes but forgot to commit updated package-lock.json
- Fix: NOT auto-fixable (code repo issue)
- Action: open GitHub issue with:
  - Exact missing package from error
  - "Run 'npm install' locally and commit the updated package-lock.json"
  - Tag the last commit that modified package.json
- Severity: MEDIUM

#### SONARQUBE_QUALITY_GATE_FAILURE
- Detection in console log:
  - "Quality gate status: ERROR", "Quality gate failed", "SonarQube analysis failed"
  - "ANALYSIS SUCCESSFUL, you can browse" followed by gate failure
- Root cause: code quality metrics (coverage, duplication, bugs, vulnerabilities) below threshold
- Fix: NOT auto-fixable
- Action: open GitHub issue with:
  - Quality gate failure reasons (parse from SonarQube output)
  - Link to SonarQube project if URL parseable from console
  - "Quality gate blocked deploy. Fix issues before re-running pipeline."
- Severity: MEDIUM (intentional gate — treat as informational, not emergency)

#### BUILD_SUCCESS_BUT_DEPLOY_BROKEN (post-deploy health check failure)
- This is the most dangerous scenario: Jenkins says ✅ SUCCESS but service is broken
- Detection: implement a post-deploy health check step
  - After `kubectl apply` or `kubectl rollout status` succeeds in Jenkins:
  - Agent calls its own health gate: `GET /cluster/health-gate`
  - AND checks specific deployment: are new pods Running+Ready?
  - AND optionally hits service health endpoint if `HEALTH_CHECK_URL` env var set
- How to implement:
  - Jenkins calls `POST /webhooks/jenkins` with phase=FINALIZED and status=SUCCESS
  - Agent checks deployment rollout status 2 minutes after success webhook
  - If deployment not healthy 2 min after "successful" deploy: alert CRITICAL
  - "Build marked SUCCESS but deployment is unhealthy. Possible: app starts but crashes on first request, health endpoint passes but other routes broken, or memory leak immediately after start."
- Action: Slack CRITICAL alert + trigger full AI diagnosis on the deployment
- This is the `post_deploy_health_checker` function in jenkins.py

#### FLAKY_TEST_PATTERN_DETECTION
- Do NOT blindly retry all test failures
- Track in `jenkins_incidents` table: which test files/suites failed
- If same test failed in last 3 builds on different commits: it's likely a FLAKY TEST, not a code bug
- Pattern detection query:
  ```sql
  SELECT failing_stage, count(*) 
  FROM jenkins_incidents 
  WHERE job_name = ? AND failure_type = 'TEST_FAILURE' 
  AND detected_at > NOW() - INTERVAL '7 days'
  GROUP BY failing_stage HAVING count(*) >= 3
  ```
- If flaky pattern detected: open GitHub issue titled "Flaky test: {test name}" with historical failure count
- If NOT flaky pattern (new failure): open regular bug issue

#### ENVIRONMENT_SPECIFIC_FAILURE (staging passes, prod fails)
- Detection: Jenkins job name contains "prod" or "production" AND same job with "staging" succeeded recently
- Cross-reference: query jenkins_incidents for staging version of same job
- If staging build succeeded but prod build failed with same commit: flag as environment-specific
- Action: Slack alert with:
  - "Same commit succeeded in staging but failed in production."
  - Common causes: different secrets, different resource limits, different replica counts, different external service endpoints
  - "Compare staging vs production ConfigMaps and resource limits"
- This adds `environment_mismatch: true` to the jenkins_incident record

---

## CROSS-CUTTING SCENARIOS

### agent/core/scanner.py — Cross-Service Dependency Failures

Add a `cross_service_analyzer` function that runs every 2 minutes:

```
Goal: detect cascading failures before they fully blow up

Logic:
1. If service A has ERROR logs referencing service B's hostname
   AND service B has any unhealthy status:
   → Emit a CASCADING_FAILURE incident linking both
   → Root cause: "Service A failures likely caused by Service B being unhealthy"
   → Fix service B first

2. If multiple services in same namespace start failing within 60 seconds of each other:
   → Check if a shared dependency (DB, Redis, ConfigMap) is the common cause
   → Emit SHARED_DEPENDENCY_FAILURE incident

3. After any fix is applied: check if other related services recover on their own
   → If yes: log as correlated recovery
```

### agent/integrations/jenkins.py — Build Trend Analysis

Add `analyze_build_trend` function called on every failure:
```
Query last 10 builds for this job from jenkins_incidents table.
Calculate:
- failure_rate = failures / total builds (last 7 days)
- If failure_rate > 0.5: "This pipeline is failing more than 50% of the time. Needs architectural review."
- If same failure_type in last 3 builds: "Recurring failure pattern detected"
- Include trend data in Slack alert: mini-chart as text: "Last 5 builds: ✅ ❌ ✅ ❌ ❌"
```

### Prometheus Metrics to Expose (agent/api/routes/metrics_endpoint.py)

Agent exposes `/metrics` in Prometheus format:
```
autopilot_incidents_total{severity, problem_type, namespace} counter
autopilot_fixes_total{action, result} counter
autopilot_fix_success_rate gauge
autopilot_scan_duration_seconds histogram
autopilot_jenkins_failures_total{job, failure_type} counter
autopilot_jenkins_retries_total{job, result} counter
autopilot_open_incidents{severity} gauge
autopilot_confidence_score_avg{problem_type} gauge
autopilot_node_health{node, condition} gauge
```

---

## UPDATED CLAUDE AI PROMPTS — EXTENDED VERSIONS

### config/prompts/k8s_diagnosis.py — REPLACE with this complete version

```python
K8S_SYSTEM_PROMPT = """You are AutoPilot, a senior Kubernetes SRE AI with deep expertise in:
- Node.js microservice deployments on Kubernetes
- Container runtime troubleshooting (containerd, CRI-O)
- Kubernetes networking (CoreDNS, NetworkPolicy, Ingress)
- Storage troubleshooting (PVC, StorageClass, PV binding)
- Cluster-level resource management (ResourceQuota, LimitRange, HPA, PDB)
- Security and RBAC troubleshooting
- StatefulSet, Job, and CronJob lifecycle management

You receive structured incident data. Return ONLY a single valid JSON object.
No markdown backticks. No preamble. No explanation outside JSON.

RULES:
1. autoFixable=false for: CRITICAL severity, kube-system (except CoreDNS/metrics-server pod restart),
   PVC/Secret/RBAC modifications, NetworkPolicy changes, PDB changes, selector fixes,
   cert-manager operations, node additions, quota increases
2. confidence: be conservative. Partial log = lower confidence. Multiple possible causes = lower confidence.
3. If you see DNS errors in logs, ALSO check if CoreDNS is healthy (separate fixPlan step)
4. For OOMKilled: always check if it's a memory leak vs just under-provisioned (different preventionTip)
5. For CrashLoopBackOff: distinguish between startup crash vs runtime crash (different fix strategies)
6. For Node.js apps: startup time can be 10-30s — factor this into probe misconfiguration analysis
7. For ARM64 environments (Oracle Cloud): note if issue may be architecture-specific

fixPlan actions (ONLY these): patch_deployment, rollout_undo, delete_pod, patch_service,
scale_hpa, restart_daemonset, patch_resource_limits, cordon_node, evict_pods_from_node,
restart_metrics_server, add_image_to_blacklist, delete_evicted_pods, force_delete_pod,
patch_probe_config, restart_coredns

RESPONSE FORMAT:
{
  "rootCause": "1-2 sentences: what failed, why, and what triggered it",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "autoFixable": true|false,
  "notAutoFixableReason": "if false: specific reason why human must handle this",
  "confidence": 0-100,
  "fixPlan": [
    {
      "action": "action_name",
      "params": { "namespace": "...", "name": "...", "patch": {} },
      "description": "what this step does in plain English",
      "kubectl_equivalent": "exact kubectl command a human would run"
    }
  ],
  "preventionTip": "specific to THIS incident — not generic advice",
  "estimatedRecovery": "realistic time estimate after fix applied",
  "relatedResources": ["other resources likely affected by this issue"],
  "cascadeRisk": "description of what else might fail if this is not fixed",
  "nodeJsSpecific": "any Node.js-specific context if relevant (startup time, event loop, etc)"
}"""
```

### config/prompts/jenkins_diagnosis.py — REPLACE with this complete version

```python
JENKINS_SYSTEM_PROMPT = """You are AutoPilot, a CI/CD expert AI specializing in:
- Jenkins pipelines for Node.js microservices
- npm/yarn build toolchains
- Docker multi-stage builds for Node.js
- Kubernetes deployments via kubectl and Helm
- Jenkins Kubernetes plugin (build agents as pods)
- GitHub integration (webhooks, issues, PR comments)
- ARM64/aarch64 build environments (Oracle Cloud infrastructure)

You receive a Jenkins console log. Return ONLY a single valid JSON object.
No markdown. No text before or after JSON.

FAILURE TYPE (pick exactly one):
FLAKY_NETWORK, NPM_PEER_DEP_CONFLICT, NPM_REGISTRY_TIMEOUT, NPM_AUDIT_FAIL,
NPM_CI_LOCK_MISMATCH, DOCKER_BUILD_FAIL, DOCKER_PUSH_FAIL, DOCKER_IN_DOCKER_FAIL,
TEST_FAILURE, FLAKY_TEST, KUBECTL_APPLY_FAIL, BUILD_OOM, MISSING_SECRET,
PERMISSION_DENIED, TIMEOUT, LIVENESS_PROBE_FAIL, SHARED_LIBRARY_FAIL,
SCM_CHECKOUT_FAIL, WORKSPACE_DIRTY, AGENT_OFFLINE, NODE_VERSION_MISMATCH,
POST_BUILD_ACTION_FAIL, QUALITY_GATE_FAIL, CREDENTIALS_MISSING, ARM64_COMPAT_FAIL,
UNKNOWN

AUTO-RETRIABLE (max 2): FLAKY_NETWORK, NPM_REGISTRY_TIMEOUT, DOCKER_PUSH_FAIL,
                         TIMEOUT, WORKSPACE_DIRTY (clean first), AGENT_OFFLINE, SCM_CHECKOUT_FAIL (network)
NOT RETRIABLE: NPM_PEER_DEP_CONFLICT, NPM_AUDIT_FAIL, NPM_CI_LOCK_MISMATCH,
               TEST_FAILURE, DOCKER_BUILD_FAIL, DOCKER_IN_DOCKER_FAIL,
               KUBECTL_APPLY_FAIL, BUILD_OOM, MISSING_SECRET, PERMISSION_DENIED,
               LIVENESS_PROBE_FAIL, SHARED_LIBRARY_FAIL, NODE_VERSION_MISMATCH,
               QUALITY_GATE_FAIL, CREDENTIALS_MISSING, ARM64_COMPAT_FAIL

IMPORTANT RULES:
- If failure is ONLY in a post{} block and deployment succeeded: set postBuildOnlyFailure=true
- If logs show ARM64/aarch64 GLIBC errors: set failureType=ARM64_COMPAT_FAIL
- For TEST_FAILURE: extract the EXACT test name(s) that failed (jest test suite + test name)
- For KUBECTL_APPLY_FAIL: extract the exact K8s manifest error message
- For NPM_AUDIT_FAIL: list the vulnerable packages found

RESPONSE FORMAT:
{
  "failureType": "...",
  "failingStage": "exact stage name from Jenkinsfile",
  "failingLine": "exact console line that shows the failure",
  "rootCause": "clear explanation of what failed and why",
  "autoRetriable": true|false,
  "cleanWorkspaceBeforeRetry": true|false,
  "postBuildOnlyFailure": true|false,
  "suggestedFix": "specific actionable fix steps if not retriable",
  "affectedPackages": ["list if npm/docker issue"],
  "failingTests": ["exact test names if TEST_FAILURE"],
  "githubIssueTitle": "concise issue title (< 80 chars)",
  "githubIssueBody": "## Summary\n...\n\n## Root Cause\n...\n\n## Failing Stage\n`{stage}`\n\n## Relevant Console Output\n```\n{max 20 lines}\n```\n\n## Steps to Fix\n1. ...\n2. ...",
  "shouldBlockDeploy": true|false,
  "urgency": "LOW|MEDIUM|HIGH|CRITICAL",
  "arm64Note": "if ARM64 compatibility issue: specific note about Oracle Cloud ARM environment"
}"""
```

---

## UPDATED SCANNER DETECTION ADDITIONS (append to scanner.py detect logic)

```python
# Add these problem_type constants to scanner.py
PROBLEM_TYPES = {
    # Existing
    "CRASH_LOOP": "CrashLoopBackOff",
    "IMAGE_PULL_FAIL": "ImagePullBackOff",
    "OOM_KILLED": "OOMKilled",
    "PENDING_TOO_LONG": "PodPendingTooLong",
    "CONFIG_ERROR": "CreateContainerConfigError",
    "NOT_READY": "PodNotReady",
    "REPLICA_MISMATCH": "DeploymentReplicaMismatch",
    "ROLLOUT_STUCK": "DeploymentRolloutStuck",
    "NODE_NOT_READY": "NodeNotReady",
    "NODE_MEMORY_PRESSURE": "NodeMemoryPressure",
    "NODE_DISK_PRESSURE": "NodeDiskPressure",
    "NODE_PID_PRESSURE": "NodePIDPressure",
    "NO_ENDPOINTS": "ServiceNoEndpoints",
    "SELECTOR_MISMATCH": "ServiceSelectorMismatch",
    "PVC_PENDING": "PVCPending",
    "PVC_LOST": "PVCLost",
    "QUOTA_EXCEEDED": "ResourceQuotaExceeded",
    "QUOTA_NEAR_LIMIT": "ResourceQuotaNearLimit",
    "HPA_SCALE_BLOCKED": "HPAScaleBlocked",
    "HPA_AT_MAX": "HPAAtMaxReplicas",
    "METRICS_SERVER_ISSUE": "MetricsServerIssue",
    "TLS_CERT_EXPIRY": "TLSCertExpiry",
    # NEW in v3.0
    "POD_EVICTED": "PodEvicted",
    "POD_STUCK_TERMINATING": "PodStuckTerminating",
    "PDB_BLOCKING_ROLLOUT": "PDBBlockingRollout",
    "INGRESS_NO_LB": "IngressNoLoadBalancer",
    "INGRESS_CONTROLLER_DOWN": "IngressControllerDown",
    "INGRESS_BACKEND_MISSING": "IngressBackendMissing",
    "INGRESS_TLS_INVALID": "IngressTLSInvalid",
    "CERT_MANAGER_FAIL": "CertManagerFailure",
    "DNS_FAILURE": "DNSResolutionFailure",
    "NETWORK_POLICY_BLOCK": "NetworkPolicyBlocking",
    "CONTAINER_RUNTIME_ERROR": "ContainerRuntimeError",
    "STATEFULSET_UPDATE_STUCK": "StatefulSetUpdateStuck",
    "JOB_FAILED": "JobFailed",
    "CRONJOB_MISSED": "CronJobMissedSchedule",
    "RBAC_FORBIDDEN": "RBACForbiddenInApp",
    "REGISTRY_RATE_LIMIT": "RegistryRateLimit",
    "NODE_RESOURCE_EXHAUSTED": "NodeResourceExhausted",
    "PROBE_MISCONFIGURED": "LivenessProbeMisconfigured",
    "CASCADING_FAILURE": "CascadingServiceFailure",
    "POD_STUCK_CONTAINER_CREATING": "PodStuckContainerCreating",
    "DEPLOYMENT_PAUSED": "DeploymentPausedTooLong",
}
```

---

## README.md ADDITIONAL SECTIONS (add to existing README requirements)

The README must also include:

### Jenkins Setup Section
```
## Jenkins Configuration

### 1. Install Generic Webhook Trigger Plugin
Manage Jenkins → Plugin Manager → Install "Generic Webhook Trigger"

### 2. Configure webhook on each pipeline job
Job → Configure → Build Triggers → Generic Webhook Trigger
- Token: (set same as JENKINS_WEBHOOK_SECRET in .env)
- Post content parameters: extract full JSON payload

### 3. Add Jenkinsfile pre-deploy health gate (copy-paste ready):
stage('Pre-Deploy Health Check') {
  steps {
    script {
      def response = httpRequest(
        url: "${AUTOPILOT_URL}/cluster/health-gate",
        httpMode: 'GET',
        customHeaders: [[name: 'Authorization', value: "Bearer ${AUTOPILOT_API_KEY}"]]
      )
      def health = readJSON text: response.content
      if (health.status == 'UNHEALTHY') {
        error("Cluster health gate FAILED. Score: ${health.score}/100. Issues: ${health.issues}")
      }
      if (health.status == 'DEGRADED') {
        echo "WARNING: Cluster is DEGRADED (score: ${health.score}). Proceeding with caution."
      }
    }
  }
}

### 4. Add post-deploy notification (copy-paste ready):
post {
  failure {
    script {
      httpRequest(
        url: "${AUTOPILOT_URL}/webhooks/jenkins",
        httpMode: 'POST',
        contentType: 'APPLICATION_JSON',
        requestBody: groovy.json.JsonOutput.toJson([
          name: env.JOB_NAME,
          build: [
            number: env.BUILD_NUMBER.toInteger(),
            phase: 'FINALIZED',
            status: 'FAILURE',
            url: env.BUILD_URL,
            scm: [branch: env.GIT_BRANCH, commit: env.GIT_COMMIT]
          ]
        ])
      )
    }
  }
  success {
    script {
      // Post-success: agent will verify deployment health
      httpRequest(
        url: "${AUTOPILOT_URL}/webhooks/jenkins",
        httpMode: 'POST',
        contentType: 'APPLICATION_JSON',
        requestBody: groovy.json.JsonOutput.toJson([
          name: env.JOB_NAME,
          build: [number: env.BUILD_NUMBER.toInteger(), phase: 'FINALIZED', status: 'SUCCESS']
        ])
      )
    }
  }
}
```

### ARM64 / Oracle Cloud Notes
```
## Oracle Cloud ARM64 Specifics

This agent runs on Oracle Cloud Infrastructure (OCI) ARM64 (aarch64) VMs.

Known ARM64 gotchas:
1. Use arm64 Docker images: node:20-alpine (already multi-arch)
   Avoid: images that only have amd64 variants
2. Python packages: some packages need compilation — use --no-binary flags if needed
   Add to requirements.txt comments which packages have ARM64 issues
3. GLIBC errors: if you see "GLIBC_2.28 not found", the base image is too old
   Fix: upgrade to ubuntu:22.04 or debian:bullseye base images
4. Jenkins agent pod: ensure Jenkins Kubernetes cloud is configured with
   nodeSelector: kubernetes.io/arch=arm64
5. The scanner handles ARM64 natively — no changes needed
```

---

## FINAL INSTRUCTION

Build every single file completely. No placeholders. No "// TODO: implement". No "pass" with comment.
Every function must work. Every component must render. Every API endpoint must return real data.

After building all files, verify:
1. `cd agent && python -c "from core.scanner import ClusterScanner; print('Agent OK')"`
2. `cd api && npx tsc --noEmit && echo "API TypeScript OK"`
3. `cd dashboard && npx tsc --noEmit && echo "Dashboard TypeScript OK"`

The system should be startable locally with:
```bash
cp .env.example .env
# edit .env with real values
docker-compose up
# Agent:     http://localhost:8000  (FastAPI webhooks)
# API:       http://localhost:3001  (Node.js dashboard API)
# Dashboard: http://localhost:5173  (React UI)
```

Coverage summary of what this system handles:
- 28 distinct Kubernetes failure types with auto-fix or guided remediation
- 24 distinct Jenkins pipeline failure types with auto-retry, GitHub issues, or Slack escalation
- Cross-service cascading failure detection
- ARM64/Oracle Cloud specific failure patterns
- Build-green-but-deploy-broken detection
- Flaky test pattern recognition
- Post-deploy health verification
- Config drift detection
- TLS certificate expiry monitoring
- Real-time React dashboard with WebSocket live updates
- Slack approval workflow for HIGH/CRITICAL incidents
- Full audit trail of every incident, diagnosis, and fix in PostgreSQL