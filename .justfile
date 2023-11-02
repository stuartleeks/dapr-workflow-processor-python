default:
	just --list

############################################################################
# recipes for running multiple services in different configurations

run-single-processor-workflow1-no-retries:
	dapr run --run-file dapr-single-processor-workflow1-no-retries.yaml
	
stop-single-processor-workflow1-no-retries:
	dapr stop --run-file dapr-single-processor-workflow1-no-retries.yaml

run-single-processor-workflow1-wf-retries:
	dapr run --run-file dapr-single-processor-workflow1-wf-retries.yaml
	
stop-single-processor-workflow1-wf-retries:
	dapr stop --run-file dapr-single-processor-workflow1-wf-retries.yaml


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