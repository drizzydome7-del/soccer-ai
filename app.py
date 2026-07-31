import streamlit as st
import requests
import pandas as pd
import json
import re
import os
from datetime import datetime

st.set_page_config(page_title="Soccer Value Finder", page_icon="⚽", layout="wide")

LOG_FILE = "predictions_log.csv"

# ----------------------------------------------------------------------------
# LEAGUE CONFIG
# Maps a display name to (football-data.org competition code, The Odds API sport key)
# ----------------------------------------------------------------------------
LEAGUES = {
    "Premier League (England)": ("PL", "soccer_epl"),
    "Champions League (Europe)": ("CL", "soccer_uefa_champs_league"),
    "La Liga (Spain)": ("PD", "soccer_spain_la_liga"),
    "Bundesliga (Germany)": ("BL1", "soccer_germany_bundesliga"),
    "Serie A (Italy)": ("SA", "soccer_italy_serie_a"),
    "Ligue 1 (France)": ("FL1", "soccer_france_ligue_one"),
    "Eredivisie (Netherlands)": ("DED", "soccer_netherlands_eredivisie"),
    "Primeira Liga (Portugal)": ("PPL", "soccer_portugal_primeira_liga"),
    "Championship (England)": ("ELC", "soccer_england_efl_champ"),
    "Brazilian Serie A (Brazil)": ("BSA", "soccer_brazil_campeonato"),
}

# ----------------------------------------------------------------------------
# SECRETS
# ----------------------------------------------------------------------------
def get_secret(name):
    val = st.secrets.get(name) if hasattr(st, "secrets") else None
    return val or os.environ.get(name)


