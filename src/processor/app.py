import time
from flask import Flask, request
import json
import logging
import os

app = Flask(__name__)
processing_delay = float(os.getenv("DELAY", "2"))

logging.basicConfig(level=logging.INFO)

@app.route('/process', methods=['POST'])
def do_stuff1():
    logger = logging.getLogger("process")
    
    data = request.json
    
    # test if data (dictionary) has key 'actions'
    correlation_id = data.get('correlation_id', '<none>')
    log_extra = {
        "correlation_id" : correlation_id
    }

    logger.info(f"[{correlation_id}] process triggered: " + json.dumps(data), extra=log_extra)
    
    logger.info(f"[{correlation_id}] Sleeping {processing_delay}...", extra=log_extra)
    time.sleep(processing_delay)
    logger.info(f"[{correlation_id}] Done...", extra=log_extra)

    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}

port = int(os.getenv("PORT", "8001"))
app.run(port=port)