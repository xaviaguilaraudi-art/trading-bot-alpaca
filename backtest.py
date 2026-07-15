"""
Backtest CONJUNT dels 3 àmbits (core + sectors + real_assets), a pesos
iguals (1/3 cadascun), amb dades històriques reals.

IMPORTANT: aquest script necessita connexió a internet per descarregar
dades (via yfinance / Yahoo Finance). Executa'l al teu ordinador:

    pip install -r requirements.txt
    python backtest.py

No s'ha pogut executar dins d'aquest sandbox perquè no té accés lliure a
internet (només dominis concrets permesos). El codi és funcional i s'ha
validat amb dades sintètiques (veure test_strategy.py).

Nota: alguns dels ETFs sectorials/de matèries primeres tenen menys
història que SPY (per exemple XLRE i XLC van néixer el 2018). L'script
retalla automàticament l'inici del backtest a la data en què TOTS els
tickers necessaris ja tenen dades, perquè la comparació sigui justa.
"""

import pandas as pd
import numpy as np

from config import SLEEVES
from strategy import decide_sleeve_allocation

START = "2007-01-01"
END = None  # fins avui
INITIAL_CAPITAL = 10_000.0


def download_prices(tickers, start, end):
    import yfinance as yf
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    return data


def all_tickers():
    tickers = set()
    for cfg in SLEEVES.values():
        tickers.update(cfg["risk_assets"].values())
        tickers.add(cfg["safe_asset"])
    return sorted(tickers)


def run_backtest():
    tickers = all_tickers()
    prices = download_prices(tickers, START, END)

    # Retalla a partir de la data en què TOTS els tickers ja cotitzen
    prices = prices.dropna(how="any")
    if prices.empty:
        raise RuntimeError("No hi ha cap període amb dades per a tots els tickers alhora.")

    monthly_dates = prices.resample("ME").last().index

    sleeve_equity = {name: INITIAL_CAPITAL * cfg["weight"] for name, cfg in SLEEVES.items()}
    sleeve_holding = {name: None for name in SLEEVES}
    total_curve = []

    for i, date in enumerate(monthly_dates):
        history_up_to_date = prices.loc[:date]
        if len(history_up_to_date) < 260:  # cal >1 any d'història (SMA200 + marge)
            total_curve.append((date, sum(sleeve_equity.values())))
            continue

        for sleeve_name, sleeve_cfg in SLEEVES.items():
            tickers_sleeve = list(sleeve_cfg["risk_assets"].values()) + [sleeve_cfg["safe_asset"]]
            history_dict = {t: history_up_to_date[t].dropna() for t in tickers_sleeve}
            allocation = decide_sleeve_allocation(sleeve_cfg["risk_assets"], sleeve_cfg["safe_asset"], history_dict)
            chosen = max(allocation, key=allocation.get)

            prev_holding = sleeve_holding[sleeve_name]
            if prev_holding is not None and i > 0:
                prev_date = monthly_dates[i - 1]
                ret = prices[prev_holding].loc[date] / prices[prev_holding].loc[prev_date] - 1.0
                sleeve_equity[sleeve_name] *= (1 + ret)

            sleeve_holding[sleeve_name] = chosen

        total_curve.append((date, sum(sleeve_equity.values())))

    curve = pd.DataFrame(total_curve, columns=["date", "equity"]).set_index("date")
    return curve, prices


def performance_report(curve: pd.DataFrame, benchmark_prices: pd.Series):
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    cagr = (curve["equity"].iloc[-1] / curve["equity"].iloc[0]) ** (1 / years) - 1
    running_max = curve["equity"].cummax()
    drawdown = (curve["equity"] - running_max) / running_max
    max_dd = drawdown.min()

    monthly_returns = curve["equity"].pct_change().dropna()
    sharpe = monthly_returns.mean() / monthly_returns.std() * np.sqrt(12)

    bench = benchmark_prices.dropna()
    bench_years = (bench.index[-1] - bench.index[0]).days / 365.25
    bench_cagr = (bench.iloc[-1] / bench.iloc[0]) ** (1 / bench_years) - 1

    print(f"--- Resultats dels 3 àmbits combinats ({curve.index[0].date()} a {curve.index[-1].date()}) ---")
    print(f"CAGR combinat:        {cagr:.2%}")
    print(f"Max drawdown:         {max_dd:.2%}")
    print(f"Sharpe (aprox):       {sharpe:.2f}")
    print(f"CAGR buy&hold SPY:    {bench_cagr:.2%}")
    print()
    print("Nota: el punt de partida del backtest ve determinat pel ticker amb menys")
    print("història d'entre tots els que fem servir (normalment un ETF sectorial o")
    print("de matèries primeres més recent), no per SPY.")


if __name__ == "__main__":
    curve, prices = run_backtest()
    performance_report(curve, prices["SPY"])
    curve.to_csv("backtest_equity_curve.csv")
    print("\nCorba d'equity guardada a backtest_equity_curve.csv")
