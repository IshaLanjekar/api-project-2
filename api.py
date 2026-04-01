from flask import Flask, request, jsonify
import pickle

app = Flask(__name__)

# load model and vectorizer
model = pickle.load(open("model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer.pkl", "rb"))

@app.route("/")
def home():
    return "API is running"

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()
    text = data.get("text")

    # transform input
    transformed = vectorizer.transform([text])

    # predict
    prediction = model.predict(transformed)[0]

    return jsonify({
        "spam": int(prediction)
    })

if __name__ == "__main__":
    app.run()