from dataclasses import dataclass, is_dataclass, asdict
from datetime import timedelta
from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext, WorkflowActivityContext
import dapr.ext.workflow as wf

from flask import Flask, request
import json
import os


app = Flask(__name__)
dapr_client = DaprClient()

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
    def from_dict(data):
        actions = []
        for action in data["actions"]:
            actions.append(ProcessingAction(**action))
        return ProcessingPayload(actions)
    
    def to_json(self):
        return json.dumps(self, cls=DataClassJSONEncoder)

def processing_workflow(context: DaprWorkflowContext, input: ProcessingPayload):
    # This is the workflow orchestrator
    # Calls here must be deterministic
    try:
        payload = ProcessingPayload(input)
        if not context.is_replaying:
            print(f"Processing_workflow - received new payload: {payload}", flush=True)

        print(f"processing_workflow triggered (replaying={context.is_replaying}):" + payload.to_json(), flush=True)

        for action in payload.actions:
            print(f"processing action: {action}", flush=True)
            response = yield context.call_activity(invoke_processor, input=action)
            print(f"activity response: {response}", flush=True)

        return "workflow done"
    except Exception as e:
        print(f"!!!workflow error: {e}", flush=True)
        raise e

def invoke_processor(context: WorkflowActivityContext, input_dict):
    print("invoke_processor triggered" + json.dumps(input_dict), flush=True)
    try:
        action = ProcessingAction(**input_dict)

        # Currently using action.name as the app_id
        # This is a simplification - imagine having a mapping and applying validation etc ;-)
        resp = dapr_client.invoke_method(app_id=action.action, method_name="process", http_verb="POST", data=action.to_json(), content_type="application/json")
        print(f"invoke_processor completed {resp.status_code}", flush=True)
        resp_data = resp.json()
        return resp_data
    except Exception as e:
        print(f"!!!invoke_processor error: {e}", flush=True)
        raise e

@app.route('/workflows', methods=['POST'])
def start_workflow():
    data = request.json
    print('POST /workflows triggered: ' + json.dumps(data), flush=True)

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