FOOTBALL_API_KEY = get_secret("FOOTBALL_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
ODDS_API_KEY = get_secret("ODDS_API_KEY")

missing = [n for n, v in [("FOOTBALL_API_KEY", FOOTBALL_API_KEY),
                           ("GEMINI_API_KEY", GEMINI_API_KEY),
                           ("ODDS_API_KEY", ODDS_API_KEY)] if not v]
if missing:
    st.error(
        f"Missing secrets: {', '.join(missing)}. Add them in "
        f"`.streamlit/secrets.toml` locally, or in your Streamlit Cloud app's "
        f"Settings → Secrets."
    )
    st.stop()


# ----------------------------------------------------------------------------
# DATA FETCHING
# ----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def fetch_fixtures(competition_code):
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches?status=SCHEDULED"
    r = requests.get(url, headers={"X-Auth-Token": FOOTBALL_API_KEY}, timeout=15)
    r.raise_for_status()
    return r.json().get("matches", [])


@st.cache_data(ttl=600)
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def normalize_name(name):
    junk = [" FC", " CF", " AFC", " SC", ".", "'"]
    n = name
    for j in junk:
        n = n.replace(j, "")
    return n.strip().lower()


def find_odds_for_fixture(home_team, away_team, odds_events):
    h, a = normalize_name(home_team), normalize_name(away_team)
    for event in odds_events:
        eh, ea = normalize_name(event.get("home_team", "")), normalize_name(event.get("away_team", ""))
        if (h in eh or eh in h) and (a in ea or ea in a):
            return event
    return None


def extract_h2h_odds(event):
    """Returns {'home': odds, 'draw': odds, 'away': odds} averaged across books, or None."""
    if not event or not event.get("bookmakers"):
        return None
    home_odds, draw_odds, away_odds = [], [], []
    home_team, away_team = event["home_team"], event["away_team"]
    for bm in event["bookmakers"]:
        for market in bm.get("markets", []):
            if market["key"] != "h2h":
                continue
            for outcome in market["outcomes"]:
                if outcome["name"] == home_team:
                    home_odds.append(outcome["price"])
                elif outcome["name"] == away_team:
                    away_odds.append(outcome["price"])
                elif outcome["name"].lower() == "draw":
                    draw_odds.append(outcome["price"])
    if not home_odds or not away_odds:
        return None
    avg = lambda lst: sum(lst) / len(lst) if lst else None
    return {"home": avg(home_odds), "draw": avg(draw_odds), "away": avg(away_odds)}


# ----------------------------------------------------------------------------
# PROBABILITY MATH
# ----------------------------------------------------------------------------
def american_to_implied_prob(odds):
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def devig_probabilities(odds_dict):
    """Converts raw American odds into no-vig 'fair' probabilities that sum to 100%."""
    implied = {k: american_to_implied_prob(v) for k, v in odds_dict.items() if v is not None}
    total = sum(implied.values())
    if total == 0:
        return {}
    return {k: (v / total) * 100 for k, v in implied.items()}


# ----------------------------------------------------------------------------
# GEMINI ANALYSIS
# ----------------------------------------------------------------------------
def get_gemini_estimate(home_team, away_team, league_name, match_date, fair_probs, raw_odds):
    prompt = f"""You are a soccer analyst. Analyze this fixture using tactical reasoning and team form.

League: {league_name}
Fixture: {home_team} (Home) vs {away_team} (Away)
Date: {match_date}
Current market-implied fair probabilities (from real sportsbook odds, vig removed):
- {home_team} win: {fair_probs.get('home', 0):.1f}%
- Draw: {fair_probs.get('draw', 0):.1f}%
- {away_team} win: {fair_probs.get('away', 0):.1f}%

Based on tactical matchup, likely team news, home/away form patterns, and the market pricing above,
give your OWN independent probability estimate for each outcome. Do not just copy the market numbers —
only deviate from them where you have a specific tactical or statistical reason to.

Respond with ONLY valid JSON, no markdown fences, no extra text, in exactly this format:
{{"home_win_prob": <number 0-100>, "draw_prob": <number 0-100>, "away_win_prob": <number 0-100>, "reasoning": "<2-3 sentence tactical rationale>"}}
The three probabilities must sum to approximately 100."""

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = re.sub(r"```json|```", "", text).strip()
        parsed = json.loads(cleaned)
        return parsed
    except Exception as e:
        return {"error": str(e)}


# ----------------------------------------------------------------------------
# LOGGING / TRACKER
# ----------------------------------------------------------------------------
def load_log():
    if os.path.isfile(LOG_FILE):
        return pd.read_csv(LOG_FILE)
    return pd.DataFrame(columns=[
        "logged_at", "league", "match", "match_date", "pick",
        "odds", "fair_prob", "model_prob", "edge", "result"
    ])


def save_log(df):
    df.to_csv(LOG_FILE, index=False)


def log_pick(league_name, match, match_date, pick, odds, fair_prob, model_prob, edge):
    df = load_log()
    new_row = {
        "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "league": league_name, "match": match, "match_date": match_date,
        "pick": pick, "odds": odds, "fair_prob": round(fair_prob, 1),
        "model_prob": round(model_prob, 1), "edge": round(edge, 1),
        "result": "PENDING",
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_log(df)


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
st.title("⚽ Soccer Value Finder")
st.caption(
    "Compares real sportsbook odds (de-vigged) against an AI tactical estimate to surface "
    "possible pricing gaps. This is a decision-support tool, not a guarantee — track your "
    "own results in the tab below to see your real hit rate over time."
)

tab_find, tab_track = st.tabs(["🔍 Find Value", "📊 My Tracked Picks"])

with tab_find:
    col1, col2 = st.columns([2, 1])
    with col1:
        league_name = st.selectbox("League", list(LEAGUES.keys()))
    with col2:
        edge_threshold = st.slider("Flag edges above (%)", 1, 25, 5)

    num_matches = st.slider("Number of upcoming fixtures to analyze", 1, 5, 2)

    if st.button("Analyze Fixtures", type="primary"):
        competition_code, sport_key = LEAGUES[league_name]

        with st.spinner("Fetching fixtures..."):
            try:
                matches = fetch_fixtures(competition_code)
            except Exception as e:
                st.error(f"Could not fetch fixtures: {e}")
                st.stop()

        if not matches:
            st.warning("No scheduled matches found for this league right now.")
            st.stop()

        with st.spinner("Fetching live odds..."):
            try:
                odds_data = fetch_odds(sport_key)
            except Exception as e:
                st.error(
                    f"Could not fetch odds for this league (the sport key may not be "
                    f"active right now, e.g. tournament-only competitions): {e}"
                )
                odds_data = []

        for match in matches[:num_matches]:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            match_date = match["utcDate"][:10]

            st.divider()
            st.subheader(f"{home} vs {away}")
            st.caption(f"{league_name} · {match_date}")

            event = find_odds_for_fixture(home, away, odds_data)
            raw_odds = extract_h2h_odds(event)

            if not raw_odds:
                st.info("No live odds found for this fixture yet — try again closer to match day.")
                continue

            fair_probs = devig_probabilities(raw_odds)

            with st.spinner("Getting AI tactical analysis..."):
                estimate = get_gemini_estimate(home, away, league_name, match_date, fair_probs, raw_odds)

            if "error" in estimate:
                st.error(f"AI analysis failed: {estimate['error']}")
                continue

            model_probs = {
                "home": estimate.get("home_win_prob", 0),
                "draw": estimate.get("draw_prob", 0),
                "away": estimate.get("away_win_prob", 0),
            }

            rows = []
            for key, label in [("home", f"{home} Win"), ("draw", "Draw"), ("away", f"{away} Win")]:
                fair = fair_probs.get(key, 0)
                model = model_probs.get(key, 0)
                edge = model - fair
                rows.append({
                    "Outcome": label,
                    "American Odds": f"{raw_odds[key]:+.0f}" if raw_odds.get(key) else "N/A",
                    "Market Fair %": f"{fair:.1f}%",
                    "AI Estimate %": f"{model:.1f}%",
                    "Edge": f"{edge:+.1f}%",
                    "_edge_val": edge, "_key": key, "_odds": raw_odds.get(key),
                    "_fair": fair, "_model": model,
                })

            df_display = pd.DataFrame(rows).drop(columns=["_edge_val", "_key", "_odds", "_fair", "_model"])
            st.dataframe(df_display, hide_index=True, use_container_width=True)

            st.markdown(f"**AI reasoning:** {estimate.get('reasoning', 'N/A')}")

            best = max(rows, key=lambda r: r["_edge_val"])
            if best["_edge_val"] >= edge_threshold:
                st.success(
                    f"📈 Positive edge flagged: **{best['Outcome']}** — AI estimates "
                    f"{best['_model']:.1f}% vs market fair {best['_fair']:.1f}% "
                    f"({best['_edge_val']:+.1f}% edge) at {best['_odds']:+.0f} odds."
                )
                if st.button(f"Log this pick — {best['Outcome']}", key=f"log_{home}_{away}"):
                    log_pick(league_name, f"{home} vs {away}", match_date, best["Outcome"],
                              best["_odds"], best["_fair"], best["_model"], best["_edge_val"])
                    st.toast("Logged to your tracker.")
            else:
                st.write("No outcome clears your edge threshold for this fixture.")

with tab_track:
    st.subheader("Your logged picks")
    df = load_log()

    if df.empty:
        st.write("Nothing logged yet. Picks you log from the Find Value tab will show up here.")
    else:
        pending = df[df["result"] == "PENDING"]
        if not pending.empty:
            st.markdown("**Update a pending pick's result:**")
            idx = st.selectbox(
                "Select pick",
                pending.index,
                format_func=lambda i: f"{pending.loc[i, 'match']} — {pending.loc[i, 'pick']} ({pending.loc[i, 'match_date']})",
            )
            result = st.radio("Result", ["Won", "Lost", "Push"], horizontal=True, key="result_radio")
            if st.button("Save result"):
                df.loc[idx, "result"] = result
                save_log(df)
                st.rerun()

        st.divider()
        st.dataframe(df, hide_index=True, use_container_width=True)

        settled = df[df["result"].isin(["Won", "Lost"])]
        if not settled.empty:
            wins = (settled["result"] == "Won").sum()
            total = len(settled)
            st.metric("Your actual hit rate (settled picks only)", f"{wins}/{total} = {wins/total*100:.1f}%")
        else:
            st.caption("Mark some picks Won/Lost above to see your real hit rate here.")

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download log as CSV", csv_bytes, "predictions_log.csv", "text/csv")
