# AutoPilot DevOps Agent

An autonomous AI DevOps agent that monitors Kubernetes clusters, detects incidents, and applies fixes — with human approval gates via Slack for critical actions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Oracle Cloud ARM64                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Kubernetes Cluster                      │   │
│  │                                                          │   │
│  │  ┌─────────────────┐    ┌──────────────────────────┐    │   │
│  │  │  autopilot ns   │    │       jenkins ns          │    │   │
│  │  │                 │    │                          │    │   │
│  │  │  ┌───────────┐  │    │  ┌────────────────────┐  │    │   │
│  │  │  │  Python   │  │    │  │      Jenkins       │  │    │   │
│  │  │  │  Agent    │◄─┼────┼──┤  (pod + service)   │  │    │   │
│  │  │  │  :8000    │  │    │  └────────────────────┘  │    │   │
│  │  │  └─────┬─────┘  │    └──────────────────────────┘    │   │
│  │  │        │         │                                    │   │
│  │  │  ┌─────▼─────┐  │    ┌──────────────────────────┐    │   │
│  │  │  │  Node.js  │  │    │   monitored namespaces    │    │   │
│  │  │  │   API     │  │    │  default / production /   │    │   │
│  │  │  │  :3001    │  │    │        staging            │    │   │
│  │  │  └─────┬─────┘  │    └──────────────────────────┘    │   │
│  │  │        │         │                                    │   │
│  │  │  ┌─────▼─────┐  │                                    │   │
│  │  │  │  React    │  │                                    │   │
│  │  │  │ Dashboard │  │                                    │   │
│  │  │  │   :80     │  │                                    │   │
│  │  │  └───────────┘  │                                    │   │
│  │  └─────────────────┘                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────────┐    │
│  │PostgreSQL│   │  Redis   │   │  NeonDB (prod postgres)   │    │
│  └──────────┘   └──────────┘   └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │                │
          ▼                ▼
    ┌──────────┐    ┌────────────┐
    │  Slack   │    │ Claude API │
    │  Bot     │    │(Anthropic) │
    └──────────┘    └────────────┘
```

**Data flow:**
1. Python agent scans cluster every 30 seconds via K8s API
2. Anomalies are classified by Claude (Anthropic API) with a confidence score
3. LOW/MEDIUM severity + high confidence → auto-fix applied immediately
4. HIGH/CRITICAL severity → Slack approval request sent, fix applied only on approval
5. All actions logged to PostgreSQL; events streamed to dashboard via Redis pub/sub

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- `kubectl` configured against your cluster
- A Kubernetes cluster (K3s, EKS, GKE, or Oracle OKE)
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- **Slack bot token** — see [Slack Bot Setup](#slack-bot-setup)
- **GitHub personal access token** — [github.com/settings/tokens](https://github.com/settings/tokens)
- Jenkins running in the cluster (or accessible via URL)

---

## Local Development (docker-compose)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/autopilot-devops-agent.git
cd autopilot-devops-agent
cp .env.example .env
```

Edit `.env` and fill in the required values. For local Docker Compose, keep `K8S_IN_CLUSTER=false` so the agent uses the mounted kubeconfig. Set `TARGET_NAMESPACES` to the namespace(s) that contain your app, for example `TARGET_NAMESPACES=task-manager`.

### 2. Start infrastructure

```bash
docker compose up -d postgres redis
# Wait for healthy status
docker compose ps
```

### 3. Start all services

```bash
docker compose up -d
```

The Python agent applies the PostgreSQL schema automatically on startup.

### 4. Verify

```bash
# Agent health
curl http://localhost:8000/health

# API health
curl http://localhost:3001/health

# Agent cluster health gate
curl -H "X-API-Key: $API_KEY" http://localhost:8000/cluster/health-gate

# Dashboard
open http://localhost:5173
```

### Useful compose commands

```bash
# View logs
docker compose logs -f agent
docker compose logs -f api

# Restart a single service
docker compose restart agent

# Stop everything
docker compose down

# Wipe volumes (destructive)
docker compose down -v
```

---

## Kubernetes Deployment

### 1. Build and push images

```bash
# Set your registry
export REGISTRY=your-registry.io/autopilot

# Build for ARM64 (Oracle Cloud)
docker buildx build --platform linux/arm64 -t $REGISTRY/autopilot-agent:latest ./agent --push
docker buildx build --platform linux/arm64 -t $REGISTRY/autopilot-api:latest ./api --push
docker buildx build --platform linux/arm64 -t $REGISTRY/autopilot-dashboard:latest ./dashboard --push
```

