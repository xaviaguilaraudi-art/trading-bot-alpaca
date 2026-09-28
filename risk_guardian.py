"""
Vigilant de risc — independent del rebalanceig mensual.

Pensat per córrer cada hora, només en horari de mercat (ho gestiona el
workflow de GitHub Actions, no aquest script). NOMÉS vigila risc: no
recalcula momentum ni fa rotacions estratègiques — això segueix sent
cosa del rebalanceig mensual (live_bot.py). Aquest script:

1. Mira l'equity de cada àmbit (marcat a mercat amb el preu actual).
2. Si un àmbit supera els llindars de pèrdua diària o drawdown, el mou
   IMMEDIATAMENT a l'actiu segur i t'avisa per Telegram.
3. Si tot va bé, no fa res (i no molesta amb avisos cada hora).

Requereix les mateixes variables d'entorn que live_bot.py:
    ALPACA_API_KEY, ALPACA_SECRET_KEY
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (opcionals, però recomanats)
"""

import json
import os
import sys
import logging
from datetime import datetime

from config import SLEEVES, PAPER_TRADING
from sleeve_ledger import load_ledger, save_ledger, mark_to_market_and_update, total_capital
from risk_state import load_all, save_all, check_sleeve
from telegram_alerts import send_telegram_message
from dashboard import generate_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("risk_guardian.log"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("risk_guardian")


def get_alpaca_client():
    from alpaca.trading.client import TradingClient
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("Falten ALPACA_API_KEY / ALPACA_SECRET_KEY.")
    return TradingClient(api_key, secret_key, paper=PAPER_TRADING)


def get_latest_prices(tickers):
    """Preu més recent de cada ticker, via les dades de mercat d'Alpaca (ràpid, sense yfinance)."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    client = StockHistoricalDataClient(api_key, secret_key)
    req = StockLatestTradeRequest(symbol_or_symbols=list(set(tickers)))
    trades = client.get_stock_latest_trade(req)
    return {t: float(trades[t].price) for t in trades}


def close_sleeve_position(client, ticker):
    try:
        client.close_position(ticker)
        log.info(f"Posició tancada per protecció de risc: {ticker}")
    except Exception as e:
        log.warning(f"No s'ha pogut tancar {ticker} (potser ja no hi ha posició): {e}")


def main():
    client = get_alpaca_client()
    account = client.get_account()
    broker_equity = float(account.equity)

    ledger = load_ledger(broker_equity)
    risk_state = load_all()

    all_tickers = set()
    for cfg in SLEEVES.values():
        all_tickers.update(cfg["risk_assets"].values())
        all_tickers.add(cfg["safe_asset"])
    for sleeve in ledger.values():
        if sleeve.get("holding"):
            all_tickers.add(sleeve["holding"])

    try:
        prices = get_latest_prices(list(all_tickers))
    except Exception as e:
        log.error(f"No s'han pogut obtenir preus: {e}. Es cancel·la aquesta comprovació.")
        return

    for sleeve_name, sleeve_cfg in SLEEVES.items():
        sleeve = ledger[sleeve_name]
        holding = sleeve.get("holding")
        if not holding or holding not in prices:
            continue  # encara no ha fet cap rebalanceig mensual

        prev_price = sleeve.get("holding_price")
        current_equity = sleeve["capital"] * (prices[holding] / prev_price) if prev_price else sleeve["capital"]

        can_trade, risk_mgr, just_recovered = check_sleeve(risk_state, sleeve_name, current_equity)

        if not can_trade:
            already_in_safe = holding == sleeve_cfg["safe_asset"]
            sleeve["capital"] = current_equity
            if not already_in_safe:
                log.warning(f"[{sleeve_name}] CIRCUIT BREAKER: {risk_mgr.halt_reason}")
                close_sleeve_position(client, holding)
                mark_to_market_and_update(ledger, sleeve_name, sleeve_cfg["safe_asset"], prices)
                send_telegram_message(
                    f"⚠️ Protecció de risc activada a l'àmbit '{sleeve_cfg['label']}'.\n"
                    f"{risk_mgr.halt_reason}\n"
                    "S'ha mogut aquesta part de la cartera a l'actiu segur. "
                    "No cal que facis res ara mateix."
                )
            # si ja estava en l'actiu segur, no cal repetir l'avís cada hora
        else:
            sleeve["capital"] = current_equity
            if just_recovered:
                send_telegram_message(
                    f"✅ L'àmbit '{sleeve_cfg['label']}' ha recuperat marge de seguretat. "
                    "Tornarà a operar amb normalitat en el proper rebalanceig mensual."
                )

    save_ledger(ledger)
    save_all(risk_state)

    _update_dashboard(ledger, prices, broker_equity)
    log.info("Comprovació de risc completada.")


def _update_dashboard(ledger: dict, prices: dict, broker_equity: float = None):
    history_file = "rebalance_history.json"
    state_file = "dashboard_state.json"

    if not os.path.exists(state_file):
        return  # encara no hi ha cap rebalanceig mensual fet, res a actualitzar

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_equity = total_capital(ledger)
    spy_price = prices.get("SPY")
    current_sleeves = {name: ledger[name].get("holding", "") for name in SLEEVES}

    # Actualitza rebalance_history.json
    if os.path.exists(history_file):
        with open(history_file) as f:
            history = json.load(f)
    else:
        history = []
    history.append({"date": now_str, "equity": total_equity, "spy_price": spy_price, "sleeves": current_sleeves})
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)

    # Actualitza dashboard_state.json i regenera dashboard.html
    with open(state_file) as f:
        state = json.load(f)

    state["last_updated"] = now_str
    state["history"] = history
    # equity = valor real del compte a Alpaca (invertit + efectiu)
    real_equity = broker_equity if broker_equity is not None else total_equity
    state["account"]["equity"] = real_equity
    state["account"]["invested"] = total_equity
    state["account"]["cash"] = max(0.0, real_equity - total_equity)
    state["account"]["peak_equity"] = max(h["equity"] for h in history)

    first = history[0]
    state["performance"]["total_return_pct"] = (
        total_equity / first["equity"] - 1 if first["equity"] else 0.0
    )
    if spy_price and first.get("spy_price"):
        state["performance"]["benchmark_return_pct"] = spy_price / first["spy_price"] - 1

    generate_dashboard(state, output_path="dashboard.html")


if __name__ == "__main__":
    main()
