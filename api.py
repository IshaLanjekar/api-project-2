from flask import Flask, request, jsonify
import pickle

# ✅ FIRST create app
app = Flask(__name__)

# ✅ THEN load model
model = pickle.load(open("spam_model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer_spam.pkl", "rb"))

# ✅ THEN routes
@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    email_text = data.get("text")
    keywords = data.get("keywords", [])

    transformed = vectorizer.transform([email_text])
    prediction = model.predict(transformed)[0]

    keyword_match = any(word.lower() in email_text.lower() for word in keywords)

    return jsonify({
        "spam": int(prediction),
        "keyword_match": keyword_match
    })

# ✅ LAST run app
if __name__ == "__main__":
    app.run(debug=True)