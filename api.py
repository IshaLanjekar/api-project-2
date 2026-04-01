from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string
import base64
import json
import os
import pickle

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

app = Flask(__name__)
SPAM_THRESHOLD = float(os.getenv("SPAM_THRESHOLD", "0.5"))
KEYWORDS_FILE = "user_keywords.json"
GOOGLE_CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "credentials.json")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:5000/oauth/callback")
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
]

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-secret")


@app.before_request
def _handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response


@app.after_request
def _add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def _load_pickle(primary_name, fallback_name):
    """Load a pickle file using primary filename, then fallback filename."""
    file_to_load = primary_name if os.path.exists(primary_name) else fallback_name
    with open(file_to_load, "rb") as f:
        return pickle.load(f)


def _load_default_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        return []

    try:
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list):
        return []

    keywords = []
    for item in raw:
        value = str(item).strip().lower()
        if value:
            keywords.append(value)
    return sorted(set(keywords))


def _default_keywords_for_request(data):
    return sorted(set(_load_default_keywords() + _extract_request_keywords(data)))


def _extract_request_keywords(data):
    raw_keywords = data.get("keywords") if isinstance(data, dict) else None
    if raw_keywords is None:
        return []

    if isinstance(raw_keywords, str):
        tokens = [part.strip().lower() for part in raw_keywords.split(",")]
        return sorted(set(token for token in tokens if token))

    if isinstance(raw_keywords, list):
        tokens = [str(item).strip().lower() for item in raw_keywords]
        return sorted(set(token for token in tokens if token))

    return []


def _find_keyword_matches(text, keywords):
    lowered_text = text.lower()
    return [keyword for keyword in keywords if keyword in lowered_text]


def _apply_keyword_rule(prediction, spam_score, keyword_matches):
    # If user-trusted keywords are present, downgrade likely false positives.
    if not keyword_matches:
        return prediction, False

    if spam_score is None and prediction == 1:
        return 0, True

    if spam_score is not None and spam_score < 0.85:
        return 0, True

    return prediction, False


def _classify_text(text, keywords):
    transformed = vectorizer.transform([text])

    spam_score = None
    confidence = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(transformed)[0]
        spam_score = float(probabilities[1])
        confidence = float(max(probabilities))
        prediction = 1 if spam_score >= SPAM_THRESHOLD else 0
    else:
        prediction = int(model.predict(transformed)[0])

    keyword_matches = _find_keyword_matches(text, keywords)
    prediction, keyword_override = _apply_keyword_rule(prediction, spam_score, keyword_matches)

    return {
        "spam": int(prediction),
        "label": "Spam" if prediction == 1 else "Not Spam",
        "spam_score": spam_score,
        "confidence": confidence,
        "threshold": SPAM_THRESHOLD,
        "keyword_matches": keyword_matches,
        "keyword_override": keyword_override,
    }


def _credentials_from_session():
    creds_dict = session.get("google_credentials")
    if not creds_dict:
        return None
    return Credentials(**creds_dict)


def _save_credentials_to_session(creds):
    session["google_credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


def _create_oauth_flow(state=None):
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE,
        scopes=GOOGLE_SCOPES,
        state=state,
    )
    flow.redirect_uri = OAUTH_REDIRECT_URI
    return flow


def _extract_header(headers, name):
    for header in headers or []:
        if (header.get("name") or "").lower() == name.lower():
            return header.get("value") or ""
    return ""


def _extract_message_text(payload):
    snippet = payload.get("snippet") or ""
    body_data = ((payload.get("payload") or {}).get("body") or {}).get("data")
    if not body_data:
        return snippet
    try:
        decoded = base64.urlsafe_b64decode(body_data.encode("utf-8")).decode("utf-8", errors="ignore")
        return decoded if decoded.strip() else snippet
    except Exception:
        return snippet


# Load model assets. Supports both old and current filenames.
model = _load_pickle("spam_model.pkl", "model.pkl")
vectorizer = _load_pickle("vectorizer_spam.pkl", "vectorizer.pkl")

@app.route("/")
def home():
    return "API is running"


@app.route("/webapp", methods=["GET"])
def webapp_home():
    connected = bool(session.get("google_credentials"))
    user_email = session.get("user_email", "")
    return render_template_string(
        """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Spam Detector OAuth App</title>
    <style>
      body { font-family: Inter, Arial, sans-serif; margin: 24px auto; max-width: 800px; color: #1f2937; }
      .card { border: 1px solid #d1d5db; border-radius: 10px; padding: 16px; margin-top: 12px; }
      .btn { display: inline-block; border-radius: 8px; padding: 10px 14px; text-decoration: none; margin-right: 8px; }
      .btn-main { background: #008080; color: #fff; }
      .btn-outline { border: 1px solid #94a3b8; color: #334155; }
      textarea { width: 100%; min-height: 120px; margin-top: 8px; }
    </style>
  </head>
  <body>
    <h1>Gmail OAuth Inbox Analyzer</h1>
    <p>Connect Gmail first, then fetch and analyze latest 30 inbox emails using your ML model.</p>
    <div class="card">
      <p><b>Connected:</b> {{ "Yes" if connected else "No" }} {{ user_email }}</p>
      <a class="btn btn-main" href="{{ url_for('oauth_login') }}">Connect Gmail</a>
      <a class="btn btn-outline" href="{{ url_for('oauth_logout') }}">Disconnect</a>
    </div>
    <div class="card">
      <p><b>Keywords</b> (comma separated)</p>
      <input id="keywords" style="width:100%;height:36px" placeholder="meeting, project, client">
      <p style="margin-top:12px"><button id="runBtn" class="btn btn-main">Fetch & Analyze Inbox</button></p>
      <pre id="out" style="white-space:pre-wrap"></pre>
    </div>
    <script>
      document.getElementById('runBtn').addEventListener('click', async () => {
        const keywords = document.getElementById('keywords').value;
        const out = document.getElementById('out');
        out.textContent = 'Analyzing...';
        const res = await fetch('/oauth/analyze-inbox', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ keywords })
        });
        const data = await res.json();
        out.textContent = JSON.stringify(data, null, 2);
      });
    </script>
  </body>
</html>
        """,
        connected=connected,
        user_email=user_email,
    )


