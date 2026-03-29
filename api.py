from flask import Flask, request, jsonify
import pickle
import re
import nltk
from nltk.corpus import stopwords

# Download stopwords (only first time)
nltk.download('stopwords')

app = Flask(__name__)

# Load your trained models
spam_model = pickle.load(open("spam_model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer_spam.pkl", "rb"))
category_model = pickle.load(open("category_model.pkl", "rb"))

# Stopwords
_stop_words = set(stopwords.words('english'))

# Text cleaning function (same as your Streamlit app)
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z]', ' ', text)
    words = text.split()
    words = [w for w in words if w not in _stop_words]
    return " ".join(words)

# Keyword matching (your main feature ⭐)
def check_keyword_importance(text, user_keywords):
    text = text.lower()
    matched = [kw for kw in user_keywords if kw.lower() in text]
    if matched:
        return True, matched
    return False, []

# MAIN API ENDPOINT
@app.route('/analyze-email', methods=['POST'])
def analyze_email():
    data = request.json

    subject = data.get('subject', '')
    body = data.get('body', '')
    user_keywords = data.get('userKeywords', [])

    text = subject + " " + body
    cleaned = clean_text(text)

    vec = vectorizer.transform([cleaned])

    # ML prediction
    prediction = spam_model.predict(vec)[0]
    confidence = spam_model.predict_proba(vec)[0]

    spam_score = confidence[1] * 100

    # Category prediction
    try:
        category = category_model.predict(vec)[0]
    except:
        category = "general"

    # ⭐ Your main feature (keyword override)
    keyword_matched, matched_words = check_keyword_importance(text, user_keywords)

    safe = False
    if keyword_matched:
        safe = True

    return jsonify({
        "spamScore": round(spam_score, 2),
        "prediction": "Spam" if prediction == 1 else "Not Spam",
        "category": category,
        "keywordMatched": keyword_matched,
        "matchedKeywords": matched_words,
        "safe": safe
    })

# Run server
if __name__ == '__main__':
    app.run(port=5000)