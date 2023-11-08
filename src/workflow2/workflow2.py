from dataclasses import dataclass, asdict
from datetime import timedelta
import json
import logging
import os
import requests
import traceback
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
    attempt_count: int


@dataclass
class ProcessingStepResult:
    name: str
    actions: list[ProcessingActionResult]


@dataclass
class ProcessingResult:
    id: str
    status: str
    steps: list[ProcessingStepResult]


def _has_errors(tasks):
    for task in tasks:
        if _is_error(task):
            return True
    return False


def _is_error(task):
    if task.is_failed:
        return True
    result = task.get_result()
    if result is None:
        return True
    if "error" in result:
        return True
    return False


def register_workflow_components(workflowRuntime):
    workflowRuntime.register_workflow(processing_workflow)
    workflowRuntime.register_activity(invoke_processor)
    workflowRuntime.register_activity(save_state)


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

        step_results = []
        for step in payload.steps:
            # Convert dataclass to dict before passing to call_activity
            # otherwise the durabletask serialisation will deserialise it as a SimpleNamespace type
            action_tasks = [
                context.call_activity(invoke_processor, input=asdict(action))
                for action in step.actions
            ]
            yield wf.when_all(action_tasks)
            if _has_errors(action_tasks):
                logger.info(
                    f"processing step completed with errors while invoking processor - skipping any remaining work: {step.name}"
                )
                step_results.append(action_tasks)
                have_errors = True
                break
            # Get the correlation_ids from the action tasks
            # These are used to correlate the results from the pubsub events
            # And will be used as the name of external events to wait for
            event_correlation_ids = [
                r.get_result().get("correlation_id") for r in action_tasks
            ]
            events = [
                context.wait_for_external_event(event_correlation_id)
                for event_correlation_id in event_correlation_ids
            ]
            yield wf.when_all(events)
            step_results.append(events)
            if _has_errors(events):
                logger.info(
                    f"processing step completed with errors from processing - skipping any remaining work: {step.name}"
                )
                have_errors = True
                break

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
                            attempt_count=1,  # no retries, so always a single attempt ;-)
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
            f"invoke_processor (wf_id: {context.workflow_id}; task_id: {context.task_id}): ⚡ triggered"
            + json.dumps(input_dict)
        )
        action = ProcessingAction(**input_dict)

        # Currently using action.name as the app_id
        # This is a simplification - imagine having a mapping and applying validation etc ;-)
        correlation_id = f"{context.workflow_id}-{context.task_id}"
        body = {
            "instance_id": context.workflow_id,
            "correlation_id": correlation_id,  # used when calling back to indicate completion
            "content": action.content,
        }

        resp = dapr_client.publish_event(
            pubsub_name="pubsub", topic_name=action.action, data=json.dumps(body)
        )
        logger.info(
            f"invoke_processor (wf_id: {context.workflow_id}; task_id: {context.task_id}) - published event: {resp}"
        )  # TODO - check resp?

        return {"success": True, "correlation_id": correlation_id}

    except Exception as e:
        logger.error(
            f"invoke_processor (wf_id: {context.workflow_id}; task_id: {context.task_id}) - failed with: {e}"
        )
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
