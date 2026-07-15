# Bot de trading sistemàtic — 3 àmbits + vigilància horària

## Abans de res: què és això i què NO és

Això és un sistema d'inversió sistemàtica basat en regles, no un
"generador d'ingressos segur". No existeix cap estratègia de trading que
sigui alhora segura i garanteixi ingressos. Tot capital invertit pot
perdre's, parcial o totalment. El que sí es pot fer és construir un
sistema disciplinat, basat en evidència acadèmica, amb gestió de risc
explícita i vigilància contínua.

Jo (Claude) no puc executar ordres reals ni moure diners per tu. Aquest
codi el fas córrer tu (o GitHub Actions en el teu nom), amb les teves
pròpies claus API, sota el teu control.

## Arquitectura: 3 àmbits independents

En lloc d'una sola estratègia, el capital es reparteix (per defecte a
parts iguals) entre 3 "àmbits" que operen de manera independent, cadascun
amb el seu propi tallafoc de risc. La idea és que si un àmbit té un mal
moment, els altres dos no necessàriament el pateixen alhora:

1. **Accions globals vs bons** (`core`): rota entre accions USA (SPY),
   accions internacionals (EFA) i bons (AGG) segons el momentum a 12
   mesos — l'estratègia original (dual momentum / GEM).
2. **Rotació de sectors del S&P 500** (`sectors`): tria el sector amb
   millor momentum d'entre 11 (tecnologia, finances, energia, salut...)
   o es refugia en bons si cap té tendència positiva.
3. **Or i matèries primeres** (`real_assets`): rota entre or (GLD) i una
   cistella de matèries primeres (DBC), històricament amb correlació
   baixa amb la borsa — precisament quan més falta fa la diversificació.

Cada àmbit opera amb ETFs diversificats (cistelles de centenars
d'empreses o actius), mai amb una sola acció — redueix dràsticament el
risc idiosincràtic. Tècnicament, els 3 àmbits comparteixen un sol compte
d'Alpaca; el propi bot porta un "llibre comptable" intern
(`sleeve_ledger.json`) per saber quant capital pertany a cadascun.

### Evidència (resultats publicats, no simulats per mi)

- **Meb Faber, GTAA** (filtre SMA200 sobre 5 classes d'actius, 1986-2026):
  CAGR 7.6%, Sharpe 1.19, **max drawdown -16.8%**.
- **Gary Antonacci, Dual Momentum / GEM** (des de 1974): retorns similars
  o superiors al S&P 500 amb **menys de la meitat del drawdown màxim**.

Aquests números són d'estudis de tercers (fonts més avall) sobre
l'estratègia base (àmbit 1), no un backtest que hagi executat jo en
aquesta sessió — l'entorn sandbox no té accés lliure a internet. El codi
de `backtest.py` calcula el resultat conjunt real dels 3 àmbits;
**executa'l al teu ordinador** per veure xifres concretes.

**Sobre "corba sempre ascendent":** no és realista ni per a aquest ni per
a cap sistema seriós. Hi haurà mesos i trimestres negatius. Un rang
raonable a llarg termini, basant-nos en l'evidència anterior, és
**5-10% anual de mitjana**, amb anys per sobre i per sota.

## Vigilància en dos nivells

- **Rebalanceig mensual** (`live_bot.py`): recalcula el momentum i decideix
  l'assignació estratègica de cada àmbit. Baixa rotació, és l'estratègia
  de fons.
- **Vigilant de risc horari** (`risk_guardian.py`): NOMÉS vigila risc
  (pèrdua diària, drawdown), en horari de mercat. Si un àmbit supera els
  límits, el mou a l'actiu segur immediatament i t'avisa per Telegram,
  sense esperar al proper mes.

## Avisos push (Telegram)

Tant el rebalanceig mensual com el vigilant horari envien un missatge de
Telegram quan hi ha un canvi rellevant o es activa una protecció. No
necessites cap altra app — el dashboard web (veure més avall) el pots
obrir des del navegador del mòbil.

## Retirades suggerides (ingressos extra)

Cada mes, el dashboard i l'avís de Telegram inclouen una **retirada
suggerida**: mai suggereix tocar el capital que has aportat, només una
part del guany acumulat per sobre d'un marge de seguretat (perfil
"equilibrat": marge del 10%, se'n suggereix retirar el 40% de l'excés).
Alguns mesos la xifra serà 0 — és normal i correcte, no un error.

Quan ingressis o retiris diners **directament des d'Alpaca** (no a través
del bot), executa:

```bash
python record_cash_flow.py --deposit 500
python record_cash_flow.py --withdrawal 300
```

perquè el bot no confongui un dipòsit teu amb un guany de l'estratègia.

## Estructura del projecte

