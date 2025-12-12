from flask import Flask, render_template_string, request
import requests

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "TRXUSDT", "BCHUSDT", "UNIUSDT"
]

MODES = {
    "1": {"name": "Scalping", "interval": "5m", "chart": "5 minute"},
    "2": {"name": "Day Trade", "interval": "15m", "chart": "15 minute"},
    "3": {"name": "Swing", "interval": "1h", "chart": "1 hour"},
    "4": {"name": "Position", "interval": "12h", "chart": "12 hour"},
}

BASE_URL = "https://fapi.binance.com/fapi/v1/klines"

app = Flask(__name__)

def ema(values, period):
    if len(values) < period:
        return values[-1] if values else 0.0
    k = 2.0 / (period + 1)
    ema_val = values[0]
    for price in values[1:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def get_indicators(symbol, interval):
    try:
        params = {"symbol": symbol, "interval": interval, "limit": 300}
        r = requests.get(BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        closes = [float(k[4]) for k in data]
        highs = [float(k[2]) for k in data]
        lows = [float(k[3]) for k in data]
        price = closes[-1]

        ema200 = ema(closes[:-50], 200) if len(closes) > 250 else ema(closes, 200)

        lookback = 14
        recent_high = max(highs[-lookback:])
        recent_low = min(lows[-lookback:])
        stoch = 50.0
        if recent_high != recent_low:
            stoch = (price - recent_low) / (recent_high - recent_low) * 100

        tr_list = []
        for i in range(1, len(data)):
            h, l, pc = highs[i], lows[i], closes[i - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            tr_list.append(tr)
        atr = sum(tr_list[-14:]) / 14 if len(tr_list) >= 14 else 0.01

        return {
            "price": price,
            "stoch": round(stoch, 2),
            "ema200": ema200,
            "atr": round(atr, 6),
        }
    except Exception:
        return None

def generate_signals(mode_key):
    interval = MODES[mode_key]["interval"]
    rows = []
    for sym in SYMBOLS:
        ind = get_indicators(sym, interval)
        if not ind:
            rows.append({
                "symbol": sym,
                "price": 0,
                "stoch": 0,
                "signal": "ERROR",
                "strength": 0,
                "entry": 0,
                "sl": "-",
                "tp": "-",
            })
            continue

        price = ind["price"]
        stoch = ind["stoch"]
        ema200 = ind["ema200"]
        atr = ind["atr"]

        trend_up = price > ema200
        trend_down = price < ema200

        signal = "HOLD"
        strength = 0.0

        if trend_up and stoch < 20:
            signal = "LONG"
            strength = max(15, 100 - stoch * 4.5)
        elif trend_down and stoch > 80:
            signal = "SHORT"
            strength = max(15, (stoch - 80) * 4.5)

        strength = round(min(100.0, strength), 1)

        entry = round(price, 6)
        if signal == "LONG":
            sl = round(entry - 1.5 * atr, 6)
            tp = round(entry + 2.0 * atr, 6)
        elif signal == "SHORT":
            sl = round(entry + 1.5 * atr, 6)
            tp = round(entry - 2.0 * atr, 6)
        else:
            sl = "-"
            tp = "-"

        rows.append({
            "symbol": sym.replace("USDT", "/USDT"),
            "price": price,
            "stoch": stoch,
            "signal": signal,
            "strength": strength,
            "entry": entry,
            "sl": sl,
            "tp": tp,
        })
    return rows

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MALIK Crypto Signals Web Dashboard</title>
  <meta http-equiv="refresh" content="15">
  <style>
    body { background: #0d1117; color: #c9d1d9; font-family: Arial, sans-serif; }
    h1 { color: #58a6ff; text-align: center; }
    .top-bar { text-align: center; margin-bottom: 15px; }
    table { width: 98%; margin: 0 auto; border-collapse: collapse; }
    th, td { padding: 6px 8px; text-align: center; }
    th { background: #21262d; color: #58a6ff; }
    tr:nth-child(even) { background: #161b22; }
    tr:nth-child(odd) { background: #0f172a; }
    .LONG { color: #39ff14; font-weight: bold; }
    .SHORT { color: #ff2d55; font-weight: bold; }
    .HOLD { color: #f0e442; }
    .ERROR { color: #ff00ff; }
    .mode-select { padding: 6px 10px; margin: 0 5px; }
    .info { color: #8b949e; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>MALIK Crypto Signals Web Dashboard</h1>

  <div class="top-bar">
    <form method="get">
      <label class="info">Mode:</label>
      <select name="mode" class="mode-select" onchange="this.form.submit()">
        {% for key, m in modes.items() %}
          <option value="{{ key }}" {% if key == current_mode %}selected{% endif %}>
            {{ key }} - {{ m.name }}
          </option>
        {% endfor %}
      </select>
      <span class="info">
        Timeframe: {{ modes[current_mode].chart }} | Auto refresh: 15s | Source: Binance Futures
      </span>
    </form>
  </div>

  <table>
    <thead>
      <tr>
        <th>Pair</th>
        <th>Price</th>
        <th>Signal</th>
        <th>Strength</th>
        <th>Stoch %K</th>
        <th>Entry</th>
        <th>SL</th>
        <th>TP</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
        <tr class="{{ row.signal }}">
          <td>{{ row.symbol }}</td>
          <td>{{ "%.4f"|format(row.price) }}</td>
          <td>{{ row.signal }}</td>
          <td>{{ row.strength }}%</td>
          <td>{{ row.stoch }}</td>
          <td>{{ row.entry }}</td>
          <td>{{ row.sl }}</td>
          <td>{{ row.tp }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""

@app.route("/")
def index():
    mode = request.args.get("mode", "2")
    if mode not in MODES:
        mode = "2"
    rows = generate_signals(mode)
    return render_template_string(TEMPLATE, rows=rows, modes=MODES, current_mode=mode)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
