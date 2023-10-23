from datetime import timedelta
from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext, WorkflowActivityContext

from flask import Flask, request
import json
import os
import time

app = Flask(__name__)
dapr_client = DaprClient()

def hello_world_wf(context: DaprWorkflowContext, input):
    # This is the workflow orchestrator
    # Calls here must be deterministic
    print("********************* HERE****")
    # test = input["test"]
    # print(f"test: {test}", flush=True)
    print(f"hello_world_wf triggered (replaying={context.is_replaying}):" + json.dumps(input), flush=True)

    response = yield context.call_activity(hello_act, input="hiya")
    print(f"activity response: {response}", flush=True)

    yield context.create_timer(context.current_utc_datetime + timedelta(seconds=5))

    response = yield context.call_activity(hello_act, input="hola")
    print(f"activity response: {response}", flush=True)
    return "workflow done"

# TODO add activity that calls processor

def hello_act(context: WorkflowActivityContext, input):
    print("********************* hello_act triggered", flush=True)
    # print("hello_act triggered" + json.dumps(input), flush=True)
    return f"activity done (input: {input})"


@app.route('/workflows', methods=['POST'])
def do_stuff1():
    # print("TESTINGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG")
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
    port = settings.DAPR_GRPC_PORT
    workflowRuntime = WorkflowRuntime(host, port)
    workflowRuntime.register_workflow(hello_world_wf)
    workflowRuntime.register_activity(hello_act)
    workflowRuntime.start()


    dapr_client.wait(10)

    time.sleep(2)
    # print("Start workflow...", flush=True)
    # resp = dapr_client.start_workflow(workflow_component="dapr", workflow_name="hello_world_wf", input={"test": "test"})
    # print(f"Workflow started: {resp.instance_id}", flush=True)


    # time.sleep(20)

    port = int(os.getenv("PORT", "8100"))
    app.run(port=port)
    print("*************************** Flask app exited - shutting down workflow runtime")

    workflowRuntime.shutdown()


if __name__ == '__main__':
    main()
