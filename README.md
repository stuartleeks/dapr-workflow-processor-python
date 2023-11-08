# workflow processor

This is a project to explore ideas for Dapr workflows calling rate-limited processing services

- [workflow processor](#workflow-processor)
	- [Components](#components)
		- [processor](#processor)
		- [workflow1](#workflow1)
		- [processor-sender](#processor-sender)
	- [Running workflow1](#running-workflow1)
		- [workflow1 - no retries](#workflow1---no-retries)
		- [workflow1 - Dapr retries](#workflow1---dapr-retries)
		- [workflow1 - workflow retries](#workflow1---workflow-retries)
	- [workflow 2](#workflow-2)
		- [workflow2 - simple](#workflow2---simple)
		- [workflow2 - with concurrency limit](#workflow2---with-concurrency-limit)
	- [Troublshooting](#troublshooting)
		- [Testing the processor service](#testing-the-processor-service)


## Components

| Component        | Description                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| processor        | Simple service to fake a long-running, rate-limited API (cheaper than CogSvcs and easier to run locally 😉) |
| workflow1        | Contains an HTTP endpoint for submitting jobs and a workflow that processes them by invoking the processor service                          |
| workflow2        | Contains an HTTP endpoint for submitting jobs and a workflow that processes them by sending messages to queue for the processing_consumer to pick up                         |
| processing_consumer | Contains a service that subscribes to messages from the queue and invokes the processor service before. Processing results are sent back to the workflow HTTP API to resume the workflow                        |
| processor-sender | A service to invoke the processor service a number of times                                                |

TODO - add diagram

### processor

The `processor` is an HTTP endpoint that can be invoked by as a Dapr service.
The service is configured with a chance of random failure and a rate limit.
The service returns the submitted content shifted via a caesar cipher.

Calls to `processor` are rate-limited (to 1 call per second)`

Configuration options:
- `PORT` - the port to listen on (default 8001), use this to override the port when running multiple instances of the service locally
- `DELAY` - how long the service should sleep for to simulate doing work (default 2s)
- `FAILURE_CHANCE` - what chance of failure there is for an invocation of the service, expressed as a percentage (default 30, i.e. 30% chance of failure)
- `SHIFT_AMOUNT` - the caesar shift amount to use when encoding the content (default 1)

### workflow1

The `workflow1` service contains a Dapr workflow and an HTTP endpoint that can be invoked to submit a job to the workflow.

There are sample jobs in `submit_jobs.http` in the repo root that show the format of the job:

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

For all of the workflow1 scenarios, there are two instances of the `processor` service running.
Service `processor1` uses a shift value of 1 (`Hello` becomes `Ifmmp`) and service `processor2` uses a shift value of 2 (`Hello` becomes `Jgnnq`).


To send requests to the workflow you can use `submit_jobs.http` or the justfile recipes.

To use `submit_jobs.http`, open the file in VS Code and use the `Send Request` button to send the request to the workflow.
The file contains requests for a job with single step + action, a job with multiple steps + actions, as well as requests to query the job status.

To use the justfile recipes run `just submit-job-simple`, `just submit-job-multi-step`, or `just submit-job-multi-step-with-processor2` from the terminal.

### workflow1 - no retries

Starting/stopping the services:

```bash
# Start
just run-workflow1-no-retries

# Stop
just stop-workflow1-no-retries
```

The above commands start `processor1` with a 30% chance of failure and a 1 RPS rate limit.

When running the multi-step/-action job you will see that when multiple requests are sent in parallel the processor returns status 429 responses (too many requests) for some of the requests due to the rate-limiting configured.
You will also likely see some status 400 responses due to the failure chance configured for `processor1`.

For ease of identifying the `invoke_processor` results in the logs the completion log message includes an emoji:

- ✅ - success
- ❌ - failure
- ⏳ - rate-limited


### workflow1 - Dapr retries

To run the same configuration as above but with Dapr retries enabled, run:

```bash
# Start
just run-workflow1-dapr-retries

# Stop
just stop-workflow1-dapr-retries
```

This uses [Dapr resiliency](https://docs.dapr.io/operations/resiliency/policies/) features specified in `components/resiliency.yaml` to apply automatic retres of failed service invocations.

If a call to `processor1` fails due to a random failure in the processor, the output will show the `Failing...` message from `processor1` but the `invoke_processor` action in `workflow1` won't see that failure unless the Dapr retry limit has been reached as Dapr will automatically retry the service invocation.
This is also shown by the `attempt_count` values being `1` in the result.


### workflow1 - workflow retries

The workflow implementation has two implementations of the orchestrator function.
The first (used in the previous steps) has no retry logic built in.
The second implementation (`workflow1_retry`) has logic to attempt actions for a step in the submitted job up to three times (i.e. up to two retries).

To run with the workflow retries (and no Dapr retries), run:

```bash
# Start
just run-workflow1-wf-retries

# Stop
just stop-workflow1-wf-retries
```

In this configuration, a failure from invoking `processor1` _is_ seen by the `invoke_processor` action in `workflow1` but the `workflow1` orchestrator has logic to retry failed steps up to a maximum of three attempts.
With this configuration, the values of `attempt_count` will reflect the retry attempts made by the workflow.

The workflow could add additional logic (e.g. falling back to another service) but in this case the workflow just creates a time to retry in a few seconds (during this time, the workflow is suspended).

## workflow 2

Workflow2 introduces a queue to decouple the workflow from the processor service.
To submit a processing step to the `processor` service, a message is sent to the queue and then the workflow waits for an external event for that step (in parallel as appropriate).
The `processing_consumer` service subscribes to the queue and invokes the `processor` service before sending a message back to the workflow's HTTP API which raises the external event to resume the workflow processing.

For all of the workflow2 scenarios, there is a single instance of the `processor` service running with a shift value of 1 (`Hello` becomes `Ifmmp`).

To send requests to the workflow you can use `submit_jobs.http` or the justfile recipes.

To use `submit_jobs.http`, open the file in VS Code and use the `Send Request` button to send the request to the workflow.
The file contains requests for a job with single step + action, a job with multiple steps + actions, as well as requests to query the job status.

To use the justfile recipes run `just submit-job-simple`, `just submit-job-multi-step`, or `just submit-job-multi-step-with-processor2` from the terminal.

### workflow2 - simple

In the simple scenario, there is no concurrency limit applied to the message consumer.

To run the simple scenario, run:

```bash
# Start
just run-workflow2-simple

# Stop
just stop-workflow2-simple
```

With this configuration, there are no retries or concurrency limits applied to the message consumer.
As a result, any jobs that contain steps with multiple actions will encounter the rate limit for the `processor` service.

### workflow2 - with concurrency limit

In this configuration, the message consumer is configured with a concurrency limit of 1 (i.e. a single message can be processed at once).

To run this scenario, run:

```bash
# Start
just run-workflow2-consumer-concurrency

# Stop
just stop-workflow2-consumer-concurrency
```

With this configuration, the message consumer can only process a single concurrent message.
In combination with the processing duration, this means that the job processing won't trigger the rate limit.

There is no retry behaviour configured for this scenario, but either of the approaches from workflow1 (Dapr retries or workflow retries) could be applied to this scenario.

## Troublshooting

### Testing the processor service

To test that the processor (`processor1`) service is working, run:

```bash
dapr invoke --app-id processor1 --method process --verb POST --data '{"id":1, "content":"test"}'
```

