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


@dataclass
class ProcessingActionResult:
    action: str
    content: str
    result: str


@dataclass
class ProcessingStepResult:
    name: str
    actions: list[ProcessingActionResult]


@dataclass
class ProcessingResult:
    id: str
    status: str
    steps: list[ProcessingStepResult]

def has_errors(tasks):
    for task in tasks:
        if task.is_failed:
            return True
        result = task.get_result()
        if "error" in result:
            return True

def processing_workflow(context: DaprWorkflowContext, input):
    # This is the workflow orchestrator
    # Calls here must be deterministic
    # TODO: consider whether logging makes sense here
    logger = logging.getLogger("processing_workflow")
    have_errors = False

    try:
        payload = ProcessingPayload.from_input(input)
        if not context.is_replaying:
            logger.info(f"Processing_workflow - received new payload: {payload}")

        logger.info(
            f"processing_workflow triggered (replaying={context.is_replaying}): {payload}"
        )

        step_results = []
        for step in payload.steps:
            logger.info(f"processing step: {step.name}")
            # Convert dataclass to dict before passing to call_activity
            # otherwise the durabletask serialisation will deserialise it as a SimpleNamespace type
            action_tasks = [
                context.call_activity(invoke_processor, input=asdict(action))
                for action in step.actions
            ]
            yield wf.when_all(action_tasks)
            step_results.append(action_tasks)
            if has_errors(action_tasks):
                logger.info(f"processing step completed with errors - skipping any remaining work: {step.name}")
                have_errors = True
                break
            logger.info(f"processing step completed: {step.name}")

        # Gather results
        results = ProcessingResult(
            id=context.instance_id,
            status = "Failed" if have_errors else "Completed",
            steps=[
                ProcessingStepResult(
                    step.name,
                    [
                        # step_results is an list of steps
                        # each item is a list of action tasks
                        # map each of these to a ProcessingActionResult
                        ProcessingActionResult(
                            action=action.action,
                            content=action.content,
                            result=step_results[step_index][action_index].get_result()
                            if len(step_results) > step_index
                            else None,
                        )
                        for action_index, action in enumerate(step.actions)
                    ],
                )
                for step_index, step in enumerate(payload.steps)
            ],
        )
        logger.info(f"processing_workflow completed: {results}")

        yield context.call_activity(save_state, input=asdict(results))

        return "workflow done"
    except Exception as e:
        logger.error(f"!!!workflow error: {e}")
        # TODO - save state here showing progress and include the error(s)?
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
        # return an error type as a result rather than throwing as
        # the workflow will be marked as failed otherwise
        return {"error": str(e)}  # TODO likely don't want to expose raw errors


def save_state(context: WorkflowActivityContext, input_dict):
    logger = logging.getLogger("save_state")

    try:
        dapr_client.save_state(
            "statestore", context.workflow_id, json.dumps(input_dict)
        )
    except Exception as e:
        logger.error(f"!!!save_state error: {e}")
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
