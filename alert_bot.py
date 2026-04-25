"""
Stock Alert Bot for NSE (India) — sends Telegram alerts on:
  • Daily price moves >= configurable %
  • Touch of 50 DMA / 200 DMA (within 1%)
  • Weekly RSI(14) crossing oversold/overbought thresholds
  • Touch of weekly Bollinger Band upper/lower (20, 2)

Telegram commands supported (sent to your bot from your account):
  /list, /add SYM..., /remove SYM, /setpct N, /setrsi LO HI,
  /toggle dma_50|dma_200|rsi_weekly|bb_weekly, /status, /help

Designed to run on GitHub Actions every 30 min.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).parent
WATCHLIST_FILE = ROOT / "watchlist.txt"
STATE_FILE = ROOT / "state.json"
CONFIG_FILE = ROOT / "config.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


# ============================================================
# Telegram helpers
# ============================================================
def tg_send(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("[telegram] credentials missing, skipping send")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        if not r.ok:
            print(f"[telegram] send error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[telegram] send exception: {e}")


def tg_get_updates(offset=None):
    if not BOT_TOKEN:
        return []
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.ok:
            return r.json().get("result", [])
        print(f"[telegram] getUpdates error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[telegram] getUpdates exception: {e}")
    return []


# ============================================================
# Persistence
# ============================================================
def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            print(f"[load] could not parse {path.name}: {e}")
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_watchlist():
    if not WATCHLIST_FILE.exists():
        return []
    out, seen = [], set()
    for line in WATCHLIST_FILE.read_text().splitlines():
        s = line.strip().upper()
        # strip leading numbers like "1\tRELIANCE"
        if "\t" in s:
            s = s.split("\t", 1)[1].strip()
        if not s or s.startswith("#"):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def save_watchlist(symbols) -> None:
    cleaned = sorted({s.strip().upper() for s in symbols if s.strip()})
    WATCHLIST_FILE.write_text("\n".join(cleaned) + "\n")


def default_config():
    return {
        "price_change_pct": 2.0,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "bb_period": 20,
        "bb_std": 2,
        "dma_touch_threshold_pct": 1.0,
        "indicators_enabled": {
            "dma_50": True,
            "dma_200": True,
            "rsi_weekly": True,
            "bb_weekly": True,
        },
    }


# ============================================================
# Telegram command processing
# ============================================================
HELP_TEXT = (
    "<b>Stock Alert Bot — Commands</b>\n"
    "/list — show all stocks in watchlist\n"
    "/add SYM1 SYM2 ... — add NSE symbols\n"
    "/remove SYM — remove a stock\n"
    "/setpct N — daily move threshold %, e.g. /setpct 2.5\n"
    "/setrsi LO HI — weekly RSI thresholds, e.g. /setrsi 30 70\n"
    "/toggle dma_50|dma_200|rsi_weekly|bb_weekly — turn an indicator on/off\n"
    "/status — show current settings\n"
    "/help — this message"
)


def process_commands(state, watchlist, config):
    last = state.get("last_update_id", 0)
    offset = last + 1 if last else None
    updates = tg_get_updates(offset=offset)
    if not updates:
        return watchlist, config, False, False

    changed_wl = False
    changed_cfg = False

    for upd in updates:
        state["last_update_id"] = upd["update_id"]
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat", {})
        if str(chat.get("id")) != str(CHAT_ID):
            continue  # ignore anyone else
        text = (msg.get("text") or "").strip()
        if not text or not text.startswith("/"):
            continue
        parts = text.split()
        cmd = parts[0].lower().split("@")[0]
        args = parts[1:]

        try:
            if cmd == "/help" or cmd == "/start":
                tg_send(HELP_TEXT)

            elif cmd == "/list":
                if not watchlist:
                    tg_send("Watchlist is empty.")
                else:
                    body = ", ".join(watchlist)
                    # chunk if huge
                    msg_str = f"<b>Watchlist ({len(watchlist)}):</b>\n{body}"
                    for i in range(0, len(msg_str), 3500):
                        tg_send(msg_str[i:i + 3500])

            elif cmd == "/add":
                added = []
                for s in args:
                    s = s.upper().strip(",")
                    if s and s not in watchlist:
                        watchlist.append(s)
                        added.append(s)
                if added:
                    changed_wl = True
                    tg_send(f"✅ Added: {', '.join(added)}\nTotal: {len(watchlist)}")
                else:
                    tg_send("Nothing added (already present or empty input).")

            elif cmd == "/remove":
                removed = []
                for s in args:
                    s = s.upper().strip(",")
                    if s in watchlist:
                        watchlist.remove(s)
                        removed.append(s)
                if removed:
                    changed_wl = True
                    tg_send(f"🗑 Removed: {', '.join(removed)}\nTotal: {len(watchlist)}")
                else:
                    tg_send("Nothing removed.")

            elif cmd == "/setpct":
                v = float(args[0])
                config["price_change_pct"] = v
                changed_cfg = True
                tg_send(f"Daily move threshold set to ±{v}%")

            elif cmd == "/setrsi":
                lo, hi = float(args[0]), float(args[1])
                config["rsi_oversold"] = lo
                config["rsi_overbought"] = hi
                changed_cfg = True
                tg_send(f"Weekly RSI thresholds: {lo} / {hi}")

            elif cmd == "/toggle":
                key = args[0].lower()
                if key in config["indicators_enabled"]:
                    config["indicators_enabled"][key] = not config["indicators_enabled"][key]
                    changed_cfg = True
                    state_str = "ON" if config["indicators_enabled"][key] else "OFF"
                    tg_send(f"Indicator '{key}' is now {state_str}")
                else:
                    keys = ", ".join(config["indicators_enabled"].keys())
                    tg_send(f"Unknown indicator. Options: {keys}")

            elif cmd == "/status":
                ind = ", ".join(
                    f"{k}={'ON' if v else 'OFF'}"
                    for k, v in config["indicators_enabled"].items()
                )
                tg_send(
                    "<b>Status</b>\n"
                    f"Stocks tracked: {len(watchlist)}\n"
                    f"Daily move: ±{config['price_change_pct']}%\n"
                    f"Weekly RSI: {config['rsi_oversold']}/{config['rsi_overbought']}\n"
                    f"DMA touch: ±{config['dma_touch_threshold_pct']}%\n"
                    f"Indicators: {ind}"
                )

            else:
                tg_send("Unknown command. Send /help for the list.")
        except Exception as e:
            tg_send(f"⚠️ Error processing '{text}': {e}")

    return watchlist, config, changed_wl, changed_cfg


# ============================================================
# Market hours
# ============================================================
def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    open_t = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=15, second=0, microsecond=0)
    return open_t <= now <= close_t


# ============================================================
# Indicators
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.ewm(alpha=1 / period, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / period, adjust=False).mean()
    # Avoid division-by-zero issues (no losses → RSI = 100; no gains → RSI = 0)
    import numpy as _np
    rs = avg_up / avg_down
    out = 100 - 100 / (1 + rs)
    out = out.where(avg_down != 0, 100)
    out = out.where(~((avg_up == 0) & (avg_down == 0)), 50)
    out = out.replace([_np.inf, -_np.inf], 100)
    return out


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def to_yf_symbol(s: str) -> str:
    """Convert NSE ticker to yfinance symbol."""
    # Most NSE symbols just need .NS suffix.
    # yfinance accepts characters like - and & via URL encoding.
    return f"{s}.NS"


# ============================================================
# Main checker
# ============================================================
def check_alerts(watchlist, config, state):
    yf_symbols = [to_yf_symbol(s) for s in watchlist]
    map_yf_to_nse = dict(zip(yf_symbols, watchlist))

    today = datetime.now(IST).date()
    today_str = today.isoformat()
    week_id = today.strftime("%G-W%V")

    alerts = []
    failures = []

    for batch in chunks(yf_symbols, 30):
        try:
            data = yf.download(
                batch,
                period="2y",  # enough for 200 DMA + ~100 weekly bars
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
        except Exception as e:
            print(f"[fetch] batch error: {e}")
            failures.extend(batch)
            continue

        for yfsym in batch:
            nse = map_yf_to_nse[yfsym]
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if yfsym not in data.columns.get_level_values(0):
                        failures.append(nse)
                        continue
                    df = data[yfsym].dropna()
                else:
                    df = data.dropna()

                if df.empty or len(df) < 5:
                    failures.append(nse)
                    continue

                last = df.iloc[-1]
                prev = df.iloc[-2]
                close = float(last["Close"])
                prev_close = float(prev["Close"])
                if prev_close == 0:
                    continue
                pct = (close - prev_close) / prev_close * 100.0

                stock_state = state.setdefault("stocks", {}).setdefault(nse, {})

                # ---- 1) Daily % move ----
                threshold = config["price_change_pct"]
                if abs(pct) >= threshold:
                    if stock_state.get("pct_move") != today_str:
                        arrow = "🟢 UP" if pct > 0 else "🔴 DOWN"
                        alerts.append(
                            f"{arrow} <b>{nse}</b> {pct:+.2f}%  ₹{close:,.2f}"
                        )
                        stock_state["pct_move"] = today_str

                # ---- 2) DMA 50 / 200 touch ----
                touch = config.get("dma_touch_threshold_pct", 1.0) / 100.0
                for ma_period, key in [(50, "dma_50"), (200, "dma_200")]:
                    if not config["indicators_enabled"].get(key, True):
                        continue
                    if len(df) < ma_period:
                        continue
                    ma_val = df["Close"].rolling(ma_period).mean().iloc[-1]
                    if pd.isna(ma_val) or ma_val == 0:
                        continue
                    diff = abs(close - ma_val) / ma_val
                    if diff <= touch:
                        if stock_state.get(key) != today_str:
                            alerts.append(
                                f"📊 <b>{nse}</b> touching {ma_period} DMA "
                                f"(MA ₹{ma_val:,.2f}, price ₹{close:,.2f})"
                            )
                            stock_state[key] = today_str

                # ---- Weekly bars ----
                weekly = df["Close"].resample("W-FRI").last().dropna()

                # ---- 3) Weekly RSI ----
                if config["indicators_enabled"].get("rsi_weekly", True) and len(weekly) >= 20:
                    wrsi_series = rsi(weekly, int(config.get("rsi_period", 14)))
                    wrsi = wrsi_series.iloc[-1]
                    if pd.notna(wrsi):
                        if wrsi <= config["rsi_oversold"]:
                            if stock_state.get("rsi_w_low") != week_id:
                                alerts.append(
                                    f"🟢 <b>{nse}</b> Weekly RSI {wrsi:.1f} ≤ "
                                    f"{config['rsi_oversold']} (oversold)"
                                )
                                stock_state["rsi_w_low"] = week_id
                        elif wrsi >= config["rsi_overbought"]:
                            if stock_state.get("rsi_w_high") != week_id:
                                alerts.append(
                                    f"🔴 <b>{nse}</b> Weekly RSI {wrsi:.1f} ≥ "
                                    f"{config['rsi_overbought']} (overbought)"
                                )
                                stock_state["rsi_w_high"] = week_id

                # ---- 4) Weekly Bollinger Bands ----
                if config["indicators_enabled"].get("bb_weekly", True) and len(weekly) >= int(config.get("bb_period", 20)):
                    period = int(config.get("bb_period", 20))
                    sd_mult = float(config.get("bb_std", 2))
                    ma20 = weekly.rolling(period).mean()
                    sd20 = weekly.rolling(period).std()
                    upper = (ma20 + sd_mult * sd20).iloc[-1]
                    lower = (ma20 - sd_mult * sd20).iloc[-1]
                    last_w = float(weekly.iloc[-1])
                    if pd.notna(upper) and pd.notna(lower) and upper > 0 and lower > 0:
                        # Touch defined as: within 'touch' of band, OR breached band
                        if last_w >= upper or abs(last_w - upper) / upper <= touch:
                            if stock_state.get("bb_w_upper") != week_id:
                                alerts.append(
                                    f"🔴 <b>{nse}</b> at/above Weekly BB Upper "
                                    f"(₹{upper:,.2f}, price ₹{last_w:,.2f})"
                                )
                                stock_state["bb_w_upper"] = week_id
                        elif last_w <= lower or abs(last_w - lower) / lower <= touch:
                            if stock_state.get("bb_w_lower") != week_id:
                                alerts.append(
                                    f"🟢 <b>{nse}</b> at/below Weekly BB Lower "
                                    f"(₹{lower:,.2f}, price ₹{last_w:,.2f})"
                                )
                                stock_state["bb_w_lower"] = week_id

            except Exception as e:
                print(f"[process] {nse}: {e}")
                failures.append(nse)
                continue

    if failures:
        print(f"[fetch] failed/no-data for {len(failures)} symbols: {failures[:20]}{'...' if len(failures)>20 else ''}")

    return alerts


# ============================================================
# Entry point
# ============================================================
def main():
    config = load_json(CONFIG_FILE, default_config())
    # ensure all keys exist (in case of older config files)
    base = default_config()
    for k, v in base.items():
        if k not in config:
            config[k] = v
    base_ind = base["indicators_enabled"]
    for k, v in base_ind.items():
        config["indicators_enabled"].setdefault(k, v)

    state = load_json(STATE_FILE, {})
    watchlist = load_watchlist()

    # Always handle Telegram commands first
    watchlist, config, changed_wl, changed_cfg = process_commands(state, watchlist, config)
    if changed_wl:
        save_watchlist(watchlist)
    if changed_cfg:
        save_json(CONFIG_FILE, config)

    if not is_market_open():
        print("[main] market closed — skipping alert scan")
        save_json(STATE_FILE, state)
        return

    if not watchlist:
        print("[main] watchlist empty — nothing to do")
        save_json(STATE_FILE, state)
        return

    alerts = check_alerts(watchlist, config, state)
    save_json(STATE_FILE, state)

    if not alerts:
        print("[main] no triggers")
        return

    header = f"⚡ <b>Alerts</b> — {datetime.now(IST).strftime('%a %d %b %H:%M IST')}\n"
    chunk, size = [], 0
    for a in alerts:
        if size + len(a) > 3500:
            tg_send(header + "\n".join(chunk))
            chunk, size = [], 0
        chunk.append(a)
        size += len(a) + 1
    if chunk:
        tg_send(header + "\n".join(chunk))


if __name__ == "__main__":
    main()