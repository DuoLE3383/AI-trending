# trainer.py (Phiên bản nâng cấp với Data Balancing và Target thực tế)
import logging
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report # CẬP NHẬT: Thêm thư viện để báo cáo chi tiết
import joblib
from . import config as config

logger = logging.getLogger(__name__)

def train_model() -> float | None:
    """
    Huấn luyện model dựa trên kết quả WIN/LOSS thực tế và trả về độ chính xác (accuracy).
    Sử dụng kỹ thuật cân bằng dữ liệu (undersampling).
    Trả về None nếu có lỗi hoặc không đủ dữ liệu hợp lệ.
    """
    logger.info("🚀 Starting Advanced Model Training...")
    
    if df.empty:
        logger.warning("Training data is empty. Skipping training.")
        return None # Trả về None để báo hiệu không huấn luyện

    logger.info(f"Loaded {df.shape[0]} records for training.")
    logger.info("Data types and non-null counts:\n" + str(df.info()))
    
    # Thay 'outcome' bằng tên cột kết quả thực tế của bạn (ví dụ: 'signal', 'target')
    outcome_col = 'outcome' 
    if outcome_col in df.columns:
        logger.info(f"Value counts for '{outcome_col}' column:\n" + str(df[outcome_col].value_counts()))
        # Kiểm tra nếu chỉ có 1 loại kết quả
        if df[outcome_col].nunique() < 2:
            logger.error(f"Training failed: Only one class ('{df[outcome_col].unique()[0]}') found in the outcome column. Cannot train.")
            return None
    else:
        logger.error(f"Training failed: The outcome column '{outcome_col}' was not found in the training data!")
        return None

    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            # CẢI TIẾN: Lấy tất cả các giao dịch đã đóng (status != 'ACTIVE')
            # và bao gồm cả pnl_percentage để xác định kết quả một cách chính xác.
            query = """
            SELECT 
                ema_fast_val, ema_medium_val, ema_slow_val, 
                rsi_val, atr_val, 
                bbands_lower, bbands_middle, bbands_upper, 
                trend,
                status,
                pnl_percentage
            FROM trend_analysis
            WHERE 
                status != 'ACTIVE' 
                AND pnl_percentage IS NOT NULL 
                AND trend IS NOT NULL
            """
            df = pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"❌ Failed to load data for training: {e}", exc_info=True)
        return None

    if df.empty:
        logger.warning("⚠️ No completed WIN/LOSS trades found. Skipping training.")
        return None

    # CẢI TIẾN: Tạo cột 'outcome' một cách linh hoạt trong Python.
    # Một giao dịch là 'WIN' nếu nó chạm TP hoặc có PnL > 0.
    df['outcome'] = df.apply(
        lambda row: 'WIN' if ('TP' in row['status'] or row['pnl_percentage'] > 0) else 'LOSS',
        axis=1
    )
    # CẬP NHẬT: Danh sách features ban đầu, 'trend' giờ là một feature
    initial_features = [
        'ema_fast_val', 'ema_medium_val', 'ema_slow_val',
        'rsi_val', 'atr_val',
        'bbands_lower', 'bbands_middle', 'bbands_upper',
        'trend' 
    ]
    target = 'outcome' # CẬP NHẬT: Mục tiêu dự đoán là 'outcome'

    df.dropna(subset=initial_features + [target], inplace=True)

    if len(df) < 50: # Đặt một ngưỡng tối thiểu cao hơn cho dữ liệu sạch
        logger.warning(f"⚠️ Not enough clean data. Only {len(df)} rows. Minimum 50 required.")
        return None

    # CẬP NHẬT: Logic cân bằng dữ liệu (Undersampling)
    logger.info("⚖️ Balancing data using Undersampling...")
    df_wins = df[df[target] == 'WIN']
    df_losses = df[df[target] == 'LOSS']

    if df_wins.empty or df_losses.empty:
        logger.warning(f"⚠️ Training data needs both WIN and LOSS samples. Skipping.")
        return None

    min_samples = min(len(df_wins), len(df_losses))
    logger.info(f"Balancing to {min_samples} WINs and {min_samples} LOSSes.")
    
    df_balanced = pd.concat([
        df_wins.sample(n=min_samples, random_state=42),
        df_losses.sample(n=min_samples, random_state=42)
    ])

    # CẬP NHẬT: Xử lý feature 'trend' (dạng text) bằng One-Hot Encoding
    X_pre_process = df_balanced[initial_features]
    y = df_balanced[target]
    
    X = pd.get_dummies(X_pre_process, columns=['trend'], drop_first=True)
    
    # Lưu lại danh sách features cuối cùng sau khi xử lý
    final_features = X.columns.tolist()

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    
    # Vì đã cân bằng, stratify không còn quá quan trọng nhưng vẫn nên giữ
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded)

    logger.info("🤖 Fitting RandomForestClassifier model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, class_weight='balanced')
    model.fit(X_train, y_train)

    # Lưu model và các thành phần cần thiết
    joblib.dump(model, "model_trend.pkl")
    joblib.dump(label_encoder, "trend_label_encoder.pkl")
    joblib.dump(final_features, "model_features.pkl") # CẬP NHẬT: Lưu danh sách feature cuối cùng

    accuracy = model.score(X_test, y_test)
    logger.info(f"✅ Model trained successfully. Accuracy on test set: {accuracy:.2%}")

    # CẬP NHẬT: In báo cáo chi tiết
    logger.info("📊 Classification Report on Test Set:")
    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=label_encoder.classes_)
    print(report) # In ra console để xem
    logger.info(f"\n{report}")
    
    return accuracy
