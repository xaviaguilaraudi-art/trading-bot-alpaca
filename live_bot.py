"""
Bot d'execució real (o paper) contra Alpaca — rebalanceig MENSUAL dels 3
àmbits independents.

FUNCIONAMENT:
- Es pensat per executar-se UN COP AL MES (rebalanceig mensual estratègic).
- La vigilància de risc entre rebalancejos la fa risk_guardian.py, cada
  hora, per separat.
- Per defecte opera en PAPER TRADING (config.PAPER_TRADING = True).

REQUISITS:
    pip install -r requirements.txt
    export ALPACA_API_KEY="..."
    export ALPACA_SECRET_KEY="..."
    export TELEGRAM_BOT_TOKEN="..."   (opcional però recomanat)
    export TELEGRAM_CHAT_ID="..."     (opcional però recomanat)
"""

import math
import os
import time
import sys
import json
import logging
from datetime import datetime

import pandas as pd

from config import SLEEVES, PAPER_TRADING, TICKER_LABELS
from strategy import decide_all_sleeves
from sleeve_ledger import load_ledger, save_ledger, mark_to_market_and_update, total_capital, reconcile_with_broker_equity
from risk_state import load_all, save_all, check_sleeve
from withdrawal import load_capital_base, compute_suggested_withdrawal
from telegram_alerts import send_telegram_message
from dashboard import generate_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("live_bot")

HISTORY_FILE = "rebalance_history.json"


def get_alpaca_client():
    from alpaca.trading.client import TradingClient
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError(
            "Falten ALPACA_API_KEY / ALPACA_SECRET_KEY com a variables d'entorn. "
            "No es continua sense credencials explícites."
        )
    return TradingClient(api_key, secret_key, paper=PAPER_TRADING)


def get_price_history(tickers, lookback_days=280):
    """Descarrega històric via yfinance (requereix internet a la màquina on s'executi)."""
    import yfinance as yf
    yf.set_tz_cache_location("/tmp")  # evita OperationalError('database is locked') a GitHub Actions
    data = yf.download(tickers, period=f"{lookback_days}d", auto_adjust=True, progress=False)["Close"]
    result = {t: data[t].dropna() for t in tickers}
    # Reintent individual per tickers que hagin tornat buits (fallada puntual de descàrrega)
    empty = [t for t, s in result.items() if len(s) == 0]
    if empty:
        log.warning(f"Reintentant descàrrega per: {empty}")
        retry = yf.download(empty, period=f"{lookback_days}d", auto_adjust=True, progress=False)["Close"]
        for t in empty:
            s = retry[t].dropna() if t in retry else pd.Series(dtype=float)
            if len(s) > 0:
                result[t] = s
            else:
                raise RuntimeError(f"No s'ha pogut descarregar dades per {t} després de reintent.")
    return result


def _sleeve_reason(sleeve_cfg, chosen_ticker, halted, halt_reason):
    if halted:
        return f"Protecció de risc activada: {halt_reason}"
    if chosen_ticker == sleeve_cfg["safe_asset"]:
        return (
            "Cap actiu d'aquest àmbit tenia una tendència prou positiva aquest mes, "
            "així que s'ha mogut a l'actiu segur."
        )
    return (
        f"{TICKER_LABELS.get(chosen_ticker, chosen_ticker)} ha tingut el millor rendiment "
        "recent d'entre les opcions d'aquest àmbit, amb una tendència a l'alça."
    )