### 2. Update image references

Edit `k8s/agent-deployment.yaml`, `k8s/api-deployment.yaml`, and `k8s/dashboard-deployment.yaml` — replace `your-registry/` with your actual registry path.

### 3. Create the namespace and RBAC

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/clusterrole.yaml
kubectl apply -f k8s/clusterrolebinding.yaml
```

### 4. Create secrets

```bash
cp k8s/secrets-template.yaml k8s/secrets.yaml
# Edit k8s/secrets.yaml — fill in all values
# DO NOT commit secrets.yaml to git
kubectl apply -f k8s/secrets.yaml
```

### 5. Apply ConfigMap

```bash
kubectl apply -f k8s/configmap.yaml
```

Review `k8s/configmap.yaml` first and adjust `TARGET_NAMESPACES`, `JENKINS_URL`, and channel names to match your environment.

### 6. Deploy workloads

```bash
kubectl apply -f k8s/agent-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/dashboard-deployment.yaml
kubectl apply -f k8s/services.yaml
```

### 7. Verify rollout

```bash
kubectl rollout status deployment/autopilot-agent -n autopilot
kubectl rollout status deployment/autopilot-api -n autopilot
kubectl rollout status deployment/autopilot-dashboard -n autopilot

kubectl get pods -n autopilot
```

### 8. Expose the dashboard (optional)

For local access via port-forward:

```bash
kubectl port-forward svc/autopilot-dashboard 8080:80 -n autopilot
```

For production, add an Ingress resource pointing to `autopilot-dashboard:80` and `autopilot-api:3001`.

---

## Required API Keys

### Anthropic API Key

1. Sign in at [console.anthropic.com](https://console.anthropic.com)
2. Go to **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-`)
4. Set as `ANTHROPIC_API_KEY` in `.env` / K8s secret

The agent uses `claude-sonnet-4-20250514` by default. Change via `CLAUDE_MODEL` in the ConfigMap.

### GitHub Personal Access Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → **Generate new token (classic)**
2. Grant scopes: `repo`, `read:org`
3. Set as `GITHUB_TOKEN` in `.env` / K8s secret
4. Set `GITHUB_REPO` to `org/repo-name`

---

## Jenkins Configuration

### Install required plugin

In Jenkins → **Manage Jenkins** → **Manage Plugins** → Available:
- Search for **Generic Webhook Trigger** and install it
- Also install **HTTP Request Plugin** (needed for Jenkinsfile snippets below)

### Configure webhook on each pipeline job

1. Open the pipeline job → **Configure**
2. Scroll to **Build Triggers** → check **Generic Webhook Trigger**
3. Under **Post content parameters**, add:
   - Variable: `build_status`, Expression: `$.build.status`, JSONPath
4. Set **Token** to the same value as `JENKINS_WEBHOOK_SECRET` in your secrets
5. Save

AutoPilot will call `POST /webhooks/jenkins` automatically; Jenkins will call `POST /webhooks/jenkins` on build completion.

### Add pre-deploy health gate to Jenkinsfile

Add this stage **before** your deploy stage. It blocks deployment if the cluster is unhealthy.

```groovy
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
```

Set the following environment variables in the pipeline (or Jenkins credentials):

```groovy
environment {
  AUTOPILOT_URL    = 'http://autopilot-agent.autopilot.svc.cluster.local:8000'
  AUTOPILOT_API_KEY = credentials('autopilot-api-key')
}
```

### Add post-build notification to Jenkinsfile

Add this `post` block at the pipeline level to notify AutoPilot of build results:

```groovy
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

---

## Slack Bot Setup

### Create the Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it `AutoPilot` and select your workspace

### Configure OAuth scopes

Under **OAuth & Permissions** → **Bot Token Scopes**, add:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Send messages |
| `channels:read` | List channels |
| `reactions:write` | Add emoji reactions |
| `app_mentions:read` | Respond to @mentions |
| `commands` | Handle slash commands |

### Configure Event Subscriptions

Under **Event Subscriptions**:
1. Enable Events
2. Set **Request URL** to `https://your-domain.com/slack/events`
3. Subscribe to bot events: `app_mention`, `message.channels`

