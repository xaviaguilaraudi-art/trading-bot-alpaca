"""
Genera un dashboard.html amb dades D'EXEMPLE (no reals), perquè puguis veure
l'aspecte i el funcionament dels 3 àmbits abans de tenir el bot connectat
a Alpaca.

Executa:
    python generate_demo_dashboard.py

Obre el dashboard_demo.html resultant al navegador.
"""

from datetime import datetime, timedelta
from dashboard import generate_dashboard
from withdrawal import _fmt_money

start_date = datetime(2026, 2, 1)
months = 6

sleeve_paths = {
    "core": {"label": "Accions globals vs bons", "tickers": ["SPY", "SPY", "AGG", "SPY", "SPY", "SPY"],
             "growth": [0.018, 0.024, -0.004, 0.031, 0.012, 0.020]},
    "sectors": {"label": "Rotació de sectors del S&P 500", "tickers": ["XLK", "XLK", "XLE", "XLE", "XLV", "XLK"],
                "growth": [0.022, 0.015, 0.009, -0.011, 0.014, 0.026]},
    "real_assets": {"label": "Or i matèries primeres", "tickers": ["GLD", "GLD", "GLD", "DBC", "GLD", "GLD"],
                    "growth": [0.006, 0.010, 0.021, -0.005, 0.008, 0.013]},
}

ticker_labels = {
    "SPY": "Accions de grans empreses dels EUA (S&P 500)",
    "AGG": "Bons (actiu refugi, baix risc)",
    "XLK": "Sector tecnològic",
    "XLE": "Sector energètic",
    "XLV": "Sector salut",
    "GLD": "Or",
    "DBC": "Cistella de matèries primeres",
}

initial_per_sleeve = 10_000 / 3
sleeve_capital = {name: initial_per_sleeve for name in sleeve_paths}
history = []
spy_price = 450.0

for i in range(months):
    date = start_date + timedelta(days=30 * i)
    for name, path in sleeve_paths.items():
        sleeve_capital[name] *= (1 + path["growth"][i])
    spy_price *= (1 + path["growth"][i] * 0.9)  # variació independent per al benchmark
    history.append({
        "date": date.strftime("%Y-%m-%d"),
        "equity": sum(sleeve_capital.values()),
        "spy_price": round(spy_price, 2),
        "sleeves": {name: path["tickers"][i] for name, path in sleeve_paths.items()},
    })

total_equity = sum(sleeve_capital.values())
first_equity = 10_000.0
first_spy = 450.0
total_return_pct = total_equity / first_equity - 1
benchmark_return_pct = spy_price / first_spy - 1

capital_base = 10_000.0
threshold = capital_base * 1.10
surplus = max(total_equity - threshold, 0)
suggested = surplus * 0.40

sleeve_summaries = {}
for name, path in sleeve_paths.items():
    chosen = path["tickers"][-1]
    sleeve_summaries[name] = {
        "label": path["label"],
        "ticker": chosen,
        "ticker_label": ticker_labels.get(chosen, chosen),
        "capital": sleeve_capital[name],
        "reason": (
            f"{ticker_labels.get(chosen, chosen)} ha tingut el millor rendiment recent "
            "d'entre les opcions d'aquest àmbit, amb una tendència a l'alça."
        ),
        "halted": False,
    }

demo_state = {
    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M") + " (DEMO — dades fictícies)",
    "next_run": (start_date + timedelta(days=30 * months)).strftime("%Y-%m-%d"),
    "mode": "PAPER",
    "status": "OK",
    "halt_reason": None,
    "account": {
        "equity": total_equity,
        "peak_equity": max(h["equity"] for h in history),
        "cash": 0.0,
        "invested": total_equity,
    },
    "sleeves": sleeve_summaries,
    "withdrawal": {
        "amount": suggested,
        "threshold": threshold,
        "message": (
            f"Aquest mes pots retirar fins a {_fmt_money(suggested)} si vols, mantenint el coixí "
            "de seguretat i deixant la resta invertit. No és obligatori: com més hi deixis, "
            "més marge de creixement mantens."
        ),
    },
    "action_required": {
        "level": "none",
        "message": (
            "Cap acció necessària. El sistema ja ha ajustat la cartera sol. "
            "Torna a obrir aquest dashboard després de la pròxima revisió."
        ),
    },
    "performance": {
        "total_return_pct": total_return_pct,
        "benchmark_return_pct": benchmark_return_pct,
        "since": history[0]["date"],
    },
    "history": history,
}

if __name__ == "__main__":
    path = generate_dashboard(demo_state, output_path="dashboard_demo.html")
    print(f"Dashboard de demostració generat a: {path}")
    print("Obre'l al navegador per veure com serà quan el bot estigui en marxa.")