def rebalance_to_targets(client, target_dollars: dict):
    """
    target_dollars: dict {ticker: import objectiu en $} agregat de tots els
    àmbits per a aquest ticker. Ajusta les posicions reals del compte
    perquè coincideixin.
    """
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    # 1) Cancel·la ordres pendents d'execucions anteriors, perquè no es
    #    dupliquin (les ordres pendents no surten a get_all_positions()).
    try:
        client.cancel_orders()
        time.sleep(2)
    except Exception as e:
        log.warning(f"No s'han pogut cancel·lar ordres pendents: {e}")

    positions = {p.symbol: float(p.market_value) for p in client.get_all_positions()}
    account_equity = float(client.get_account().equity)
    min_trade = max(account_equity * 0.005, 1.0)  # ignora ajustos menors al 0.5%

    # 2) Primer VENDES (alliberen buying power), després COMPRES.
    sells, buys = [], []
    for ticker, current_value in positions.items():
        target_value = target_dollars.get(ticker, 0.0)
        if target_value <= 0:
            sells.append((ticker, None))  # tancar sencera
        elif current_value - target_value >= min_trade:
            sells.append((ticker, current_value - target_value))
    for ticker, target_value in target_dollars.items():
        diff_value = target_value - positions.get(ticker, 0.0)
        if diff_value >= min_trade:
            buys.append((ticker, diff_value))

    def _submit(ticker, side, amount):
        notional = math.floor(amount * 100) / 100
        log.info(f"Ordre: {side.value} {ticker} per ${notional}")
        try:
            client.submit_order(MarketOrderRequest(
                symbol=ticker, notional=notional, side=side, time_in_force=TimeInForce.DAY,
            ))
        except Exception as e:
            log.warning(f"No s'ha pogut enviar l'ordre de {ticker}: {e}")

    for ticker, amount in sells:
        if amount is None:
            try:
                client.close_position(ticker)
                log.info(f"Tancant posició residual a {ticker}")
            except Exception as e:
                log.warning(f"No s'ha pogut tancar {ticker}: {e}")
        else:
            _submit(ticker, OrderSide.SELL, amount)

    if sells:
        _wait_for_fills(client)

    if buys:
        # No gastar més del buying power real (evita errors per cèntims)
        buying_power = float(client.get_account().buying_power)
        total_buys = sum(a for _, a in buys)
        scale = min(1.0, buying_power / total_buys) if total_buys > 0 else 1.0
        for ticker, amount in buys:
            _submit(ticker, OrderSide.BUY, amount * scale)


def _wait_for_fills(client, timeout_s: int = 60):
    """Espera que no quedin ordres obertes (fins a timeout_s segons)."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    waited = 0
    while waited < timeout_s:
        open_orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
        if not open_orders:
            return
        time.sleep(3)
        waited += 3
    log.warning("Hi ha vendes que encara no s'han executat; les compres poden quedar curtes.")


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def save_history(history: list):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def already_rebalanced_this_month() -> bool:
    """True si a l'historial ja hi ha un rebalanceig mensual (data 'AAAA-MM-DD',
    sense hora — les entrades horàries del vigilant de risc porten hora) d'aquest mes."""
    this_month = datetime.today().strftime("%Y-%m")
    return any(
        len(h.get("date", "")) == 10 and h["date"].startswith(this_month)
        for h in load_history()
    )


def _next_run_date() -> str:
    """Primer dia laborable (dl-dv) del mes vinent. No té en compte festius
    dels EUA; si ho és, el bot ho detecta i ho fa l'endemà."""
    now = datetime.today()
    nxt = now.replace(year=now.year + 1, month=1, day=1) if now.month == 12 else now.replace(month=now.month + 1, day=1)
    while nxt.weekday() >= 5:
        nxt = nxt.replace(day=nxt.day + 1)
    return nxt.strftime("%Y-%m-%d")


