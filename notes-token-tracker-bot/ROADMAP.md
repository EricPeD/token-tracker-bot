- - -

- [ ] Moralis Wallet History API funcionando con parsing robusto
- [ ] Añadir @tenacity para retry automático (post-MVP)
- [ ] Documentación con Sphinx (post-MVP)

- - -

**Fase 0: Research & Setup (hecho-ish, 1-2 días más)**

- Research APIs: Probado Etherscan V2, pivot a Moralis (key generada). Crítica: Moralis free hasta 1M req/mes –¿suficiente para uso personal? Sí, pero monitoriza usage en dashboard. Fuente: [Moralis Pricing](https://moralis.io/pricing/).
- Repo: Creado (token-tracker-bot). Añadido .gitignore, LICENSE (MIT), pyproject.toml.
- Estructura: Actualizada con utils/format.py, watcher/storage.py (para cache última tx). Añade docs/ para Sphinx futuro.
- Tech setup: Deps instaladas (aiohttp, etc.). 
  Nota: Usa pip install -e .[dev] para extras como pytest.
- Trade-off: Moralis over Etherscan –pros: simpler parsing; contras: learning curve si cambias provider. ¿Seguro no fallback a Etherscan? No, enfócate.
- Trade-off: Moralis vs Etherscan –pros Moralis (formatted); contras (bugs como field names).

**Fase 1: MVP (3-5 días, hoy terminamos basics)**

- Bot básico: Comandos /start (bienvenida), /setwallet {address} (guarda en storage), /addtoken {contract} (generaliza más allá MYST), /check (on-demand query a Moralis, filtra nuevos depósitos).
- Watcher: On-demand (no loop), clase MoralisWatcher con get_deposits(). Cache última timestamp/tx_id en storage.py (JSON file para simpleza).
- Notificaciones: Msg formateado (amount, from, tx link a Polygonscan). Usa utils/format.py para Markdown rico.
- Logging: structlog a file (con levels: info para tx, error para API fails).
- Tests: pytest para watcher (mock aiohttp responses con pytest-asyncio).
- Trade-off: On-demand vs auto –empezamos on-demand por educación/simplicidad, pero prepárate para /autotrack (asyncio loop). Fuente: [Asyncio Loops Tutorial](https://realpython.com/async-io-python/) –webhooks mejor largo plazo.

**Fase 2: Elevación Portfolio (5-7 días)**

- Generalizar: Múltiples tokens/wallets via DB (SQLAlchemy + SQLite para histórico).
- Dashboard: Streamlit para visuales (tabla tx, chart volumen recibido).
- Alertas: /setminamount {value} (filtra en /check o auto).
- Docker: Post-MVP, para deploy fácil.
- CI/CD: GitHub Actions (ruff lint, pytest, coverage badge).
- Trade-off: DB vs JSON –añade complejidad, pero permite queries (e.g., "top remitentes"). ¿SQLite suficiente? Sí para start, migra Postgres si cloud.

**Fase 3: Optimizaciones/Futuras**

- Añadir webhooks: Moralis Streams (real-time push a bot endpoint).
- Análisis: Fees, remitente labels (integra Coingecko para USD value).
- Export: CSV reports.
- Nice-to-have: ERC-721 support (similar, pero parse tokenId).
- Trade-off: Features extras vs focus

- - -
