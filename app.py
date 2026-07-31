import csv
import os
import re
from google import genai
import pandas as pd
import requests
import streamlit as st

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="AI Soccer Betting Assistant", page_icon="⚽", layout="wide"
)

# --- YOUR API KEYS ---
FOOTBALL_API_KEY = "f90e1e51400546f4a73a3d4be7fa2726"
AQ_KEY = "AQ.Ab8RN6Kk4SJyCMqwwg6OoMNer8H_XX2smo0zEArpRFiENAZBEQ"

# --- INITIALIZE OFFICIAL GEMINI CLIENT (Supports AQ. Keys) ---
client = genai.Client(api_key=AQ_KEY)


# --- HELPER FUNCTIONS ---
def get_footy_stats_data():
  return "FootyStats baseline integration active."


def extract_confidence(ai_text):
  match = re.search(
      r'(?:Confidence Score|Confidence)[:\s\*]+([\d\.]+)\s*/\s*10',
      ai_text,
      re.IGNORECASE,
  )
  if match:
    try:
      return float(match.group(1))
    except ValueError:
      return 5.0
  return 5.0


def log_prediction(date, league, match, bet_pick, confidence_score):
  file_exists = os.path.isfile("predictions_log.csv")
  with open(
      "predictions_log.csv", mode="a", newline="", encoding="utf-8"
  ) as f:
    writer = csv.writer(f)
    if not file_exists:
      writer.writerow(
          [
              "Timestamp",
              "League",
              "Match",
              "Recommended Bet",
              "Confidence",
              "Actual Result",
          ]
      )
    writer.writerow(
        [date, league, match, bet_pick, f"{confidence_score}/10", "PENDING"]
    )


def get_ai_memory_summary():
  try:
    if not os.path.isfile("predictions_log.csv"):
      return "No historical memory file yet."
    df = pd.read_csv("predictions_log.csv")
    completed = df[df["Actual Result"] != "PENDING"]
    if completed.empty:
      return "No completed historical data yet."
    losses = completed[completed["Actual Result"] == "LOSS"]
    lessons = []
    for _, row in losses.iterrows():
      lessons.append(
          f"- Past Error: Bet on {row['Match']} ({row['Recommended Bet']})"
          f" failed. Avoid repeating similar over-estimations."
      )
    return (
        "🧠 AI LESSONS LEARNED FROM PAST MISTAKES (ADAPT YOUR MODEL):\n"
        + "\n".join(lessons[:5])
        if lessons
        else "No past losses recorded yet."
    )
  except Exception:
    return "Memory file initializing."


# --- STREAMLIT TABS UI ---
st.title("⚽ AI Soccer Betting Assistant & Quant Terminal")
tab1, tab2 = st.tabs(["⚽ Live Match Analyzer", "📊 Performance & Backtest Log"])

