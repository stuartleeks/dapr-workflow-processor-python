from flask import Flask, request
import json

app = Flask(__name__)


@app.route('/do_stuff1', methods=['POST'])
def do_stuff1():
    data = request.json
    print('do_stuff1 triggered: ' + json.dumps(data), flush=True)
    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}

@app.route('/do_stuff2', methods=['POST'])
def do_stuff2():
    data = request.json
    print('do_stuff2 triggered: ' + json.dumps(data), flush=True)
    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}


app.run(port=8001)