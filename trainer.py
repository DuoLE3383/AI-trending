# trainer.py
import logging
import sqlite3
import numpy as np
import tensorflow as tf
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "trend_analysis.db"  # Hoặc config.SQLITE_DB_PATH

def fetch_recent_signals(db_path: str):
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT 
                    ema_fast_val, ema_medium_val, ema_slow_val, 
                    rsi_val, bbands_lower, bbands_middle, bbands_upper, 
                    atr_val, entry_price, stop_loss, take_profit_1,
                    status
                FROM trend_analysis 
                WHERE analysis_timestamp_utc >= ? 
                  AND status IN ('TP1_HIT', 'SL_HIT')
            """, (since,)).fetchall()
        return rows
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return []

def prepare_data(rows):
    X = []
    y = []

    for row in rows:
        features = [
            row["ema_fast_val"], row["ema_medium_val"], row["ema_slow_val"],
            row["rsi_val"], row["bbands_lower"], row["bbands_middle"], row["bbands_upper"],
            row["atr_val"], row["entry_price"], row["stop_loss"], row["take_profit_1"]
        ]
        if None in features:
            continue  # Bỏ qua nếu có giá trị thiếu
        X.append(features)
        y.append(1 if row["status"] == "TP1_HIT" else 0)

    return np.array(X), np.array(y)

def build_model(input_shape):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=input_shape),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')  # binary classification
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def train_model():
    rows = fetch_recent_signals(DB_PATH)
    if not rows:
        logger.info("Không có dữ liệu mới để huấn luyện.")
        return

    X, y = prepare_data(rows)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_val, y_train, y_val = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    model = build_model(input_shape=(X.shape[1],))
    model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=20, batch_size=8, verbose=1)

    # ✅ Save model và scaler nếu cần
    model.save("trained_model.h5")
    logger.info("🎉 Model saved as trained_model.h5")

if __name__ == "__main__":
    train_model()
