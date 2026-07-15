"""
Llibre comptable intern per repartir el capital d'UN sol compte d'Alpaca
entre els 3 àmbits independents.

Alpaca no té "sub-comptes"; per poder tractar cada àmbit com si tingués el
seu propi capital i el seu propi tallafoc de risc, el propi bot porta el
compte de quant capital "pertany" a cada àmbit i com evoluciona (marcant-lo
a mercat amb el preu de l'actiu que té cada àmbit en cada moment). Les
ordres reals que s'envien a Alpaca sumen el que vol cada àmbit per a cada
ticker — de cara al broker és una sola cartera.

Fitxer persistit: sleeve_ledger.json
"""

import json
import os

from config import SLEEVES

LEDGER_FILE = "sleeve_ledger.json"


def _empty_ledger(total_equity: float) -> dict:
    ledger = {}
    for name, cfg in SLEEVES.items():
        ledger[name] = {
            "capital": total_equity * cfg["weight"],
            "holding": None,
            "holding_price": None,
        }
    return ledger


def load_ledger(total_equity: float) -> dict:
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE) as f:
            ledger = json.load(f)
        # si s'han afegit àmbits nous a config.py que no existien al fitxer
        for name, cfg in SLEEVES.items():
            if name not in ledger:
                ledger[name] = {
                    "capital": total_equity * cfg["weight"],
                    "holding": None,
                    "holding_price": None,
                }
        return ledger
    return _empty_ledger(total_equity)


def save_ledger(ledger: dict):
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)


def mark_to_market_and_update(ledger: dict, sleeve_name: str, new_holding: str, current_prices: dict) -> dict:
    """
    Actualitza el capital d'un àmbit aplicant el retorn de la posició que
    tenia fins ara (si en tenia), i deixa registrada la nova posició.
    `current_prices`: dict {ticker: preu actual} amb, com a mínim, el
    ticker de la posició anterior i el de la nova.
    """
    sleeve = ledger[sleeve_name]
    prev_holding = sleeve.get("holding")
    prev_price = sleeve.get("holding_price")

    if prev_holding and prev_price and prev_holding in current_prices:
        ret = current_prices[prev_holding] / prev_price - 1.0
        sleeve["capital"] = sleeve["capital"] * (1 + ret)

    sleeve["holding"] = new_holding
    sleeve["holding_price"] = current_prices.get(new_holding)
    return sleeve


def total_capital(ledger: dict) -> float:
    return sum(s["capital"] for s in ledger.values())


def reconcile_with_broker_equity(ledger: dict, broker_equity: float):
    """
    Si hi ha hagut dipòsits/retirades des de fora (via Alpaca directament),
    el total del ledger no coincidirà amb l'equity real del broker. Es
    reparteix la diferència proporcionalment entre àmbits perquè el ledger
    torni a quadrar, sense inventar-nos guanys o pèrdues que no existeixen.
    """
    current_total = total_capital(ledger)
    if current_total <= 0:
        return _empty_ledger(broker_equity)
    factor = broker_equity / current_total
    for sleeve in ledger.values():
        sleeve["capital"] *= factor
    return ledger
