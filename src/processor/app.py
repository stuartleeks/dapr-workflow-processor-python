import time
from flask import Flask, request
import json
import logging
import os
import random
import string

app = Flask(__name__)
processing_delay = float(os.getenv("DELAY", "2"))
failure_chance = int(os.getenv("FAILURE_CHANCE", "30"))

logging.basicConfig(level=logging.INFO)


def caesar_shift(plaintext, shift):
    alphabet = string.ascii_letters
    shifted_alphabet = alphabet[shift:] + alphabet[:shift]
    trans_table = str.maketrans(alphabet, shifted_alphabet)
    return plaintext.translate(trans_table)


@app.route("/process", methods=["POST"])
def do_stuff1():
    logger = logging.getLogger("process")

    data = request.json

    # test if data (dictionary) has key 'actions'
    correlation_id = data.get("correlation_id", "<none>")
    log_extra = {"correlation_id": correlation_id}
    input_content = data["content"]

    logger.info(
        f"[{correlation_id}] process triggered: " + json.dumps(data), extra=log_extra
    )

    logger.info(f"[{correlation_id}] Sleeping {processing_delay}...", extra=log_extra)
    time.sleep(processing_delay)
    logger.info(f"[{correlation_id}] Done...", extra=log_extra)

    if failure_chance > 0:
        random_value = random.randint(1, 100)
        logger.info(
            f"[{correlation_id}] Random value: {random_value}, failure chance: {failure_chance}",
            extra=log_extra,
        )
        if random_value <= failure_chance:
            logger.info(f"[{correlation_id}] Failing...", extra=log_extra)
            return (
                # message and errorCode fields are set as the Dapr python client SDK 
                # looks for these and surfaces them in the raised exception
                json.dumps(
                    {
                        "success": False,
                        "message": "Failed by random chance 😢",
                        "errorCode": 400,
                    }
                ),
                400,
                {"ContentType": "application/json"},
            )

    return (
        json.dumps({"success": True, "result": caesar_shift(input_content, 1)}),
        200,
        {"ContentType": "application/json"},
    )


port = int(os.getenv("PORT", "8001"))
app.run(port=port)
