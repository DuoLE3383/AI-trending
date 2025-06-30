import sqlite3
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt, get_jwt_identity
from functools import wraps

# Assuming these are in the same directory or a sub-module
# You might need to adjust imports based on your project structure
# from . import config
# from .performance_analyzer import get_performance_stats

# --- Mocked config and functions for standalone execution ---
class MockConfig:
    SQLITE_DB_PATH = 'trading_bot.db'
config = MockConfig()

def get_performance_stats():
    # In a real scenario, this would calculate stats.
    return {'win_rate': 65.5, 'total_completed_trades': 120, 'wins': 78, 'losses': 42}
# --- End of Mock ---


app = Flask(__name__)

# --- JWT Configuration ---
# IMPORTANT: Change this secret key in a real application!
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
    conn = sqlite3.connect(config.SQLITE_DB_PATH, uri=True) 
    conn.row_factory = sqlite3.Row
    return conn

# --- Login Endpoint (Updated to include role in token) ---
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
        # Add role to the JWT claims
        additional_claims = {"role": user["role"]}
        access_token = create_access_token(identity=username, additional_claims=additional_claims)
        return jsonify(access_token=access_token)
    
    return jsonify({"msg": "Bad username or password"}), 401

# --- NEW: Admin User Management Endpoints ---

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
def create_user():
    """Creates a new user."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user') # Defaults to 'user' if not provided

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
        return jsonify({"msg": f"User '{username}' already exists"}), 409 # Conflict
    finally:
        if conn:
            conn.close()

    return jsonify({"msg": f"User '{username}' created successfully"}), 201

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required()
def delete_user(user_id):
    """Deletes a user by their ID."""
    current_user_identity = get_jwt_identity()
    conn = get_db_connection()
    user_to_delete = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    # Prevent admin from deleting themselves
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


# --- Protected Data Endpoints (No changes needed here) ---
@app.route('/api/stats', methods=['GET'])
@jwt_required()
def get_stats():
    # ... same as before
    stats = get_performance_stats()
    return jsonify(stats)

@app.route('/api/trades', methods=['GET'])
@jwt_required()
def get_trades():
    # ... same as before
    status_filter = request.args.get('status', 'all')
    limit = request.args.get('limit', 20, type=int)
    # ... query logic ...
    return jsonify([]) # Placeholder for brevity


if __name__ == '__main__':
    # You will need to run `create_user_db.py` (from previous steps)
    # once to set up the database table with the new 'role' column.
    logger.info("🚀 Starting Flask API server with Admin features...")
    app.run(host='0.0.0.0', port=8080, debug=False)
