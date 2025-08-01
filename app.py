import os
import pandas as pd
import numpy as np
from flask import Flask, request, render_template
from sklearn.model_selection import KFold
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_data(df):
    # Check if dataset has at least one feature and one target column
    if df.shape[1] < 2:
        raise ValueError("Dataset must have at least one feature and one target column.")

    # Fill numeric missing values with mean and then others with empty string
    df.fillna(df.mean(numeric_only=True), inplace=True)
    df.fillna('', inplace=True)

    label_encoders = {}
    for column in df.select_dtypes(include=['object']).columns:
        le = LabelEncoder()
        df[column] = le.fit_transform(df[column].astype(str))
        label_encoders[column] = le

    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]

    # Check if target appears continuous (numeric with many unique values) and discretize it
    if pd.api.types.is_numeric_dtype(y) and y.nunique() > 10:
        # Using quantile-based discretization into 4 bins
        y = pd.qcut(y, q=4, labels=False, duplicates='drop')

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, y.values, df

def evaluate_model(model, X, y):
    if len(y) < 2:
        raise ValueError("Dataset must have at least 2 samples for evaluation.")
    # Use number of splits equal to min(5, number of samples)
    n_splits = 5 if len(y) >= 5 else len(y)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)

    acc_scores = []
    prec_scores = []
    rec_scores = []
    f1_scores = []

    for train_index, test_index in kf.split(X):
        X_train, X_test = X[train_index], X[test_index]
        y_train, y_test = y[train_index], y[test_index]

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        acc_scores.append(accuracy_score(y_test, y_pred))
        prec_scores.append(precision_score(y_test, y_pred, average='weighted', zero_division=0))
        rec_scores.append(recall_score(y_test, y_pred, average='weighted', zero_division=0))
        f1_scores.append(f1_score(y_test, y_pred, average='weighted'))

    return {
        'accuracy': round(np.mean(acc_scores) * 100, 2),
        'precision': round(np.mean(prec_scores) * 100, 2),
        'recall': round(np.mean(rec_scores) * 100, 2),
        'f1_score': round(np.mean(f1_scores) * 100, 2)
    }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return "No file uploaded!"

    file = request.files['file']

    if file.filename == '':
        return "No file selected!"

    if file and allowed_file(file.filename):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            df = pd.read_csv(filepath)
            X, y, processed_df = preprocess_data(df)
        except Exception as e:
            return f"Error processing file: {e}"

        models = {
            'Logistic Regression': LogisticRegression(max_iter=1000),
            'Decision Tree': DecisionTreeClassifier(),
            'Random Forest': RandomForestClassifier(),
            'Support Vector Machine': SVC(),
            'K-Nearest Neighbors': KNeighborsClassifier(),
            'Naive Bayes': GaussianNB()
        }

        results = []
        feature_importance = {}

        for model_name, model in models.items():
            try:
                metrics = evaluate_model(model, X, y)
                results.append({'model': model_name, **metrics})
                if hasattr(model, 'feature_importances_'):
                    model.fit(X, y)
                    feature_importance[model_name] = model.feature_importances_
            except Exception as e:
                # If a model evaluation fails, record the error and continue
                results.append({'model': model_name,
                                'accuracy': 0,
                                'precision': 0,
                                'recall': 0,
                                'f1_score': 0})
                print(f"Error evaluating {model_name}: {e}")

        feature_names = processed_df.columns[:-1]

        dataset_info = {
            'shape': processed_df.shape,
            'missing_values': processed_df.isnull().sum().to_dict(),
            'data_types': processed_df.dtypes.apply(str).to_dict()
        }

        chart_data = {
            'models': [r['model'] for r in results],
            'accuracies': [r['accuracy'] for r in results]
        }

        return render_template('results.html',
                               results=results,
                               feature_importance=feature_importance,
                               feature_names=feature_names,
                               dataset_info=dataset_info,
                               chart_data=chart_data,
                               enumerate=enumerate)
    else:
        return "Invalid file type. Only CSV files are allowed!"

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
