"""
Lògica de senyal: Momentum (Antonacci) + filtre de tendència (Meb Faber),
generalitzada perquè cada àmbit ("sleeve") pugui tenir un nombre diferent
d'actius de risc (2 al nucli, 11 sectors, 2 en matèries primeres...).

Regla de decisió (cada rebalanceig mensual), per a un àmbit qualsevol:
1. Es calcula el momentum a 12 mesos de CADA actiu de risc de l'àmbit.
2. Es tria el que tingui millor momentum.
3. Momentum absolut: si fins i tot el millor té momentum negatiu, es
   considera que tot l'àmbit està en un mal moment i es va a l'actiu segur.
4. Filtre de tendència addicional: si el momentum és positiu però el preu
   actual és per sota de la seva mitjana mòbil de 200 dies, també es va a
   l'actiu segur (evita entrar-hi quan la tendència s'està trencant).

Amb 2 actius (el nucli original) es comporta exactament igual que abans.
Amb N actius (sectors) es converteix en una rotació sectorial estàndard.
"""

import pandas as pd
from config import SLEEVES, LOOKBACK_MONTHS, TREND_FILTER_SMA_DAYS


def total_return(prices: pd.Series, months: int) -> float:
    """Retorn total dels darrers `months` mesos (aproximat en dies de trading)."""
    trading_days = int(months * 21)
    if len(prices) <= trading_days:
        raise ValueError(
            f"No hi ha prou història ({len(prices)} dies) per calcular "
            f"un momentum de {months} mesos ({trading_days} dies)."
        )
    return prices.iloc[-1] / prices.iloc[-trading_days] - 1.0


def above_sma(prices: pd.Series, window: int) -> bool:
    """Cert si el darrer preu és per sobre de la seva mitjana mòbil de `window` dies."""
    if len(prices) < window:
        raise ValueError(f"No hi ha prou història per calcular la SMA{window}.")
    sma = prices.rolling(window).mean().iloc[-1]
    return prices.iloc[-1] > sma


def decide_sleeve_allocation(risk_assets: dict, safe_asset: str, price_history: dict) -> dict:
    """
    risk_assets: dict {nom_intern: ticker} — pot tenir 2, 11, o qualsevol N.
    safe_asset: ticker de l'actiu refugi de l'àmbit.
    price_history: dict {ticker: pandas.Series de preus, ordenats per data}.

    Retorna: dict {ticker: pes 0.0-1.0} que suma 1.0 (o buit si no hi ha
    prou història encara, en aquest cas cal tractar-ho com "no decidir").
    """
    tickers = list(risk_assets.values())
    momentums = {}
    for t in tickers:
        momentums[t] = total_return(price_history[t], LOOKBACK_MONTHS)

    best_ticker = max(momentums, key=momentums.get)
    best_momentum = momentums[best_ticker]

    allocation = {t: 0.0 for t in tickers + [safe_asset]}

    # Momentum absolut: si ni tan sols el millor actiu de l'àmbit té
    # momentum positiu, tot l'àmbit va a l'actiu segur.
    if best_momentum < 0:
        allocation[safe_asset] = 1.0
        return allocation

    # Filtre de tendència addicional sobre l'actiu escollit
    try:
        trending_up = above_sma(price_history[best_ticker], TREND_FILTER_SMA_DAYS)
    except ValueError:
        trending_up = True  # no prou història -> no bloquejar, confiar en el momentum

    if trending_up:
        allocation[best_ticker] = 1.0
    else:
        allocation[safe_asset] = 1.0

    return allocation


def decide_all_sleeves(price_history: dict) -> dict:
    """
    Calcula l'assignació objectiu per als 3 àmbits definits a config.SLEEVES.
    Retorna: dict {nom_àmbit: {ticker: pes}}
    """
    results = {}
    for sleeve_name, sleeve_cfg in SLEEVES.items():
        results[sleeve_name] = decide_sleeve_allocation(
            sleeve_cfg["risk_assets"], sleeve_cfg["safe_asset"], price_history
        )
    return results


# --- Compatibilitat amb el codi anterior (backtest.py original, tests) ---
def decide_allocation(price_history: dict) -> dict:
    """Manté el comportament antic: només l'àmbit 'core' (2 actius vs bons)."""
    core = SLEEVES["core"]
    return decide_sleeve_allocation(core["risk_assets"], core["safe_asset"], price_history)
