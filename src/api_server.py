import sqlite3
import logging
import os # NEW: Import the os module for path handling
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt, get_jwt_identity
from functools import wraps

# --- CORRECTED DATABASE PATH LOGIC ---
# This ensures the server always looks for the database in its own directory,
# preventing path-related errors.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'trading_bot.db')

class MockConfig:
    SQLITE_DB_PATH = DB_PATH # Use the robust, absolute path
config = MockConfig()

def get_performance_stats():
    return {'win_rate': 65.5, 'total_completed_trades': 120, 'wins': 78, 'losses': 42}
# --- End of Mock ---


app = Flask(__name__)

# --- JWT Configuration ---
app.config["JWT_SECRET_KEY"] = "a-super-secret-key-that-is-long-and-random-for-admin" 
jwt = JWTManager(app)

# Enable CORS for all routes
CORS(app) 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Decorator for Admin-Only Routes ---
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") == "admin":
                return fn(*args, **kwargs)
            else:
                return jsonify(msg="Admins only!"), 403
        return decorator
    return wrapper

def get_db_connection():
    # This now connects to the database using the absolute path.
    conn = sqlite3.connect(config.SQLITE_DB_PATH, uri=True) 
    conn.row_factory = sqlite3.Row
    return conn

# --- Login Endpoint ---
@app.route('/api/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        additional_claims = {"role": user["role"]}
        access_token = create_access_token(identity=username, additional_claims=additional_claims)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Bad username or password"}), 401

# --- NEW: Public Registration Endpoint ---
@app.route('/api/register', methods=['POST'])
def register():
    """Creates a new user with a 'user' role."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    # New users created via this public endpoint always get the 'user' role
    role = 'user' 

    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hashed_password, role)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"msg": f"User '{username}' already exists"}), 409 # Conflict
    finally:
        if conn:
            conn.close()

    return jsonify({"msg": f"User '{username}' created successfully"}), 201


# --- Admin User Management Endpoints ---
@app.route('/api/admin/users', methods=['GET'])
@admin_required()
def get_all_users():
    """Returns a list of all users (excluding passwords)."""
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, role FROM users').fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])

@app.route('/api/admin/users', methods=['POST'])
@admin_required()
def create_user_by_admin():
    """Creates a new user (admin can specify role)."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400
    if role not in ['admin', 'user']:
        return jsonify({"msg": "Invalid role specified"}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hashed_password, role)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"msg": f"User '{username}' already exists"}), 409
    finally:
        if conn:
            conn.close()
    return jsonify({"msg": f"User '{username}' created successfully by admin"}), 201

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required()
def delete_user(user_id):
    """Deletes a user by their ID."""
    current_user_identity = get_jwt_identity()
    conn = get_db_connection()
    user_to_delete = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if user_to_delete and user_to_delete['username'] == current_user_identity:
        conn.close()
        return jsonify({"msg": "You cannot delete your own account."}), 403

    if not user_to_delete:
        conn.close()
        return jsonify({"msg": "User not found."}), 404

    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"msg": f"User with ID {user_id} deleted."}), 200


# --- Protected Data Endpoints ---
@app.route('/api/stats', methods=['GET'])
@jwt_required()
def get_stats():
    stats = get_performance_stats()
    return jsonify(stats)

@app.route('/api/trades', methods=['GET'])
@jwt_required()
def get_trades():
    status_filter = request.args.get('status', 'all')
    limit = request.args.get('limit', 20, type=int)
    # Placeholder for brevity
    return jsonify([]) 


if __name__ == '__main__':
    # REMINDER: You must run the `create_user_db.py` script once
    # to create the database file and table before starting this server.
    logger.info("🚀 Starting Flask API server with Admin and Register features...")
    app.run(host='0.0.0.0', port=8080, debug=False)
