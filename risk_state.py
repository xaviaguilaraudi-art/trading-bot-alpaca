"""
Estat de risc compartit entre live_bot.py (mensual) i risk_guardian.py
(horari), perquè tots dos avaluïn els llindars de risc exactament amb la
mateixa lògica i el mateix historial de "pic" (equity_peak) per àmbit.
"""

import json
import os
from datetime import date

from risk_manager import RiskManager, AccountState

STATE_FILE = "risk_guardian_state.json"


def load_all() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_all(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_sleeve(state: dict, sleeve_name: str, current_equity: float):
    """
    Actualitza l'estat de risc d'un àmbit i retorna (can_trade, risk_mgr, just_recovered).
    `just_recovered` és cert si abans estava aturat i ara ja no cal.
    """
    today_str = date.today().isoformat()
    s = state.get(sleeve_name, {
        "equity_peak": current_equity,
        "day_start_equity": current_equity,
        "day_start_date": today_str,
        "halted": False,
    })

    if s["day_start_date"] != today_str:
        s["day_start_equity"] = current_equity
        s["day_start_date"] = today_str

    s["equity_peak"] = max(s["equity_peak"], current_equity)

    risk_mgr = RiskManager()
    account_state = AccountState(
        equity_now=current_equity,
        equity_yesterday=s["day_start_equity"],
        equity_peak=s["equity_peak"],
    )
    can_trade = risk_mgr.check(account_state)

    just_recovered = can_trade and s["halted"]
    s["halted"] = not can_trade

    state[sleeve_name] = s
    return can_trade, risk_mgr, just_recovered
