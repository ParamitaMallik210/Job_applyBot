# Naukri / LinkedIn Job-Match Bot

Polls Naukri and LinkedIn twice a day, filters for software engineering roles matching your profile, scores each posting against your resume with an ATS-style match, and DMs you on Telegram with the matches + suggested resume tweaks.

**No auto-apply.** You decide whether to apply.

---

## What it does

1. **Searches** Naukri (and LinkedIn public listings, best-effort) for these titles:
   - Software Engineer, SDE, Software Developer, Associate / Junior Software Engineer
   - Application Developer, Back End Developer / Engineer
   - Full Stack Developer / Engineer
2. **Filters out** Senior / Lead / Manager / QA / DevOps / Intern / etc.
3. **Backup match**: if the title looks unusual but the JD strongly matches a software dev role, it still gets in.
4. **Location**: Bengaluru + Hyderabad (edit `config.yml` to change).
5. **Salary**: min 15 LPA when disclosed (most postings hide it — those still come through).
6. **ATS scoring**:
   - Keyword overlap: % of your skills the JD asks for
   - Missing-from-resume: skills the JD wants that aren't on your resume
   - Claude suggestions: 3 actionable resume edits for THAT job
7. **Notifications**: Telegram DM at **9 AM IST** and **7 PM IST**.

---

## One-time setup — from scratch

### Step 1 — Create a Telegram bot (5 min, free)

1. Install the [Telegram app](https://apps.apple.com/app/telegram-messenger/id686449807) on your iPhone and sign in with your phone number.
2. In Telegram, search for **`@BotFather`** and open the chat. Tap **Start**.
3. Send `/newbot`. BotFather asks two things:
   - A **name** (anything, e.g. "Job Match Bot")
   - A **username** ending in `bot` (e.g. `your_name_jobmatch_bot`)
4. BotFather replies with a token that looks like `123456789:ABCdefGhI_xyz...`. **Save this — this is your `TELEGRAM_BOT_TOKEN`.**
5. Now search for **`@userinfobot`** in Telegram, open the chat, tap **Start**. It replies with your numeric `Id:` — **that's your `TELEGRAM_CHAT_ID`.**
6. Important: open a chat with your new bot (search its username) and tap **Start**. Until you send the bot at least one message, it can't DM you.

### Step 2 — Get an Anthropic API key (for resume suggestions)

1. Go to <https://console.anthropic.com> and sign up.
2. Top up $5 of credit (this will last months at our usage).
3. Create an API key under **Settings → API Keys**. Copy it (`sk-ant-...`).

If you skip this step, the bot still works — you just get match scores without LLM resume suggestions.

### Step 3 — Create a private GitHub repo

1. Sign in at <https://github.com> (create an account if needed).
2. Click **+ → New repository**.
3. Name: `naukri-job-bot` (or anything). **Set it to Private.** Skip "Add a README". Click **Create**.
4. On your Mac, open Terminal and run (replace `YOUR-USERNAME`):
   ```bash
   cd ~/naukri-job-bot
   git init
   git add .
   git commit -m "initial bot"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/naukri-job-bot.git
   git push -u origin main
   ```
   If git asks for credentials, follow GitHub's prompt to use a personal access token (PAT) — see <https://docs.github.com/en/get-started/quickstart/set-up-git>.

### Step 4 — Add your resume

1. Copy your resume PDF into `~/naukri-job-bot/resume/resume.pdf`.
2. Open `config.yml` and tweak `ats.my_skills` to match the skills actually on your resume.
3. Commit and push:
   ```bash
   cd ~/naukri-job-bot
   git add resume/resume.pdf config.yml
   git commit -m "add resume + tune skills"
   git push
   ```

### Step 5 — Add secrets to GitHub

1. In your repo on github.com, click **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** three times and add:
   - Name: `TELEGRAM_BOT_TOKEN` — Value: the token from Step 1
   - Name: `TELEGRAM_CHAT_ID` — Value: the numeric ID from Step 1
   - Name: `ANTHROPIC_API_KEY` — Value: the key from Step 2

### Step 6 — Test it

1. In your repo on github.com, click **Actions** in the top tab.
2. If Actions is disabled, GitHub will prompt you to enable it — click the green button.
3. In the left sidebar, click **Job Bot**, then **Run workflow → Run workflow**.
4. Wait ~2 minutes. You should get a Telegram message — either matches, or "no new matches this cycle".
5. The cron will now run automatically at 9 AM and 7 PM IST every day.

---

## Tuning

Everything is in `config.yml`:

- **`title_whitelist` / `title_blocklist`** — which job titles to include/exclude
- **`jd_match.phrases`** — backup keywords for unusually-titled postings
- **`profile.min_ctc_lpa`** — minimum disclosed salary
- **`profile.locations`** — cities; add `Remote` to include WFH postings
- **`ats.my_skills`** — list of skills the bot looks for in your resume + each JD
- **`notify.min_score_to_notify`** — drop notifications below this ATS %
- **`ats.llm_suggestions: false`** — disable Claude if you want $0 cost

After any change, commit + push. The next scheduled run picks it up.

---

## Run locally (optional)

```bash
cd ~/naukri-job-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export ANTHROPIC_API_KEY=...
python -m src.main
```

---

## Caveats up front

- **Naukri changes their HTML / API headers occasionally.** When the bot suddenly returns zero results, that's almost always why — `src/sources/naukri.py` is the one place to patch.
- **LinkedIn blocks GitHub Actions IPs aggressively.** Expect LinkedIn to be silent some runs. That's normal; Naukri is the primary source.
- **Salary filter is lenient.** Most postings don't disclose CTC, and dropping all undisclosed postings throws out 80%+ of matches. The bot only excludes a posting when CTC is disclosed AND is below 15 LPA.
- **Auto-apply is intentionally not built.** Naukri/LinkedIn ToS prohibit it, and accounts get banned.
