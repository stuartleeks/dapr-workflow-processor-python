import time
from flask import Flask, request
import json
import os

app = Flask(__name__)


@app.route('/do_stuff1', methods=['POST'])
def do_stuff1():
    data = request.json
    print('do_stuff1 triggered: ' + json.dumps(data), flush=True)

    time.sleep(2)
    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}

@app.route('/do_stuff2', methods=['POST'])
def do_stuff2():
    data = request.json
    print('do_stuff2 triggered: ' + json.dumps(data), flush=True)
    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}

port = int(os.getenv("PORT", "8001"))
app.run(port=port)