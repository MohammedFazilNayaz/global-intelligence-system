# Global Intelligence Platform — AWS EC2 Deployment Guide (Docker Compose)

This document provides exact, production-grade instructions for deploying the **Global Intelligence Platform** to an AWS EC2 instance using Docker Compose.

---

## 1. Deployment Architecture Overview

The production architecture runs as a set of isolated Docker containers interconnected via a private bridge network (`app_network`):

```
                       [ Internet Traffic ]
                                │
                                ▼
                       ┌─────────────────┐
                       │   AWS EC2       │
                       │ Security Group  │
                       │ (Ports 80, 443) │
                       └────────┬────────┘
                                │
                                ▼
    ┌────────────────────────────────────────────────────────┐
    │  Host EC2 Instance (Ubuntu 22.04/24.04 LTS)           │
    │                                                        │
    │   ┌────────────────────────────────────────────────┐   │
    │   │ global_intelligence_frontend (Nginx :80)       │   │
    │   │  - Serves compiled React/Vite SPA              │   │
    │   │  - Reverse proxies /api/ -> backend:8000       │   │
    │   │  - Handles Gzip compression & security headers │   │
    │   └───────────────────────┬────────────────────────┘   │
    │                           │ (Internal Docker Network)  │
    │                           ▼                            │
    │   ┌────────────────────────────────────────────────┐   │
    │   │ global_intelligence_backend (FastAPI :8000)    │   │
    │   │  - IngestionScheduler (in-process coordinator) │   │
    │   │  - DocumentPipelineWorkerPool (2 async workers)│   │
    │   │  - Runs Alembic migrations on startup          │   │
    │   │  - Internal port ONLY (never bound to host)    │   │
    │   └───────────────────────┬────────────────────────┘   │
    │                           │                            │
    │                           ▼                            │
    │   ┌────────────────────────────────────────────────┐   │
    │   │ global_intelligence_postgres (PostgreSQL 16)   │   │
    │   │  - Persistent named volume: postgres_data      │   │
    │   │  - Internal port 5432 (never bound to host)    │   │
    │   └────────────────────────────────────────────────┘   │
    └────────────────────────────────────────────────────────┘
```

### Key Architectural Tenets:
1. **Network Isolation**: PostgreSQL (port 5432) and FastAPI (port 8000) are **never** exposed to the host or internet. Only Nginx (port 80/443) binds to the host.
2. **Scheduler Integrity**: The IngestionScheduler and DocumentPipelineWorkerPool run as an in-process coordinator inside the FastAPI backend container (`--workers 1`). This prevents duplicate scheduler loops, eliminates overlapping feed fetches, and preserves real-time in-memory queue telemetry for `/api/v1/ingestion/status`.
3. **Persistent Storage**: PostgreSQL data is written to a Docker named volume (`postgres_data`) mapped to the host's `/var/lib/docker/volumes/` directory, surviving container restarts and upgrades.

---

## 2. Recommended EC2 Instance Requirements

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Instance Type** | `t3.medium` (2 vCPU, 4 GB RAM) | `t3.large` or `t4g.large` (2 vCPU, 8 GB RAM) |
| **Operating System** | Ubuntu 22.04 LTS or 24.04 LTS | Ubuntu 24.04 LTS (x86_64) |
| **Storage (EBS)** | 30 GB gp3 SSD | 50 GB gp3 SSD (IOPS 3000, 125 MB/s) |
| **Architecture** | x86_64 / amd64 | x86_64 / amd64 |

*Note: For ARM64 (`t4g.*`) instances, the multi-stage Dockerfiles build natively without code changes.*

---

## 3. AWS Security Group Rules

Create a dedicated Security Group (e.g. `sg-global-intelligence-prod`):

### Inbound Rules (Ingress)
| Type | Port Range | Protocol | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | `22` | TCP | `Your-Office-or-Bastion-IP/32` | Administrative server access (Strictly restricted) |
| **HTTP** | `80` | TCP | `0.0.0.0/0` | Public web dashboard & API reverse proxy |
| **HTTPS** | `443` | TCP | `0.0.0.0/0` | Secure web dashboard & API (when SSL configured) |

> [!CAUTION]
> **NEVER** add inbound rules for port `5432` (PostgreSQL) or port `8000` (FastAPI). These services communicate strictly over the internal Docker bridge network.

### Outbound Rules (Egress)
| Type | Port Range | Protocol | Destination | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **All Traffic** | All | All | `0.0.0.0/0` | Feed ingestion (USGS GeoJSON, RSS/Atom, Central Banks, Market APIs) |

---

## 4. Environment Variables Reference

Production configuration is managed exclusively via the untracked `.env` file on the EC2 host.

