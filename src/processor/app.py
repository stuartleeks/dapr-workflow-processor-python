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
    logger.info('process triggered: ' + json.dumps(data))
    
    logger.info(f"Sleeping {processing_delay}...")
    time.sleep(processing_delay)
    logger.info("Done...")

    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}

port = int(os.getenv("PORT", "8001"))
app.run(port=port)