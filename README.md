# QSR Voice Agent

A voice-first ordering system for quick-service restaurants. Customers talk to a LiveKit voice agent to browse the menu and build a cart, then pay via a UPI QR code (PayU hosted checkout) — all reflected live in a web frontend.

## Architecture

- **`agent/`** — LiveKit voice agent worker (Python). Runs the STT → LLM → TTS pipeline via LiveKit Cloud's hosted inference gateway, answers menu questions, builds the cart through function tools, and creates the order on the backend once the customer confirms. Publishes `cart_update` / `order_update` data messages so the frontend stays in sync with the spoken conversation.
- **`backend/`** — FastAPI service (Python). Owns the menu, orders, sessions, PayU payment flow, and conversation recording, backed by Postgres via SQLAlchemy/Alembic.
- **`frontend/`** — React + Vite web app (TypeScript). Customer-facing ordering UI (menu, cart, voice controls, checkout/payment result) plus an admin app for managing the menu.
- **`docker-compose.yml`** — Local Postgres instance used by the backend.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Postgres) or a local Postgres instance
- A [LiveKit Cloud](https://cloud.livekit.io/) project (URL, API key, API secret)
- PayU sandbox merchant credentials ([test.payu.in](https://test.payu.in))

## Setup

### 1. Database

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in LiveKit and PayU credentials, and set ADMIN_JWT_SECRET (openssl rand -hex 32)
alembic upgrade head
python scripts/import_menu.py seed/sample_menu.json   # optional: load sample menu
python scripts/create_admin.py admin   # create the first /admin login (prompts for a password)
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`.

### 3. Voice agent

```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in LiveKit credentials + BACKEND_URL
python agent.py dev
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_BACKEND_URL
npm run dev
```

Frontend runs at `http://localhost:5173`.

## Admin dashboard

The menu admin at `/admin` (`frontend/src/admin/`) requires logging in with an `admin_users` account. There's no self-signup — accounts are created with a backend script:

```bash
cd backend && source .venv/bin/activate
python scripts/create_admin.py <username>   # prompts for a password; safe to re-run to reset one
```

Login issues a JWT (signed with `ADMIN_JWT_SECRET`, valid for `ADMIN_JWT_EXPIRE_MINUTES`, default 12h) that all `/admin/*` API routes require. Each account has a `role` (currently always `owner`) reserved for future role-based permissions. In production, run `create_admin.py` once via your host's shell/console to bootstrap the first account — there's currently no in-app way to add more, so do the same for any additional admins until that's built.

## Notes

- Checkout is restricted to UPI only (PayU `enforce_paymethod=upi`) — no cards, netbanking, or wallets.
- Until a physical receipt printer is wired up, a successful payment saves a printable HTML receipt to disk and opens it in a new tab as a stand-in.
- PayU's success/failure callback hits the backend directly, so `BACKEND_PUBLIC_BASE_URL` must be publicly reachable in any real deployment (not just `localhost`).
