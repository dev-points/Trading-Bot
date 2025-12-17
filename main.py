import requests
import hashlib
import hmac
import time
import numpy as np
import os
from dotenv import load_dotenv
from datetime import datetime

# === Load API Keys === #
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

# === Configuration === #
SYMBOL = 'XRPUSDT'
INTERVAL = '1m'
RSI_PERIOD = 14
FETCH_INTERVAL = 1.0  # seconds
CAPITAL_USDT = 2.0
BUY_RSI_MIN, BUY_RSI_MAX = 47, 52
RSI_SELL = 43
PROFIT_TARGET_PERCENT = 0.01  # 1%
STOPLOSS_TARGET_PERCENT = -0.0009  # -0.09% (keeps your original value)
BASE_URL = 'https://api.mexc.com'

# Dynamic loss control defaults
MAX_LOSS_COUNT = 3
COOLDOWN_TIME = 600  # 10 minutes

# === Telegram === #
def send_telegram_message(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=3)
    except Exception:
        pass


def check_telegram_commands(last_update_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 3, "offset": (last_update_id + 1) if last_update_id else None}
    try:
        r = requests.get(url, params=params, timeout=3)
        data = r.json()
        if not data.get("result"):
            return None, last_update_id
        latest = data["result"][-1]
        text = latest.get("message", {}).get("text", "")
        if not text:
            return None, last_update_id
        text = text.strip().lower()
        return text, latest["update_id"]
    except Exception:
        return None, last_update_id


# === Market Data === #
def fetch_latest_price(symbol):
    try:
        r = requests.get(BASE_URL + '/api/v3/ticker/price', params={'symbol': symbol}, timeout=0.8)
        return float(r.json()['price'])
    except Exception:
        return None


def fetch_recent_candles(symbol, interval=INTERVAL, limit=100):
    try:
        r = requests.get(BASE_URL + '/api/v3/klines', params={'symbol': symbol, 'interval': interval, 'limit': limit}, timeout=1.5)
        return r.json()
    except Exception:
        return None


# === Account Data === #
def fetch_account_balance(asset='USDT'):
    ts = str(int(time.time() * 1000))
    q = f"timestamp={ts}&recvWindow=5000"
    sig = hmac.new(API_SECRET.encode(), q.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE_URL}/api/v3/account?{q}&signature={sig}"
    try:
        r = requests.get(url, headers={'X-MEXC-APIKEY': API_KEY}, timeout=2)
        data = r.json()
        for b in data.get('balances', []):
            if b['asset'].upper() == asset.upper():
                free_bal = float(b['free'])
                locked_bal = float(b['locked'])
                return free_bal, locked_bal
    except Exception as e:
        print("Balance fetch error:", e)
    return None, None


# === Indicators === #
def calculate_rsi(candles, period=RSI_PERIOD):
    closes = [float(c[4]) for c in candles]
    if len(closes) <= period:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_sar(candles):
    high = [float(c[2]) for c in candles]
    low = [float(c[3]) for c in candles]
    if len(high) < 2 or len(low) < 2:
        return float(low[-1]), 'Downtrend'
    sar = [low[0]]
    trend = 'up' if high[1] > high[0] else 'down'
    ep = high[0] if trend == 'up' else low[0]
    af, max_af = 0.02, 0.2
    for i in range(1, len(candles)):
        prev = sar[-1]
        if trend == 'up':
            new = min(prev + af * (ep - prev), low[i - 1], low[i])
            if low[i] < new:
                trend, ep, af = 'down', low[i], 0.02
                sar.append(ep)
                continue
            if high[i] > ep:
                ep, af = high[i], min(af + 0.02, max_af)
        else:
            new = max(prev + af * (ep - prev), high[i - 1], high[i])
            if high[i] > new:
                trend, ep, af = 'up', high[i], 0.02
                sar.append(ep)
                continue
            if low[i] < ep:
                ep, af = low[i], min(af + 0.02, max_af)
        sar.append(new)
    latest_sar = sar[-1]
    latest_price = float(candles[-1][4])
    trend_dir = 'Uptrend' if latest_price > latest_sar else 'Downtrend'
    return latest_sar, trend_dir


# === Orders === #
def place_market_order(symbol, side, qty):
    ts = str(int(time.time() * 1000))
    qty = float(f"{qty:.2f}")
    q = f"symbol={symbol}&side={side}&type=MARKET&quantity={qty}&recvWindow=5000&timestamp={ts}"
    sig = hmac.new(API_SECRET.encode(), q.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE_URL}/api/v3/order?{q}&signature={sig}"
    try:
        r = requests.post(url, headers={'X-MEXC-APIKEY': API_KEY}, timeout=3)
        if r.status_code == 200:
            print(f"[{side}] Executed:", r.json())
        else:
            print(f"[{side}] Failed:", r.text)
    except Exception as e:
        print("Order error:", e)


