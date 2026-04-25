
# Stock Alert Bot — Setup Guide (Beginner-Friendly)

A Telegram bot that watches your NSE stock list and pings you when:

- A stock moves ≥ ±2% in a day (configurable)
- Price touches the 50-DMA or 200-DMA (within 1%)
- Weekly RSI(14) crosses 30 (oversold) or 70 (overbought)
- Weekly closing price touches the upper or lower Bollinger Band (20, 2)

It runs **for free, forever** on **GitHub Actions** — no laptop needed, no credit card.

---

## What you need before starting

1. A free **GitHub account** — sign up at https://github.com/signup
2. Your **Telegram bot token** (from @BotFather, looks like `123456789:ABCdef...`)
3. Your **Telegram chat ID** (a number like `987654321`).
   *Quick way to find it:* message `@userinfobot` on Telegram → it replies with your chat ID.
4. The folder I built for you (`stock-alert-bot/` — the parent of this file).

Total setup time: **about 15 minutes**.

---

## Step 1 — Create a new GitHub repository

1. Go to https://github.com/new
2. **Repository name:** `stock-alert-bot` (or any name you like)
3. **Visibility:** select **Public** ← *important: this gives you unlimited free Actions minutes. The watchlist is just a list of stock symbols, nothing private.*
4. Leave everything else unchecked. Click **Create repository**.
5. You'll land on an empty repo page. Keep this tab open.

---

## Step 2 — Upload the files

The easiest way (no git knowledge needed):

1. On the empty repo page, click **"uploading an existing file"** (it's a blue link in the middle of the page).
2. Open the `stock-alert-bot` folder on your computer.
3. **Drag-and-drop ALL files and the `.github` folder** into the upload area:
   - `alert_bot.py`
   - `watchlist.txt`
   - `config.json`
   - `state.json`
   - `requirements.txt`
   - `.gitignore`
   - `SETUP.md` (this file — optional but nice)
   - `.github/` (the whole folder — make sure it uploads)
4. At the bottom, type a commit message like *"initial upload"*.
5. Click **Commit changes**.

> **If `.github` doesn't upload via drag-and-drop:** GitHub sometimes hides folders starting with a dot. Workaround:
> 1. After the other files upload, click **Add file → Create new file**.
> 2. In the file-name box, type exactly: `.github/workflows/alerts.yml`
> 3. Open `.github/workflows/alerts.yml` from your computer in Notepad, copy ALL the contents, paste into GitHub.
> 4. Click **Commit new file**.

---

## Step 3 — Add your secrets (Telegram credentials)

This is where your bot token and chat ID go. They're encrypted by GitHub and never visible — even to you after saving.

1. In your repo, click **Settings** (top tab).
2. In the left sidebar: **Secrets and variables → Actions**.
3. Click **New repository secret**.
4. **Name:** `TELEGRAM_BOT_TOKEN`
   **Secret:** paste your token from BotFather (the long string with a colon).
   Click **Add secret**.
5. Click **New repository secret** again.
6. **Name:** `TELEGRAM_CHAT_ID`
   **Secret:** paste your numeric chat ID.
   Click **Add secret**.

---

## Step 4 — Run it once manually to test

1. In your repo, click the **Actions** tab.
2. If you see a yellow banner *"Workflows aren't being run on this repository"* → click **I understand my workflows, go ahead and enable them**.
3. In the left sidebar, click **Stock Alerts**.
4. On the right, click **Run workflow → Run workflow** (the green button).
5. Wait ~1 minute. Refresh the page — you'll see a run appear. Click into it to watch it execute.

If everything is set up right:

- During market hours (Mon-Fri 9:15 am – 3:15 pm IST) → you'll receive any triggered alerts on Telegram.
- Outside market hours → you'll see in the logs `market closed — skipping alert scan`. That's expected.
- In either case, send your bot `/help` from Telegram — within 30 minutes the next scheduled run will reply with the command list. That confirms the Telegram connection works.

---

## Step 5 — You're done!

The workflow now runs **every 30 minutes, automatically**. Alerts arrive on Telegram only when something actually triggers (no spam).

---

## How to use it day-to-day

Just send commands to your bot from Telegram:

| Command | What it does |
|---|---|
| `/help` | Show all commands |
| `/list` | Show your full watchlist |
| `/add RELIANCE TCS INFY` | Add one or more stocks (NSE symbols, space-separated) |
| `/remove RELIANCE` | Remove a stock |
| `/setpct 2.5` | Change the daily move threshold (e.g. ±2.5%) |
| `/setrsi 25 75` | Change weekly RSI thresholds (oversold / overbought) |
| `/toggle dma_50` | Turn the 50-DMA alerts on/off. Same for `dma_200`, `rsi_weekly`, `bb_weekly` |
| `/status` | Show current settings + stock count |

> **Note:** commands are processed every 30 min. If you `/add` a stock at 10:03 am, alerts for it begin at the 10:30 run.

---

## Troubleshooting

**"The workflow runs but I never get a Telegram message."**
- Open the workflow run logs (Actions tab → click latest run → click `run`).
- If you see `[telegram] credentials missing` → your secrets aren't named exactly `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (case-sensitive!).
- If you see `[telegram] send error: 401` → your bot token is wrong.
- If you see `[telegram] send error: 400 ... chat not found` → your chat ID is wrong (or you've never messaged the bot — open Telegram and send the bot any message first).
- If you see `market closed — skipping alert scan` → that's normal outside Mon-Fri 9:15 am – 3:15 pm IST.

**"I get the same alert multiple times in one day."**
- Shouldn't happen — `state.json` prevents duplicates. If it does, open `state.json` in the repo to inspect. Each daily alert is keyed to today's date; each weekly alert to this ISO week.

**"Some symbols never produce alerts."**
- Check the workflow logs for a line like `[fetch] failed/no-data for ... symbols`. Yahoo may not have data for newly-listed stocks or some ETFs. You can `/remove` them.
- Note: a few symbols use special yfinance suffixes. If a symbol consistently fails, message me and I'll fix it.

**"How do I stop it?"**
- Settings → Actions → Disable Actions. Or just delete the repo.

---

## Cost & limits (the fine print)

- **GitHub Actions** is free forever for **public repos** (unlimited minutes). For private repos: 2,000 minutes/month free (this bot uses ~1,500/month, so still free, but cuts close).
- **Yahoo Finance** is free, no API key. Occasionally rate-limited; the script handles errors gracefully.
- **Telegram Bot API** is free, no limits for personal use.

**Result: ₹0/month, forever.**

---

## Want to add a new technical indicator later?

Just tell me what you want (e.g. "MACD crossover", "20-day high", "volume spike") and I'll add it to `alert_bot.py`. You then upload the new file to GitHub (replacing the old one) and you're done — no other changes needed.