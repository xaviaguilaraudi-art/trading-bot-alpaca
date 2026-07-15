"""
Circuit breakers i gestió de risc.

Aquest mòdul és el que converteix un simple bot de senyals en un sistema
"segur per defecte": qualsevol condició anòmala atura l'operativa i mou
la cartera a l'actiu segur, en lloc de seguir operant sense supervisió.
"""

from dataclasses import dataclass
from config import MAX_DAILY_LOSS_PCT, MAX_DRAWDOWN_PCT


@dataclass
class AccountState:
    equity_now: float
    equity_yesterday: float
    equity_peak: float  # màxim històric del compte (per calcular drawdown)


class RiskManager:
    def __init__(self):
        self.halted = False
        self.halt_reason = None

    def check(self, state: AccountState) -> bool:
        """
        Retorna True si es pot operar amb normalitat.
        Retorna False (i marca `halted`) si s'ha de forçar posició defensiva.
        """
        if state.equity_yesterday <= 0 or state.equity_peak <= 0:
            return True  # dades insuficients, no bloquejar en el primer dia

        daily_loss = (state.equity_yesterday - state.equity_now) / state.equity_yesterday
        drawdown = (state.equity_peak - state.equity_now) / state.equity_peak

        if daily_loss > MAX_DAILY_LOSS_PCT:
            self.halted = True
            self.halt_reason = (
                f"Pèrdua diària de {daily_loss:.1%} supera el límit de "
                f"{MAX_DAILY_LOSS_PCT:.1%}. Aturant operativa."
            )
            return False

        if drawdown > MAX_DRAWDOWN_PCT:
            self.halted = True
            self.halt_reason = (
                f"Drawdown de {drawdown:.1%} supera el límit de "
                f"{MAX_DRAWDOWN_PCT:.1%}. Aturant operativa i movent a l'actiu segur d'aquest àmbit."
            )
            return False

        self.halted = False
        self.halt_reason = None
        return True
