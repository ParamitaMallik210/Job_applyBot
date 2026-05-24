# Job Bot — Complete Setup Guide

Recreate the entire job-monitoring bot from scratch on any machine. End-to-end build, ~30–45 minutes.

---

## 1. What you're building

A personal job-search bot that runs **twice a day on GitHub Actions** (12:30 PM + 9:30 PM IST), with zero ongoing cost.

### Features

| Capability | How it works |
|---|---|
| **Multi-source scraping** | Naukri, LinkedIn, Indeed, Foundit, Instahyre, Hirist — best-effort; failures in one don't break the others |
| **Title filtering** | Whitelist of titles (Software Engineer, SDE-1, SDE-2, Full Stack Dev, etc.) + blocklist (Senior, Lead, QA, Intern, DevOps, etc.) |
| **JD fallback match** | A posting with an odd title can still qualify if its description hits enough software-dev phrases |
| **Location filter** | Bengaluru / Bangalore / Hyderabad |
| **Salary filter** | Minimum 14 LPA when disclosed; passes through "Not disclosed" postings (since ~80% hide salary) |
| **Experience filter** | Drops postings whose minimum required experience is >1 year above your profile |
| **ATS scoring** | Keyword overlap between JD and your resume; reports missing skills |
| **Dedup** | `state.json` tracks job IDs already notified to avoid repeats |
| **Telegram cards** | Compact 2-line cards per match with `🚀 Apply`, `📋 Details`, `📌 Track Applied` inline buttons |
| **Application tracker** | Separate Telegram channel for running total: applied, active, interviewing, offered, rejected, withdrawn |

### Architecture diagram

```
┌─────────────────────────────────────────────────┐
│  GitHub Actions cron (12:30 + 21:30 IST)        │
└──────────────────┬──────────────────────────────┘
                   │ run python -m src.main
                   ▼
┌─────────────────────────────────────────────────┐
│ src/sources/  →  naukri, linkedin, indeed,      │
│                  foundit, instahyre, hirist     │
└──────────────────┬──────────────────────────────┘
                   │ raw job dicts
                   ▼
┌─────────────────────────────────────────────────┐
│ src/filters.py  →  title / location / salary    │
│                    / experience checks          │
└──────────────────┬──────────────────────────────┘
                   │ matched jobs
                   ▼
┌─────────────────────────────────────────────────┐
│ src/ats/  →  resume parse + keyword match score │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ src/notify/telegram.py → DM to user (Chat 1)    │
└─────────────────────────────────────────────────┘

         ↓ user taps "📌 Track Applied"
         ↓ pre-filled GitHub Issue gets submitted

┌─────────────────────────────────────────────────┐
│ .github/workflows/applied-tracker.yml triggers  │
│  → counts issues by label                       │
│  → posts to dedicated channel (Chat 2)          │
└─────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

On the new machine you only need:

- **Python 3.11+** (`python3 --version`)
- **git** (`git --version`)
- **GitHub CLI** (`gh --version`) — install: `brew install gh` on macOS, `sudo apt install gh` on Ubuntu
- An **iPhone or Android** with Telegram installed
- A **GitHub account** (free)
- (Optional) **VS Code** — `brew install --cask visual-studio-code` on macOS

That's it — no cloud account, no paid services, no Claude/OpenAI/Anthropic key required.

---

## 3. Telegram setup

### 3a. Create the bot (5 min)

1. On your phone, install **Telegram** from the App Store / Play Store and sign in.
2. Search **`@BotFather`** (✅ verified). Tap **Start**.
3. Send `/newbot`. Provide:
   - **Name**: anything, e.g. `Job Match Bot`
   - **Username**: must end in `bot`, e.g. `your_name_jobmatch_bot`
4. BotFather replies with a **token** like `123456789:ABC...`. Save it — this is `TELEGRAM_BOT_TOKEN`.
5. Search your new bot by its username → tap **Start**. (Bots can't DM you until you start a chat first.)

### 3b. Get your personal chat ID (1 min)

1. Search **`@userinfobot`** in Telegram → tap **Start**.
2. It replies with `Id: <number>`. Save it — this is `TELEGRAM_CHAT_ID`.

### 3c. Create the applications tracker channel (3 min)

1. In Telegram, tap the **✏️ pencil icon** (top-right) → **New Channel**.
2. Name: `My Job Applications` → **Private Channel** → **Skip** adding subscribers.
3. Tap channel name at top → **Administrators** → **Add Admin** → search your bot's username → **Save**.
4. Send any test message in the channel (e.g. "hello").
5. Get the channel's chat ID — easiest method is from your bot's recent updates. On any machine:
   ```bash
   curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates" | python3 -c "
   import json, sys
   for u in json.load(sys.stdin).get('result', []):
       for k in ('channel_post', 'message', 'my_chat_member'):
           if k in u:
               c = u[k].get('chat', {})
               print(c.get('type'), c.get('id'), c.get('title') or c.get('first_name'))"
   ```
   Look for the line where type is `channel` — that ID (negative, starting `-100`) is `TELEGRAM_APPLIED_CHAT_ID`.

---

## 4. GitHub repo setup

### 4a. Authenticate

```bash
gh auth login
# → choose: GitHub.com → HTTPS → Login with browser
```

### 4b. Create a private repo

```bash
gh repo create job-applybot --private --confirm
```

### 4c. Clone the code (option A — copy from this repo)

If you still have the existing local copy:
```bash
cp -R ~/naukri-job-bot ~/job-applybot-new
cd ~/job-applybot-new
rm -rf .git state.json
git init && git remote add origin https://github.com/<YOUR_USERNAME>/job-applybot.git
```

### 4c. Clone the code (option B — build files from this guide)

If starting completely fresh, follow Section 7 below to recreate the file structure.

### 4d. First push

```bash
cd ~/job-applybot
git add .
git commit -m "initial bot setup"
git branch -M main
git push -u origin main
```

---

## 5. Add your resume

```bash
cp ~/Downloads/<your-resume>.pdf ~/job-applybot/resume/resume.pdf
cd ~/job-applybot
git add resume/resume.pdf
git commit -m "add resume"
git push
```

If your PDF name has spaces, wrap it in quotes.

---

## 6. Configure secrets

Run all four — replacing the values:

```bash
REPO="<YOUR_USERNAME>/job-applybot"