### Configure Interactivity

Under **Interactivity & Shortcuts**:
1. Enable Interactivity
2. Set **Request URL** to `https://your-domain.com/slack/actions`

This is required for the approval buttons to work.

### Install and copy tokens

1. Under **Install App** → **Install to Workspace**
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`) → `SLACK_BOT_TOKEN`
3. Under **Basic Information** → **Signing Secret** → `SLACK_SIGNING_SECRET`

### Invite the bot to channels

```
/invite @AutoPilot
```

Do this in both `#devops-alerts` and `#devops-approvals`.

---

## Oracle Cloud ARM64 Specifics

All deployments include `nodeSelector: kubernetes.io/arch: arm64` to ensure pods land on ARM64 (aarch64) nodes.

### Multi-arch image builds

Use `docker buildx` with QEMU emulation for cross-compilation on x86 dev machines:

```bash
# One-time setup
docker buildx create --use --name multiarch
docker run --privileged --rm tonistiigi/binfmt --install all

# Build for ARM64
docker buildx build --platform linux/arm64 -t your-registry/autopilot-agent:latest ./agent --push
```

### Oracle Cloud ingress

Oracle Cloud's load balancer requires an annotation on the Service for external access:

```yaml
metadata:
  annotations:
    service.beta.kubernetes.io/oci-load-balancer-shape: "flexible"
    service.beta.kubernetes.io/oci-load-balancer-shape-flex-min: "10"
    service.beta.kubernetes.io/oci-load-balancer-shape-flex-max: "100"
```

### Storage class

Use `oci-bv` as the storage class for PersistentVolumeClaims:

```yaml
storageClassName: oci-bv
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key for Claude |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Claude model ID |
| `AI_CONFIDENCE_THRESHOLD` | No | `85` | Min confidence (0-100) to auto-fix |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | Yes | — | Redis connection string |
| `K8S_IN_CLUSTER` | No | `false` | Use in-cluster K8s auth |
| `KUBECONFIG` | No | `~/.kube/config` | Kubeconfig path (out-of-cluster) |
| `TARGET_NAMESPACES` | No | `default` | Comma-separated namespaces to watch |
| `JENKINS_URL` | No | — | Jenkins base URL |
| `JENKINS_USER` | No | — | Jenkins API username |
| `JENKINS_TOKEN` | No | — | Jenkins API token |
| `JENKINS_WEBHOOK_SECRET` | No | — | Shared secret for webhook validation |
| `JENKINS_MAX_RETRIES` | No | `2` | Max Jenkins trigger retries |
| `SLACK_BOT_TOKEN` | Yes | — | Slack bot OAuth token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Yes | — | Slack signing secret |
| `SLACK_ALERT_CHANNEL` | No | `#devops-alerts` | Channel for incident alerts |
| `SLACK_APPROVAL_CHANNEL` | No | `#devops-approvals` | Channel for approval requests |
| `SLACK_APPROVAL_TIMEOUT_MINUTES` | No | `30` | Approval window before auto-escalate |
| `GITHUB_TOKEN` | No | — | GitHub PAT for repo access |
| `GITHUB_REPO` | No | — | `org/repo` to post issue comments |
| `SMTP_HOST` | No | — | SMTP server for email escalation |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASS` | No | — | SMTP password / app password |
| `ESCALATION_EMAIL` | No | — | Email for critical escalations |
| `SCAN_INTERVAL_SECONDS` | No | `30` | How often to scan the cluster |
| `POST_FIX_VERIFY_DELAY_SECONDS` | No | `120` | Wait after fix before verifying |
| `ENABLE_AUTO_FIX` | No | `true` | Master switch for auto-fixes |
| `DRY_RUN` | No | `false` | Log and alert but never execute fixes |
| `DRIFT_AUTO_CORRECT` | No | `false` | Auto-correct replica drift |
| `AGENT_PORT` | No | `8000` | HTTP port for the Python agent |
| `API_PORT` | No | `3001` | HTTP port for the Node.js dashboard API |
| `API_KEY` | Yes | — | Bearer token for agent API access |
| `DASHBOARD_URL` | No | — | Dashboard URL (for cross-origin config) |
| `AGENT_URL` | No | — | Agent URL (used by Node API) |
| `VITE_API_URL` | No | — | Dashboard → API base URL |
| `VITE_WS_URL` | No | — | Dashboard → WebSocket URL |
| `VITE_API_KEY` | No | — | Dashboard API key |

---

## Troubleshooting

### Agent pod is CrashLoopBackOff

```bash
kubectl logs -n autopilot deployment/autopilot-agent --previous
```

Common causes:
- `ANTHROPIC_API_KEY` not set or invalid → check `kubectl get secret autopilot-secrets -n autopilot`
- `DATABASE_URL` unreachable → verify PostgreSQL pod is running and service DNS resolves
- RBAC permission denied → re-apply `clusterrole.yaml` and `clusterrolebinding.yaml`

### Slack approvals not working

1. Confirm the agent is reachable from the internet (or Slack's servers) at `/slack/actions`
2. Check the **Interactivity Request URL** in the Slack app settings matches your deployment URL
3. Verify `SLACK_SIGNING_SECRET` matches the value in Basic Information

### Jenkins webhook 401 / signature mismatch

- Ensure `JENKINS_WEBHOOK_SECRET` in the agent secrets matches the **Token** field in the Generic Webhook Trigger plugin configuration
- Check the agent logs: `kubectl logs -n autopilot deployment/autopilot-agent | grep webhook`

### Agent not detecting issues in a namespace

- Confirm the namespace is listed in `TARGET_NAMESPACES` (ConfigMap or `.env`)
- The ClusterRole grants read access to all namespaces; verify with:

```bash
kubectl auth can-i list pods --as=system:serviceaccount:autopilot:autopilot-agent -n production
```

### Dashboard shows no data

1. Check the Node API is running: `curl http://localhost:3001/health`
2. Verify `VITE_API_URL` and `VITE_WS_URL` point to the correct API host
3. Check browser console for CORS errors — update `DASHBOARD_URL` in the agent config to match the dashboard origin

