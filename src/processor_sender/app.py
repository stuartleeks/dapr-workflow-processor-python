from dapr.clients import DaprClient

import json
import time
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)

def invoke_via_api():
    base_url = os.getenv('BASE_URL', 'http://localhost') + ':' + os.getenv(
                        'DAPR_HTTP_PORT', '3500')
    # Adding app id as part of the header
    headers1 = {'dapr-app-id': 'processor1', 'content-type': 'application/json'}
    headers2 = {'dapr-app-id': 'processor2', 'content-type': 'application/json'}

    for i in range(1, 50):
        body = {'id': i}

        print("Calling process (via API)...", flush=True)
        result = requests.post(
            url=f"{base_url}/process",
            data=json.dumps(body),
            headers=headers1
        )
        print(f"Response {result.status_code}: " + result.text, flush=True)

        time.sleep(0.1)

def invoke_via_sdk():
    with DaprClient() as d:
        print("Waiting for sidecar...")
        d.wait(10)
        
        for i in range(1, 5):
            body = {'id': i}

            print("Calling process (via SDK)...", flush=True)
            result = d.invoke_method(app_id="processor1", method_name="process", data=json.dumps(body), content_type="application/json", http_verb="POST")
            print(f"Response {result.status_code}: " + result.text(), flush=True)

            time.sleep(0.1)

if __name__ == '__main__':
    # invoke_via_api()
    invoke_via_sdk()