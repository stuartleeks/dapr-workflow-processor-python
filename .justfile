default:
	just --list

run:
	dapr run --run-file dapr.yml
	
stop:
	dapr stop --run-file dapr.yml


run-processor:
	cd src/processor/ && \
	dapr run --app-port 8001 --app-id processor --resources-path ../../components --config ../../components/appconfig.yaml -- python app.py

run-sender:
	cd src/sender/ && \
	dapr run --app-id sender  --resources-path ../../components --app-protocol http --config ../../components/appconfig.yaml -- python3 app.py
