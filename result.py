# In run.py, you can add this new function after your signal_check_loop

async def summary_loop():
    """LOOP 3: The Periodic Summarizer."""
    logger.info(f"--- ✅ Summary Loop starting (interval: 10 minutes) ---")
    while True:
        try:
            # Wait a bit on startup before the first summary
            await asyncio.sleep(30) 
            
            logger.info("--- Generating daily analysis summary... ---")
            summary_data = get_analysis_summary(db_path=config.SQLITE_DB_PATH, time_period_hours=600)
            
            if 'error' in summary_data:
                logger.error(f"Could not generate summary: {summary_data['error']}")
            else:
                total = summary_data['total_entries']
                counts = summary_data.get('trend_counts', {})
                
                # Format the summary into a clean string for logging
                summary_str = f"📊 Daily Summary: Total Entries (10 minutes): {total}. "
                if counts:
                    trend_breakdown = ", ".join([f"{k}: {v}" for k, v in counts.items()])
                    summary_str += f"Breakdown: [{trend_breakdown}]"
                else:
                    summary_str += "No new trends recorded."

                logger.info(summary_str)
                # NOTE: You could also use your `notifier` here to send this summary to Telegram!
                # await notifier.send_message(chat_id=..., text=summary_str)

        except Exception as e:
            logger.error(f"❌ A critical error occurred in summary_loop: {e}", exc_info=True)
        
        # Sleep for 24 hours before the next summary
        await asyncio.sleep(600)
        
# Add this new function to your results.py file

from collections import Counter

def get_win_loss_stats(db_path: str):
    """
    Queries the database to calculate win/loss statistics based on signal outcomes.
    """
    conn = get_db_connection(db_path) # Assumes you have the get_db_connection from my earlier example
    if not conn:
        return {"error": "Could not connect to the database."}

    try:
        cursor = conn.cursor()
        
        # We only care about completed trades, so we ignore 'ACTIVE' ones.
        query = "SELECT status FROM trend_analysis WHERE status != 'ACTIVE'"
        cursor.execute(query)
        
        # Fetch all results; e.g., [('TP1_HIT',), ('SL_HIT',), ('TP1_HIT',)]
        outcomes = [row['status'] for row in cursor.fetchall()]
        
        if not outcomes:
            return {
                "total_completed_trades": 0,
                "win_rate": 0,
                "loss_rate": 0,
                "breakdown": {}
            }

        # Count the occurrences of each outcome status
        status_counts = Counter(outcomes)
        
        # Define what counts as a "win" or a "loss"
        wins = sum(count for status, count in status_counts.items() if 'TP' in status)
        losses = status_counts.get('SL_HIT', 0)
        
        total_completed = wins + losses
        
        win_rate = (wins / total_completed) * 100 if total_completed > 0 else 0
        loss_rate = (losses / total_completed) * 100 if total_completed > 0 else 0
        
        return {
            "total_completed_trades": total_completed,
            "win_rate": f"{win_rate:.2f}%",
            "loss_rate": f"{loss_rate:.2f}%",
            "breakdown": dict(status_counts)
        }

    except sqlite3.Error as e:
        logger.error(f"❌ Failed to query database for stats: {e}")
        return {"error": f"Failed to query database for stats: {e}"}
    finally:
        if conn:
            conn.close()
