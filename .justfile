default:
	just --list

############################################################################
# recipes for running multiple services in different configurations

run-workflow1-no-retries:
	dapr run --run-file dapr-workflow1-no-retries.yaml
	
stop-workflow1-no-retries:
	dapr stop --run-file dapr-workflow1-no-retries.yaml

run-workflow1-dapr-retries:
	dapr run --run-file dapr-workflow1-dapr-retries.yaml
	
stop-workflow1-dapr-retries:
	dapr stop --run-file dapr-workflow1-dapr-retries.yaml

run-workflow1-wf-retries:
	dapr run --run-file dapr-workflow1-wf-retries.yaml
	
stop-workflow1-wf-retries:
	dapr stop --run-file dapr-workflow1-wf-retries.yaml


run-workflow2-simple:
	dapr run --run-file dapr-workflow2-simple.yaml
	
stop-workflow2-simple:
	dapr stop --run-file dapr-workflow2-simple.yaml

run-workflow2-consumer-concurrency:
	dapr run --run-file dapr-workflow2-consumer-concurrency.yaml
	
stop-workflow2-consumer-concurrency:
	dapr stop --run-file dapr-workflow2-consumer-concurrency.yaml


############################################################################
# recipes for submitting and watching jobs

submit-job-simple:
	echo '{"steps": [{"name": "simple_test","actions" : [{"action": "processor1","content" : "Hello World"}]}]}'  \
	| ./scripts/run-workflow.sh

submit-job-multi-step:
	echo '{"steps": [{"name": "parallel_step","actions" : [{"action": "processor1","content" : "Hello World"},{"action": "processor1","content" : "Do stuff"},{"action": "processor1","content" : "Do more stuff"}]},{"name": "final_step","actions" : [{"action": "processor1","content" : "Finale"}]}]}'  \
	| ./scripts/run-workflow.sh

submit-job-multi-step-with-processor2:
	echo '{"steps": [{"name": "parallel_step","actions" : [{"action": "processor2","content" : "Hello World"},{"action": "processor1","content" : "Do stuff"},{"action": "processor1","content" : "Do more stuff"}]},{"name": "final_step","actions" : [{"action": "processor1","content" : "Finale"}]}]}'  \
	| ./scripts/run-workflow.sh


############################################################################
# recipes for running services individually

run-svc-processor1:
	cd src/processor/ && \
	dapr run --app-port 8001 --app-id processor1 --resources-path ../../components --config ../../components/wf-config-1rps-no-resiliency.yaml -- python app.py

run-svc-processor-sender:
	cd src/processor_sender/ && \
	dapr run --app-id processor_sender  --resources-path ../../components --app-protocol http --config ../../components/wf-config-1rps-no-resiliency.yaml -- python3 app.py

run-svc-workflow1:
	cd src/workflow1/ && \
	dapr run --app-id workflow1 --resources-path ../../components --app-protocol grpc \
		--enable-api-logging --log-level debug \
		-- python3 app.py


############################################################################
# Misc recipes

clean-dapr-logs:
	find . -type d -name ".dapr" | xargs rm -rf