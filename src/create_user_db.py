import sqlite3
from werkzeug.security import generate_password_hash
import os

# Assumes your database is in a file named 'trading_bot.db' in the same directory
# Adjust this path if your config.py points elsewhere
DB_PATH = 'trading_bot.db' 

# --- WARNING: This will delete existing users if the table exists! ---
# --- Run this script ONLY ONCE to set up your database.      ---

# Connect to the database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Setting up the database...")

# Drop the users table if it exists, for a clean setup
cursor.execute("DROP TABLE IF EXISTS users")
print("Dropped existing 'users' table (if any).")

# Create the users table
# Storing the password HASH, never the plain text password!
cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
""")
print("Created new 'users' table.")

# --- Create a sample user ---
# You will use these credentials to log in from the frontend
sample_username = 'testuser'
sample_password = 'password123' 

# Hash the password for secure storage
hashed_password = generate_password_hash(sample_password, method='pbkdf2:sha256')

# Insert the sample user into the database
try:
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (sample_username, hashed_password)
    )
    conn.commit()
    print(f"Successfully created sample user:")
    print(f"  Username: {sample_username}")
    print(f"  Password: {sample_password}")

except sqlite3.IntegrityError:
    print(f"User '{sample_username}' already exists.")
finally:
    # Close the connection
    conn.close()
    print("Database setup complete. Connection closed.")