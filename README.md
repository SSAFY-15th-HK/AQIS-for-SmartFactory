# AQIS for SmartFactory

AQIS는 스마트팩토리 품질 검사 흐름을 시뮬레이션하고, 이후 실제 장비 연동으로 확장하기 위한 프로젝트입니다.

## Structure

```text
server/             FastAPI + WebSocket backend
AQIS-sim/           Simulation-only workspace
  robodk/           RoboDK station, assets, and simulation script
  web/              Vite React dashboard for simulation monitoring
AQIS-real/          Reserved workspace for real hardware integration
docs/               Architecture and interface documents
sample-data/        Sample images and videos
```

## Simulation Quick Start

### 1. Server

```bash
cd server
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

### 2. Simulation Web

```bash
cd AQIS-sim/web
npm install
npm run dev -- --host 0.0.0.0
```

Open:

```text
http://localhost:5173
```

### 3. RoboDK Simulation

Open the station:

```text
AQIS-sim/robodk/AQIS.rdk
```

Run the RoboDK script:

```text
AQIS-sim/robodk/Main.py
```

## Direction

- `AQIS-sim/web` is intentionally simulation-only.
- Future real hardware UI should live separately under `AQIS-real/` or another clearly named real-client folder.
- Shared server APIs should stay in `server/`; sim-only assumptions should be documented or isolated before real hardware work begins.
