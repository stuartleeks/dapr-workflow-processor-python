default:
	just --list

run:
	dapr run --run-file dapr.yaml
	
stop:
	dapr stop --run-file dapr.yaml


run-processor1:
	cd src/processor/ && \
	dapr run --app-port 8001 --app-id processor1 --resources-path ../../components --config ../../components/appconfig.yaml -- python app.py

run-processor-sender:
	cd src/processor_sender/ && \
	dapr run --app-id processor_sender  --resources-path ../../components --app-protocol http --config ../../components/appconfig.yaml -- python3 app.py

run-workflow1:
	cd src/workflow1/ && \
	dapr run --app-id workflow1 --resources-path ../../components --app-protocol grpc \
		--enable-api-logging --log-level debug \
		-- python3 app.py