### Redis connection refused

For local development ensure Redis is healthy:

```bash
docker compose ps redis
docker compose exec redis redis-cli ping   # should return PONG
```

For K8s, verify the `REDIS_URL` in the ConfigMap uses the correct in-cluster DNS:
`redis://redis.autopilot.svc.cluster.local:6379`

---

## Hard Rules (Always Enforced)

These rules are hard-coded in the agent and cannot be overridden via configuration:

1. **Never auto-fix `kube-system`** — except CoreDNS and metrics-server pod restarts
2. **Never delete PVCs, PersistentVolumes, or Secrets** — data loss prevention
3. **Never create or modify RBAC resources** — privilege escalation prevention
4. **Never auto-fix CRITICAL severity** — always requires explicit Slack approval
5. **Never auto-fix if confidence < `AI_CONFIDENCE_THRESHOLD`** — avoids low-confidence mutations
6. **Never fix the `autopilot-agent` pod itself** — prevents self-disruption
7. **Never retry Jenkins more than `JENKINS_MAX_RETRIES` times** — prevents build spam
8. **All fix methods must be idempotent** — safe to re-run if interrupted
9. **All fix executions are logged to DB before and after** — full audit trail
10. **If `DRY_RUN=true`: log and alert but never execute** — safe for staging/testing

---

## Project Structure

```
autopilot-devops-agent/
├── agent/                  # Python FastAPI agent
│   ├── core/
│   │   ├── scanner.py      # K8s cluster scanning logic
│   │   └── executor.py     # Fix execution engine
│   ├── db/
│   │   └── schema.sql      # PostgreSQL schema
│   ├── main.py             # FastAPI entry point
│   └── Dockerfile
├── api/                    # Node.js / TypeScript read API
│   ├── src/
│   │   └── index.ts        # Express entry point
│   └── Dockerfile
├── dashboard/              # React 18 + Vite dashboard
│   ├── src/
│   │   └── main.tsx        # React entry point
│   └── Dockerfile
├── k8s/                    # Kubernetes manifests
│   ├── namespace.yaml
│   ├── serviceaccount.yaml
│   ├── clusterrole.yaml
│   ├── clusterrolebinding.yaml
│   ├── configmap.yaml
│   ├── secrets-template.yaml
│   ├── agent-deployment.yaml
│   ├── api-deployment.yaml
│   ├── dashboard-deployment.yaml
│   └── services.yaml
├── docker-compose.yml
├── .env.example
├── CLAUDE.md
└── README.md
```

---

## License

MIT — Built by Raj at Hexaware Technologies.
