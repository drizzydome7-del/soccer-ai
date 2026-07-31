# Soccer Value Finder

Compares real sportsbook odds against an AI tactical estimate to flag possible
pricing gaps, and lets you track your own results over time.

## What this does (and doesn't do)

- Pulls real upcoming fixtures and real sportsbook odds.
- Removes the bookmaker's built-in margin ("de-vigging") to get a fair market probability.
- Asks Gemini for an independent probability estimate based on tactics/form.
- Flags fixtures where the AI's estimate is meaningfully higher than the market's fair price.
- Lets you log picks and mark them Won/Lost later, so you can see your *real* hit rate — not a made-up confidence score.

This does **not** guarantee winning bets. Nothing can. Treat the "edge" numbers as a
starting point for your own judgment, not a signal to bet blindly. Only bet money you
can afford to lose, and use the tracker tab honestly — it's the only way to know if
this is actually helping you.

## 1. Get your three free API keys

1. **Football-Data.org** (fixtures) — register at https://www.football-data.org/client/register, free tier is plenty for this.
2. **Google AI Studio** (Gemini) — get a free key at https://aistudio.google.com/apikey
3. **The Odds API** (real betting odds) — sign up at https://the-odds-api.com/ , free tier gives 500 requests/month.

Keep these three values somewhere safe. Never paste them into your code file.

## 2. Run it locally first (recommended before deploying)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# now open .streamlit/secrets.toml and paste in your real keys
streamlit run app.py
```

It should open in your browser automatically at http://localhost:8501

## 3. Push to GitHub

- Create a new **repository** on GitHub (public or private, either works with Streamlit Cloud).
- Upload everything in this folder EXCEPT `.streamlit/secrets.toml` (the `.gitignore` file
  here already prevents it from being committed if you're using git normally — just don't
  manually drag it into the GitHub web uploader).

## 4. Deploy for free on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click "New app", pick your repository, and set the main file path to `app.py`.
3. Before clicking Deploy, go to "Advanced settings" → **Secrets**, and paste in:

```toml
FOOTBALL_API_KEY = "your-real-key"
GEMINI_API_KEY = "your-real-key"
ODDS_API_KEY = "your-real-key"
```

4. Click Deploy. You'll get a permanent public URL like `yourapp.streamlit.app`.

## Notes on the leagues list

The Odds API only lists a soccer competition as an active "sport key" when it's
currently in season / has upcoming matches with posted odds. Tournament-only
competitions (World Cup, Euros) will show no odds outside of their tournament window —
that's expected, not a bug. You can check what's currently active at
https://the-odds-api.com/sports-odds-data/soccer-odds.html

## Notes on the tracker

`predictions_log.csv` is stored on whatever machine runs the app. Locally, this
persists fine. On Streamlit Community Cloud, the free tier can restart your app
(clearing local files) after periods of inactivity — download your log with the
"Download log as CSV" button periodically so you don't lose your history. If you
want the tracker to be fully permanent long-term, the next upgrade would be pointing
it at a small free database (e.g. Google Sheets or Supabase) instead of a local CSV —
happy to help with that once you're ready.
