import logging
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import config

logger = logging.getLogger(__name__)

def train_model():
    logger.info("🚀 Training ML model using scikit-learn...")

    # Load data từ SQLite
    conn = sqlite3.connect(config.SQLITE_DB_PATH)
    df = pd.read_sql("SELECT * FROM trend_analysis WHERE status != 'ACTIVE'", conn)
    conn.close()

    if df.empty:
        logger.warning("⚠️ No completed trades found to train the model.")
        return

    # Chuẩn hóa dữ liệu
    features = [
        'ema_fast_val', 'ema_medium_val', 'ema_slow_val',
        'rsi_val', 'atr_val',
        'bbands_lower', 'bbands_middle', 'bbands_upper',
        'entry_price', 'stop_loss', 'take_profit_1'
    ]
    df = df.dropna(subset=features + ['trend'])

    X = df[features]
    y = df['trend']

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    # Huấn luyện mô hình
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Lưu mô hình
    joblib.dump(model, "model_trend.pkl")
    joblib.dump(label_encoder, "trend_label_encoder.pkl")

    accuracy = model.score(X_test, y_test)
    logger.info(f"✅ Model trained successfully. Accuracy: {accuracy:.2%}")
