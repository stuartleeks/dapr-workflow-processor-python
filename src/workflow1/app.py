from dataclasses import dataclass, is_dataclass, asdict
from datetime import timedelta
import logging
from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext, WorkflowActivityContext
import dapr.ext.workflow as wf

from flask import Flask, request
import json
import os


app = Flask(__name__)
dapr_client = DaprClient()
logging.basicConfig(level=logging.INFO)


class DataClassJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if is_dataclass(o):
                return asdict(o)
            return super().default(o)
        
@dataclass
class ProcessingAction():
    action: str
    content: str

    def to_json(self):
        return json.dumps(self, cls=DataClassJSONEncoder)

@dataclass
class ProcessingPayload():
    actions: list[ProcessingAction]

    @staticmethod
    def from_input(data):
        actions = []
        for action in data:
            actions.append(ProcessingAction(**action))
        return ProcessingPayload(actions)

    def to_json(self):
        return json.dumps(self, cls=DataClassJSONEncoder)

def processing_workflow(context: DaprWorkflowContext, input: ProcessingPayload):
    # This is the workflow orchestrator
    # Calls here must be deterministic
    # TODO: consider whether logging makes sense here
    logger = logging.getLogger('processing_workflow')

    try:
        payload = ProcessingPayload.from_input(input)
        if not context.is_replaying:
            logger.info(f"Processing_workflow - received new payload: {payload}")

        logger.info(f"processing_workflow triggered (replaying={context.is_replaying}):" + payload.to_json())

        for action in payload.actions:
            logger.info(f"processing action: {action}")
            response = yield context.call_activity(invoke_processor, input=action)
            logger.info(f"activity response: {response}")

        return "workflow done"
    except Exception as e:
        logger.error(f"!!!workflow error: {e}")
        raise e

def invoke_processor(context: WorkflowActivityContext, input_dict):
    logger = logging.getLogger('invoke_processor')
    
    logger.info(f"invoke_processor triggered (wf_id: {context.workflow_id}; task_id: {context.task_id})" + json.dumps(input_dict))
    try:
        action = ProcessingAction(**input_dict)

        # Currently using action.name as the app_id
        # This is a simplification - imagine having a mapping and applying validation etc ;-)
        data = {
            "correlation_id": f"{context.workflow_id}-{context.task_id}",
            "content": action.content,
        }
        resp = dapr_client.invoke_method(app_id=action.action, method_name="process", http_verb="POST", data=json.dumps(data), content_type="application/json")
        logger.info(f"invoke_processor completed {resp.status_code}")
        resp_data = resp.json()
        return resp_data
    except Exception as e:
        logger.error(f"!!!invoke_processor error: {e}")
        raise e

@app.route('/workflows', methods=['POST'])
def start_workflow():
    logger = logging.getLogger('start_workflow')
    data = request.json
    logger.info('POST /workflows triggered: ' + json.dumps(data))

    # Here we are passing data from input to workflow - might want early validation here ;-)
    response = dapr_client.start_workflow(workflow_component="dapr", workflow_name="processing_workflow", input=data)
    
    return {'success': True, "instance_id" : response.instance_id}, 200, {
        'ContentType': 'application/json'}

@app.route('/workflows/<instance_id>', methods=['GET'])
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
    print("*************************** Flask app exited - shutting down workflow runtime")

    workflowRuntime.shutdown()


if __name__ == '__main__':
    main()
