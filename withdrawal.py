"""
Calculador de "retirada suggerida" mensual (perfil equilibrat).

Principi: el bot MAI suggereix retirar per sota del capital que hi has
aportat net (dipòsits - retirades anteriors). Només suggereix moure't a
efectiu una part del guany acumulat per sobre d'un marge de seguretat.

capital_base = el que consideres "teu diner aportat", es guarda a
capital_ledger.json i només canvia quan tu (o el bot, en detectar un
dipòsit/retirada real) l'actualitzeu — mai automàticament per l'evolució
del mercat.

Fes servir record_cash_flow.py cada vegada que ingressis o retiris diners
directament des d'Alpaca, perquè aquest número es mantingui correcte.
"""

import json
import os

from config import WITHDRAWAL_BUFFER_PCT, WITHDRAWAL_FRACTION

CAPITAL_LEDGER_FILE = "capital_ledger.json"


def _fmt_money(x: float) -> str:
    """Format només del número (mai de la resta de la frase, per no trencar la puntuació)."""
    return f"{x:,.2f} $".replace(",", "@").replace(".", ",").replace("@", ".")


def load_capital_base(default_equity: float) -> float:
    if os.path.exists(CAPITAL_LEDGER_FILE):
        with open(CAPITAL_LEDGER_FILE) as f:
            data = json.load(f)
        return data["capital_base"]
    # Primer cop que s'executa: el capital aportat és l'equity actual
    save_capital_base(default_equity)
    return default_equity


def save_capital_base(capital_base: float):
    with open(CAPITAL_LEDGER_FILE, "w") as f:
        json.dump({"capital_base": capital_base}, f, indent=2)


def adjust_capital_base(delta: float) -> float:
    """delta positiu = dipòsit, delta negatiu = retirada."""
    current = load_capital_base(default_equity=0.0)
    new_base = current + delta
    save_capital_base(new_base)
    return new_base


def compute_suggested_withdrawal(equity_now: float, capital_base: float) -> dict:
    """
    Retorna un dict amb:
      - amount: import suggerit de retirada (0 si no en toca cap)
      - threshold: equity a partir de la qual es comença a suggerir res
      - message: explicació en llenguatge planer
    """
    threshold = capital_base * (1 + WITHDRAWAL_BUFFER_PCT)

    if equity_now <= threshold:
        falta = threshold - equity_now
        return {
            "amount": 0.0,
            "threshold": threshold,
            "message": (
                "Aquest mes no hi ha marge per retirar res. El compte encara no supera "
                f"el coixí de seguretat (li falten {_fmt_money(falta)} per arribar-hi). "
                "Deixa-ho créixer sense tocar-ho."
            ),
        }

    surplus = equity_now - threshold
    suggested = surplus * WITHDRAWAL_FRACTION
    return {
        "amount": suggested,
        "threshold": threshold,
        "message": (
            f"Aquest mes pots retirar fins a {_fmt_money(suggested)} si vols, mantenint el coixí "
            "de seguretat i deixant la resta invertit. No és obligatori: com més hi deixis, "
            "més marge de creixement mantens."
        ),
    }
