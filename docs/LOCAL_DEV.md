# EMCIP Local Development Setup

This guide covers setting up the local development environment with Docker for Postgres and Redis.

---

## Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Python 3.11+** with virtual environment
- **Git** for version control

---

## Quick Start

### 1. Start Infrastructure Services

```powershell
# Navigate to project root
cd "I:\EDS Content Generation"

# Start Postgres and Redis
docker compose up -d

# Verify services are running
docker compose ps
```

**Expected output:**
```
NAME                COMMAND                  STATUS          PORTS
emcip_postgres      "docker-entrypoint.s…"   Up (healthy)    0.0.0.0:5432->5432/tcp
emcip_redis         "docker-entrypoint.s…"   Up (healthy)    0.0.0.0:6379->6379/tcp
```

### 2. Configure Environment

```powershell
# Copy example env file (if not already done)
copy .env.example .env

# Edit .env with your actual values (API keys, etc.)
notepad .env
```

**Key settings for local dev:**
```ini
# Database (matches docker-compose defaults)
DB_NAME=emcip
DB_USER=emcip
DB_PASSWORD=emcip_dev_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
```

### 3. Run Migrations

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run database migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 4. Start Django

```powershell
python manage.py runserver
```

**Access points:**
- Django Admin: http://127.0.0.1:8000/admin/
- API: http://127.0.0.1:8000/api/

---

## Debug Tools (Optional)

Start additional debugging tools:

```powershell
# Start with pgAdmin and Redis Commander
docker compose --profile debug up -d
```

**Access points:**
- pgAdmin: http://localhost:5050 (login: admin@emcip.local / admin)
- Redis Commander: http://localhost:8081

---

## Running Celery Worker

```powershell
# Terminal 1: Start Celery worker
celery -A config worker -l info

# Terminal 2: (Optional) Start Celery Beat for scheduled tasks
celery -A config beat -l info
```

---

## Service Management

### Stop Services
```powershell
docker compose down
```

### Stop and Remove Volumes (DELETES DATA)
```powershell
docker compose down -v
```

### View Logs
```powershell
# All services
docker compose logs -f

# Specific service
docker compose logs -f postgres
```

### Restart a Service
```powershell
docker compose restart postgres
```

---

## Database Access

### Django Shell
```powershell
python manage.py shell
```

### Direct Postgres Access
```powershell
docker exec -it emcip_postgres psql -U emcip -d emcip
```

### Direct Redis Access
```powershell
docker exec -it emcip_redis redis-cli
```

---

## Switching Between SQLite and Postgres

### Use SQLite (for quick testing)
In `.env`, comment out or remove `DB_NAME`:
```ini
# DB_NAME=emcip
```

### Use Postgres (default for development)
In `.env`, ensure `DB_NAME` is set:
```ini
DB_NAME=emcip
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 5432 already in use | Stop local Postgres or change `DB_PORT` in `.env` |
| Port 6379 already in use | Stop local Redis or change `REDIS_PORT` in `.env` |
| Can't connect to database | Ensure `docker compose up -d` succeeded |
| Migration errors | Check `DB_HOST=localhost` (not `postgres`) |
| Celery not finding tasks | Ensure Redis is running, check `CELERY_BROKER_URL` |

---

## Environment Modes

| Mode | Database | Celery | Use Case |
|------|----------|--------|----------|
| Quick Test | SQLite | Eager | Fast iteration, no Docker |
| Local Dev | Postgres | Redis | Full pipeline testing |
| Production | Postgres | Redis | Deployed environment |

---

*Last Updated: 2025-12-23 - Phase 1*
