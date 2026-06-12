# AutoPilot DevOps Agent — Complete Setup Guide

> **Who is this for?** Anyone with basic Linux + terminal skills who wants to deploy AutoPilot to monitor their Kubernetes application. No prior DevOps expertise required — every command is explained.

---

## Table of Contents

1. [What Does AutoPilot Do?](#1-what-does-autopilot-do)
2. [How Everything Fits Together](#2-how-everything-fits-together)
3. [Prerequisites — What You Need Before Starting](#3-prerequisites--what-you-need-before-starting)
4. [Option A — Local Test with Docker Compose](#4-option-a--local-test-with-docker-compose)
5. [Option B — Full Production Deployment on Kubernetes](#5-option-b--full-production-deployment-on-kubernetes)
   - [Step 1: Understand the Files](#step-1-understand-the-files)
   - [Step 2: Build and Push Docker Images](#step-2-build-and-push-docker-images)
   - [Step 3: Edit the ConfigMap](#step-3-edit-the-configmap)
   - [Step 4: Create the Secrets File](#step-4-create-the-secrets-file)
   - [Step 5: Apply All Kubernetes Manifests](#step-5-apply-all-kubernetes-manifests)
   - [Step 6: Verify Everything is Running](#step-6-verify-everything-is-running)
   - [Step 7: Open the Dashboard](#step-7-open-the-dashboard)
6. [Jenkins Integration — External Jenkins Server](#6-jenkins-integration--external-jenkins-server)
   - [Part A: Install Jenkins](#part-a-install-jenkins)
   - [Part B: Configure Jenkins API Token](#part-b-configure-jenkins-api-token)
   - [Part C: Create the Freestyle Pipeline Job](#part-c-create-the-freestyle-pipeline-job)
   - [Part D: Tell AutoPilot About Your Jenkins](#part-d-tell-autopilot-about-your-jenkins)
7. [Slack Integration (Optional but Recommended)](#7-slack-integration-optional-but-recommended)
8. [Using the Dashboard](#8-using-the-dashboard)
9. [How AutoPilot Works Day-to-Day](#9-how-autopilot-works-day-to-day)
10. [Troubleshooting](#10-troubleshooting)
11. [Quick Reference — All URLs and Ports](#11-quick-reference--all-urls-and-ports)

---

## 1. What Does AutoPilot Do?

AutoPilot is an **autonomous AI DevOps agent**. You deploy it once, point it at your Kubernetes namespace, and it watches your pods 24/7. When something breaks:

1. It **detects** the problem (crash loops, image pull failures, out-of-memory, missing endpoints, and 30+ other issues).
2. It sends the problem to **your chosen AI provider** — either **Anthropic Claude** or **OpenAI ChatGPT** — which diagnoses the root cause and writes a fix plan.
3. If the confidence score is high enough and it is not a critical issue, it **executes the fix automatically** (restarts pods, rolls back deployments, adjusts resources, etc.).
4. It sends an **alert to Slack** with what happened and what it did.
5. For dangerous fixes, it **asks for your approval** via Slack before doing anything.

AutoPilot also integrates with **Jenkins**: when a build pipeline fails, AutoPilot classifies the failure as a flaky test, an infrastructure problem, or a real code bug — and takes action accordingly.

> **🧠 Bring your own AI: Claude OR ChatGPT.** AutoPilot does not lock you into one AI company. If you already pay for an **OpenAI (ChatGPT)** key, use that. If you prefer **Anthropic (Claude)**, use that instead. You pick **one** provider with a single setting (`LLM_PROVIDER`) and supply that provider's API key — nothing else changes. You can even switch between them later from the dashboard **Settings** page without redeploying. The rest of this guide points out exactly where to make this choice.

---

## 2. How Everything Fits Together

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR KUBERNETES CLUSTER                   │
│                                                             │
│  ┌─────────────────┐   Redis pub/sub    ┌────────────────┐  │
│  │  Python Agent   │──────────────────▶│  Node.js API   │  │
│  │  (port 8000)    │   incident_queue   │  (port 3001)   │  │
│  │                 │                   │                │  │
│  │  • Scans K8s    │   ┌─────────────┐ │  • REST API    │  │
│  │  • Calls AI     │   │  PostgreSQL │ │  • WebSocket   │  │
│  │  • Applies fixes│──▶│  Database   │◀│  • Read-only   │  │
│  │  • Jenkins hook │   └─────────────┘ └───────┬────────┘  │
│  └────────┬────────┘                           │           │
│           │                           ┌────────▼────────┐  │
│           │   ┌─────────────────┐     │ React Dashboard │  │
│           │   │  Redis Cache    │     │  (port 80/30011)│  │
│           └──▶│  (queue+pubsub) │     │                 │  │
│               └─────────────────┘     │  • Live charts  │  │
│                                       │  • Incident log │  │
│  namespace: autopilot                 │  • Fix history  │  │
└───────────────────────────────────────┴─────────────────┘──┘
        ▲ watches                               ▲ browser
        │                                       │
┌───────┴──────────┐               ┌────────────┴──────────┐
│  taskflow        │               │  You / Team           │
│  namespace       │               │  http://NODE_IP:30011  │
│  (your app)      │               └───────────────────────┘
└──────────────────┘
        ▲ webhook
        │
┌───────┴──────────┐
│  Jenkins Server  │  (separate external server)
│  (external)      │  POST → http://NODE_IP:30008/webhooks/jenkins
└──────────────────┘
```

**Three components run inside K8s:**
| Component | What it does | Port |
|-----------|-------------|------|
| `autopilot-agent` | Python — scans K8s, calls AI (Claude **or** ChatGPT), applies fixes | 30008 (external) |
| `autopilot-api` | Node.js — serves the REST API and WebSocket | 30010 (external) |
| `autopilot-dashboard` | React — the browser UI | 30011 (external) |

**Two databases (also inside K8s):**
| Service | What it stores |
|---------|---------------|
| PostgreSQL | Incidents, fix history, Jenkins builds, desired state |
| Redis | Incident queue (list) + real-time events (pub/sub) |

---

## 3. Prerequisites — What You Need Before Starting

### On your local machine (where you run kubectl)

| Tool | Why you need it | Install |
|------|----------------|---------|
| `kubectl` | Manage your K8s cluster | https://kubernetes.io/docs/tasks/tools/ |
| `docker` | Build container images | https://docs.docker.com/get-docker/ |
| `docker buildx` | Build for ARM64 (included with Docker Desktop, manual on Linux) | Comes with Docker |
| A Docker Hub account | Push images so K8s can pull them | https://hub.docker.com/ |

### On your Kubernetes cluster

- A working K8s cluster (tested on Oracle Cloud with ARM64 nodes)
- `kubectl` configured and able to reach it (`kubectl get nodes` should work)
- The `taskflow` namespace already exists with your app running in it

### API Keys you will need

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| Anthropic API Key (Claude) | https://console.anthropic.com | **One of these two is required** |
| OpenAI API Key (ChatGPT) | https://platform.openai.com/api-keys | **One of these two is required** |
| Jenkins API Token | Jenkins UI → User → Configure | Only if using Jenkins |
| Slack Bot Token | https://api.slack.com/apps | Optional |
| GitHub Token | https://github.com/settings/tokens | Optional |

> **Which AI key do I need — Claude or ChatGPT?** You only need **ONE**, not both. Pick the company you already have an account/billing with:
> - Have **ChatGPT / OpenAI**? Get an OpenAI key and you will set `LLM_PROVIDER=openai`.
> - Have **Claude / Anthropic**? Get an Anthropic key and you will set `LLM_PROVIDER=anthropic` (this is the default).
>
> Whichever one you pick, you put that key in your secrets and set `LLM_PROVIDER` to match. The other key can be left blank. That's the whole choice — the rest of AutoPilot behaves identically either way.

---

## 4. Option A — Local Test with Docker Compose

> Use this first to verify everything works before deploying to K8s. It runs the full stack on your laptop.

### Step 1: Clone and enter the repo

```bash
git clone <your-repo-url>
cd AutoPilot-DevOps-Agent
```

### Step 2: Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in **at minimum** these values:

```env
# ── Pick your AI provider: "anthropic" (Claude) OR "openai" (ChatGPT) ──
LLM_PROVIDER=anthropic            ← Change to "openai" if you use ChatGPT

# Then fill in the key for the provider you chose above.
# You only need ONE of these — leave the other blank.
ANTHROPIC_API_KEY=sk-ant-...      ← Fill this if LLM_PROVIDER=anthropic
OPENAI_API_KEY=sk-proj-...        ← Fill this if LLM_PROVIDER=openai

API_KEY=make-this-a-long-random-string   ← Used to protect the API
VITE_API_KEY=make-this-a-long-random-string   ← Same value as API_KEY

# For local Docker Compose, these URLs point to localhost
VITE_API_URL=http://localhost:3001
VITE_WS_URL=ws://localhost:3001
```

> **Example — using ChatGPT instead of Claude:** set `LLM_PROVIDER=openai`, put your key in `OPENAI_API_KEY=sk-proj-...`, and leave `ANTHROPIC_API_KEY` blank. The default model is `gpt-4o`; you can change it with `OPENAI_MODEL=` if you want a different one (e.g. `gpt-4o-mini` for lower cost). The agent will refuse to start if `LLM_PROVIDER` and the matching key don't line up — that's a safety check, not a bug.

> **Note:** For local Docker Compose, `K8S_IN_CLUSTER=false` (already set in .env.example). The agent will use your `~/.kube/config` file to connect to K8s. Your cluster's `taskflow` namespace will still be scanned.

### Step 3: Start everything

```bash
docker compose up --build
```

This will:
1. Start PostgreSQL and Redis
2. Build and start the Python agent
3. Build and start the Node.js API
4. Build and start the React dashboard

Wait about 60 seconds for everything to come up.

### Step 4: Open the dashboard

Go to: **http://localhost:5173**

Log in with the `VITE_API_KEY` value you set in `.env`.

If you see the dashboard with your cluster data — everything works! Now move on to the K8s deployment.

---

## 5. Option B — Full Production Deployment on Kubernetes

### Step 1: Understand the Files

```
k8s/
├── namespace.yaml          ← Creates the "autopilot" namespace
├── serviceaccount.yaml     ← Identity that the agent runs as
├── clusterrole.yaml        ← Permissions (what the agent can READ and MODIFY)
├── clusterrolebinding.yaml ← Links the serviceaccount to the clusterrole
├── configmap.yaml          ← Non-secret settings (URLs, intervals, model name)
├── secrets-template.yaml   ← Template — you copy this and fill in your secrets
├── postgres.yaml           ← PostgreSQL database (StatefulSet + Service)
├── redis.yaml              ← Redis cache (Deployment + Service)
├── agent-deployment.yaml   ← The Python agent
├── api-deployment.yaml     ← The Node.js API
├── dashboard-deployment.yaml ← The React dashboard
└── services.yaml           ← NodePort services to expose everything externally
```

**What is ConfigMap vs Secrets?**

Think of it this way:
- **ConfigMap** = a sticky note anyone can read. Use it for settings that are NOT passwords: URLs, timeout values, model names, on/off switches.
- **Secrets** = a locked safe. Use it for anything you would NOT want visible if someone accessed your cluster: API keys, tokens, database passwords.

### Step 2: Build and Push Docker Images

You need to build three Docker images for ARM64 and push them to Docker Hub.

**First, log in to Docker Hub:**
```bash
docker login
```

**Set up buildx for ARM64 cross-compilation** (run once):
```bash
docker buildx create --name mybuilder --use
docker buildx inspect --bootstrap
```

**Build and push the Python agent:**
```bash
cd agent
docker buildx build \
  --platform linux/arm64 \
  -t 0x1luffy/autopilot-agent:latest \
  --push \
  .
cd ..
```

**Build and push the Node.js API:**
```bash
cd api
docker buildx build \
  --platform linux/arm64 \
  -t 0x1luffy/autopilot-api:latest \
  --push \
  .
cd ..
```

**Build and push the React dashboard:**

> **Important:** The dashboard bakes the API URL into the image at build time. Replace `YOUR_NODE_IP` with your Oracle Cloud VM's public IP address.

```bash
cd dashboard
docker buildx build \
  --platform linux/arm64 \
  --build-arg VITE_API_URL=http://YOUR_NODE_IP:30010 \
  --build-arg VITE_WS_URL=ws://YOUR_NODE_IP:30010 \
  --build-arg VITE_API_KEY=change-me-to-a-strong-secret \
  -t 0x1luffy/autopilot-dashboard:latest \
  --push \
  .
cd ..
```

> **How to find your Node IP:**
> ```bash
> kubectl get nodes -o wide
> # Look at the EXTERNAL-IP or INTERNAL-IP column
> ```

### Step 3: Edit the ConfigMap

Open `k8s/configmap.yaml` and update these values:

```yaml
data:
  TARGET_NAMESPACES: "taskflow"        # ← Your app's namespace
  LLM_PROVIDER: "anthropic"            # ← "anthropic" (Claude) or "openai" (ChatGPT)
  JENKINS_URL: "http://YOUR_JENKINS_SERVER_IP:8080"  # ← Jenkins server IP
  # Everything else can stay as-is
```

**What each setting means:**

| Key | What it does | Change it? |
|-----|-------------|-----------|
| `TARGET_NAMESPACES` | Which K8s namespaces to watch | Yes — set to `taskflow` |
| `LLM_PROVIDER` | Which AI to use: `anthropic` (Claude) or `openai` (ChatGPT) | Set to whichever provider's key you have |
| `CLAUDE_MODEL` | Which Claude model to use (when `LLM_PROVIDER=anthropic`) | No — `claude-sonnet-4-6` is correct |
| `OPENAI_MODEL` | Which OpenAI model to use (when `LLM_PROVIDER=openai`) | Default `gpt-4o`; `gpt-4o-mini` is cheaper |
| `OPENAI_BASE_URL` | Custom endpoint for Azure OpenAI / gateways (advanced) | Leave empty unless you know you need it |
| `JENKINS_URL` | Where your Jenkins server lives | Yes — put your Jenkins IP |
| `SCAN_INTERVAL_SECONDS` | How often to scan for problems | Optional — default 30s is fine |
| `ENABLE_AUTO_FIX` | Whether to actually apply fixes | Keep `true` for production |
| `DRY_RUN` | If `true`, logs everything but never fixes | Use `true` for testing |
| `AI_CONFIDENCE_THRESHOLD` | Min confidence (0-100) before auto-fix | Default 85 is safe |

> **Reminder:** `LLM_PROVIDER` (here in the ConfigMap) and the API key (in your Secrets, next step) must match. If you set `LLM_PROVIDER: "openai"` you must provide `OPENAI_API_KEY`; if you set `anthropic` you must provide `ANTHROPIC_API_KEY`.

### Step 4: Create the Secrets File

```bash
# Copy the template
cp k8s/secrets-template.yaml k8s/secrets.yaml

# Add secrets.yaml to .gitignore so you never commit it
echo "k8s/secrets.yaml" >> .gitignore
```

Now open `k8s/secrets.yaml` and fill in your values:

```yaml
stringData:
  # ── AI provider key — fill in ONLY the one matching LLM_PROVIDER in the ConfigMap ──
  ANTHROPIC_API_KEY: "sk-ant-api03-..."    ← Fill if LLM_PROVIDER=anthropic (else leave blank)
  OPENAI_API_KEY: "sk-proj-..."            ← Fill if LLM_PROVIDER=openai (else leave blank)
  DATABASE_URL: "postgresql://autopilot:autopilot@postgres.autopilot.svc.cluster.local:5432/autopilot"
                                            ← Leave this exactly as-is
  JENKINS_USER: "admin"                    ← Jenkins admin username
  JENKINS_TOKEN: "your-jenkins-api-token"  ← From Jenkins (see Section 6)
  JENKINS_WEBHOOK_SECRET: "pick-any-random-string"   ← You choose this
  SLACK_BOT_TOKEN: "xoxb-..."              ← Leave blank if not using Slack
  SLACK_APP_TOKEN: "xapp-..."              ← Leave blank if not using Slack
  SLACK_SIGNING_SECRET: ""                 ← Leave blank if not using Slack
  GITHUB_TOKEN: "ghp_..."                  ← Optional, for creating GH issues
  GITHUB_REPO: "your-org/your-repo"        ← Optional
  SMTP_USER: "your@email.com"             ← Optional, for email alerts
  SMTP_PASS: "your-app-password"           ← Optional
  ESCALATION_EMAIL: "your@email.com"       ← Optional
  API_KEY: "make-this-a-long-random-secret-string"   ← Protects the API
```

> **Security rule:** Never commit `k8s/secrets.yaml` to git. The template is safe to commit; the filled-in version is not.

### Step 5: Apply All Kubernetes Manifests

Run these commands **in order** (order matters because namespace must exist before anything else):

```bash
# 1. Create the autopilot namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create RBAC (identity + permissions for the agent)
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/clusterrole.yaml
kubectl apply -f k8s/clusterrolebinding.yaml

# 3. Apply ConfigMap (non-secret settings)
kubectl apply -f k8s/configmap.yaml

# 4. Apply Secrets (sensitive values)
kubectl apply -f k8s/secrets.yaml

# 5. Deploy PostgreSQL and Redis (the databases)
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 6. Wait for databases to be ready before deploying the apps
kubectl rollout status statefulset/postgres -n autopilot
kubectl rollout status deployment/redis -n autopilot

# 7. Deploy the three AutoPilot services
kubectl apply -f k8s/agent-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/dashboard-deployment.yaml

# 8. Apply the NodePort services (makes everything accessible from outside)
kubectl apply -f k8s/services.yaml
```

### Step 6: Verify Everything is Running

```bash
# All pods should be "Running" with READY 1/1 (or 2/2 for api and dashboard)
kubectl get pods -n autopilot

# Expected output:
# NAME                                    READY   STATUS    RESTARTS
# autopilot-agent-xxxxx                   1/1     Running   0
# autopilot-api-xxxxx                     2/2     Running   0
# autopilot-api-yyyyy                     2/2     Running   0
# autopilot-dashboard-xxxxx               2/2     Running   0
# autopilot-dashboard-yyyyy               2/2     Running   0
# postgres-0                              1/1     Running   0
# redis-xxxxx                             1/1     Running   0
```

**If a pod is not Running, check its logs:**
```bash
# Replace <pod-name> with the actual name from kubectl get pods
kubectl logs <pod-name> -n autopilot

# Example:
kubectl logs autopilot-agent-7d9f8b6c5-xkpqr -n autopilot
```

**Check the services are exposed:**
```bash
kubectl get services -n autopilot

# You should see NodePort services:
# autopilot-agent      NodePort   ...  8000:30008/TCP
# autopilot-api        NodePort   ...  3001:30010/TCP
# autopilot-dashboard  NodePort   ...  80:30011/TCP
```

**Quick health checks:**
```bash
NODE_IP=YOUR_NODE_IP   # Replace with your actual IP

# Check agent is alive
curl http://$NODE_IP:30008/health

# Check API is alive
curl http://$NODE_IP:30010/health

# Both should return: {"status":"ok",...}
```

### Step 7: Open the Dashboard

Open your browser and go to:

```
http://YOUR_NODE_IP:30011
```

You will be asked for an API key — use the value you set for `API_KEY` in your `secrets.yaml`.

> **Firewall note:** If you are on Oracle Cloud, you must open these ports in your security list:
> - TCP 30008 (agent webhook, for Jenkins)
> - TCP 30010 (API + WebSocket)
> - TCP 30011 (dashboard browser UI)
>
> Go to: OCI Console → Networking → Virtual Cloud Networks → Security Lists → Add Ingress Rules

---

## 6. Jenkins Integration — External Jenkins Server

AutoPilot can monitor your Jenkins pipelines. When a build fails, AutoPilot:
1. Fetches the console log from Jenkins
2. Sends it to your AI provider (Claude or ChatGPT) for analysis
3. Classifies the failure: **flaky test**, **infra problem**, or **real bug**
4. For flaky/infra failures: auto-triggers a retry
5. For real bugs: creates a GitHub issue and sends a Slack alert
6. Respects `JENKINS_MAX_RETRIES` — won't retry forever

### Part A: Install Jenkins

On your separate Jenkins server (Ubuntu):

```bash
# Install Java (Jenkins requires it)
sudo apt update
sudo apt install -y openjdk-17-jdk

# Add Jenkins repo and install
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | \
  sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null

echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] \
  https://pkg.jenkins.io/debian-stable binary/" | \
  sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

sudo apt update
sudo apt install -y jenkins

# Start and enable Jenkins
sudo systemctl start jenkins
sudo systemctl enable jenkins
```

Jenkins will be at: `http://YOUR_JENKINS_SERVER_IP:8080`

Get the initial admin password:
```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Complete the setup wizard in your browser. Choose "Install suggested plugins".

### Part B: Configure Jenkins API Token

AutoPilot needs a Jenkins API token to fetch build logs and trigger retries.

1. Log in to Jenkins
2. Click your username (top-right) → **Configure**
3. Scroll down to **API Token** section
4. Click **Add new Token**
5. Give it a name: `autopilot`
6. Click **Generate**
7. **Copy the token now** — you cannot see it again

This token goes into `JENKINS_TOKEN` in your `k8s/secrets.yaml`.

**Required Jenkins plugins** (install via Manage Jenkins → Plugins → Available):
- **Generic Webhook Trigger** — so Jenkins can receive webhooks and also send them
- (The rest of the suggested plugins are fine)

### Part C: Create the Freestyle Pipeline Job

1. Go to Jenkins → **New Item**
2. Enter a name (e.g., `taskflow-deploy`)
3. Select **Freestyle project** → OK

**In the job configuration:**

**Build Triggers section:**
- Check: **Generic Webhook Trigger**
- Under "Post content parameters", add:
  - Variable: `build_status`, Expression: `$.build.status`, Default: `STARTED`
- Token: `taskflow-deploy-token` (any string you choose)

**Build Steps section:**
Add whatever build steps your pipeline needs (e.g., run tests, build Docker image, deploy to K8s).

**Post-build Actions section:**

Add: **HTTP Request** (if plugin available) or use a shell script to notify AutoPilot.

The easiest way is to add a shell script at the end of your build:

```bash
# At the END of your build step, add this shell command:
# Replace NODE_IP and WEBHOOK_SECRET with your actual values
NODE_IP="YOUR_NODE_IP"
WEBHOOK_SECRET="YOUR_WEBHOOK_SECRET"   # Same as JENKINS_WEBHOOK_SECRET in secrets.yaml
JOB_NAME="${JOB_NAME}"
BUILD_NUMBER="${BUILD_NUMBER}"
BUILD_STATUS="${BUILD_STATUS:-SUCCESS}"

curl -s -X POST "http://${NODE_IP}:30008/webhooks/jenkins" \
  -H "Content-Type: application/json" \
  -H "X-Jenkins-Token: ${WEBHOOK_SECRET}" \
  -d "{
    \"job_name\": \"${JOB_NAME}\",
    \"build_number\": ${BUILD_NUMBER},
    \"build_url\": \"${BUILD_URL}\",
    \"result\": \"${BUILD_STATUS}\",
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }"
```

### Part D: Tell AutoPilot About Your Jenkins

Update `k8s/configmap.yaml`:
```yaml
JENKINS_URL: "http://YOUR_JENKINS_SERVER_IP:8080"
```

Update `k8s/secrets.yaml`:
```yaml
JENKINS_USER: "admin"
JENKINS_TOKEN: "your-jenkins-api-token"   ← From Part B
JENKINS_WEBHOOK_SECRET: "your-secret"      ← Must match the script above
```

Re-apply the updated files:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Restart the agent to pick up the new config
kubectl rollout restart deployment/autopilot-agent -n autopilot
```

---

## 7. Slack Integration (Optional but Recommended)

Slack integration lets AutoPilot:
- Alert you when it detects an incident
- Ask for approval before applying dangerous fixes
- Confirm when a fix was applied successfully

### Step 1: Create a Slack App

1. Go to: https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name: `AutoPilot DevOps` — choose your workspace → Create App

### Step 2: Enable Socket Mode

1. In the app settings, go to **Socket Mode** (left sidebar)
2. Enable Socket Mode → it will generate an **App-Level Token**
3. Give it the scope `connections:write`
4. Copy the token — this is your `SLACK_APP_TOKEN` (starts with `xapp-`)

### Step 3: Add Bot Permissions

1. Go to **OAuth & Permissions** (left sidebar)
2. Under **Bot Token Scopes**, add:
   - `chat:write`
   - `channels:read`
   - `reactions:write`
   - `im:write`
3. Click **Install to Workspace**
4. Copy the **Bot User OAuth Token** — this is your `SLACK_BOT_TOKEN` (starts with `xoxb-`)

### Step 4: Get the Signing Secret

1. Go to **Basic Information** (left sidebar)
2. Under **App Credentials**, copy the **Signing Secret** — this is `SLACK_SIGNING_SECRET`

### Step 5: Create the Channels

Create two Slack channels in your workspace:
- `#devops-alerts` — for incident notifications
- `#devops-approvals` — for fix approval requests

Invite the AutoPilot bot to both channels:
```
/invite @AutoPilot DevOps
```

### Step 6: Update Your Secrets

In `k8s/secrets.yaml`:
```yaml
SLACK_BOT_TOKEN: "xoxb-your-bot-token"
SLACK_APP_TOKEN: "xapp-your-app-level-token"
SLACK_SIGNING_SECRET: "your-signing-secret"
```

In `k8s/configmap.yaml` (already set):
```yaml
SLACK_ALERT_CHANNEL: "#devops-alerts"
SLACK_APPROVAL_CHANNEL: "#devops-approvals"
```

Re-apply and restart:
```bash
kubectl apply -f k8s/secrets.yaml
kubectl rollout restart deployment/autopilot-agent -n autopilot
```

---

## 8. Using the Dashboard

### Open the UI
```
http://YOUR_NODE_IP:30011
```

Enter your `API_KEY` when prompted.

### Dashboard Pages

| Page | What you see |
|------|-------------|
| **Overview** | Live cluster health, active incidents, recent fixes |
| **Incidents** | Full log of every detected problem with severity and status |
| **Fix History** | Every fix that was executed — what was done and whether it worked |
| **Cluster** | Namespace and pod health status |
| **Jenkins** | Jenkins build history and failure analysis |
| **Metrics** | Charts of incident rates, fix success rates over time |
| **Settings** | View/change AutoPilot config — including the **AI Provider** card to switch between Claude and ChatGPT |

### Switching AI provider from the dashboard

On the **Settings** page there is an **AI Provider** card. You can click **Anthropic Claude** or **OpenAI ChatGPT** and edit the model name, then **Save** — the change takes effect immediately, no redeploy needed.

> The provider you switch to must already have its API key configured in your Secrets. If you try to switch to a provider whose key is missing, the dashboard will show an error and keep the current provider.

### Real-time Updates

The dashboard uses WebSocket to receive live events. You should see new incidents appear within 30 seconds of them occurring in the cluster — no refresh needed.

---

## 9. How AutoPilot Works Day-to-Day

### The Scan Loop (every 30 seconds)

```
1. Agent scans all pods in TARGET_NAMESPACES
2. Detects problems (CrashLoopBackOff, ImagePullBackOff, OOMKilled, etc.)
3. Pushes new incidents to the Redis queue
4. Worker picks up each incident
5. Sends incident details to your AI provider (Claude or ChatGPT)
6. The AI returns: root cause + fix plan + confidence score
7. If confidence >= 85 AND severity != CRITICAL: auto-fix
8. If severity == CRITICAL: send Slack approval request, wait up to 30 min
9. Execute fix (or skip if DRY_RUN=true)
10. Log result to PostgreSQL
11. Publish event to Redis pub/sub → WebSocket → Dashboard
12. Verify fix worked after POST_FIX_VERIFY_DELAY_SECONDS (120s)
```

### Hard Safety Rules (never broken)

- **Never touches `kube-system`** (except CoreDNS/metrics-server restart)
- **Never deletes PVCs, PersistentVolumes, or Secrets**
- **Never creates or modifies RBAC resources**
- **Always requires Slack approval for CRITICAL severity**
- **Skips fix if AI confidence < 85%**
- **Never fixes its own pod** (`autopilot-agent`)
- **Never retries Jenkins more than `JENKINS_MAX_RETRIES` times**
- **All fixes are idempotent** (safe to run twice)

---

## 10. Troubleshooting

### Agent pod is in CrashLoopBackOff

```bash
kubectl logs deployment/autopilot-agent -n autopilot --previous
```

Common causes:
- **AI provider key missing/mismatched** — the agent refuses to start if `LLM_PROVIDER` doesn't match a supplied key. If `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` must be set; if `LLM_PROVIDER=openai`, `OPENAI_API_KEY` must be set. The log will say e.g. `LLM_PROVIDER=openai requires OPENAI_API_KEY`.
- **`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` is wrong** — check your secrets.yaml for typos
- **Can't reach PostgreSQL** — run `kubectl get pods -n autopilot` to see if postgres-0 is Running
- **Can't reach Redis** — same check for the redis pod

### Dashboard shows "Failed to connect"

```bash
# Check the API is running
curl http://YOUR_NODE_IP:30010/health

# Check the port is open on Oracle Cloud firewall
# OCI Console → VCN → Security Lists → must allow TCP 30010 ingress
```

### "Unauthorized" error in dashboard

- Make sure `VITE_API_KEY` (used when building the dashboard image) and `API_KEY` (in secrets.yaml) are **the same value**.
- If they differ, rebuild the dashboard image with the correct `VITE_API_KEY` build arg.

### Jenkins webhook not being received

```bash
# Test from your Jenkins server directly
curl -v -X POST "http://YOUR_NODE_IP:30008/webhooks/jenkins" \
  -H "Content-Type: application/json" \
  -H "X-Jenkins-Token: YOUR_WEBHOOK_SECRET" \
  -d '{"job_name":"test","build_number":1,"result":"FAILURE","build_url":"http://jenkins:8080/job/test/1/"}'

# Should return 200 OK
# If connection refused: check port 30008 is open in firewall
# If 403: check X-Jenkins-Token header value matches JENKINS_WEBHOOK_SECRET
```

### Agent is detecting incidents but not fixing them

Check if `DRY_RUN=true` in your configmap:
```bash
kubectl get configmap autopilot-config -n autopilot -o yaml | grep DRY_RUN
```

If it is, edit the configmap and restart:
```bash
kubectl edit configmap autopilot-config -n autopilot
# Change DRY_RUN: "false"
kubectl rollout restart deployment/autopilot-agent -n autopilot
```

### I want to switch AI provider (Claude ⇄ ChatGPT) after deploying

**Fastest way (no redeploy):** open the dashboard → **Settings** → **AI Provider** card → pick the provider → **Save**. This works as long as that provider's key is already in your Secrets.

**Permanent way (survives pod restarts):** make sure the key exists in `k8s/secrets.yaml`, then change `LLM_PROVIDER` in the ConfigMap and restart:
```bash
# 1. Ensure the target provider's key is filled in secrets.yaml (OPENAI_API_KEY or ANTHROPIC_API_KEY)
kubectl apply -f k8s/secrets.yaml

# 2. Flip the provider in the ConfigMap (e.g. to openai)
kubectl edit configmap autopilot-config -n autopilot
# Change LLM_PROVIDER: "openai"   (and OPENAI_MODEL if you like)

# 3. Restart the agent so it reloads config
kubectl rollout restart deployment/autopilot-agent -n autopilot
```

> If the agent crashes after switching, you almost certainly forgot to add the new provider's key to your Secrets (see "Agent pod is in CrashLoopBackOff" above).

### Database connection issues

```bash
# Get a shell inside postgres pod and test it
kubectl exec -it postgres-0 -n autopilot -- psql -U autopilot -c "\dt"

# Should list tables: incidents, fix_executions, jenkins_incidents, etc.
# If no tables: the agent creates them on first start — check agent logs
```

### Resetting everything and starting fresh

```bash
# Delete all AutoPilot resources (keeps your app namespace untouched)
kubectl delete namespace autopilot

# Re-apply everything from scratch
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/clusterrole.yaml
kubectl apply -f k8s/clusterrolebinding.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml   # Your filled-in secrets file
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl rollout status statefulset/postgres -n autopilot
kubectl apply -f k8s/agent-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/dashboard-deployment.yaml
kubectl apply -f k8s/services.yaml
```

---

## 11. Quick Reference — All URLs and Ports

Replace `NODE_IP` with your Oracle Cloud VM's public IP address.

### AutoPilot URLs

| Service | URL | What it is |
|---------|-----|-----------|
| Dashboard (browser) | `http://NODE_IP:30011` | The UI you use daily |
| API | `http://NODE_IP:30010` | REST API (used by dashboard) |
| Agent health | `http://NODE_IP:30008/health` | Check agent is alive |
| Jenkins webhook | `http://NODE_IP:30008/webhooks/jenkins` | Jenkins posts here on build finish |

### K8s Internal URLs (used by pods talking to each other)

| Service | Internal URL |
|---------|-------------|
| Python Agent | `http://autopilot-agent.autopilot.svc.cluster.local:8000` |
| Node.js API | `http://autopilot-api.autopilot.svc.cluster.local:3001` |
| PostgreSQL | `postgres.autopilot.svc.cluster.local:5432` |
| Redis | `redis.autopilot.svc.cluster.local:6379` |

### Useful kubectl Commands

```bash
# See all AutoPilot pods
kubectl get pods -n autopilot

# Watch pods in real time
kubectl get pods -n autopilot -w

# Follow agent logs live
kubectl logs -f deployment/autopilot-agent -n autopilot

# Follow API logs live
kubectl logs -f deployment/autopilot-api -n autopilot

# Check your monitored app (taskflow)
kubectl get pods -n taskflow

# See all services and their NodePorts
kubectl get services -n autopilot

# Check what ConfigMap values are set
kubectl get configmap autopilot-config -n autopilot -o yaml

# Restart a specific component (e.g., after config change)
kubectl rollout restart deployment/autopilot-agent -n autopilot
kubectl rollout restart deployment/autopilot-api -n autopilot
kubectl rollout restart deployment/autopilot-dashboard -n autopilot
```

### File Reference

```
AutoPilot-DevOps-Agent/
├── agent/                    ← Python AI agent
│   ├── main.py               ← Entry point
│   ├── config/settings.py    ← All config keys and defaults
│   ├── core/scanner.py       ← K8s problem detection
│   ├── core/executor.py      ← Fix execution
│   ├── integrations/
│   │   ├── jenkins.py        ← Jenkins webhook + build analysis
│   │   ├── slack.py          ← Slack alerts + approvals
│   │   └── github.py         ← GitHub issue creation
│   ├── db/schema.sql         ← PostgreSQL table definitions
│   └── Dockerfile
├── api/                      ← Node.js read-only API
│   ├── src/index.ts          ← Entry point, CORS, middleware
│   ├── src/config.ts         ← Config from env vars
│   └── Dockerfile
├── dashboard/                ← React dashboard
│   ├── src/main.tsx          ← Entry point
│   ├── src/api/client.ts     ← API calls (uses VITE_API_URL + VITE_API_KEY)
│   ├── vite.config.ts
│   └── Dockerfile            ← Takes VITE_* as build args (baked in at build time)
├── k8s/                      ← All Kubernetes manifests
├── docker-compose.yml        ← Local development
├── .env.example              ← Template for local .env
└── END_TO_END_SETUP.md       ← This file
```

---

## Summary: The Minimal Checklist

If you remember nothing else, follow this order:

- [ ] Pick your AI: set `LLM_PROVIDER` in `k8s/configmap.yaml` to `anthropic` (Claude) or `openai` (ChatGPT)
- [ ] Fill in `k8s/configmap.yaml` — set `JENKINS_URL` to your Jenkins server IP
- [ ] Fill in `k8s/secrets.yaml` — set the matching AI key (`ANTHROPIC_API_KEY` **or** `OPENAI_API_KEY`) and `API_KEY` at minimum
- [ ] Build 3 Docker images for ARM64 and push to Docker Hub
- [ ] Build the dashboard image with `--build-arg VITE_API_URL=http://NODE_IP:30010`
- [ ] `kubectl apply` all manifests in the order shown in Step 5
- [ ] Open firewall ports 30008, 30010, 30011 on Oracle Cloud
- [ ] Open `http://NODE_IP:30011` in your browser
- [ ] On Jenkins: add the webhook shell script calling `NODE_IP:30008/webhooks/jenkins`
