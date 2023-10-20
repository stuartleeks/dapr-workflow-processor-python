import json
import time
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)

base_url = os.getenv('BASE_URL', 'http://localhost') + ':' + os.getenv(
                    'DAPR_HTTP_PORT', '3500')
# Adding app id as part of the header
headers = {'dapr-app-id': 'processor', 'content-type': 'application/json'}

for i in range(1, 50):
    body = {'id': i}

    result = requests.post(
        url=f"{base_url}/do_stuff",
        data=json.dumps(body),
        headers=headers
    )
    print(f"Response (do_stuff ) {result.status_code}: " + result.text, flush=True)

    result = requests.post(
        url=f"{base_url}/do_stuff2",
        data=json.dumps(body),
        headers=headers
    )
    print(f"Response (do_stuff2) {result.status_code}: " + result.text, flush=True)

    time.sleep(0.5)