# USDC Router

Non-custodial web service that shows where USDC earns more right now — **Solana** or **Aptos** — and moves funds there in one click using **Circle CCTP V2** (native USDC, no wrapped tokens, no bridge pools).

> **Status:** work in progress. The project skeleton, protocol registry and stack are in place; the rate collector, dashboard and Telegram bot (Stage 1) are being built. See the [Roadmap](#roadmap).

## Problem

USDC lending rates differ by 2–10% APY between chains and change daily. Tracking them by hand is tedious, and moving funds across chains scares newcomers: bridges, wrapped tokens, two wallets.

## Solution

- A real-time dashboard of USDC supply APY across the largest lending protocols on both chains.
- Telegram alerts when the spread between the best Solana and best Aptos rate exceeds your threshold.
- One-click transfer: withdraw from a protocol → burn/mint via CCTP V2 → deposit into the target protocol. The user signs at most two transactions.

## Key design decisions

- **Non-custodial.** The server only *builds* transactions; they are always signed in the user's own wallet. No private keys on the server.
- **No custom smart contracts in the MVP.** Only existing protocols and Circle CCTP V2.
- **Pure Python, no custom JavaScript.** Server-side rendering (Jinja2), charts generated in Python (Plotly), QR codes via `qrcode`. Signing goes through mobile wallets:
  - Solana: [Solana Pay transaction requests](https://docs.solanapay.com/spec) (Phantom, Solflare)
  - Aptos: Petra deeplinks with payload encryption (X25519 + XSalsa20-Poly1305 via PyNaCl)
- **Pluggable protocol adapters.** Each protocol implements one interface (`get_apy()`, `get_tvl()`, `get_user_position()`, `build_withdraw_tx()`, `build_deposit_tx()`); adding a protocol means a new adapter and a config entry, nothing else changes.
- **Failure-safe transfers.** CCTP message data is persisted, so an interrupted transfer can be finished later ("Finish transfer"), and funds are never lost if the service goes down.
- **Data redundancy.** On-chain data via RPC is the primary source; DefiLlama Yields is the fallback. A protocol is flagged "data in question" if the two diverge by more than 1 pp for 30 minutes.

## Supported networks and protocols (MVP)

| Network | Lending protocols | Wallets |
|---------|-------------------|---------|
| Solana  | Kamino Lend, MarginFi, Jupiter Lend | Phantom, Solflare |
| Aptos   | Aries Markets, Echelon, Thala | Petra (mobile) |

The registry lives in [config/protocols.yaml](config/protocols.yaml).

## Architecture

```
                ┌────────────────────┐
                │  Rate collector    │  every 5 min, APScheduler
                │  (adapters + RPC / │
                │   DefiLlama)       │
                └─────────┬──────────┘
                          ▼
┌──────────┐    ┌────────────────────┐    ┌──────────────┐
│ Telegram │◄───│  FastAPI app       │───►│ PostgreSQL / │
│ bot      │    │  API · SSR UI ·    │    │ TimescaleDB  │
│ (aiogram)│    │  tx builders       │    │ + Redis      │
└──────────┘    └─────────┬──────────┘    └──────────────┘
                          │
                          ▼
                ┌────────────────────┐
                │ Transfer service   │  CCTP V2 attestation,
                │ (arq worker)       │  receiveMessage
                └────────────────────┘
```

| Module | Tech |
|--------|------|
| Web UI | FastAPI, Jinja2, Plotly, qrcode |
| API | FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Solana signing | solders, anchorpy |
| Aptos signing | aptos-sdk, PyNaCl |
| Rate collector | solana-py, httpx, APScheduler |
| Transfer service | Circle CCTP V2 API (httpx), arq |
| Telegram bot | aiogram 3 |
| Storage | PostgreSQL (TimescaleDB), Redis |
| Quality | pytest, pytest-asyncio, respx, ruff, mypy, Docker Compose |

### Project layout

```
app/
  adapters/    per-protocol adapters (solana/, aptos/)
  api/         HTTP endpoints
  bot/         Telegram bot
  charts/      Plotly chart generation
  collector/   scheduled rate collection
  core/        config, DB, shared code
  services/    transfer / CCTP logic
  templates/   Jinja2 templates
  static/      static assets
alembic/       DB migrations
config/        protocol registry (protocols.yaml)
tests/
```

## Roadmap

| Stage | Scope | Signer | Status |
|-------|-------|--------|--------|
| 1. Dashboard | USDC rates, history charts, spread calculator, Telegram alerts | none (read-only) | 🚧 in progress |
| 2. One-click transfer | Withdraw → CCTP V2 → deposit, transfer history, service fee | user | planned |
| 3. Vault | Shared pool with automatic bot rebalancing (Anchor + Move contracts) | contract + operator bot | planned, after audit |

**Stage 1 features:** top block with best Solana / best Aptos APY and spread direction; sortable protocols table (APY base + rewards, TVL, utilization); APY charts for 24h / 7d / 30d; break-even calculator; Telegram bot (`/start`, `/rates`, `/alert <pp>`, `/stop`).

**Stage 2 features:** wallet connection via QR / deeplinks, on-chain USDC positions, confirmation screen with all fees and break-even time, transaction simulation before signing, live status page (Withdrawn → Burned → Attested → Minted → Deposited), recovery of interrupted transfers.

## Getting started

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy app
```

Run instructions (Docker Compose, migrations, environment variables) will be added as Stage 1 lands.

## Security

- No user private keys are ever stored or seen by the server.
- Transactions are simulated before signing; the sign button is disabled on simulation failure.
- CCTP and protocol addresses are pinned in config and verified against official docs on each release.

## Disclaimer

DeFi carries risk. Yields are not guaranteed, and lending protocols can be exploited or paused. This project is not financial advice.
