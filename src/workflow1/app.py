import logging
from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.workflow import (
    WorkflowRuntime,
)

from flask import Flask, request
import json
import os

from workflow1 import processing_workflow, invoke_processor, save_state


app = Flask(__name__)
dapr_client = DaprClient()
logging.basicConfig(level=logging.INFO)


@app.route("/workflows", methods=["POST"])
def start_workflow():
    logger = logging.getLogger("start_workflow")
    data = request.json
    logger.info("POST /workflows triggered: " + json.dumps(data))

    # Here we are passing data from input to workflow
    # This 'works' because we have matched the data format of the body with the workload input
    # but you might want some validation here ;-)
    response = dapr_client.start_workflow(
        workflow_component="dapr", workflow_name="processing_workflow", input=data
    )

    return (
        {"success": True, "instance_id": response.instance_id},
        200,
        {
            "ContentType": "application/json",
            "Location": f"/workflows/{response.instance_id}",
        },
    )


@app.route("/workflows/<instance_id>", methods=["GET"])
def query_workflow(instance_id):
    workflow_response = dapr_client.get_workflow(
        instance_id=instance_id, workflow_component="dapr"
    )
    if workflow_response.runtime_status == "Completed":
        state = dapr_client.get_state("statestore", workflow_response.instance_id)
        response = state.json()
    else:
        response = {"status": workflow_response.runtime_status}

    return response


def main():
    host = settings.DAPR_RUNTIME_HOST
    grpc_port = settings.DAPR_GRPC_PORT
    workflowRuntime = WorkflowRuntime(host, grpc_port)
    workflowRuntime.register_workflow(processing_workflow)
    workflowRuntime.register_activity(invoke_processor)
    workflowRuntime.register_activity(save_state)
    print(f"Starting workflow runtime on {host}:{grpc_port}", flush=True)
    workflowRuntime.start()

    print("Waiting for dapr sidecar...", flush=True)
    dapr_client.wait(10)

    app_port = int(os.getenv("APP_PORT", "8100"))
    print(f"dapr sidecar ready, starting flask app on port {app_port}", flush=True)
    app.run(port=app_port)
    print(
        "*************************** Flask app exited - shutting down workflow runtime"
    )

    workflowRuntime.shutdown()


if __name__ == "__main__":
    main()
