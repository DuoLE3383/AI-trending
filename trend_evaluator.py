import logging
import pandas as pd
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# In-memory store for active predictions
# Structure: {symbol: {"predicted_trend": str, "price_at_prediction": float, "timestamp_of_prediction": pd.Timestamp, "cycles_since_prediction": int}}
active_predictions: Dict[str, Dict[str, Any]] = {}

# How many cycles to wait before evaluating a prediction.
# If your main loop sleeps for 1 hour, EVALUATION_PERIOD_CYCLES = 1 means evaluate after 1 hour.
EVALUATION_PERIOD_CYCLES = 1

def record_strong_trend_prediction(
    symbol: str,
    predicted_trend: str,
    price_at_prediction: float,
    timestamp: pd.Timestamp
):
    """Records a new strong trend prediction, overwriting any existing one for the symbol."""
    if symbol in active_predictions:
        logger.info(f"Overwriting active prediction for {symbol} due to new strong trend signal: {predicted_trend} @ ${price_at_prediction:,.4f}")
    
    active_predictions[symbol] = {
        "predicted_trend": predicted_trend,
        "price_at_prediction": price_at_prediction,
        "timestamp_of_prediction": timestamp,
        "cycles_since_prediction": 0  # Reset cycle count for new/overwritten prediction
    }
    logger.info(f"Recorded new prediction for {symbol}: Trend={predicted_trend}, Price=${price_at_prediction:,.4f} at {timestamp}")

def evaluate_predictions(
    current_cycle_analysis_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Evaluates active predictions against current market data.
    :param current_cycle_analysis_results: A list of analysis result dictionaries from the current cycle.
    :return: A list of dictionaries, each representing an evaluated prediction's outcome.
    """
    evaluated_outcomes = []
    symbols_to_remove_from_active = []

    current_data_map = {item['symbol']: item for item in current_cycle_analysis_results if item.get('price') is not None and pd.notna(item.get('price'))}

    for symbol, prediction_data in list(active_predictions.items()): # Iterate over a copy for safe modification
        prediction_data["cycles_since_prediction"] += 1

        if prediction_data["cycles_since_prediction"] >= EVALUATION_PERIOD_CYCLES:
            if symbol in current_data_map:
                current_price = current_data_map[symbol]['price'] # Already checked for None/NaN
                price_at_prediction = prediction_data["price_at_prediction"]
                predicted_trend = prediction_data["predicted_trend"]
                
                percentage_change = ((current_price - price_at_prediction) / price_at_prediction) * 100 if price_at_prediction != 0 else float('inf')
                outcome_description = "Inconclusive"
                is_correct_prediction = None

                if "StrongBullish" in predicted_trend:
                    if current_price > price_at_prediction:
                        outcome_description = "Correct (Price Increased)"
                        is_correct_prediction = True
                    elif current_price < price_at_prediction:
                        outcome_description = "Incorrect (Price Decreased)"
                        is_correct_prediction = False
                    else:
                        outcome_description = "Neutral (Price Unchanged)"
                        is_correct_prediction = False # Or define as per preference
                elif "StrongBearish" in predicted_trend:
                    if current_price < price_at_prediction:
                        outcome_description = "Correct (Price Decreased)"
                        is_correct_prediction = True
                    elif current_price > price_at_prediction:
                        outcome_description = "Incorrect (Price Increased)"
                        is_correct_prediction = False
                    else:
                        outcome_description = "Neutral (Price Unchanged)"
                        is_correct_prediction = False # Or define as per preference

                eval_result = {
                    "symbol": symbol,
                    "predicted_trend": predicted_trend,
                    "price_at_prediction": price_at_prediction,
                    "timestamp_of_prediction": prediction_data["timestamp_of_prediction"],
                    "price_at_evaluation": current_price,
                    "timestamp_of_evaluation": pd.to_datetime('now', utc=True),
                    "percentage_change": percentage_change,
                    "outcome": outcome_description,
                    "is_correct": is_correct_prediction
                }
                evaluated_outcomes.append(eval_result)
                symbols_to_remove_from_active.append(symbol)
            else:
                logger.warning(f"No current valid price data for {symbol} to evaluate prediction. Prediction will remain active or be re-evaluated next cycle if data appears.")
                # If a symbol is no longer in SYMBOLS or consistently has no data, it might stay here.
                # Consider adding a max_cycles_to_keep_active if symbol data is missing.
        else:
            logger.debug(f"Prediction for {symbol} not yet due for evaluation. Cycles: {prediction_data['cycles_since_prediction']}/{EVALUATION_PERIOD_CYCLES}")

    for symbol in symbols_to_remove_from_active:
        if symbol in active_predictions:
            del active_predictions[symbol]
            logger.info(f"Removed evaluated prediction for {symbol} from active list.")
            
    return evaluated_outcomes