```
trading_bot/
├── config.py                          # paràmetres — SLEEVES, risc, retirades, Telegram
├── strategy.py                         # lògica de senyal, generalitzada a N actius per àmbit
├── risk_manager.py                      # regles pures del circuit breaker
├── risk_state.py                        # estat de risc compartit (mensual + horari)
├── sleeve_ledger.py                     # llibre comptable intern dels 3 àmbits
├── withdrawal.py                        # calculador de retirada suggerida
├── record_cash_flow.py                  # registra dipòsits/retirades manuals
├── telegram_alerts.py                   # avisos push
├── live_bot.py                          # rebalanceig MENSUAL (estratègic)
├── risk_guardian.py                     # vigilància HORÀRIA (només risc)
├── dashboard.py                         # generador del dashboard.html
├── generate_demo_dashboard.py           # dashboard amb dades D'EXEMPLE
├── backtest.py                          # backtest conjunt dels 3 àmbits (executar localment)
├── test_strategy.py                     # tests de fum
├── requirements.txt
├── .gitignore
└── .github/workflows/
    ├── rebalance.yml                     # mensual
    └── risk_guardian.yml                 # horari, en horari de mercat
```

## El dashboard: què has de mirar

Cada vegada que `live_bot.py` o `risk_guardian.py` s'executen, actualitzen
`dashboard.html`. Obre'l al navegador (o des del mòbil via GitHub Pages,
veure guia de configuració) i hi trobaràs:

- **Banner d'estat**: verd si tot va amb normalitat, vermell si algun
  àmbit ha activat una protecció.
- **Què has de fer tu, ara mateix**: gairebé sempre "cap acció necessària".
- **Els 3 àmbits per separat**: què hi ha invertit i per què a cadascun.
- **Retirada suggerida** del mes.
- **Tresoreria**: efectiu vs invertit.
- **Rendiment**: valor actual, guany/pèrdua, comparació amb comprar i
  mantenir el S&P 500.
- **Gràfic i historial** dels últims rebalancejos.

### Previsualitzar-lo abans de connectar res

```bash
python generate_demo_dashboard.py
```

## Cost: 0 € — sempre

- **Alpaca**: gratuït, sense dipòsit mínim, tant en paper com en real.
- **GitHub Actions**: gratuït per a aquest volum (mensual + horari en
  horari de mercat són molt per sota del pla gratuït de 2.000 minuts/mes).
- **Telegram**: gratuït i sense límit pràctic.
- **GitHub Pages** (dashboard des del mòbil): gratuït.

## Passos de configuració

Per no barrejar aquí una llista que ja estem seguint junts pas a pas al
xat, la seqüència completa (comptes previs, ampliació del codi, GitHub,
Claude Code, validació) la porto com a llista de tasques a la conversa —
consulta-la allà per veure exactament on som.

## Pas a diners reals (només si ho decideixes tu explícitament)

1. Canvia `PAPER_TRADING = False` a `config.py`.
2. Genera claus API noves des de la secció "Live" (no "Paper") d'Alpaca.
3. Comença amb capital que et puguis permetre perdre completament.
4. Revisa els llindars de risc a `config.py` abans de fer-ho.

## Sobre les captures que em vas enviar

Semblaven un anunci de "hobbiecode" (miniserie gratuïta que condueix a una
acadèmia de pagament) i una plataforma amb apalancament sobre MetaTrader 5
— molt més arriscada que el que hem construït aquí. Qualsevol promesa de
"guanyar de forma consistent" amb robots hauria d'aixecar sospites; aquest
sistema fa essencialment el mateix (automatització basada en regles) de
forma gratuïta i transparent.

## Límits importants

- No hi ha garantia de rendiment futur basat en resultats passats.
- El bot no gestiona fiscalitat — consulta un assessor fiscal.
- No sóc assessor financer; això és informació educativa i codi
  funcional, no una recomanació d'inversió personalitzada.
- El repartiment intern de capital entre àmbits (`sleeve_ledger.json`) és
  una aproximació comptable del propi bot, no una funcionalitat oficial
  d'Alpaca — es reconcilia automàticament amb l'equity real del compte a
  cada execució.

## Fonts

- Faber, M. — [A Quantitative Approach to Tactical Asset Allocation](https://www.trendfollowing.com/whitepaper/CMT-Simple.pdf)
- [GTAA Strategy backtest](https://bestfolio.app/strategies/gtaa)
- Antonacci, G. — [Extended Backtest of Global Equities Momentum](https://medium.com/@garyantonacci_30463/extended-backtest-of-global-equities-momentum-dual-momentum-eb12902612e0)
- [Dual Momentum Investing: A Quant's Review](https://robotwealth.com/dual-momentum-review/)
- [Alpaca — Paper Trading docs](https://docs.alpaca.markets/us/docs/paper-trading)