| Variable | Example Value | Description |
| :--- | :--- | :--- |
| `POSTGRES_DB` | `global_intelligence` | PostgreSQL database name. |
| `POSTGRES_USER` | `postgres` | PostgreSQL root user. |
| `POSTGRES_PASSWORD` | *(Secure random secret)* | Strong password (e.g. 32 chars generated via openssl). |
| `DATABASE_URL` | `postgresql+psycopg://...` | Constructed URL for backend container to reach `postgres:5432`. |
| `PROJECT_NAME` | `"Global Intelligence Platform"` | Name displayed across API docs and status page. |
| `ENVIRONMENT` | `production` | Production environment flag. |
| `DEBUG` | `false` | Disables debug logs and detailed traceback exposure. |
| `LOG_LEVEL` | `INFO` | Logging level (`INFO`, `WARNING`, `ERROR`). |
| `API_V1_STR` | `/api/v1` | Base API route prefix. |
| `ENABLE_SCHEDULER` | `true` | Starts IngestionScheduler and async pipeline workers in backend. |
| `RUN_MIGRATIONS` | `true` | Automatically executes `alembic upgrade head` upon boot. |
| `SEED_ON_STARTUP` | `false` | If `true`, seeds the 35 verified global sources on first boot. |
| `REQUEST_TIMEOUT_SECONDS` | `15.0` | Ingestion fetch timeout per source. |
| `MAX_RETRIES` | `3` | Maximum HTTP connection retries. |
| `BACKOFF_FACTOR` | `1.5` | Exponential retry backoff multiplier. |
| `DEFAULT_USER_AGENT` | `GlobalIntelligencePlatform/1.0` | Outbound HTTP User-Agent header for feed collectors. |
| `VITE_API_URL` | `/api/v1` | Relative API URL routed via Nginx reverse proxy. |
| `NGINX_PORT` | `80` | Host port exposed for web traffic. |

---

## 5. Step-by-Step EC2 Deployment Commands

### Step 1: Connect to the EC2 Instance
```bash
ssh -i /path/to/your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

### Step 2: System Updates and Docker Installation
```bash
# Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# Install Docker's official GPG key and repository
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine, Docker CLI, and Docker Compose Plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow ubuntu user to execute docker commands without sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker installation
docker --version
docker compose version
```

### Step 3: Clone Repository
```bash
cd /opt
sudo mkdir -p global-intelligence
sudo chown -R $USER:$USER global-intelligence
cd global-intelligence

git clone https://github.com/MohammedFazilNayaz/global-intelligence-system.git .
```

### Step 4: Configure Production Environment Variables
```bash
# Copy template to untracked .env file
cp .env.example .env

# Generate a cryptographically secure PostgreSQL password
PG_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)

# Replace placeholders in .env
sed -i "s/your_secure_postgres_password_here/${PG_PASS}/g" .env
sed -i "s/DEBUG=true/DEBUG=false/g" .env
sed -i "s/ENVIRONMENT=development/ENVIRONMENT=production/g" .env

# Restrict permissions so only the owner can read .env
chmod 600 .env
```

### Step 5: Build and Launch Containers
```bash
# Validate Docker Compose configuration
docker compose config

# Build images and start all services in detached mode
docker compose up -d --build
```

### Step 6: Verify Service Health
```bash
# Monitor container status and health probes
docker compose ps

# Follow startup logs (database readiness, Alembic migrations, scheduler boot)
docker compose logs -f
```

Expected healthcheck output:
```
NAME                           IMAGE                          STATUS                    PORTS
global_intelligence_postgres   postgres:16-alpine             Up (healthy)              
global_intelligence_backend    .../backend:latest             Up (healthy)              
global_intelligence_frontend   .../frontend:latest            Up (healthy)              0.0.0.0:80->80/tcp
```

### Step 7: Seed Verified Global Intelligence Sources
Once the containers are running and healthy, seed the 35 verified global intelligence feeds:
```bash
docker compose exec backend python scripts/seed_sources.py
```

### Step 8: Test Public Endpoints
```bash
# Verify root system health from the host
curl -f http://localhost/health

# Verify API v1 health
curl -f http://localhost/api/v1/health

# Verify Ingestion Scheduler runtime telemetry
curl -f http://localhost/api/v1/ingestion/status
```

Access the web dashboard in your browser: `http://<EC2-PUBLIC-IP>`

---

## 6. Database Migration Procedure

Database migrations are automated via `scripts/docker-entrypoint.sh` using Alembic on container boot:
- The backend checks PostgreSQL connectivity using `SELECT 1;`.
- Once connected, it executes `alembic upgrade head`.

