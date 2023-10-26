from dataclasses import dataclass, asdict
import json
import logging
from dapr.ext.workflow import (
    DaprWorkflowContext,
    WorkflowActivityContext,
)
import dapr.ext.workflow as wf
from dapr.clients import DaprClient

dapr_client = DaprClient()


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
                logger.info(
                    f"processing step completed with errors - skipping any remaining work: {step.name}"
                )
                have_errors = True
                break
            logger.info(f"processing step completed: {step.name}")

        # Gather results
        results = ProcessingResult(
            id=context.instance_id,
            status="Failed" if have_errors else "Completed",
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
