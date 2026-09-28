"""
Generador del dashboard (dashboard.html).

Pensat per algú que NO segueix els mercats: llenguatge planer, un missatge
clar de "què has de fer" i res que requereixi interpretar xifres tècniques.

No necessita internet ni servidor: és un sol fitxer HTML amb tot incrustat
(dades + gràfic SVG generat en Python). Fes doble clic per obrir-lo al
navegador, o deixa'l obert i refresca la pàgina després de cada execució.

`generate_dashboard(state, output_path)` és cridat automàticament per
`live_bot.py` després de cada rebalanceig. També es pot cridar manualment
(veure `generate_demo_dashboard.py` per un exemple amb dades fictícies).
"""

import json
import html as html_lib
from datetime import datetime


def _fmt_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x*100:.1f}%"


def _fmt_money(x: float) -> str:
    return f"{x:,.2f} $".replace(",", ".")


def _status_banner(state: dict) -> str:
    if state["status"] == "OK":
        return (
            '<div class="banner banner-ok">'
            '<div class="banner-icon">✓</div>'
            '<div><div class="banner-title">Tot funciona amb normalitat</div>'
            '<div class="banner-sub">El sistema opera automàticament segons les regles configurades.</div></div>'
            "</div>"
        )
    reason_text = state.get("halt_reason") or "S'ha activat un límit de seguretat."
    return (
        '<div class="banner banner-alert">'
        '<div class="banner-icon">!</div>'
        '<div><div class="banner-title">Operativa aturada automàticament</div>'
        f'<div class="banner-sub">{html_lib.escape(reason_text)}</div></div>'
        "</div>"
    )


def _action_card(state: dict) -> str:
    action = state["action_required"]
    level_class = {"none": "action-none", "info": "action-info", "warning": "action-warning"}.get(
        action["level"], "action-info"
    )
    return (
        '<div class="card">'
        '<div class="card-label">Què has de fer tu, ara mateix</div>'
        f'<div class="action {level_class}">{html_lib.escape(action["message"])}</div>'
        "</div>"
    )


def _sleeves_card(state: dict) -> str:
    sleeves = state.get("sleeves")
    if not sleeves:
        return ""
    items = []
    for s in sleeves.values():
        halted_tag = ' <span class="sleeve-halted">protegit</span>' if s.get("halted") else ""
        items.append(
            '<div class="sleeve-item">'
            f'<div class="sleeve-name">{html_lib.escape(s["label"])}{halted_tag}</div>'
            f'<div class="holding-name">{html_lib.escape(s["ticker_label"])}</div>'
            f'<div class="holding-ticker">Fons: {html_lib.escape(s["ticker"])} · '
            f'{_fmt_money(s["capital"])}</div>'
            f'<div class="holding-reason">{html_lib.escape(s["reason"])}</div>'
            "</div>"
        )
    return (
        '<div class="card">'
        '<div class="card-label">On està invertit el teu capital ara (3 àmbits)</div>'
        f'<div class="sleeves-grid">{"".join(items)}</div>'
        "</div>"
    )


def _withdrawal_card(state: dict) -> str:
    w = state.get("withdrawal")
    if not w:
        return ""
    has_amount = w.get("amount", 0) > 0
    level_class = "action-none" if has_amount else "action-info"
    return (
        '<div class="card">'
        '<div class="card-label">Retirada suggerida aquest mes</div>'
        f'<div class="action {level_class}">{html_lib.escape(w["message"])}</div>'
        "</div>"
    )


def _treasury_card(state: dict) -> str:
    acc = state["account"]
    cash = acc.get("cash")
    invested = acc.get("invested")
    if cash is None or invested is None:
        return ""
    return (
        '<div class="card">'
        '<div class="card-label">Estat de la tresoreria</div>'
        '<div class="perf-grid">'
        f'<div><div class="perf-value">{_fmt_money(acc["equity"])}</div>'
        '<div class="perf-caption">Total del compte</div></div>'
        f'<div><div class="perf-value">{_fmt_money(invested)}</div>'
        '<div class="perf-caption">Invertit ara mateix</div></div>'
        f'<div><div class="perf-value">{_fmt_money(cash)}</div>'
        '<div class="perf-caption">Efectiu disponible</div></div>'
        "</div>"
        '<div class="perf-note">Pots ingressar o retirar diners quan vulguis directament '
        "des del teu compte d'Alpaca (transferència bancària) — el bot no ho gestiona, "
        "només opera amb els diners que hi hagi en cada moment.</div>"
        "</div>"
    )


