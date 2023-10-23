import json
import time
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)

base_url = os.getenv('BASE_URL', 'http://localhost') + ':' + os.getenv(
                    'DAPR_HTTP_PORT', '3500')
# Adding app id as part of the header
headers1 = {'dapr-app-id': 'processor1', 'content-type': 'application/json'}
headers2 = {'dapr-app-id': 'processor2', 'content-type': 'application/json'}

for i in range(1, 50):
    body = {'id': i}

    print("Calling do_stuff1...", flush=True)
    result = requests.post(
        url=f"{base_url}/do_stuff1",
        data=json.dumps(body),
        headers=headers1
    )
    print(f"Response (do_stuff1 ) {result.status_code}: " + result.text, flush=True)

    # result = requests.post(
    #     url=f"{base_url}/do_stuff",
    #     data=json.dumps(body),
    #     headers=headers2
    # )
    # print(f"Response (do_stuff2) {result.status_code}: " + result.text, flush=True)

    time.sleep(0.1)