def main():
    mode = "PAPER" if PAPER_TRADING else "LIVE (DINERS REALS)"
    log.info(f"=== Iniciant rebalanceig mensual — mode: {mode} ===")

    # Execució manual (botó "Run workflow" o en local) = forçar rebalanceig.
    # Execució programada = només el primer dia laborable del mes.
    manual_run = os.environ.get("GITHUB_EVENT_NAME", "manual") != "schedule"

    if not manual_run and already_rebalanced_this_month():
        log.info("Aquest mes ja s'ha fet el rebalanceig. No cal fer res.")
        return

    client = get_alpaca_client()

    # Si el mercat està tancat, les ordres es queden pendents i es poden
    # duplicar en una segona execució. Millor no fer res.
    clock = client.get_clock()
    if not clock.is_open:
        if manual_run:
            msg = (f"Mercat tancat (proper obertura: {clock.next_open}). "
                   "No s'ha fet cap rebalanceig. Torna-ho a llançar amb el mercat obert.")
            log.warning(msg)
            send_telegram_message(f"⏸️ {msg}")
        else:
            # Cap de setmana o festiu: ho tornarà a provar demà automàticament.
            log.info(f"Mercat tancat avui (proper obertura: {clock.next_open}). Es reintentarà el proper dia.")
        return

    account = client.get_account()
    broker_equity = float(account.equity)
    cash = float(account.cash)

    ledger = load_ledger(broker_equity)
    ledger = reconcile_with_broker_equity(ledger, broker_equity)

    all_tickers = set()
    for cfg in SLEEVES.values():
        all_tickers.update(cfg["risk_assets"].values())
        all_tickers.add(cfg["safe_asset"])
    for sleeve in ledger.values():
        if sleeve.get("holding"):
            all_tickers.add(sleeve["holding"])

    price_history = get_price_history(list(all_tickers))
    latest_prices = {t: float(s.iloc[-1]) for t, s in price_history.items() if len(s) > 0}

    strategic_targets = decide_all_sleeves(price_history)
    risk_state = load_all()

    target_dollars = {}
    sleeve_summaries = {}

    for sleeve_name, sleeve_cfg in SLEEVES.items():
        sleeve = ledger[sleeve_name]
        holding = sleeve.get("holding")
        prev_price = sleeve.get("holding_price")

        if holding and prev_price and holding in latest_prices:
            current_equity = sleeve["capital"] * (latest_prices[holding] / prev_price)
        else:
            current_equity = sleeve["capital"]

        can_trade, risk_mgr, _ = check_sleeve(risk_state, sleeve_name, current_equity)

        if can_trade:
            allocation = strategic_targets[sleeve_name]
            chosen = max(allocation, key=allocation.get)
            halted = False
            halt_reason = None
        else:
            chosen = sleeve_cfg["safe_asset"]
            halted = True
            halt_reason = risk_mgr.halt_reason
            log.warning(f"[{sleeve_name}] CIRCUIT BREAKER al rebalanceig mensual: {halt_reason}")

        mark_to_market_and_update(ledger, sleeve_name, chosen, latest_prices)

        target_dollars[chosen] = target_dollars.get(chosen, 0.0) + ledger[sleeve_name]["capital"]

        sleeve_summaries[sleeve_name] = {
            "label": sleeve_cfg["label"],
            "ticker": chosen,
            "ticker_label": TICKER_LABELS.get(chosen, chosen),
            "capital": ledger[sleeve_name]["capital"],
            "reason": _sleeve_reason(sleeve_cfg, chosen, halted, halt_reason),
            "halted": halted,
        }

    save_ledger(ledger)
    save_all(risk_state)

    if not PAPER_TRADING:
        log.warning("MODE LIVE ACTIU — s'executaran ordres amb diners reals.")

    rebalance_to_targets(client, target_dollars)

    total_equity_now = total_capital(ledger)
    capital_base = load_capital_base(total_equity_now)
    withdrawal = compute_suggested_withdrawal(total_equity_now, capital_base)

    # --- Historial i benchmark ---
    history = load_history()
    today = datetime.today().strftime("%Y-%m-%d")
    spy_price = latest_prices.get("SPY")
    # Si ja hi ha un rebalanceig d'avui (re-execució), el substituïm en lloc de duplicar-lo
    history = [h for h in history if h.get("date") != today]
    history.append({
        "date": today,
        "equity": total_equity_now,
        "spy_price": spy_price,
        "sleeves": {name: s["ticker"] for name, s in sleeve_summaries.items()},
    })
    save_history(history)

    first = history[0]
    total_return_pct = total_equity_now / first["equity"] - 1 if first["equity"] else 0.0
    benchmark_return_pct = (spy_price / first["spy_price"] - 1) if first.get("spy_price") and spy_price else 0.0

    any_halted = any(s["halted"] for s in sleeve_summaries.values())

    dashboard_state = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "next_run": _next_run_date(),
        "mode": "PAPER" if PAPER_TRADING else "LIVE",
        "status": "HALTED" if any_halted else "OK",
        "halt_reason": next((s["reason"] for s in sleeve_summaries.values() if s["halted"]), None),
        "account": {
            "equity": total_equity_now,
            "peak_equity": max(h["equity"] for h in history),
            "cash": max(0.0, broker_equity - total_equity_now),
            "invested": total_equity_now,
        },
        "sleeves": sleeve_summaries,
        "current_holding": next(iter(sleeve_summaries.values())),  # compatibilitat amb versió d'un sol àmbit
        "action_required": (
            {"level": "warning", "message": (
                "Un o més àmbits han activat una protecció de risc i s'han mogut a l'actiu segur. "
                "No cal que facis res ara mateix — és automàtic."
            )} if any_halted else
            {"level": "none", "message": "Cap acció necessària. El sistema ja ha ajustat la cartera sol."}
        ),
        "withdrawal": withdrawal,
        "performance": {
            "total_return_pct": total_return_pct,
            "benchmark_return_pct": benchmark_return_pct,
            "since": first["date"],
        },
        "history": history,
    }
    path = generate_dashboard(dashboard_state, output_path="dashboard.html")
    log.info(f"Dashboard actualitzat: {path}")

    lines = [f"📊 Rebalanceig mensual completat ({mode})"]
    for s in sleeve_summaries.values():
        lines.append(f"• {s['label']}: {s['ticker_label']} ({s['capital']:,.0f} $)".replace(",", "."))
    lines.append(withdrawal["message"])
    send_telegram_message("\n".join(lines))

    log.info("=== Rebalanceig completat ===")


if __name__ == "__main__":
    main()