def _performance_card(state: dict) -> str:
    p = state["performance"]
    acc = state["account"]
    diff = p["total_return_pct"] - p["benchmark_return_pct"]
    diff_txt = "millor" if diff >= 0 else "pitjor"
    return (
        '<div class="card card-wide">'
        '<div class="card-label">Com va el teu capital</div>'
        '<div class="perf-grid">'
        f'<div><div class="perf-value">{_fmt_money(acc["equity"])}</div>'
        f'<div class="perf-caption">Valor actual del compte</div></div>'
        f'<div><div class="perf-value perf-{"pos" if p["total_return_pct"]>=0 else "neg"}">'
        f'{_fmt_pct(p["total_return_pct"])}</div>'
        f'<div class="perf-caption">Guany/pèrdua des de l\'inici ({html_lib.escape(p["since"])})</div></div>'
        f'<div><div class="perf-value">{_fmt_pct(p["benchmark_return_pct"])}</div>'
        f'<div class="perf-caption">Referència: comprar i mantenir S&amp;P 500</div></div>'
        "</div>"
        f'<div class="perf-note">El sistema ho ha fet <b>{abs(diff)*100:.1f} punts {diff_txt}</b> '
        "que simplement comprar i mantenir el mercat en aquest període.</div>"
        "</div>"
    )


def _equity_chart_svg(history: list) -> str:
    if len(history) < 2:
        return '<div class="chart-empty">Encara no hi ha prou historial per mostrar un gràfic.</div>'

    values = [h["equity"] for h in history]
    vmin, vmax = min(values), max(values)
    vrange = (vmax - vmin) or 1.0
    W, H, PAD, TOP_PAD = 600, 170, 10, 24

    coords = []
    n = len(values)
    for i, v in enumerate(values):
        x = PAD + (W - 2 * PAD) * (i / (n - 1))
        y = H - PAD - (H - PAD - TOP_PAD) * ((v - vmin) / vrange)
        coords.append((x, y))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    price_dots = []
    trade_markers = []
    for i, h in enumerate(history):
        sleeves_now = h.get("sleeves", {})
        sleeves_prev = history[i - 1].get("sleeves", {}) if i > 0 else {}
        is_trade = (i == 0 or sleeves_now != sleeves_prev)
        x, y = coords[i]
        detail = ", ".join(f"{k}: {v}" for k, v in sleeves_now.items()) or str(h.get("holding", ""))
        label = html_lib.escape(f"{h['date']}: {detail}")
        if is_trade:
            trade_markers.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2563eb" stroke="white" stroke-width="1.5">'
                f"<title>{label}</title></circle>"
            )
        else:
            price_dots.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="#d1d5db">'
                f"<title>{label}</title></circle>"
            )

    first_date = history[0]["date"]
    last_date = history[-1]["date"]

    legend = (
        '<div class="chart-legend">'
        '<svg width="10" height="10" viewBox="0 0 10 10" style="vertical-align:middle;margin-right:4px">'
        '<circle cx="5" cy="5" r="4" fill="#2563eb" stroke="white" stroke-width="1.5"/></svg>'
        'Compra o canvi de posició&nbsp;&nbsp;'
        '<svg width="10" height="10" viewBox="0 0 10 10" style="vertical-align:middle;margin-right:4px">'
        '<circle cx="5" cy="5" r="2.5" fill="#d1d5db"/></svg>'
        'Variació de preu sense canvi de posició. Passa el ratolí per sobre per veure el detall.'
        '</div>'
    )

    return f"""
    <svg viewBox="0 0 {W} {H}" class="equity-chart" xmlns="http://www.w3.org/2000/svg">
        <polyline points="{polyline}" fill="none" stroke="var(--accent, #2563eb)" stroke-width="2.5" />
        {"".join(price_dots)}
        {"".join(trade_markers)}
        <text x="{PAD}" y="{H-2}" font-size="11" fill="#888">{html_lib.escape(str(first_date))}</text>
        <text x="{W-PAD}" y="{H-2}" font-size="11" fill="#888" text-anchor="end">{html_lib.escape(str(last_date))}</text>
    </svg>
    {legend}
    """


def _history_table(history: list) -> str:
    rows = []
    for h in reversed(history[-12:]):  # últims 12 rebalancejos
        if "sleeves" in h:
            actius = ", ".join(str(v) for v in h["sleeves"].values())
        else:
            actius = str(h.get("holding", "-"))
        rows.append(
            f"<tr><td>{html_lib.escape(str(h['date']))}</td>"
            f"<td>{html_lib.escape(actius)}</td>"
            f"<td>{_fmt_money(h['equity'])}</td></tr>"
        )
    return "".join(rows)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<title>Dashboard del bot de trading</title>
