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

USE_RETRIES = os.getenv("USE_RETRIES", "false").lower() == "true"
MAX_RETRIES = 3
RETRY_SLEEP = 3


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
    fn = (
        processing_workflow_with_retries
        if USE_RETRIES
        else processing_workflow_no_retries
    )
    return fn(context, input)
    # for r in fn(context, input):
    #     yield r


def processing_workflow_no_retries(context: DaprWorkflowContext, input):
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
            step_results.append(action_tasks)
            if _has_errors(action_tasks):
                logger.info(
                    f"processing step completed with errors - skipping any remaining work: {step.name}"
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


def processing_workflow_with_retries(context: DaprWorkflowContext, input):
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
            step_results_dic = {}  # track final results
            attempt_count = 1
            success = False
            while True:
                # Convert dataclass to dict before passing to call_activity
                # otherwise the durabletask serialisation will deserialise it as a SimpleNamespace type
                action_task_dict = {
                    action_index: context.call_activity(
                        invoke_processor, input=asdict(action)
                    )
                    for action_index, action in enumerate(step.actions)
                    if action_index not in step_results_dic
                }
                action_tasks = action_task_dict.values()

                if len(action_tasks) == 0:
                    raise Exception("No actions to process")

                yield wf.when_all(action_tasks)

                # Determine whether to retry any actions
                if _has_errors(action_tasks):
                    attempt_count += 1
                    if attempt_count > MAX_RETRIES:
                        # copy all tasks to result dict (i.e. include errors)
                        for action_index, task in action_task_dict.items():
                            action = step.actions[action_index]
                            step_results_dic[action_index] = ProcessingActionResult(
                                action=action.action,
                                content=action.content,
                                result=task.get_result(),
                                attempt_count=attempt_count - 1,  # already incremented
                            )
                        break
                    else:
                        # copy successful tasks to result dict
                        for action_index, task in action_task_dict.items():
                            if not _is_error(task):
                                action = step.actions[action_index]
                                step_results_dic[action_index] = ProcessingActionResult(
                                    action=action.action,
                                    content=action.content,
                                    result=task.get_result(),
                                    attempt_count=attempt_count,  # already incremented
                                )
                        
                        # Insert logic to handle failures here
                        # In this example, we're going to suspend the workflow for RETRY_SLEEP seconds 
                        # before resuming to continue to the next attempt
                        yield context.create_timer(context.current_utc_datetime + timedelta(seconds=RETRY_SLEEP))
                        continue
                else:
                    # copy all tasks to result dict
                    for action_index, task in action_task_dict.items():
                        action = step.actions[action_index]
                        step_results_dic[action_index] = ProcessingActionResult(
                            action=action.action,
                            content=action.content,
                            result=task.get_result(),
                            attempt_count=attempt_count,
                        )
                    success = True
                    break

            if len(step_results_dic) != len(step.actions):
                raise Exception(
                    f"Expected {len(step.actions)} results but got {len(step_results_dic)} (step={step.name}))"
                )

            step_results.append(step_results_dic)
            if not success:
                logger.info(
                    f"processing step completed with errors - skipping any remaining work: {step.name}"
                )
                break

        # Gather results
        results = ProcessingResult(
            id=context.instance_id,
            status="Completed" if success else "Failed",
            steps=[
                ProcessingStepResult(
                    step.name,
                    [
                        step_results[step_index][action_index]
                        for action_index, action in enumerate(step.actions)
                    ] if step_index < len(step_results) else [
                        ProcessingActionResult(
                            action=action.action,
                            content=action.content,
                            result=None,
                            attempt_count=0)
                        for action in step.actions
                    ],
                )
                for step_index, step in enumerate(payload.steps)
            ],
        )
        logger.info(f"processing_workflow completed: {results}")

        yield context.call_activity(save_state, input=asdict(results))

        return "workflow done"
    except Exception as e:
        logger.error(f"!!!workflow error: {traceback.format_exception(e)}")
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
        body = {
            "correlation_id": f"{context.workflow_id}-{context.task_id}",
            "content": action.content,
        }
        # wanted to use dapr_client.invoke_method but it obscures the response status code
        # resp = dapr_client.invoke_method(
        #     app_id=action.action,
        #     method_name="process",
        #     http_verb="POST",
        #     data=json.dumps(body),
        #     content_type="application/json",
        # )

        dapr_http_port = os.getenv("DAPR_HTTP_PORT", "3500")
        resp = requests.post(
            url=f"http://localhost:{dapr_http_port}/v1.0/invoke/{action.action}/method/process",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        if resp.ok:
            logger.info(
                f"invoke_processor (wf_id: {context.workflow_id}; task_id: {context.task_id}): ✅ completed {resp.status_code}"
            )
            resp_data = resp.json()
            return resp_data
        else:
            emoji = "⏳" if resp.status_code == 429 else "❌"
            logger.error(f"invoke_processor failed: {emoji} {resp.status_code}; {resp.text}")
            resp_data = {"error": _json_or_text(resp), "status_code": resp.status_code}
            return resp_data

    except Exception as e:
        logger.error(f"invoke_processor (wf_id: {context.workflow_id}; task_id: {context.task_id}) - failed with: {e}")
        # return an error type as a result rather than throwing as
        # the workflow will be marked as failed otherwise
        return {"error": str(e)}  # TODO likely don't want to expose raw errors


def _json_or_text(resp: requests.Response):
    try:
        return resp.json()
    except:
        return resp.text


def save_state(context: WorkflowActivityContext, input_dict):
    logger = logging.getLogger("save_state")

    try:
        dapr_client.save_state(
            "statestore", context.workflow_id, json.dumps(input_dict)
        )
    except Exception as e:
        logger.error(f"!!!save_state error: {e}")
        raise e
