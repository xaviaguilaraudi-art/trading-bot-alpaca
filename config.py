"""
Configuració central de l'estratègia i del bot.
Edita només aquest fitxer per ajustar paràmetres — la resta del codi el llegeix d'aquí.
"""

# --- Els 3 àmbits independents ---
# Cada àmbit rota entre els seus propis actius de risc i, si no hi ha
# tendència favorable, es refugia en SAFE_ASSET. Els tres es tracten com a
# "carteres" independents (cadascuna amb el seu propi tallafoc de risc), tot
# i que operen dins del mateix compte d'Alpaca — el repartiment de capital
# entre àmbits el porta el propi bot (veure sleeve_ledger.py).
#
# La idea de tenir-ne 3 és diversificar per FONT de risc, no només per actiu:
# si un àmbit passa un mal moment, els altres dos no necessàriament el
# pateixen alhora, i el conjunt hauria de ser més estable que qualsevol dels
# tres per separat.
SLEEVES = {
    "core": {
        "label": "Accions globals vs bons",
        "risk_assets": {
            "US_EQUITY": "SPY",   # S&P 500 (grans empreses USA)
            "INTL_EQUITY": "EFA",  # Grans empreses internacionals
        },
        "safe_asset": "AGG",
        "weight": 1 / 3,
    },
    "sectors": {
        "label": "Rotació de sectors del S&P 500",
        "risk_assets": {
            "TECNOLOGIA": "XLK",
            "FINANCES": "XLF",
            "ENERGIA": "XLE",
            "SALUT": "XLV",
            "CONSUM_DISCRECIONAL": "XLY",
            "CONSUM_BASIC": "XLP",
            "INDUSTRIA": "XLI",
            "MATERIALS": "XLB",
            "SERVEIS_PUBLICS": "XLU",
            "IMMOBILIARI": "XLRE",
            "COMUNICACIONS": "XLC",
        },
        "safe_asset": "AGG",
        "weight": 1 / 3,
    },
    "real_assets": {
        "label": "Or i matèries primeres",
        "risk_assets": {
            "OR": "GLD",
            "MATERIES_PRIMERES": "DBC",
        },
        "safe_asset": "AGG",
        "weight": 1 / 3,
    },
}

CASH_PROXY = "BIL"  # Lletres del tresor a curt termini (equivalent a cash)

# Etiquetes en llenguatge planer per al dashboard (no tothom sap què és "EFA")
TICKER_LABELS = {
    "SPY": "Accions de grans empreses dels EUA (S&P 500)",
    "EFA": "Accions de grans empreses internacionals",
    "AGG": "Bons (actiu refugi, baix risc)",
    "BIL": "Equivalent a efectiu (lletres del tresor)",
    "XLK": "Sector tecnològic",
    "XLF": "Sector financer",
    "XLE": "Sector energètic",
    "XLV": "Sector salut",
    "XLY": "Sector consum discrecional",
    "XLP": "Sector consum bàsic",
    "XLI": "Sector industrial",
    "XLB": "Sector materials",
    "XLU": "Sector serveis públics",
    "XLRE": "Sector immobiliari",
    "XLC": "Sector comunicacions",
    "GLD": "Or",
    "DBC": "Cistella de matèries primeres",
}

# --- Paràmetres de l'estratègia (comuns als 3 àmbits) ---
LOOKBACK_MONTHS = 12          # Momentum a 12 mesos (estàndard acadèmic)
TREND_FILTER_SMA_DAYS = 200   # Filtre de tendència addicional (Meb Faber)
REBALANCE_FREQUENCY = "monthly"  # Rebalanceig mensual (baixa rotació = menys costos/impostos)

# --- Gestió de risc (CRÍTIC — no desactivar) ---
MAX_POSITION_PCT = 1.0          # % màxim d'un àmbit en un sol actiu (ja diversificat via ETF)
MAX_DAILY_LOSS_PCT = 0.05       # Si un àmbit cau >5% en un dia -> aturada automàtica d'aquell àmbit
MAX_DRAWDOWN_PCT = 0.20         # Si el drawdown d'un àmbit supera 20% -> liquidar a cash i aturar
STOP_LOSS_PCT = 0.15            # Stop-loss dur per posició (seguretat addicional)

# --- Vigilant de risc horari ---
RISK_GUARDIAN_INTERVAL = "hourly_market_hours"  # informatiu; l'horari real el fixa el workflow

# --- Retirades suggerides (perfil "equilibrat") ---
# El bot MAI suggereix tocar el capital aportat. Només suggereix retirar una
# part del guany acumulat per sobre d'un marge de seguretat.
WITHDRAWAL_BUFFER_PCT = 0.10     # cal anar un 10% per sobre del capital aportat abans de suggerir res
WITHDRAWAL_FRACTION = 0.40       # del que superi aquest marge, se'n suggereix retirar un 40%

# --- Mode d'execució ---
# IMPORTANT: comença SEMPRE en PAPER = True. Només canvia a False quan hagis
# validat el bot en paper trading durant setmanes i n'entenguis el comportament.
PAPER_TRADING = True

# --- Alpaca API ---
# No posis mai les claus reals aquí. Usa variables d'entorn:
#   export ALPACA_API_KEY="..."
#   export ALPACA_SECRET_KEY="..."
ALPACA_BASE_URL_PAPER = "https://paper-api.alpaca.markets"
ALPACA_BASE_URL_LIVE = "https://api.alpaca.markets"

# --- Telegram (avisos push) ---
# No posis mai el token aquí. Usa variables d'entorn:
#   export TELEGRAM_BOT_TOKEN="..."
#   export TELEGRAM_CHAT_ID="..."
TELEGRAM_ENABLED = True
