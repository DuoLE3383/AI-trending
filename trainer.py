# trainer.py (Phiên bản cải thiện với các bước kiểm tra dữ liệu bổ sung)
import logging
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import config

logger = logging.getLogger(__name__)

def train_model() -> float | None:
    """
    Huấn luyện model và trả về độ chính xác (accuracy) trên tập test.
    Trả về None nếu có lỗi hoặc không đủ dữ liệu hợp lệ.
    """
    logger.info("🚀 Training ML model using scikit-learn...")

    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            query = "SELECT ema_fast_val, ema_medium_val, ema_slow_val, rsi_val, atr_val, bbands_lower, bbands_middle, bbands_upper, trend FROM trend_analysis WHERE status != 'ACTIVE'"
            df = pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"❌ Failed to load data for training: {e}", exc_info=True)
        return None

    if df.empty:
        logger.warning("⚠️ No completed trades found in the database. Skipping training.")
        return None

    features = [
        'ema_fast_val', 'ema_medium_val', 'ema_slow_val',
        'rsi_val', 'atr_val',
        'bbands_lower', 'bbands_middle', 'bbands_upper'
    ]
    target = 'trend'
    
    df.dropna(subset=features + [target], inplace=True)

    if len(df) < 10: # Cần có đủ dữ liệu để huấn luyện một cách có ý nghĩa
        logger.warning(f"⚠️ Not enough clean data to train model. Only {len(df)} rows available. Minimum 50 required.")
        return None

    X = df[features]
    y = df[target]

    # CẢI THIỆN: Kiểm tra xem có đủ lớp để phân loại không
    if y.nunique() < 2:
        logger.warning(f"⚠️ Training data contains only one class ('{y.unique()[0]}'). Cannot train a classifier. Skipping.")
        return None

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    # test_size=0.2 yêu cầu ít nhất 2 mẫu cho mỗi lớp khi dùng stratify
    if any(count < 2 for count in pd.Series(y_encoded).value_counts()):
        logger.warning("⚠️ Each class must have at least 2 samples for stratified split. Skipping training.")
        return None

    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded)

    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    joblib.dump(model, "model_trend.pkl")
    joblib.dump(label_encoder, "trend_label_encoder.pkl")
    joblib.dump(features, "model_features.pkl")

    accuracy = model.score(X_test, y_test)
    logger.info(f"✅ Model trained successfully. Accuracy on test set: {accuracy:.2%}")
    
    return accuracy
