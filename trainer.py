# trainer.py

import logging
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import config

logger = logging.getLogger(__name__)

def train_model() -> float | None: # Thêm gợi ý type hint cho giá trị trả về
    """
    Huấn luyện model và trả về độ chính xác (accuracy) trên tập test.
    Trả về None nếu có lỗi hoặc không đủ dữ liệu.
    """
    logger.info("🚀 Training ML model using scikit-learn...")

    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            query = "SELECT ema_fast_val, ema_medium_val, ema_slow_val, rsi_val, atr_val, bbands_lower, bbands_middle, bbands_upper, trend FROM trend_analysis WHERE status != 'ACTIVE'"
            df = pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Failed to load data for training: {e}", exc_info=True)
        return None

    if df.empty:
        logger.warning("⚠️ No completed trades found to train the model.")
        return None

    features = [
        'ema_fast_val', 'ema_medium_val', 'ema_slow_val',
        'rsi_val', 'atr_val',
        'bbands_lower', 'bbands_middle', 'bbands_upper'
    ]
    target = 'trend'
    
    df = df.dropna(subset=features + [target])

    if len(df) < 50:
        logger.warning(f"⚠️ Not enough clean data to train model. Only {len(df)} rows available.")
        return None

    X = df[features]
    y = df[target]

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded)

    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    joblib.dump(model, "model_trend.pkl")
    joblib.dump(label_encoder, "trend_label_encoder.pkl")
    joblib.dump(features, "model_features.pkl")

    accuracy = model.score(X_test, y_test)
    logger.info(f"✅ Model trained successfully. Accuracy on test set: {accuracy:.2%}")
    
    # CẬP NHẬT QUAN TRỌNG: Trả về giá trị accuracy
    return accuracy