#!/bin/bash
set -e

# Start new workflow
echo "Starting new workflow"
resp=$(curl \
    --silent \
    --include \
    --request POST \
    --url http://localhost:8100/workflows \
    --header 'content-type: application/json' \
    --data '{"steps": [{"name": "simple_test","actions" : [{"action": "processor1","content" : "Hello World"}]}]}')

# Get location header and body from response
head=true
location=""
while read -r line; do 
    if $head; then 
        if [[ $line = $'\r' ]]; then
            head=false
        else
            # if line starts with "Location:" extract remainder
            if [[ $line == Location:* ]]; then
                # extract Location header value and trim newlines
                location=$(echo "${line#Location: }"# | tr -d '\n\r')
            fi
        fi
    else
        body="$body"$'\n'"$line"
    fi
done < <(echo "$resp")

instance_id=$(echo "$body" | jq -r .instance_id)
if [[ -z $instance_id ]]; then
    echo "instance_id not set in result: $resp"
    exit 1
fi
if [[ -z $location ]]; then
    echo "location not set in result: $resp"
    exit 1
fi

echo "Waiting for workflow to complete..."
# switch screen while watching workflow
function revert_screen {
    # ensure we're back on the original screen on unhandled error or if the user interrupts the script
    tput rmcup
}
trap revert_screen EXIT
tput smcup
while :
do
    clear
    echo "Refreshing workflow status..."
    resp=$(curl \
        --silent \
        --request GET \
        --url "http://localhost:8100${location}" )
    status=$(echo "$resp" | jq -r .status)
    if [[ "$status" != "Running" ]]; then
        echo "Status: $status - done"
        break
    fi
    echo "$resp" | jq
    sleep 2
done

tput rmcup
echo "Workflow complete"
echo "$resp" | jq