### Manual Migration Check or Direct Run
To run or inspect migrations manually inside the running backend container:

```bash
# Check current migration revision in database
docker compose exec backend alembic current

# Check available head revisions
docker compose exec backend alembic heads

# Manually upgrade to head
docker compose exec backend alembic upgrade head

# View migration history
docker compose exec backend alembic history --verbose
```

---

## 7. Database Backup & Restore Procedure

### Taking a Database Backup
Run `pg_dump` directly against the internal container without exposing any ports:

```bash
# Create local backups directory
mkdir -p /opt/global-intelligence/backups
BACKUP_FILE="/opt/global-intelligence/backups/global_intelligence_$(date +%Y%m%d_%H%M%S).sql.gz"

# Execute compressed backup
docker compose exec -T postgres pg_dump -U postgres -d global_intelligence | gzip > "$BACKUP_FILE"

echo "Backup created at: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"
```

### Automated Nightly Backup Cron
Add a nightly cron job on the EC2 host:
```bash
(crontab -l 2>/dev/null; echo "0 2 * * * docker compose -f /opt/global-intelligence/docker-compose.yml exec -T postgres pg_dump -U postgres -d global_intelligence | gzip > /opt/global-intelligence/backups/db_\$(date +\%Y\%m\%d).sql.gz && find /opt/global-intelligence/backups -name '*.sql.gz' -mtime +14 -delete") | crontab -
```

### Restoring from Backup
```bash
# 1. Stop backend services to halt writes
docker compose stop backend frontend

# 2. Re-create clean database
docker compose exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS global_intelligence;"
docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE global_intelligence;"

# 3. Restore data from gzip file
gunzip -c /opt/global-intelligence/backups/YOUR_BACKUP_FILE.sql.gz | docker compose exec -T postgres psql -U postgres -d global_intelligence

# 4. Restart backend and frontend
docker compose start backend frontend

# 5. Verify health
docker compose exec backend python -c "from backend.app.db.session import engine; from sqlalchemy import text; print(engine.connect().execute(text('SELECT count(*) FROM sources')).scalar(), 'sources restored')"
```

---

## 8. Rollback Procedure

If a deployment or schema migration introduces an unexpected defect:

### Option A: Application Code Rollback (No Migration Reversal Needed)
```bash
# Revert Git repository to the previous stable release commit
git checkout <PREVIOUS_COMMIT_OR_TAG>

# Rebuild and restart containers
docker compose up -d --build
```

### Option B: Database Migration Rollback
```bash
# 1. Downgrade Alembic migration by 1 revision
docker compose exec backend alembic downgrade -1

# 2. Check current active migration
docker compose exec backend alembic current

# 3. Rebuild and restart application containers
docker compose restart backend
```

### Option C: Complete Emergency State Rollback (Full Snapshot Restore)
```bash
# Stop current deployment
docker compose down

# Restore database from previous night's backup (see Section 7)
docker compose up -d postgres
# (execute restore steps)

# Check out previous stable Git tag
git checkout <STABLE_TAG>

# Bring services back up
docker compose up -d --build
```

---

## 9. HTTPS / TLS Configuration (Post-Deployment)

Initially, Nginx serves HTTP on port 80. To secure production traffic with HTTPS:

### Method 1: AWS Application Load Balancer (Recommended for AWS)
1. Point your domain (e.g. `intelligence.yourdomain.com`) to an AWS ALB via Route 53.
2. Request a free SSL/TLS certificate via AWS Certificate Manager (ACM).
3. Configure the ALB Listener on port `443` with the ACM certificate, forwarding traffic to the EC2 instance on port `80`.
4. Nginx receives forwarded traffic and inspects the `X-Forwarded-Proto` header.

### Method 2: Let's Encrypt / Certbot on Host
```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain and install certificate
sudo certbot certonly --webroot -w /var/lib/docker/volumes/globalintelligentnewasystem_frontend/_data -d yourdomain.com

# Update nginx/default.conf to uncomment port 443 SSL directives and reload:
docker compose exec frontend nginx -s reload
```

---

## 10. Operational Monitoring & Diagnostics

### Viewing Real-Time Logs
```bash
# Tail all container logs
docker compose logs -f --tail=100

# Tail backend and scheduler logs
docker compose logs -f backend

# Tail Nginx access and error logs
docker compose logs -f frontend
```

### Inspecting Resource Usage
```bash
# View live CPU, memory, network, and block I/O per container
docker stats
```

### Checking Ingestion Backlog & Scheduler Telemetry
```bash
docker compose exec backend curl -s http://127.0.0.1:8000/api/v1/ingestion/status | jq .
```
