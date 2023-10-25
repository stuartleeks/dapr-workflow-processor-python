from dataclasses import dataclass, is_dataclass, asdict
import dataclasses
from datetime import timedelta
import logging
from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.workflow import (
    WorkflowRuntime,
    DaprWorkflowContext,
    WorkflowActivityContext,
)
import dapr.ext.workflow as wf

from flask import Flask, request
import json
import os


app = Flask(__name__)
dapr_client = DaprClient()
logging.basicConfig(level=logging.INFO)


@dataclass
class ProcessingAction:
    action: str
    content: str


@dataclass
class ProcessingStep:
    name: str
    actions: list[ProcessingAction]

    @staticmethod
    def from_input(data):
        name = data["name"]
        actions = []
        for action in data["actions"]:
            actions.append(ProcessingAction(**action))

        return ProcessingStep(name, actions)


@dataclass
class ProcessingPayload:
    steps: list[ProcessingStep]

    @staticmethod
    def from_input(data):
        steps = []
        for step in data["steps"]:
            steps.append(ProcessingStep.from_input(step))
        return ProcessingPayload(steps)


def processing_workflow(context: DaprWorkflowContext, input):
    # This is the workflow orchestrator
    # Calls here must be deterministic
    # TODO: consider whether logging makes sense here
    logger = logging.getLogger("processing_workflow")

    try:
        payload = ProcessingPayload.from_input(input)
        if not context.is_replaying:
            logger.info(f"Processing_workflow - received new payload: {payload}")

        logger.info(
            f"processing_workflow triggered (replaying={context.is_replaying}): {payload}"
        )

        for step in payload.steps:
            logger.info(f"processing step: {step.name}")
            # Convert dataclass to dict before passing to call_activity
            # otherwise the durabletask serialisation will deserialise it as a SimpleNamespace type
            action_tasks = [
                context.call_activity(invoke_processor, input=asdict(action))
                for action in step.actions
            ]
            yield wf.when_all(action_tasks)
            logger.info(f"processing step completed: {step.name}")

        return "workflow done"
    except Exception as e:
        logger.error(f"!!!workflow error: {e}")
        raise e


def invoke_processor(context: WorkflowActivityContext, input_dict):
    logger = logging.getLogger("invoke_processor")

    try:
        logger.info(
            f"invoke_processor triggered (wf_id: {context.workflow_id}; task_id: {context.task_id})"
            + json.dumps(input_dict)
        )
        action = ProcessingAction(**input_dict)

        # Currently using action.name as the app_id
        # This is a simplification - imagine having a mapping and applying validation etc ;-)
        body = {
            "correlation_id": f"{context.workflow_id}-{context.task_id}",
            "content": action.content,
        }
        resp = dapr_client.invoke_method(
            app_id=action.action,
            method_name="process",
            http_verb="POST",
            data=json.dumps(body),
            content_type="application/json",
        )
        logger.info(f"invoke_processor completed {resp.status_code}")
        resp_data = resp.json()
        return resp_data
    except Exception as e:
        logger.error(f"!!!invoke_processor error: {e}")
        raise e


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
        {"ContentType": "application/json"},
    )


@app.route("/workflows/<instance_id>", methods=["GET"])
def query_workflow(instance_id):
    resp = dapr_client.get_workflow(instance_id=instance_id, workflow_component="dapr")
    return resp.runtime_status


def main():
    host = settings.DAPR_RUNTIME_HOST
    grpc_port = settings.DAPR_GRPC_PORT
    workflowRuntime = WorkflowRuntime(host, grpc_port)
    workflowRuntime.register_workflow(processing_workflow)
    workflowRuntime.register_activity(invoke_processor)
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