<style>
  :root {{
    --accent: #2563eb;
    --ok: #16a34a;
    --warn: #d97706;
    --danger: #dc2626;
    --bg: #f7f8fa;
    --card-bg: #ffffff;
    --text: #1f2430;
    --muted: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--text);
  }}
  .container {{ max-width: 720px; margin: 0 auto; }}
  h1 {{ font-size: 20px; margin: 0 0 4px 0; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 20px; }}
  .banner {{
    display: flex; align-items: center; gap: 14px;
    padding: 16px 18px; border-radius: 12px; margin-bottom: 18px;
  }}
  .banner-ok {{ background: #ecfdf3; border: 1px solid #a7e8c1; }}
  .banner-alert {{ background: #fef2f2; border: 1px solid #fca5a5; }}
  .banner-icon {{
    width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-weight: bold; font-size: 16px; color: white;
  }}
  .banner-ok .banner-icon {{ background: var(--ok); }}
  .banner-alert .banner-icon {{ background: var(--danger); }}
  .banner-title {{ font-weight: 600; font-size: 15px; }}
  .banner-sub {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}
  .card {{
    background: var(--card-bg); border-radius: 12px; padding: 18px 20px;
    margin-bottom: 14px; border: 1px solid #e5e7eb;
  }}
  .card-wide {{ padding-bottom: 14px; }}
  .card-label {{
    font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
    color: var(--muted); margin-bottom: 8px; font-weight: 600;
  }}
  .action {{ font-size: 15px; line-height: 1.5; padding: 10px 12px; border-radius: 8px; }}
  .action-none {{ background: #ecfdf3; color: #14532d; }}
  .action-info {{ background: #eff6ff; color: #1e3a8a; }}
  .action-warning {{ background: #fffbeb; color: #78350f; }}
  .holding-name {{ font-size: 16px; font-weight: 600; }}
  .holding-ticker {{ font-size: 13px; color: var(--muted); margin: 4px 0 10px 0; }}
  .holding-reason {{ font-size: 13px; color: #374151; }}
  .sleeves-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px;
  }}
  .sleeve-item {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; }}
  .sleeve-name {{ font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 4px; }}
  .sleeve-halted {{
    display: inline-block; background: #fef2f2; color: #991b1b; font-size: 10px;
    padding: 1px 6px; border-radius: 999px; margin-left: 4px; font-weight: 600;
  }}
  .perf-grid {{
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 8px 0 4px 0;
  }}
  .perf-value {{ font-size: 20px; font-weight: 700; }}
  .perf-pos {{ color: var(--ok); }}
  .perf-neg {{ color: var(--danger); }}
  .perf-caption {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .perf-note {{ font-size: 13px; color: #374151; margin-top: 10px; }}
  .equity-chart {{ width: 100%; height: auto; margin-top: 8px; }}
  .chart-legend {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
  .chart-empty {{ font-size: 13px; color: var(--muted); padding: 20px 0; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 4px; border-bottom: 1px solid #f0f0f0; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; }}
  .footer {{
    font-size: 12px; color: var(--muted); text-align: center; margin-top: 20px; line-height: 1.6;
  }}
  .mode-pill {{
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600; margin-left: 8px;
  }}
  .mode-paper {{ background: #eff6ff; color: #1e3a8a; }}
  .mode-live {{ background: #fef2f2; color: #991b1b; }}
</style>
</head>
<body>
<div class="container">
  <h1>El teu bot de trading
    <span class="mode-pill {mode_pill_class}">{mode_label}</span>
  </h1>
  <div class="subtitle">Última actualització: {last_updated} · Pròxima revisió: {next_run}</div>

  {banner}
  {action_card}
  {sleeves_card}
  {withdrawal_card}
  {treasury_card}
  {performance_card}

  <div class="card">
    <div class="card-label">Evolució del valor del compte</div>
    {chart}
  </div>

  <div class="card">
    <div class="card-label">Historial dels últims rebalancejos</div>
    <table>
      <thead><tr><th>Data</th><th>Actiu</th><th>Valor del compte</th></tr></thead>
      <tbody>{history_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    Aquest dashboard es genera automàticament cada vegada que el bot fa un rebalanceig.
    Obre de nou aquest fitxer (o refresca la pàgina) després de cada execució per veure l'estat actualitzat.<br>
    Això no és una recomanació d'inversió personalitzada; és informació generada pel teu propi sistema.
  </div>
</div>
</body>
</html>
"""


def generate_dashboard(state: dict, output_path: str = "dashboard.html") -> str:
    mode_is_paper = state.get("mode", "PAPER") == "PAPER"
    html_out = HTML_TEMPLATE.format(
        mode_pill_class="mode-paper" if mode_is_paper else "mode-live",
        mode_label="PAPER (simulació)" if mode_is_paper else "REAL (diners reals)",
        last_updated=html_lib.escape(state.get("last_updated", "-")),
        next_run=html_lib.escape(state.get("next_run", "-")),
        banner=_status_banner(state),
        action_card=_action_card(state),
        sleeves_card=_sleeves_card(state),
        withdrawal_card=_withdrawal_card(state),
        treasury_card=_treasury_card(state),
        performance_card=_performance_card(state),
        chart=_equity_chart_svg(state.get("history", [])),
        history_rows=_history_table(state.get("history", [])),
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    state_path = output_path.replace(".html", "_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return output_path
