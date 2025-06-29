# api_server.py
import sqlite3
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
import main.src.config as config # Import config để lấy đường dẫn DB
from performance_analyzer import get_performance_stats # Import hàm tính toán đã có
# --- Chạy Server ---
app = Flask(__name__)
# Kích hoạt CORS để React app có thể gọi API từ một domain khác (khi phát triển)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row # Giúp truy cập dữ liệu theo tên cột
    return conn

# --- Định nghĩa các API Endpoints ---

@app.route('/')
def index():
    """Endpoint gốc để kiểm tra server có đang chạy không."""
    logger.info("Health check endpoint was hit.")
    return jsonify({
        "message": "Welcome to the Trading Bot API!",
        "status": "ok",
        "available_endpoints": [
            "/api/stats",
            "/api/trades"
        ]
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    logger.info(f"API request received for /api/stats from {request.remote_addr}")
    try:
        stats = get_performance_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu thống kê: {e}")
        return jsonify({"error": "Không thể lấy dữ liệu thống kê"}), 500


@app.route('/api/trades', methods=['GET'])
def get_trades():
    logger.info(f"API request received for /api/trades from {request.remote_addr} with params: {request.args}")
    status_filter = request.args.get('status', 'all')
    limit = request.args.get('limit', 20, type=int)

    query = "SELECT * FROM trend_analysis"
    params = []
    
    # Xây dựng mệnh đề WHERE một cách an toàn
    if status_filter == 'active':
        query += " WHERE status = ?"
        params.append('ACTIVE')
    elif status_filter == 'closed':
        query += " WHERE status != ?"
        params.append('ACTIVE')
    
    query += " ORDER BY analysis_timestamp_utc DESC LIMIT ?"
    params.append(limit)

    conn = None
    try:
        conn = get_db_connection()
        trades = conn.execute(query, tuple(params)).fetchall()
        # Chuyển đổi kết quả thành list of dicts
        trades_list = [dict(row) for row in trades]
        return jsonify(trades_list)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách giao dịch: {e}")
        return jsonify({"error": "Không thể lấy danh sách giao dịch"}), 500
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    logger.info("🚀 Starting Flask API server for Trading Bot Dashboard (standalone mode)...")
    # Chạy server ở địa chỉ 127.0.0.1 (localhost) và cổng 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