gh secret set TELEGRAM_BOT_TOKEN --repo "$REPO" --body "<your bot token>"
gh secret set TELEGRAM_CHAT_ID --repo "$REPO" --body "<your personal chat id>"
gh secret set TELEGRAM_APPLIED_CHAT_ID --repo "$REPO" --body "<your channel chat id, starts with -100>"

# Optional — for LLM resume suggestions (not required):
# gh secret set ANTHROPIC_API_KEY --repo "$REPO" --body "sk-ant-..."
```

Verify they're set:
```bash
gh secret list --repo "$REPO"
```

---

## 7. File layout (for option B / reference)

```
job-applybot/
├── .github/workflows/
│   ├── job-bot.yml              ← cron: scan + notify, runs 12:30 + 21:30 IST
│   └── applied-tracker.yml      ← triggers on Issue events, updates channel
├── src/
│   ├── main.py                  ← orchestrator
│   ├── config.py                ← yaml loader
│   ├── filters.py               ← title / location / salary / experience checks
│   ├── state.py                 ← seen-job-id dedup
│   ├── sources/
│   │   ├── naukri.py            ← Naukri JSON API
│   │   ├── linkedin.py          ← LinkedIn guest-search HTML
│   │   ├── indeed.py            ← Indeed embedded JSON
│   │   ├── foundit.py           ← Foundit middleware API
│   │   ├── instahyre.py         ← Instahyre public job_search API
│   │   └── hirist.py            ← Hirist HTML scrape
│   ├── ats/
│   │   ├── resume_parser.py     ← pypdf
│   │   └── matcher.py           ← keyword overlap + optional Claude call
│   └── notify/
│       ├── telegram.py          ← cards with inline buttons
│       └── whatsapp.py          ← CallMeBot fallback (optional)
├── resume/
│   └── resume.pdf               ← your CV (committed to PRIVATE repo only)
├── config.yml                   ← all thresholds, titles, skills, channels
├── requirements.txt
├── state.json                   ← auto-managed by the bot
└── SETUP_GUIDE.md               ← this file
```

### Key config knobs in `config.yml`

```yaml
profile:
  experience_years: 2
  min_ctc_lpa: 14
  locations: [Bengaluru, Bangalore, Hyderabad]

title_whitelist: [Software Engineer, SDE, SDE-1, SDE 1, SDE-2, Software Developer, ...]
title_blocklist: [Senior, Lead, Principal, Staff, Architect, QA, DevOps, Intern, ...]

