default:
	just --list

run:
	dapr run --run-file dapr.yml
	
stop:
	dapr stop --run-file dapr.yml