@app.route("/oauth/login", methods=["GET"])
def oauth_login():
    flow = _create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    return redirect(authorization_url)


@app.route("/oauth/callback", methods=["GET"])
def oauth_callback():
    state = session.get("oauth_state")
    if not state:
        return jsonify({"error": "Missing OAuth state in session"}), 400

    flow = _create_oauth_flow(state=state)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    _save_credentials_to_session(creds)

    # Resolve basic user identity for display.
    oauth2 = build("oauth2", "v2", credentials=creds, cache_discovery=False)
    user_info = oauth2.userinfo().get().execute()
    session["user_email"] = user_info.get("email", "")

    return redirect(url_for("webapp_home"))


@app.route("/oauth/logout", methods=["GET"])
def oauth_logout():
    session.pop("google_credentials", None)
    session.pop("user_email", None)
    session.pop("oauth_state", None)
    return redirect(url_for("webapp_home"))


@app.route("/oauth/analyze-inbox", methods=["POST"])
def oauth_analyze_inbox():
    creds = _credentials_from_session()
    if not creds:
        return jsonify({"error": "Not connected. Please connect Gmail first."}), 401

    data = request.get_json(silent=True) or {}
    keywords = _default_keywords_for_request(data)

    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    message_refs = (
        gmail.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=30)
        .execute()
        .get("messages", [])
    )

    if not message_refs:
        return jsonify({"summary": {"total": 0, "spam": 0, "safe": 0}, "results": []})

    results = []
    spam_count = 0
    safe_count = 0

    for ref in message_refs:
        message = (
            gmail.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        payload = message.get("payload") or {}
        headers = payload.get("headers") or []
        subject = _extract_header(headers, "Subject")
        sender = _extract_header(headers, "From")
        text = (subject + "\n\n" + _extract_message_text(message)).strip()

        if not text:
            continue

        prediction = _classify_text(text, keywords)
        if prediction["spam"] == 1:
            spam_count += 1
        else:
            safe_count += 1

        results.append(
            {
                "subject": subject,
                "from": sender,
                "label": prediction["label"],
                "confidence": prediction["confidence"],
                "keyword_matches": prediction["keyword_matches"],
            }
        )

    return jsonify(
        {
            "summary": {"total": len(results), "spam": spam_count, "safe": safe_count},
            "results": results,
            "user_email": session.get("user_email", ""),
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/keywords", methods=["GET"])
def get_keywords():
    return jsonify({"keywords": _load_default_keywords()})

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Missing or empty 'text'"}), 400

    keywords = _default_keywords_for_request(data)
    result = _classify_text(text, keywords)

    return jsonify(
        {
            "spam": result["spam"],
            "spam_score": result["spam_score"],
            "keyword_matches": result["keyword_matches"],
            "keyword_override": result["keyword_override"],
        }
    )


@app.route("/addon/predict", methods=["POST"])
def addon_predict():
    """Predict endpoint tailored for Gmail Add-on card rendering."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Missing or empty 'text'"}), 400

    keywords = _default_keywords_for_request(data)
    result = _classify_text(text, keywords)

    return jsonify(
        {
            "spam": result["spam"],
            "label": result["label"],
            "spam_score": result["spam_score"],
            "confidence": result["confidence"],
            "threshold": SPAM_THRESHOLD,
            "keyword_matches": result["keyword_matches"],
            "keyword_override": result["keyword_override"],
        }
    )


@app.route("/addon/predict-batch", methods=["POST"])
def addon_predict_batch():
    """Batch prediction endpoint for inbox analysis in Gmail add-on."""
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []

    if not isinstance(items, list) or not items:
        return jsonify({"error": "Missing or empty 'items'"}), 400

    normalized_items = []
    texts = []
    for item in items[:30]:
        subject = str((item or {}).get("subject") or "")
        text = str((item or {}).get("text") or "").strip()
        if not text:
            continue
        normalized_items.append({"subject": subject})
        texts.append(text)

    if not texts:
        return jsonify({"error": "No valid texts found in items"}), 400

    keywords = _default_keywords_for_request(data)

    results = []
    spam_count = 0
    safe_count = 0

    for idx, text in enumerate(texts):
        prediction = _classify_text(text, keywords)

        if prediction["spam"] == 1:
            spam_count += 1
        else:
            safe_count += 1

        results.append(
            {
                "subject": normalized_items[idx]["subject"],
                "spam": prediction["spam"],
                "label": prediction["label"],
                "spam_score": prediction["spam_score"],
                "confidence": prediction["confidence"],
                "keyword_matches": prediction["keyword_matches"],
                "keyword_override": prediction["keyword_override"],
            }
        )

    return jsonify(
        {
            "summary": {
                "total": len(results),
                "spam": spam_count,
                "safe": safe_count,
            },
            "results": results,
            "threshold": SPAM_THRESHOLD,
        }
    )

if __name__ == "__main__":
    app.run()