import os
from flask import Flask, render_template_string
from google import genai
import requests

app = Flask(__name__)

# --- YOUR API KEYS ---
FOOTBALL_API_KEY = "f90e1e51400546f4a73a3d4be7fa2726"
AQ_KEY = "AQ.Ab8RN6Kk4SJyCMqwwg6OoMNer8H_XX2smo0zEArpRFiENAZBEQ"

# Initialize official Gemini client (fully supports AQ. keys)
client = genai.Client(api_key=AQ_KEY)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Soccer Betting Assistant</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; max-width: 900px; margin: auto; }
        h1 { color: #38bdf8; text-align: center; }
        .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        pre { white-space: pre-wrap; word-wrap: break-word; font-family: inherit; line-height: 1.5; }
        a.btn { display: block; text-align: center; background: #0ea5e9; color: white; padding: 12px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-bottom: 30px; }
        a.btn:hover { background: #0284c7; }
    </style>
</head>
<body>
    <h1>⚽ AI Soccer Betting Assistant</h1>
    <a class="btn" href="/analyze">🚀 Run Premier League AI Analysis</a>
    
    {% if results %}
        <div class="card">
            <h2>Analysis Results:</h2>
            <pre>{{ results }}</pre>
        </div>
    {% endif %}
</body>
</html>
"""


@app.route("/")
def home():
  return render_template_string(HTML_TEMPLATE, results=None)


@app.route("/analyze")
def analyze():
  url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
  headers = {"X-Auth-Token": FOOTBALL_API_KEY}
  response = requests.get(url, headers=headers)

  if response.status_code != 200:
    return render_template_string(
        HTML_TEMPLATE,
        results=f"❌ Football API Error: Status code {response.status_code}",
    )

  data = response.json()
  matches = data.get("matches", [])
  if not matches:
    return render_template_string(
        HTML_TEMPLATE, results="⚠️ No scheduled matches found."
    )

  output = ""
  for i, match in enumerate(matches[:2], 1):
    home_team = match["homeTeam"]["name"]
    away_team = match["awayTeam"]["name"]
    match_date = match["utcDate"][:10]

    prompt = f"""
You are an elite sports betting analyst and quantitative oddsmaker. Analyze this upcoming fixture objectively:
- Fixture: {home_team} (Home) vs {away_team} (Away)
- Date: {match_date}

Provide an institutional-grade betting breakdown formatted strictly with:
1. Tactical Game-State & Blueprint
2. Quantitative Edge & Statistical Drivers
3. Primary Sharp Betting Pick (Expressed in American odds format, e.g., -150, +220)
4. Risk Profile & Confidence Score (Rate out of 10)
"""

    try:
      ai_res = client.models.generate_content(
          model="gemini-2.5-flash", contents=prompt
      )
      output += (
          f"--- Match {i}: {home_team} vs {away_team} ({match_date}) ---\n"
          f"{ai_res.text}\n\n\n"
      )
    except Exception as e:
      output += (
          f"--- Match {i} Error ---\nGemini API Error: {str(e)}\n\n\n"
      )

  return render_template_string(HTML_TEMPLATE, results=output)


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
