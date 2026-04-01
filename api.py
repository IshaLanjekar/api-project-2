from flask import Flask, request, jsonify
import json
import os
import pickle

app = Flask(__name__)
SPAM_THRESHOLD = float(os.getenv("SPAM_THRESHOLD", "0.5"))
KEYWORDS_FILE = "user_keywords.json"


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


# Load model assets. Supports both old and current filenames.
model = _load_pickle("spam_model.pkl", "model.pkl")
vectorizer = _load_pickle("vectorizer_spam.pkl", "vectorizer.pkl")

@app.route("/")
def home():
    return "API is running"


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

    # transform input
    transformed = vectorizer.transform([text])

    spam_score = None
    if hasattr(model, "predict_proba"):
        spam_score = float(model.predict_proba(transformed)[0][1])
        prediction = 1 if spam_score >= SPAM_THRESHOLD else 0
    else:
        prediction = int(model.predict(transformed)[0])

    keywords = sorted(set(_load_default_keywords() + _extract_request_keywords(data)))
    keyword_matches = _find_keyword_matches(text, keywords)
    prediction, keyword_override = _apply_keyword_rule(prediction, spam_score, keyword_matches)

    return jsonify(
        {
            "spam": int(prediction),
            "spam_score": spam_score,
            "keyword_matches": keyword_matches,
            "keyword_override": keyword_override,
        }
    )


@app.route("/addon/predict", methods=["POST"])
def addon_predict():
    """Predict endpoint tailored for Gmail Add-on card rendering."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Missing or empty 'text'"}), 400

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

    keywords = sorted(set(_load_default_keywords() + _extract_request_keywords(data)))
    keyword_matches = _find_keyword_matches(text, keywords)
    prediction, keyword_override = _apply_keyword_rule(prediction, spam_score, keyword_matches)

    return jsonify(
        {
            "spam": prediction,
            "label": "Spam" if prediction == 1 else "Not Spam",
            "spam_score": spam_score,
            "confidence": confidence,
            "threshold": SPAM_THRESHOLD,
            "keyword_matches": keyword_matches,
            "keyword_override": keyword_override,
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

    transformed = vectorizer.transform(texts)

    use_proba = hasattr(model, "predict_proba")
    probabilities = model.predict_proba(transformed) if use_proba else None
    base_predictions = model.predict(transformed)

    keywords = sorted(set(_load_default_keywords() + _extract_request_keywords(data)))

    results = []
    spam_count = 0
    safe_count = 0

    for idx, text in enumerate(texts):
        spam_score = float(probabilities[idx][1]) if use_proba else None
        confidence = float(max(probabilities[idx])) if use_proba else None
        prediction = int(base_predictions[idx])

        if use_proba:
            prediction = 1 if spam_score >= SPAM_THRESHOLD else 0

        keyword_matches = _find_keyword_matches(text, keywords)
        prediction, keyword_override = _apply_keyword_rule(prediction, spam_score, keyword_matches)

        if prediction == 1:
            spam_count += 1
        else:
            safe_count += 1

        results.append(
            {
                "subject": normalized_items[idx]["subject"],
                "spam": prediction,
                "label": "Spam" if prediction == 1 else "Not Spam",
                "spam_score": spam_score,
                "confidence": confidence,
                "keyword_matches": keyword_matches,
                "keyword_override": keyword_override,
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