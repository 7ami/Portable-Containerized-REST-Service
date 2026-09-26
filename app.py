import os
import math
from flask import Flask, request, jsonify
import redis
from redis.exceptions import RedisError

app = Flask(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
PORT = int(os.environ.get("PORT", 5000))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=2.0,
    socket_timeout=2.0
)

LBS_TO_KG_FACTOR = 0.45359237
FORMULA_STR = "kg = lbs * 0.45359237"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/stats", methods=["GET"])
def stats():
    try:
        count = redis_client.get("conversions")
        conversions = int(count) if count is not None else 0
        return jsonify({"conversions": conversions}), 200
    except RedisError as err:
        return jsonify({
            "error": "Redis service unavailable",
            "details": str(err)
        }), 503


@app.route("/convert", methods=["GET"])
def convert():
    lbs_param = request.args.get("lbs")

    if lbs_param is None or lbs_param.strip() == "":
        return jsonify({"error": "Missing required query parameter: 'lbs'"}), 400

    try:
        lbs_val = float(lbs_param)
    except (ValueError, TypeError):
        return jsonify({"error": "Query parameter 'lbs' must be a valid number"}), 400

    if math.isnan(lbs_val) or math.isinf(lbs_val) or lbs_val < 0:
        return jsonify({
            "error": "Value for 'lbs' must be a non-negative finite number"
        }), 422

    kg_val = round(lbs_val * LBS_TO_KG_FACTOR, 3)

    formatted_lbs = int(lbs_val) if lbs_val.is_integer() else lbs_val
    formatted_kg = int(kg_val) if kg_val.is_integer() else kg_val

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
    app.run(host="0.0.0.0", port=PORT)
