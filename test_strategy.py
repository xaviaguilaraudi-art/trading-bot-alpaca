"""
Test de fum amb dades sintètiques: no valida rendiment (per això cal el
backtest amb dades reals), només que la lògica no peta i es comporta
com s'espera en casos coneguts. Cobreix la lògica generalitzada a N actius,
el ledger d'àmbits i el calculador de retirades.
"""

import numpy as np
import pandas as pd

from strategy import decide_sleeve_allocation, decide_allocation, total_return
from risk_manager import RiskManager, AccountState
from sleeve_ledger import _empty_ledger, mark_to_market_and_update, total_capital, reconcile_with_broker_equity
from withdrawal import compute_suggested_withdrawal


def make_series(n_days, start_price, daily_return):
    dates = pd.date_range("2015-01-01", periods=n_days, freq="B")
    prices = start_price * (1 + daily_return) ** np.arange(n_days)
    return pd.Series(prices, index=dates)


def test_bull_market_picks_best_performer():
    us = make_series(400, 100, 0.0015)
    intl = make_series(400, 100, 0.0005)
    safe = make_series(400, 100, 0.0001)
    alloc = decide_allocation({"SPY": us, "EFA": intl, "AGG": safe})
    assert alloc["SPY"] == 1.0, alloc
    print("OK: en mercat alcista fort, tria l'actiu amb millor momentum (compatibilitat 2 actius).")


def test_bear_market_goes_defensive():
    us = make_series(400, 100, -0.0015)
    intl = make_series(400, 100, -0.0010)
    safe = make_series(400, 100, 0.0001)
    alloc = decide_allocation({"SPY": us, "EFA": intl, "AGG": safe})
    assert alloc["AGG"] == 1.0, alloc
    print("OK: en mercat baixista, es mou a l'actiu segur.")


def test_sector_rotation_with_many_assets():
    """Amb 5 sectors, hauria de triar el que té millor momentum si té tendència positiva."""
    risk_assets = {f"SECTOR_{i}": f"SEC{i}" for i in range(5)}
    price_history = {}
    for i, ticker in enumerate(risk_assets.values()):
        # el sector 3 té clarament el millor rendiment
        rate = 0.002 if ticker == "SEC3" else 0.0003 * (i + 1)
        price_history[ticker] = make_series(400, 100, rate)
    price_history["AGG"] = make_series(400, 100, 0.0001)

    alloc = decide_sleeve_allocation(risk_assets, "AGG", price_history)
    assert alloc["SEC3"] == 1.0, alloc
    print("OK: amb N actius (rotació sectorial), tria el de millor momentum.")


def test_all_sectors_negative_goes_defensive():
    risk_assets = {f"SECTOR_{i}": f"SEC{i}" for i in range(4)}
    price_history = {t: make_series(400, 100, -0.0008) for t in risk_assets.values()}
    price_history["AGG"] = make_series(400, 100, 0.0001)
    alloc = decide_sleeve_allocation(risk_assets, "AGG", price_history)
    assert alloc["AGG"] == 1.0, alloc
    print("OK: si tots els sectors tenen momentum negatiu, va a l'actiu segur.")


def test_insufficient_history_raises():
    short_series = make_series(10, 100, 0.001)
    try:
        total_return(short_series, 12)
        raise AssertionError("Hauria d'haver fallat per manca d'història")
    except ValueError:
        print("OK: detecta correctament manca d'història i no calcula un valor fals.")


def test_risk_manager_halts_on_drawdown():
    rm = RiskManager()
    state = AccountState(equity_now=75_000, equity_yesterday=76_000, equity_peak=100_000)
    can_trade = rm.check(state)
    assert can_trade is False
    assert rm.halted is True
    print("OK: circuit breaker de drawdown (>20%) atura l'operativa:", rm.halt_reason)


def test_risk_manager_allows_normal_conditions():
    rm = RiskManager()
    state = AccountState(equity_now=101_000, equity_yesterday=100_500, equity_peak=101_500)
    can_trade = rm.check(state)
    assert can_trade is True
    assert rm.halted is False
    print("OK: en condicions normals, el bot pot operar amb normalitat.")


def test_sleeve_ledger_mark_to_market():
    ledger = _empty_ledger(9000.0)  # 3000 per àmbit
    assert abs(total_capital(ledger) - 9000.0) < 0.01

    ledger["core"]["holding"] = "SPY"
    ledger["core"]["holding_price"] = 100.0
    mark_to_market_and_update(ledger, "core", "SPY", {"SPY": 110.0})  # +10%
    assert abs(ledger["core"]["capital"] - 3300.0) < 0.5
    print("OK: el ledger marca a mercat correctament un guany del 10%.")


def test_sleeve_ledger_reconcile_with_deposit():
    ledger = _empty_ledger(9000.0)
    ledger = reconcile_with_broker_equity(ledger, 9900.0)  # dipòsit extern de 900
    assert abs(total_capital(ledger) - 9900.0) < 0.01
    print("OK: el ledger es reconcilia amb un dipòsit extern sense inventar-se guanys.")


def test_withdrawal_no_surplus():
    result = compute_suggested_withdrawal(equity_now=10_000, capital_base=10_000)
    assert result["amount"] == 0.0
    print("OK: sense superàvit per sobre del marge, no suggereix cap retirada.")


def test_withdrawal_with_surplus():
    # marge 10% -> llindar 11.000; per sobre: 1.000 de superàvit; 40% -> 400
    result = compute_suggested_withdrawal(equity_now=12_000, capital_base=10_000)
    assert abs(result["amount"] - 400.0) < 0.01, result
    print("OK: amb superàvit real, suggereix retirar el percentatge configurat.")


if __name__ == "__main__":
    test_bull_market_picks_best_performer()
    test_bear_market_goes_defensive()
    test_sector_rotation_with_many_assets()
    test_all_sectors_negative_goes_defensive()
    test_insufficient_history_raises()
    test_risk_manager_halts_on_drawdown()
    test_risk_manager_allows_normal_conditions()
    test_sleeve_ledger_mark_to_market()
    test_sleeve_ledger_reconcile_with_deposit()
    test_withdrawal_no_surplus()
    test_withdrawal_with_surplus()
    print("\nTots els tests passen.")
