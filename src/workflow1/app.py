from datetime import timedelta
from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext, WorkflowActivityContext

from flask import Flask, request
import json
import os

port = int(os.getenv("APP_PORT", "8100"))

app = Flask(__name__)
dapr_client = DaprClient()

def hello_world_wf(context: DaprWorkflowContext, input):
    # This is the workflow orchestrator
    # Calls here must be deterministic

    # test = input["test"]
    # print(f"test: {test}", flush=True)

    try:
        print(f"hello_world_wf triggered (replaying={context.is_replaying}):" + json.dumps(input), flush=True)

        response = yield context.call_activity(hello_act, input="hiya")
        print(f"activity response: {response}", flush=True)

        response = yield context.call_activity(invoke_processor1, input="hiya")
        print(f"activity response: {response}", flush=True)

        yield context.create_timer(context.current_utc_datetime + timedelta(seconds=5))

        response = yield context.call_activity(hello_act, input="hola")
        print(f"activity response: {response}", flush=True)
        return "workflow done"
    except Exception as e:
        print(f"!!!workflow error: {e}", flush=True)
        return "workflow error"

def hello_act(context: WorkflowActivityContext, input):
    print("hello_act triggered" + json.dumps(input), flush=True)
    return f"activity done (input: {input})"

def invoke_processor1(context: WorkflowActivityContext, input):
    print("invoke_processor1 triggered" + json.dumps(input), flush=True)
    resp = dapr_client.invoke_method(app_id="processor1", method_name="do_stuff1", http_verb="POST", data=json.dumps({"test": "test"}))
    print(f"invoke_processor1 completed {resp.status_code}", flush=True)
    return f"activity done (input: {input})"

@app.route('/workflows', methods=['POST'])
def do_stuff1():
    data = request.json
    print('start_wf1 triggered: ' + json.dumps(data), flush=True)

    # TODO pass data from input to workflow
    response = dapr_client.start_workflow(workflow_component="dapr", workflow_name="hello_world_wf", input={"test": "test"})
    
    return {'success': True, "instance_id" : response.instance_id}, 200, {
        'ContentType': 'application/json'}

@app.route('/workflows/<instance_id>', methods=['GET'])
def query_wf1(instance_id):
    resp = dapr_client.get_workflow(instance_id=instance_id, workflow_component="dapr")
    return resp.runtime_status

def main():
    host = settings.DAPR_RUNTIME_HOST
    grpc_port = settings.DAPR_GRPC_PORT
    workflowRuntime = WorkflowRuntime(host, grpc_port)
    workflowRuntime.register_workflow(hello_world_wf)
    workflowRuntime.register_activity(hello_act)
    workflowRuntime.register_activity(invoke_processor1)
    print(f"Starting workflow runtime on {host}:{grpc_port}", flush=True)
    workflowRuntime.start()

    print("Waiting for dapr sidecar...", flush=True)
    dapr_client.wait(10)

    print(f"dapr sidecar ready, starting flask app on port {port}", flush=True)
    app.run(port=port)
    print("*************************** Flask app exited - shutting down workflow runtime")

    workflowRuntime.shutdown()


if __name__ == '__main__':
    main()