ats:
  llm_suggestions: false   # true → use Claude API for resume edit suggestions (paid)
  my_skills: [c#, .net, azure, docker, java, ...]

notify:
  channel: telegram        # telegram | whatsapp | both
  min_score_to_notify: 40  # drop matches below this %

sources:
  naukri:    { enabled: true, pages_per_query: 6 }
  linkedin:  { enabled: true, pages_per_query: 4 }
  indeed:    { enabled: true, pages_per_query: 2 }
  foundit:   { enabled: true, pages_per_query: 2 }
  instahyre: { enabled: true, pages_per_query: 2 }
  hirist:    { enabled: true, pages_per_query: 1 }
```

### Cron times

In `.github/workflows/job-bot.yml`:
```yaml
schedule:
  - cron: "0 7 * * *"   # 12:30 PM IST
  - cron: "0 16 * * *"  # 9:30 PM IST
```
(GitHub cron is in UTC. IST = UTC + 5:30.)

---

## 8. First test

Trigger the bot manually:

```bash
gh workflow run job-bot.yml --repo <YOUR_USERNAME>/job-applybot
gh run watch --repo <YOUR_USERNAME>/job-applybot
```

Within ~1–2 minutes:
- You'll get a Telegram DM from your bot with one or more job match cards.
- Each card has `🚀 Apply | 📋 Details` on one row, `📌 Track Applied` on the next.

Tap **📌 Track Applied** on any match → GitHub opens an Issue form in browser with the application pre-filled → tap **Submit**.

Within seconds, your `My Job Applications` channel gets a running-total update.

---

## 9. Day-to-day use

### Update your resume
```bash
cp ~/Downloads/resume-v2.pdf ~/job-applybot/resume/resume.pdf
cd ~/job-applybot
git add resume/resume.pdf && git commit -m "update resume" && git push
```
Next scheduled run will use the new resume.

### Edit filters / skills
1. Open `config.yml` in any editor
2. Add/remove titles, skills, locations, etc.
3. Commit & push — next run uses the new config

### Update an application's status
1. Go to your repo → **Issues** tab
2. Click the issue → **Labels** → set `interviewing` / `offered` / `rejected` / `withdrawn`
3. The tracker channel auto-posts the new counts

### See all your applications at a glance
- Browser: `https://github.com/<YOUR_USERNAME>/job-applybot/issues?q=label:applied`
- Mobile: GitHub mobile app → repo → Issues tab

### Pause the bot temporarily
Disable the workflows from the **Actions** tab on GitHub:
- Click **Job Bot** → "..." → **Disable workflow**
- Click **Applied Tracker** → "..." → **Disable workflow**

Re-enable the same way when ready.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Naukri returned 406` | Anti-bot fingerprinting changed | Update `_HEADERS` in `src/sources/naukri.py` — match what naukri.com sends in DevTools Network tab |
| `LinkedIn returned 429` | Rate-limited (very common on GitHub Actions IPs) | Expected; the other sources still run. Reduce `linkedin.pages_per_query` |
| `Indeed returned 403` | Cloudflare blocked GitHub Actions IP | Disable Indeed in config or switch host to a residential VPN |
| `Telegram 404 "chat not found"` | You haven't started a chat with the bot, or chat ID is wrong | Open the bot in Telegram → tap **Start** |
| `Telegram 400 "Bad Request"` | MarkdownV2 escape issue in some title with special chars | Re-escape in `src/notify/telegram.py:_escape` |
| GitHub Actions consumes too many minutes | Cron firing too often, or pages too deep | Lower `pages_per_query` per source in `config.yml` |
| No matches for days | All your matches were already in `state.json` | This is normal — bot only sends genuinely new postings |
| Want a one-time backfill | Clear seen IDs | `echo '{"seen_ids":[]}' > state.json && git commit -am "reset state" && git push` |

---

## 11. Security checklist

- ✅ Repo is **Private** (otherwise your resume is exposed to the world)
- ✅ Bot token is only in **GitHub Secrets**, never committed to code or chat
- ✅ If a token is ever exposed: `BotFather → /revoke → @YourBot → Confirm`, then re-set secret
- ✅ Resume is in the repo but only readable by you and GitHub Actions
- ✅ No third-party services have access to your data (no Anthropic / OpenAI key in use)
- ⚠️ Anyone with admin access to your repo can read your resume — don't grant push access to others

---

## 12. Cost summary

| Item | Cost |
|---|---|
| GitHub Actions runtime | ~5 min/day × 2 = 10 min/day → 300 min/month (free tier covers 2000) |
| GitHub private repo | $0 |
| Telegram bot + channel | $0 |
| Python dependencies | $0 |
| **Total monthly cost** | **$0** |

The bot will keep running indefinitely without any subscription or recurring payment.

---

## 13. What to do if a job source breaks 6 months from now

The most common failure: a job site rotates anti-bot headers or changes their HTML/JSON structure.

**Debug recipe:**
1. Check the last run's logs:
   ```bash
   gh run list --repo <YOUR_USERNAME>/job-applybot --limit 5
   gh run view <run-id> --log | grep -i "<source-name>"
   ```
2. Open the source's website in Chrome → DevTools → Network tab → reload → find the JSON/HTML request the page makes for job search
3. Copy the headers from the request → update the corresponding `_HEADERS` dict in `src/sources/<name>.py`
4. Commit, push, trigger a manual run, verify

You only need to touch ONE file per broken source. The others keep running.

---

That's everything. Good luck with the search. 🚀
