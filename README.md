# Grocery (Mono-repo)

Tech stack:
- Backend: FastAPI (Python)
- Collector: Python (httpx, bs4)
- DB: Postgres (Docker Compose)
- Frontend: React + Vite + TypeScript (初始化见 apps/dashboard/README.md)
- Contracts: Shared Pydantic models

## Quick start

```bash
docker compose -f infra/compose.yaml up -d
```

Backend (dev):
```bash
cd apps/grocery-api
python -m venv .venv && .venv/Scripts/activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Collector (dev):
```bash
cd apps/grocery-collector
python -m venv .venv && .venv/Scripts/activate  # Windows
pip install -r requirements.txt
python -m collector.run_once
```

Frontend (create with Vite):
```bash
cd apps/dashboard
npm create vite@latest . -- --template react-ts
npm install
npm install axios react-router-dom
npm run dev
```

Visit API docs: http://localhost:8000/docs
