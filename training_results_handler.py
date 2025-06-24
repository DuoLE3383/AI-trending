# training_results_handler.py
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json # To store hyperparameters as JSON string

import config

logger = logging.getLogger(__name__)

def init_training_db(db_path: str) -> None:
    """
    Initializes the training results table in the SQLite database if it doesn't exist.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.TRAINING_RESULTS_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version TEXT NOT NULL,
                    training_timestamp_utc TEXT NOT NULL,
                    accuracy REAL,
                    precision REAL,
                    recall REAL,
                    f1_score REAL,
                    loss REAL,
                    hyperparameters TEXT, -- Stored as JSON string
                    notes TEXT,
                    UNIQUE(model_version, training_timestamp_utc)
                );
            """)
            conn.commit()
        logger.info(f"✅ Training results table '{config.TRAINING_RESULTS_TABLE_NAME}' initialized successfully.")
    except sqlite3.Error as e:
        logger.critical(f"❌ Error initializing training results database: {e}", exc_info=True)
        raise

def save_training_result(result_data: Dict[str, Any]) -> None:
    """
    Saves a new training result to the database.

    Args:
        result_data (Dict[str, Any]): A dictionary containing training metrics and metadata.
                                      Expected keys: 'model_version', 'accuracy', 'precision',
                                      'recall', 'f1_score', 'loss', 'hyperparameters' (dict), 'notes'.
    """
    sql_insert = f"""
    INSERT INTO {config.TRAINING_RESULTS_TABLE_NAME} (
        model_version, training_timestamp_utc, accuracy, precision, recall, f1_score, loss, hyperparameters, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # Convert hyperparameters dict to JSON string
    hyperparameters_json = json.dumps(result_data.get('hyperparameters', {}))

    db_values = (
        result_data.get('model_version', 'N/A'),
        datetime.utcnow().isoformat(), # Use current UTC time for consistency
        result_data.get('accuracy'),
        result_data.get('precision'),
        result_data.get('recall'),
        result_data.get('f1_score'),
        result_data.get('loss'),
        hyperparameters_json,
        result_data.get('notes', '')
    )

    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            conn.execute(sql_insert, db_values)
            conn.commit()
        logger.info(f"✅ Training result saved for model '{result_data.get('model_version', 'N/A')}' (Accuracy: {result_data.get('accuracy'):.4f}).")
    except sqlite3.Error as e:
        logger.error(f"❌ Error saving training result for model '{result_data.get('model_version', 'N/A')}': {e}", exc_info=True)

def get_latest_training_result() -> Optional[Dict[str, Any]]:
    """
    Retrieves the most recent training result from the database.

    Returns:
        Optional[Dict[str, Any]]: A dictionary of the latest training result, or None if no results found.
    """
    query = f"""
    SELECT * FROM {config.TRAINING_RESULTS_TABLE_NAME}
    ORDER BY training_timestamp_utc DESC
    LIMIT 1;
    """
    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query)
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Convert hyperparameters JSON string back to dict
                if 'hyperparameters' in result and result['hyperparameters']:
                    result['hyperparameters'] = json.loads(result['hyperparameters'])
                return result
            return None
    except sqlite3.Error as e:
        logger.error(f"❌ Error retrieving latest training result: {e}", exc_info=True)
        return None