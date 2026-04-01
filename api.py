from flask import Flask, request, jsonify
import os
import pickle

app = Flask(__name__)


def _load_pickle(primary_name, fallback_name):
    """Load a pickle file using primary filename, then fallback filename."""
    file_to_load = primary_name if os.path.exists(primary_name) else fallback_name
    with open(file_to_load, "rb") as f:
        return pickle.load(f)


# Load model assets. Supports both old and current filenames.
model = _load_pickle("spam_model.pkl", "model.pkl")
vectorizer = _load_pickle("vectorizer_spam.pkl", "vectorizer.pkl")

@app.route("/")
def home():
    return "API is running"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Missing or empty 'text'"}), 400

    # transform input
    transformed = vectorizer.transform([text])

    # predict
    prediction = model.predict(transformed)[0]

    return jsonify({"spam": int(prediction)})


@app.route("/addon/predict", methods=["POST"])
def addon_predict():
    """Predict endpoint tailored for Gmail Add-on card rendering."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Missing or empty 'text'"}), 400

    transformed = vectorizer.transform([text])
    prediction = int(model.predict(transformed)[0])

    confidence = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(transformed)[0]
        confidence = float(max(probabilities))

    return jsonify(
        {
            "spam": prediction,
            "label": "Spam" if prediction == 1 else "Not Spam",
            "confidence": confidence,
        }
    )

if __name__ == "__main__":
    app.run()