# workflow processor

This is a project to explore ideas for Dapr workflows calling rate-limited processing services


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



### processor-sender

The `processor-sender` service was mostly added as a quick way to test the behaviour of the `processor` service.

TODO - add more docs

## Running

All of the scenarios assume that you are running in the dev container and have run `dapr init`.



### workflow1 with single processor

Starting/stopping the services:

```bash
# Start
just run-single-processor-workflow1-no-retries

# Stop
just stop-single-processor-workflow1-no-retries
```

The above commands start `processor1` with a 30% chance of failure and a 1 RPS rate limit.


To send requests to the workflow you can use `single-processor.http`. Open the file in VS Code and use the `Send Request` button to send the request to the workflow. The file contains requests for a job with single step + action, a job with multiple steps + actions, as well as requests to query the job status.


When running the multi-step/-action job you will see that when multiple requests are sent in parallel the processor returns status 429 responses (too many requests) for some of the requests due to the rate-limiting configured. You will also likely see some status 400 responses due to the failure chance configured for `processor1`.





## Troublshooting

### Testing the processor service

To test that the processor (`processor1`) service is working, run


```bash
dapr invoke --app-id processor1 --method process --verb POST --data '{"id":1, "content":"test"}'
```



## TODO

- workflow calls to processor: retries specified in resiliency.yaml
- how to run
- points of note
  - configuring rate-limiting
  - resiliency.yaml to set retries
  - enabling retries in workflow
  - setting chance of failure in processor
