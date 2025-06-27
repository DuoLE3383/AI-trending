# api_server.py
import sqlite3
import logging
from flask import Flask, jsonify
from flask_cors import CORS
import config # Import config để lấy đường dẫn DB
from performance_analyzer import get_performance_stats # Import hàm tính toán đã có

# --- Cấu hình ---
# Tạo một Flask app
app = Flask(__name__)
# Kích hoạt CORS để React app có thể gọi API từ một domain khác (khi phát triển)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Tạo kết nối đến database SQLite."""
    conn = sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row # Giúp truy cập dữ liệu theo tên cột
    return conn

# --- Định nghĩa các API Endpoints ---

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Endpoint cung cấp các số liệu thống kê tổng quan.
    Ví dụ: http://127.0.0.1:5000/api/stats
    """
    try:
        stats = get_performance_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu thống kê: {e}")
        return jsonify({"error": "Không thể lấy dữ liệu thống kê"}), 500


@app.route('/api/trades', methods=['GET'])
def get_trades():
    """
    Endpoint cung cấp danh sách các giao dịch.
    Lọc theo status: ?status=active hoặc ?status=closed
    Lấy giới hạn: ?limit=10
    Ví dụ: http://127.0.0.1:5000/api/trades?status=closed&limit=15
    """
    from flask import request
    status_filter = request.args.get('status', 'all')
    limit = request.args.get('limit', 20, type=int)

    query = "SELECT * FROM trend_analysis"
    
    if status_filter == 'active':
        query += " WHERE status = 'ACTIVE'"
    elif status_filter == 'closed':
        query += " WHERE status != 'ACTIVE'"
    
    query += " ORDER BY analysis_timestamp_utc DESC LIMIT ?"

    try:
        conn = get_db_connection()
        trades = conn.execute(query, (limit,)).fetchall()
        conn.close()
        # Chuyển đổi kết quả thành list of dicts
        trades_list = [dict(row) for row in trades]
        return jsonify(trades_list)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách giao dịch: {e}")
        return jsonify({"error": "Không thể lấy danh sách giao dịch"}), 500

# --- Chạy Server ---
from flask import Flask
from flask_cors import CORS # <--- 1. Import thư viện

# ... (các import khác)

app = Flask(__name__)
CORS(app) # <--- 2. Kích hoạt CORS cho toàn bộ ứng dụng

# --- Chạy Flask server ---

if __name__ == '__main__':
    logger.info("🚀 Starting Flask API server for Trading Bot Dashboard...")
    # Chạy server ở địa chỉ 127.0.0.1 (localhost) và cổng 5000
    app.run(host='0.0.0.0', port=5000, debug=True)

