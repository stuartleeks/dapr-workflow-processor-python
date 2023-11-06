# workflow processor

This is a project to explore ideas for Dapr workflows calling rate-limited processing services

- [workflow processor](#workflow-processor)
	- [Components](#components)
		- [processor](#processor)
		- [workflow1](#workflow1)
		- [processor-sender](#processor-sender)
	- [Running workflow1](#running-workflow1)
		- [workflow1 with single processor - no retries](#workflow1-with-single-processor---no-retries)
		- [workflow with single processor - Dapr retries](#workflow-with-single-processor---dapr-retries)
		- [workflow with single processor - workflow retries](#workflow-with-single-processor---workflow-retries)
	- [Troublshooting](#troublshooting)
		- [Testing the processor service](#testing-the-processor-service)


## Components

| Component        | Description                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| processor        | Simple service to fake a long-running, rate-limited API (cheaper than CogSvcs and easier to run locally 😉) |
| workflow1        | Contains an HTTP endpoint for submitting jobs and a workflow that processes them                           |
| processor-sender | A service to invoke the processor service a number of times                                                |

TODO - add diagram

### processor

The `processor` is an HTTP endpoint that can be invoked by as a Dapr service.

Calls to `processor` are rate-limited (to 1 call per second)`

Configuration options:
- `DELAY` - how long the service should sleep for to simulate doing work (default 2s)
- `FAILURE_CHANCE` - what chance of failure there is for an invocation of the service, expressed as a percentage (default 30, i.e. 30% chance of failure)

### workflow1

The `workflow1` service contains a Dapr workflow and an HTTP endpoint that can be invoked to submit a job to the workflow.

There are sample jobs in `single-processor.http` in the `workflow1` folder that show the format of the job:

```json
{
	"steps": [
		{
			"name": "parallel_step",
			"actions" : [
				{
					"action": "processor1",
					"content" : "Hello World"
				},
				{
					"action": "processor1",
					"content" : "Do stuff"
				},
				{
					"action": "processor1",
					"content" : "Do more stuff"
				}
			]
		},
			{
			"name": "final_step",
			"actions" : [
				{
					"action": "processor1",
					"content" : "Finale"
				}
			]
		}
	]
}
```

A job consists of a number of steps, each of which contains a number of actions.
Each step is executed in sequence, but the actions within a step are executed in parallel.
The `action` value indicates which service to invoke (in this case `processor1` which is a deployment of the `processor` service).

The result from the workflow is in the format shown below:

```json
{
	"id": "60eea8fa-514f-473f-a7ff-0d66330d0220",
	"status": "Completed",
	"steps": [
		{
			"actions": [
				{
					"action": "processor1",
					"attempt_count": 1,
					"content": "Hello World",
					"result": {
						"result": "Ifmmp Xpsme",
						"success": true
					}
				},
				{
					"action": "processor1",
					"attempt_count": 1,
					"content": "Do stuff",
					"result": {
						"result": "Ep tuvgg",
						"success": true
					}
				},
				{
					"action": "processor1",
					"attempt_count": 1,
					"content": "Do more stuff",
					"result": {
						"result": "Ep npsf tuvgg",
						"success": true
					}
				}
			],
			"name": "parallel_step"
		},
		{
			"actions": [
				{
					"action": "processor1",
					"attempt_count": 1,
					"content": "Finale",
					"result": {
						"result": "Gjobmf",
						"success": true
					}
				}
			],
			"name": "final_step"
		}
	]
}
```

The `status` property indicates whether the job completed successfully or not.
The `steps` property contains the results of each step, including the results of each action within the step.
Each item under `actions` also includes an `attempt_count` property which indicates how many times the action was attempted which is relevant in some of the retry configurations.


### processor-sender

The `processor-sender` service was mostly added as a quick way to test the behaviour of the `processor` service.


## Running workflow1

All of the scenarios assume that you are running in the dev container and have run `dapr init`.

### workflow1 with single processor - no retries

Starting/stopping the services:

```bash
# Start
just run-single-processor-workflow1-no-retries

# Stop
just stop-single-processor-workflow1-no-retries
```

The above commands start `processor1` with a 30% chance of failure and a 1 RPS rate limit.


To send requests to the workflow you can use `single-processor.http`.
Open the file in VS Code and use the `Send Request` button to send the request to the workflow.
The file contains requests for a job with single step + action, a job with multiple steps + actions, as well as requests to query the job status.


When running the multi-step/-action job you will see that when multiple requests are sent in parallel the processor returns status 429 responses (too many requests) for some of the requests due to the rate-limiting configured.
You will also likely see some status 400 responses due to the failure chance configured for `processor1`.

For ease of identifying the `invoke_processor` results in the logs the completion log message includes an emoji:

- ✅ - success
- ❌ - failure
- ⏳ - rate-limited


### workflow with single processor - Dapr retries

To run the same configuration as above but with Dapr retries enabled, run:

```bash
# Start
just run-single-processor-workflow1-dapr-retries

# Stop
just stop-single-processor-workflow1-dapr-retries
```

This uses [Dapr resiliency](https://docs.dapr.io/operations/resiliency/policies/) features specified in `components/resiliency.yaml` to apply automatic retres of failed service invocations.

If a call to `processor1` fails due to a random failure in the processor, the output will show the `Failing...` message from `processor1` but the `invoke_processor` action in `workflow1` won't see that failure unless the Dapr retry limit has been reached as Dapr will automatically retry the service invocation.
This is also shown by the `attempt_count` values being `1` in the result.


### workflow with single processor - workflow retries

The workflow implementation has two implementations of the orchestrator function.
The first (used in the previous steps) has no retry logic built in.
The second implementation (`workflow1_retry`) has logic to attempt actions for a step in the submitted job up to three times (i.e. up to two retries).

To run with the workflow retries (and no Dapr retries), run:

```bash
# Start
just run-single-processor-workflow1-wf-retries

# Stop
just stop-single-processor-workflow1-wf-retries
```

In this configuration, a failure from invoking `processor1` _is_ seen by the `invoke_processor` action in `workflow1` but the `workflow1` orchestrator has logic to retry failed steps up to a maximum of three attempts.
With this configuration, the values of `attempt_count` will reflect the retry attempts made by the workflow.

The workflow could add additional logic (e.g. falling back to another service) but in this case the workflow just creates a time to retry in a few seconds (during this time, the workflow is suspended).

## Troublshooting

### Testing the processor service

To test that the processor (`processor1`) service is working, run


```bash
dapr invoke --app-id processor1 --method process --verb POST --data '{"id":1, "content":"test"}'
```