with tab1:
  st.subheader("Select a League & Analyze Upcoming Fixtures")

  leagues = {
      "Premier League (England)": "PL",
      "Champions League (Europe)": "CL",
      "La Liga (Spain)": "PD",
      "Bundesliga (Germany)": "BL1",
      "Serie A (Italy)": "SA",
      "Ligue 1 (France)": "FL1",
      "Eredivisie (Netherlands)": "DED",
      "Primeira Liga (Portugal)": "PPL",
      "Championship (England)": "ELC",
      "Brazilian Série A (Brazil)": "BSA",
      "World Cup (World)": "WC",
      "European Championship (Europe)": "EC",
  }

  selected_league_name = st.selectbox("Choose League", list(leagues.keys()))
  league_code = leagues[selected_league_name]

  if st.button("🚀 Fetch Fixtures & Run AI Oddsmaker"):
    with st.spinner(f"Fetching fixtures for {selected_league_name}..."):
      url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
      headers = {"X-Auth-Token": FOOTBALL_API_KEY}
      response = requests.get(url, headers=headers)

      if response.status_code == 200:
        data = response.json()
        matches = data.get("matches", [])
        if matches:
          matches_to_analyze = matches[:2]
          ai_memory = get_ai_memory_summary()
          extra_stats = get_footy_stats_data() if league_code == "PL" else ""

          for i, match in enumerate(matches_to_analyze, 1):
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            match_date = match["utcDate"]

            st.markdown(
                f"### ⚽ Match {i}: {home_team} vs {away_team}"
                f" ({match_date[:10]})"
            )

            prompt_text = f"""
You are the Head Quantitative Oddsmaker and Lead Betting Analyst for an elite sports syndication fund with an audited 90%+ hit rate. Your entire focus is finding mathematical value, mispriced odds, and structural edges.

{ai_memory}

Analyze the upcoming fixture with brutal objectivity and analytical depth:
- League: {selected_league_name}
- Fixture: {home_team} (Home) vs {away_team} (Away)
- Date: {match_date}
- Advanced Data Insights & Metrics: {extra_stats}

Perform a rigorous multi-angle evaluation using home/away split performance, tactical matchups, and historical momentum.

Provide an institutional-grade betting breakdown formatted strictly as follows (Express all estimated odds, implied market pricing, and lines **strictly in American odds format** (e.g., -150, +220). Do not use decimal or fractional odds.):

1. **Tactical Game-State & Blueprint**: 
   - How will the tactical setups clash? (Identify control zones, transition vulnerabilities, and expected match tempo).
2. **Quantitative Edge & Statistical Drivers**: 
   - Highlight 2-3 hard data points or trends from the dataset that heavily sway the probability of this outcome.
3. **Primary Sharp Betting Pick**: 
   - State the exact bet type clearly (e.g., Match Winner, Both Teams To Score [Yes/No], or Over/Under goals) along with the mathematical justification and American odds line.
4. **Risk Profile & Unit Allocation**: 
   - Confidence Score: [X / 10] (Only rate 8.5+ if multiple data signals converge).
   - Recommended Unit Size: [e.g., 1.5 Units / Pass] based on risk management principles.

Constraint: Avoid filler words, generic fan opinions, or emotional commentary. Every statement must be anchored to tactical reality or statistical probability.
"""

            try:
              # Use the official Google GenAI SDK client
              ai_response = client.models.generate_content(
                  model="gemini-2.5-flash", contents=prompt_text
              )
              prediction_text = ai_response.text

              st.markdown(prediction_text)

              conf_score = extract_confidence(prediction_text)
              if conf_score < 8.5:
                st.warning(
                    f"🛑 [PASS - NO VALUE] Confidence score is {conf_score}/10."
                    " Below strict 8.5 threshold. Skipping bet."
                )
              else:
                st.success(
                    f"✅ [HIGH CONVERGENCE SIGNAL] Confidence score is"
                    f" {conf_score}/10. Approved for execution!"
                )
                log_prediction(
                    match_date[:10],
                    selected_league_name,
                    f"{home_team} vs {away_team}",
                    "See AI Breakdown",
                    conf_score,
                )
                st.info("📂 Automatically logged to predictions_log.csv!")

            except Exception as e:
              st.error(f"Gemini API Error: {str(e)}")

            st.divider()
        else:
          st.warning("No scheduled matches found for this league.")
      else:
        st.error(f"Failed to fetch fixtures from API: {response.status_code}")

with tab2:
  st.subheader("Audited Backtesting Log & AI Memory Tracker")
  if os.path.isfile("predictions_log.csv"):
    df = pd.read_csv("predictions_log.csv")

    completed = df[df["Actual Result"] != "PENDING"]
    wins = len(completed[completed["Actual Result"] == "WIN"])
    total_completed = len(completed)
    win_rate = (wins / total_completed * 100) if total_completed > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Logged Picks", len(df))
    col2.metric("Win Rate (%)", f"{win_rate:.1f}%")
    col3.metric("Min Confidence Filter", "8.5 / 10")

    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("Update Match Outcomes (Feed AI Memory)")
    st.write(
        "Change status from PENDING to WIN or LOSS to train the AI's historical"
        " memory."
    )

    if not df.empty:
      row_index = st.number_input(
          "Row Index to Update",
          min_value=0,
          max_value=max(0, len(df) - 1),
          step=1,
      )
      new_result = st.selectbox("Actual Result", ["PENDING", "WIN", "LOSS"])
      if st.button("Update Log Entry"):
        df.loc[row_index, "Actual Result"] = new_result
        df.to_csv("predictions_log.csv", index=False)
        st.success(
            f"Updated row {row_index} result to {new_result}! AI memory"
            " updated."
        )
        st.rerun()
  else:
    st.warning("predictions_log.csv not found yet.")
