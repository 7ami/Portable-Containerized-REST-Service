import os
import math
from flask import Flask, request, jsonify
import redis
from redis.exceptions import RedisError

# Initialize Flask application
app = Flask(__name__)

# Retrieve configuration from environment variables (separating config from code)
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
PORT = int(os.environ.get("PORT", 5000))

# Redis client connection pool
# Note: decode_responses=True returns string responses rather than bytes
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=2.0,
    socket_timeout=2.0
)

# Conversion constant according to official international avoirdupois pound definition
LBS_TO_KG_FACTOR = 0.45359237
FORMULA_STR = "kg = lbs * 0.45359237"


@app.route("/health", methods=["GET"])
def health():
    """
    Application liveness endpoint.
    Used by Docker container healthcheck and orchestration monitoring.
    """
    return jsonify({"status": "ok"}), 200


@app.route("/stats", methods=["GET"])
def stats():
    """
    Returns the total count of successful conversions recorded in Redis.
    Does not increment on invalid conversion requests.
    """
    try:
        count = redis_client.get("conversions")
        conversions = int(count) if count is not None else 0
        return jsonify({"conversions": conversions}), 200
    except RedisError as err:
        # Graduate CS 554 failure scenario handling:
        # Gracefully handle Redis unavailability without crashing the application process
        return jsonify({
            "error": "Redis service unavailable",
            "details": str(err)
        }), 503


@app.route("/convert", methods=["GET"])
def convert():
    """
    Converts pounds (lbs) to kilograms (kg).
    Formula: kg = lbs * 0.45359237 (rounded to 3 decimal places).
    Increments Redis 'conversions' counter only on valid, successful conversions.
    """
    lbs_param = request.args.get("lbs")

    # 400 Bad Request: Check if query parameter is missing
    if lbs_param is None or lbs_param.strip() == "":
        return jsonify({"error": "Missing required query parameter: 'lbs'"}), 400

    # 400 Bad Request: Check if query parameter is a valid number
    try:
        lbs_val = float(lbs_param)
    except (ValueError, TypeError):
        return jsonify({"error": "Query parameter 'lbs' must be a valid number"}), 400

    # 422 Unprocessable Entity: Check if value is negative or non-finite (NaN, Infinity)
    if math.isnan(lbs_val) or math.isinf(lbs_val) or lbs_val < 0:
        return jsonify({
            "error": "Value for 'lbs' must be a non-negative finite number"
        }), 422

    # Calculate kilogram conversion and round to 3 decimal places
    kg_val = round(lbs_val * LBS_TO_KG_FACTOR, 3)

    # Format numbers for clean JSON output matching sample specifications
    # (e.g., 150 -> 150, 0.0 -> 0)
    formatted_lbs = int(lbs_val) if lbs_val.is_integer() else lbs_val
    formatted_kg = int(kg_val) if kg_val.is_integer() else kg_val

    # Increment persistent conversion counter in Redis
    try:
        redis_client.incr("conversions")
    except RedisError as err:
        return jsonify({
            "error": "Failed to persist conversion count to Redis",
            "details": str(err)
        }), 503

    return jsonify({
        "lbs": formatted_lbs,
        "kg": formatted_kg,
        "formula": FORMULA_STR
    }), 200


if __name__ == "__main__":
    # In containerized environments, host MUST be 0.0.0.0 to accept external bridge connections
    app.run(host="0.0.0.0", port=PORT)
