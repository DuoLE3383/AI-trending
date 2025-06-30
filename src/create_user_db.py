import sqlite3
from werkzeug.security import generate_password_hash
import os

# The path to your database file.
DB_PATH = 'trading_bot.db' 

# --- WARNING: This will delete the existing 'users' table if it exists! ---
# --- Run this script ONLY ONCE to set up your database with the new user. ---

# Connect to the database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Setting up the database...")

# Drop the users table if it exists, for a clean setup
cursor.execute("DROP TABLE IF EXISTS users")
print("Dropped existing 'users' table (if any).")

# Create the users table with the new 'role' column
cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
)
""")
print("Created new 'users' table with 'role' column.")

# --- NEW: Default User Credentials ---
# The default user is now 'user' with password 'pass'
default_username = 'user'
default_password = 'pass' 
default_role = 'user'

# Create an admin user as well for testing the admin panel
admin_username = 'admin'
admin_password = 'admin123123'
admin_role = 'admin'


# Hash the passwords for secure storage
hashed_default_password = generate_password_hash(default_password, method='pbkdf2:sha256')
hashed_admin_password = generate_password_hash(admin_password, method='pbkdf2:sha256')

try:
    # Insert the default user
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (default_username, hashed_default_password, default_role)
    )
    print(f"Successfully created default user:")
    print(f"  Username: {default_username}")
    print(f"  Password: {default_password}")

    # Insert the admin user
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (admin_username, hashed_admin_password, admin_role)
    )
    print(f"Successfully created admin user:")
    print(f"  Username: {admin_username}")
    print(f"  Password: {admin_password}")

    conn.commit()

except sqlite3.IntegrityError as e:
    print(f"An error occurred: {e}")
finally:
    # Close the connection
    conn.close()
    print("Database setup complete. Connection closed.")
