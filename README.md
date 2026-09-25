# USDC Router (Solana + Aptos)

<img width="1200" height="880" alt="5_dashboard_en" src="https://github.com/user-attachments/assets/7ca78872-750a-4723-87d9-13a5786e8dea" />
<img width="1200" height="880" alt="1_dashboard" src="https://github.com/user-attachments/assets/4a31fbbe-c991-41c9-8f4c-63fe9071c971" />
<img width="1200" height="810" alt="2_charts" src="https://github.com/user-attachments/assets/c22e0725-63fa-47c0-bd5f-788f519d2515" />
<img width="1200" height="510" alt="3_calculator" src="https://github.com/user-attachments/assets/682b9f97-f39c-4fe7-a553-3b2b30f497f5" />
<img width="1000" height="2100" alt="4_mobile" src="https://github.com/user-attachments/assets/d6e6f678-98b1-4379-b635-1404846a0cd5" />


Реализация ТЗ. Python 3.12, FastAPI + Jinja2 (без собственного JS), SQLAlchemy 2 async, aiogram 3.

## Запуск (dev)

```bash
uv venv --python 3.12 .venv && uv pip install -e ".[dev]" --group dev   # или pip install -e .
.venv/Scripts/python -m uvicorn app.main:app      # SQLite, первый сбор ставок сразу при старте
.venv/Scripts/python -m pytest                    # 27 тестов
TELEGRAM_TOKEN=... python -m app.bot.telegram_bot
```
Прод: `cp .env.example .env && docker compose up` (Postgres/Timescale + Redis, миграции Alembic).

## Статус по ТЗ

| Раздел | Статус |
|---|---|
| 4.1 Сборщик (каждые 5 мин, история в БД, резервный источник, пометка расхождений >1 п.п./30 мин) | ✅ работает на реальных данных DefiLlama |
| 4.2 Дашборд: карточки, таблица с сортировкой, графики Plotly 24ч/7д/30д, спред, калькулятор + порог окупаемости | ✅ |
| 4.3 Telegram: /start /rates /alert /stop, 30 мин подряд, не чаще 6 ч | ✅ (логика покрыта тестами; с реальным токеном не запускался) |
| 4.4 Новый протокол = запись в `config/protocols.yaml` + класс адаптера | ✅ |
| 5.1 Подключение кошельков: Solana connect (Solana Pay), Petra deeplink + QR | ✅ реализовано, **не проверено с реальными кошельками** |
| 5.2 Сценарий перевода: конечный автомат, статус (meta refresh), история, комиссия 0,1%, мин. 10 USDC | ✅ каркас и БД |
| 5.3 «Завершить перевод» после сжигания (attestation по хэшу сожжения) | ✅ до шага attestation |
| **Сборка транзакций**: вывод из протокола, `depositForBurn`, `receiveMessage`, депозит/hook | ❌ **не реализовано** (см. ниже) |
| Позиции пользователя в протоколах (`get_user_position`) | ❌ |
| On-chain адаптеры ставок (RPC/IDL) | ❌ пока DefiLlama |
| 8 CSP, симуляция, RPC-failover, мониторинг | CSP ✅, RPC-failover для Solana ✅, симуляция/мониторинг ❌ |
| Этап 3 (vault) | вне MVP |

## Что нужно знать

1. **Протоколы без данных.** На DefiLlama Yields нет пулов MarginFi, Aries и Thala (лендинг) —
   на дашборде они честно показывают «нет данных», а не выдуманные ставки. Нужны on-chain адаптеры
   (`get_onchain_rates`), 1–2 дня на каждый, как в ТЗ. Kamino: в конфиге взят один из USDC-рынков
   (`Figure Market`, TVL $2.5M) — перед стартом выберите основной рынок.
2. **Транзакции не собираются намеренно.** Ошибка в `depositForBurn` (адрес получателя, сумма, домен)
   = потеря денег, а проверить её можно только на devnet/testnet с реальными кошельками. Адаптеры
   бросают `NotImplementedError`. Делать по плану ТЗ, неделя 4: Solana devnet ↔ Aptos testnet.
3. **Формат ответа Petra** разобран по официальной документации, но ТЗ прямо требует проверить
   https-адрес возврата прототипом — сделать первым делом на этапе 2.
4. Ключи dApp для Petra и сессии хранятся в памяти процесса — для нескольких воркеров нужен Redis.
5. Адреса CCTP V2 (`config/cctp.yaml`) сверены с developers.circle.com 2026-09-25; сверять при каждом релизе.
6. Docker-конфигурация написана, но не запускалась (Docker daemon был выключен).