# === Main Loop === #
if __name__ == "__main__":
    position = None
    force_buy = force_sell = False
    bot_active = True
    last_update_id, last_telegram_check = None, 0

    total_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    loss_streak = 0
    last_pause_time = None
    trade_history = []

    candles = None
    while candles is None:
        candles = fetch_recent_candles(SYMBOL)
        if candles:
            break
        print(" Retrying to fetch initial candles...")
        time.sleep(2)

    send_telegram_message(f" MEXC Bot started on {SYMBOL} with ${CAPITAL_USDT} capital.")
    print(f" Bot started successfully — monitoring {SYMBOL}")

    while True:
        start = time.time()

        # === Auto Resume After Cooldown === #
        if not bot_active and last_pause_time:
            if time.time() - last_pause_time >= COOLDOWN_TIME:
                bot_active = True
                loss_streak = 0
                last_pause_time = None
                send_telegram_message(" Bot resumed after cooldown period.")

        # === Telegram Commands === #
        if start - last_telegram_check > 5:
            cmd, last_update_id = check_telegram_commands(last_update_id)
            last_telegram_check = start

            if cmd:
                if cmd in ['/cmd', '/command']:
                    msg = (
                        " *MEXC Trading Bot Commands*\n\n"
                        "/start - Start/resume the bot\n"
                        "/stop - Stop/pause the bot\n"
                        "/status - Show bot status and indicators\n"
                        "/buy - Force buy immediately\n"
                        "/sell - Force sell immediately\n"
                        "/setpair <symbol> - Change trading pair\n"
                        "/setcapital <amount> - Set trading capital\n"
                        "/setlosscount <count> <minutes> - Adjust loss control\n"
                        "/resetlosscount - Reset loss streak\n"
                        "/pnl - Show total profit/loss\n"
                        "/trades - Show recent trades\n"
                    )
                    send_telegram_message(msg)
                elif cmd == '/buy':
                    force_buy = True
                    send_telegram_message(" Force BUY command received.")
                elif cmd == '/sell':
                    force_sell = True
                    send_telegram_message(" Force SELL command received.")
                elif cmd == '/stop':
                    bot_active = False
                    send_telegram_message(" Bot stopped manually.")
                elif cmd == '/start':
                    bot_active = True
                    send_telegram_message("🚀 Bot started manually.")
                elif cmd.startswith('/setpair'):
                    parts = cmd.split()
                    if len(parts) == 2:
                        new_symbol = parts[1].upper()
                        test_price = fetch_latest_price(new_symbol)
                        if test_price:
                            SYMBOL = new_symbol
                            candles = fetch_recent_candles(SYMBOL)
                            send_telegram_message(f" Trading pair updated to {SYMBOL}")
                            position = None
                            trade_history.clear()
                        else:
                            send_telegram_message(" Invalid or unsupported pair.")
                elif cmd.startswith('/setcapital'):
                    parts = cmd.split()
                    if len(parts) == 2:
                        try:
                            new_cap = float(parts[1])
                            if new_cap <= 0:
                                raise ValueError
                            CAPITAL_USDT = new_cap
                            send_telegram_message(f" Trading capital updated to ${CAPITAL_USDT}")
                        except ValueError:
                            send_telegram_message(" Invalid amount. Example: /setcapital 5")
                elif cmd.startswith('/setlosscount'):
                    parts = cmd.split()
                    if len(parts) == 3:
                        try:
                            new_count = int(parts[1])
                            new_minutes = int(parts[2])
                            if new_count <= 0 or new_minutes <= 0:
                                raise ValueError
                            MAX_LOSS_COUNT = new_count
                            COOLDOWN_TIME = new_minutes * 60
                            send_telegram_message(f" Loss control updated: {MAX_LOSS_COUNT} losses → pause {new_minutes} min.")
                        except ValueError:
                            send_telegram_message(" Usage: /setlosscount <count> <minutes>")
                elif cmd == '/resetlosscount':
                    loss_streak = 0
                    bot_active = True
                    last_pause_time = None
                    send_telegram_message(" Loss count reset to 0. Bot resumed trading.")
                elif cmd == '/status':
                    price = fetch_latest_price(SYMBOL)
                    rsi = calculate_rsi(candles)
                    sar, trend = calculate_sar(candles)

                    quote_asset = SYMBOL[-4:].upper() if SYMBOL.endswith('USDT') else SYMBOL[-3:].upper()
                    base_asset = SYMBOL.replace(quote_asset, '')

                    free_q, locked_q = fetch_account_balance(quote_asset)
                    free_b, locked_b = fetch_account_balance(base_asset)

                    msg = f" *Bot Status*\n\n" \
                          f"Pair: {SYMBOL}\nActive: {' ON' if bot_active else ' OFF'}\n" \
                          f"Loss Streak: {loss_streak}/{MAX_LOSS_COUNT}\n" \
                          f"Cooldown: {COOLDOWN_TIME/60:.0f} min\n"

                    if free_q is not None:
                        msg += f"\n Balances:\n{quote_asset}: {free_q:.2f} \n"
                    if free_b is not None:
                        msg += f"{base_asset}: {free_b:.4f}  locked\n"

                    if price is not None:
                        msg += f"\nPrice: {price:.4f}\n"
                    msg += f"RSI: {rsi:.2f}\nSAR: {sar:.4f}\nTrend: {trend}\n" \
                           f"Capital: ${CAPITAL_USDT}"
                    if position:
                        pnl = (price - position['buy_price']) * position['amount'] if price else 0.0
                        msg += f"\n\n Position:\nBuy: {position['buy_price']:.4f}\nAmount: {position['amount']:.4f}\nPnL: ${pnl:.4f}"
                    else:
                        msg += "\n\n No open position"
                    send_telegram_message(msg)
                elif cmd == '/pnl':
                    net_pnl = total_profit + total_loss
                    msg = (
                        f" *Total Performance*\n\n"
                        f"Total Trades: {total_trades}\n"
                        f" Profit: ${total_profit:.4f}\n"
                        f" Loss: ${total_loss:.4f}\n"
                        f" Net: ${net_pnl:.4f}\n"
                        f" Loss Streak: {loss_streak}/{MAX_LOSS_COUNT}"
                    )
                    send_telegram_message(msg)
                elif cmd == '/trades':
                    if not trade_history:
                        send_telegram_message(" No trades yet.")
                    else:
                        msg = " *Trade History*\n\n"
                        for t in trade_history[-10:]:
                            msg += f"{t['time']} | {t['side']} {t['symbol']} @ {t['price']:.4f} | Amt: {t['amount']:.4f}"
                            if 'pnl' in t:
                                msg += f" | PnL: ${t['pnl']:.4f}"
                            msg += "\n"
                        send_telegram_message(msg)

        # === Price & Indicators === #
        price = fetch_latest_price(SYMBOL)
        if not price:
            time.sleep(FETCH_INTERVAL)
            continue

        if candles and isinstance(candles[-1], list) and len(candles[-1]) > 4:
            candles[-1][4] = str(price)
        else:
            candles = fetch_recent_candles(SYMBOL)

        if int(start) % 30 == 0:
            new_candles = fetch_recent_candles(SYMBOL)
            if new_candles:
                candles = new_candles

        rsi = calculate_rsi(candles)
        sar, trend = calculate_sar(candles)
        print(f"Pair: {SYMBOL} | Price: {price:.4f} | RSI: {rsi:.2f} | SAR: {sar:.4f} | Trend: {trend} | Active: {bot_active}")

        # === Trading Logic === #
        if bot_active:
            if position is None:
                if force_buy or (BUY_RSI_MIN <= rsi <= BUY_RSI_MAX and price > sar):
                    qty = CAPITAL_USDT / price
                    place_market_order(SYMBOL, 'BUY', qty)
                    position = {'buy_price': price, 'amount': qty}
                    trade_history.append({'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'side': 'BUY', 'symbol': SYMBOL, 'price': price, 'amount': qty})
                    send_telegram_message(f" Bought {SYMBOL} at {price:.4f} (${CAPITAL_USDT})")
                    force_buy = False
            else:
                pnl = (price - position['buy_price']) * position['amount']
                profit_target = CAPITAL_USDT * PROFIT_TARGET_PERCENT
                stoploss_target = CAPITAL_USDT * STOPLOSS_TARGET_PERCENT
                if force_sell or pnl >= profit_target or pnl <= stoploss_target or rsi <= RSI_SELL:
                    place_market_order(SYMBOL, 'SELL', position['amount'])
                    send_telegram_message(f" Sold {SYMBOL} at {price:.4f} | PnL: ${pnl:.4f}")
                    total_trades += 1
                    if pnl > 0:
                        total_profit += pnl
                        loss_streak = 0
                    else:
                        total_loss += pnl
                        loss_streak += 1
                        if loss_streak >= MAX_LOSS_COUNT:
                            bot_active = False
                            last_pause_time = time.time()
                            send_telegram_message(f" Bot paused after {MAX_LOSS_COUNT} losses. Cooling down for {COOLDOWN_TIME/60:.0f} min.")
                    trade_history.append({'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'side': 'SELL', 'symbol': SYMBOL, 'price': price, 'amount': position['amount'], 'pnl': pnl})
                    position = None
                    force_sell = False

        time.sleep(max(0, FETCH_INTERVAL - (time.time() - start)))
