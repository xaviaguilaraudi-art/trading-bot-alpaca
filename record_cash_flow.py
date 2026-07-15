"""
Executa aquest script cada vegada que ingressis o retiris diners
DIRECTAMENT des d'Alpaca (transferència bancària), perquè el bot sàpiga
quin és el teu capital aportat real i no confongui un dipòsit amb un guany.

Ús:
    python record_cash_flow.py --deposit 500
    python record_cash_flow.py --withdrawal 300
"""

import argparse
from withdrawal import adjust_capital_base

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deposit", type=float, help="Import ingressat")
    group.add_argument("--withdrawal", type=float, help="Import retirat")
    args = parser.parse_args()

    if args.deposit is not None:
        new_base = adjust_capital_base(args.deposit)
        print(f"Dipòsit registrat: +{args.deposit:.2f}. Nou capital base: {new_base:.2f}")
    else:
        new_base = adjust_capital_base(-args.withdrawal)
        print(f"Retirada registrada: -{args.withdrawal:.2f}. Nou capital base: {new_base:.2f}")
