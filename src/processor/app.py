import time
from flask import Flask, request
import json
import os

app = Flask(__name__)


@app.route('/process', methods=['POST'])
def do_stuff1():
    data = request.json
    print('process triggered: ' + json.dumps(data), flush=True)
    time.sleep(2)
    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}

port = int(os.getenv("PORT", "8001"))
app.run(port=port)