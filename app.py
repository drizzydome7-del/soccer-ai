import os
from google import genai
import requests
import streamlit as st

# Page layout styling
st.set_page_config(
    page_title="AI Soccer Betting Assistant", page_icon="⚽", layout="centered"
)

st.title("⚽ My Custom AI Soccer Predictor")
st.write(
    "Generate professional, oddsmaker-grade betting breakdowns instantly."
)

# Safely load keys from Streamlit Secrets (with fallback to sidebar inputs if needed)
secret_gemini = (
    st.secrets.get("GEMINI_API_KEY", "") if "secrets" in dir(st) else ""
)
secret_football = (
    st.secrets.get("FOOTBALL_API_KEY", "f90e1e51400546f4a73a3d4be7fa2726")
    if "secrets" in dir(st)
    else "f90e1e51400546f4a73a3d4be7fa2726"
)

# Sidebar configuration
st.sidebar.header("API Configuration")
football_api_key = st.sidebar.text_input(
    "Football-Data API Key", type="password", value=secret_football
)
gemini_api_key = st.sidebar.text_input(
    "Gemini API Key / Token", type="password", value=secret_gemini
)

# League Selection Dropdown
league_choice = st.sidebar.selectbox(
    "Select League",
    [
        "Premier League (PL)",
        "Champions League (CL)",
        "Spanish La Liga (PD)",
    ],
)
league_code = league_choice.split("(")[1].replace(")", "")

if st.button("🚀 Analyze Upcoming Match"):
  if not football_api_key or not gemini_api_key:
    st.error("Please provide both API keys in the sidebar or secrets.")
  else:
    with st.spinner("Fetching live match data..."):
      url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
      headers = {"X-Auth-Token": football_api_key}
      response = requests.get(url, headers=headers)

    if response.status_code == 200:
      data = response.json()
      matches = data.get("matches", [])

      if matches:
        next_match = matches[0]
        home_team = next_match["homeTeam"]["name"]
        away_team = next_match["awayTeam"]["name"]
        match_date = next_match["utcDate"]

        st.success(
            f"Match Found: **{home_team} vs {away_team}** on {match_date[:10]}"
        )

        with st.spinner("🤖 Consulting your AI oddsmaker..."):
          try:
            # For OAuth / service tokens, explicitly pass the token and configure client
            client = genai.Client(api_key=gemini_api_key)
            prompt_text = f"""
                        You are an expert soccer betting analyst and oddsmaker (like Linemaker AI). 
                        Analyze the upcoming match: {home_team} (Home) playing against {away_team} (Away). Date: {match_date}.
                        
                        Provide a professional betting breakdown containing:
                        1. Match Overview & Expected Vibe
                        2. Key Factors to Watch
                        3. Best Betting Prediction (Match Winner, Both Teams to Score, or Over/Under goals)
                        4. Confidence Level (Out of 10)
                        
                        Keep it punchy, sharp, and structured nicely.
                        """

            ai_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text,
            )

            st.markdown("---")
            st.markdown(ai_response.text)

          except Exception as e:
            st.error(
                f"❌ AI Generation Failed. Exact Error Details: {str(e)}"
            )
      else:
        st.warning(
            "No scheduled matches found for this competition right now."
        )
    else:
      st.error(f"Failed to fetch match data. Error code: {response.status_code}")
