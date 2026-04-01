import argparse
import csv
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split


def _normalize_label(raw_label):
    value = str(raw_label).strip().lower()
    if value in {"1", "spam", "true", "yes"}:
        return 1
    if value in {"0", "ham", "not spam", "false", "no"}:
        return 0
    try:
        return 1 if int(float(value)) == 1 else 0
    except ValueError as exc:
        raise ValueError(f"Unsupported label value: {raw_label}") from exc


def load_dataset(csv_path):
    texts = []
    labels = []

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"text", "label"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("CSV must contain columns: text,label")

        for row in reader:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            label = _normalize_label(row.get("label", ""))
            texts.append(text)
            labels.append(label)

    if not texts:
        raise ValueError("No valid rows found in dataset")

    return texts, labels


def train_and_save(dataset_path, model_out, vectorizer_out, test_size, random_state):
    texts, labels = load_dataset(dataset_path)

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_features=50000,
    )

    x_train_vec = vectorizer.fit_transform(x_train)
    x_test_vec = vectorizer.transform(x_test)

    model = LogisticRegression(
        class_weight="balanced",
        max_iter=2000,
        random_state=random_state,
    )
    model.fit(x_train_vec, y_train)

    predictions = model.predict(x_test_vec)
    accuracy = accuracy_score(y_test, predictions)

    print(f"Rows used: {len(texts)}")
    print(f"Train rows: {len(x_train)} | Test rows: {len(x_test)}")
    print(f"Accuracy: {accuracy:.4f}")
    print("\nClassification report:")
    print(classification_report(y_test, predictions, digits=4))

    with open(model_out, "wb") as f:
        pickle.dump(model, f)

    with open(vectorizer_out, "wb") as f:
        pickle.dump(vectorizer, f)

    print(f"Saved model to: {model_out}")
    print(f"Saved vectorizer to: {vectorizer_out}")


def main():
    parser = argparse.ArgumentParser(description="Train spam classifier and save pickle files")
    parser.add_argument("--dataset", default="test_training_data.csv", help="Path to CSV file")
    parser.add_argument("--model-out", default="spam_model.pkl", help="Output model pickle path")
    parser.add_argument(
        "--vectorizer-out",
        default="vectorizer_spam.pkl",
        help="Output vectorizer pickle path",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split ratio")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    train_and_save(
        dataset_path=str(dataset_path),
        model_out=args.model_out,
        vectorizer_out=args.vectorizer_out,
        test_size=args.test_size,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    main()
