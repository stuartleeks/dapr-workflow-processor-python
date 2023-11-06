import logging
import os
from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
from dapr.clients.grpc._response import TopicEventResponse
from dapr.clients import DaprClient

import json

import requests

app = App()


dapr_client = DaprClient()


@app.subscribe(pubsub_name="pubsub", topic="processor1")
def processing_consumer_processor1(event: v1.Event) -> TopicEventResponse:
    action = "processor1"
    try:
        logger = logging.getLogger()

        data = json.loads(event.Data())
        print(f"processing_consumer_processor1: Got data {data}", flush=True)

        instance_id = data.get("instance_id")
        if not instance_id:
            raise Exception("instance_id not found in data")

        correlation_id = data.get("correlation_id")
        if not correlation_id:
            raise Exception("correlation_id not found in data")

        content = data.get("content")
        if not content:
            raise Exception("content not found in data")

        # invoke the processing service
        body = {
            "correlation_id": correlation_id,
            "content": content,
        }
        dapr_http_port = os.getenv("DAPR_HTTP_PORT", "3500")
        resp = requests.post(
            url=f"http://localhost:{dapr_http_port}/v1.0/invoke/{action}/method/process",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        if resp.ok:
            logger.info(
                f"processing_consumer_processor1 (correlation_id: {correlation_id}): ✅ completed {resp.status_code}"
            )
            resp_data = resp.json()
        else:
            emoji = "⏳" if resp.status_code == 429 else "❌"
            logger.error(
                f"processing_consumer_processor1 (correlation_id: {correlation_id}) failed: {emoji} {resp.status_code}; {resp.text}"
            )
            resp_data = {"error": _json_or_text(resp), "status_code": resp.status_code}

        # send a response back to the workflow
        workflow = "workflow2" # this could be specified in the payload for more flexibility
        body = {
            "instance_id": instance_id,
            "correlation_id": correlation_id,
            "response": resp_data,
        }
        resp = requests.post(
            url=f"http://localhost:{dapr_http_port}/v1.0/invoke/{workflow}/method/raise-event",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()

        return TopicEventResponse("success")
    except Exception as e:
        logger.error(f"!!! error: {e}")
        return TopicEventResponse("drop")


def _json_or_text(resp: requests.Response):
    try:
        return resp.json()
    except:
        return resp.text


app_port = os.environ.get("APP_PORT")
print(f"Starting processing-consumer on port {app_port}", flush=True)
app.run(app_port)
