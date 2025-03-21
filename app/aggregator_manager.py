import time
import requests
import logging

from services.redis_service import redis_service  # for job info
import json

COORDINATOR_HOST = "195.251.63.193"
COORDINATOR_PORT = 12314

FINAL_OUTPUT_URL = "http://some-other-service:12345/api/final-output"


def trigger_and_poll_aggregator(job_id: str) -> dict:
    """
    1) Retrieve participants from Redis (job_info["updatedClients"]).
    2) POST to aggregator, initiating secure aggregation for jobId.
    3) Poll /api/get-result until COMPLETED.
    4) Decode final aggregator array into a readable format.
    5) Optionally send final decoded output to an external service.
    Returns the final aggregator response (dict).
    """
    job_info = redis_service.get_job_info(job_id)
    if not job_info:
        logging.warning(f"[Aggregator] No job info found in Redis for job {job_id}. Aborting aggregator call.")
        return {}

    # Suppose "updatedClients" are the participants
    # or if you store participant IDs in some "participants" field, adapt below
    updated_clients = list(job_info.get("updatedClients", []))
    # make sure that all the elements in the list are strings
    updated_clients = [str(client) for client in updated_clients]
    
    if not updated_clients:
        logging.warning(f"[Aggregator] No updated clients found for job {job_id}. Nothing to aggregate.")
        return {}
    
    logging.info(f"[Aggregator] Starting secure aggregation for job {job_id} with clients: {updated_clients}")

    agg_url = f"http://{COORDINATOR_HOST}:{COORDINATOR_PORT}/api/secure-aggregation/job-id/{job_id}"
    body = {
        "computationType": "sum",
        "clients": updated_clients
    }
    try:
        resp = requests.post(agg_url, json=body, timeout=15)
        if resp.status_code != 200:
            logging.warning(f"[Aggregator] Unexpected HTTP {resp.status_code} from aggregator.")
            return {}
        logging.info(f"[Aggregator] Secure aggregation started for job {job_id}.")
    except requests.RequestException as e:
        logging.warning(f"[Aggregator] Error posting aggregator request: {e}")
        return {}

    get_res_url = f"http://{COORDINATOR_HOST}:{COORDINATOR_PORT}/api/get-result/job-id/{job_id}"

    while True:
        try:
            r = requests.get(get_res_url, timeout=15)
            if r.status_code == 200:
                result_json = r.json()
                if result_json.get("status") == "COMPLETED":
                    logging.info(f"[Aggregator] Aggregation completed for job {job_id}.")

                    # Get aggregator's final array
                    computation_output = result_json.get("computationOutput", [])

                    # Decode aggregator array using stored schema
                    decoded_info = decode_final_output(job_id, computation_output)
                    if decoded_info:
                        result_json["decodedFeatures"] = decoded_info
                        logging.info(f"[Aggregator] Decoded final output for job {job_id}: {decoded_info}")

                        # 5) Send final decoded output to external service
                        send_final_output(decoded_info,updated_clients)

                    return result_json
                else:
                    logging.info(f"[Aggregator] job {job_id} in progress, status={result_json.get('status')}")
            else:
                logging.warning(f"[Aggregator] Poll got HTTP {r.status_code}. Retrying in 3s...")
        except requests.RequestException as e:
            logging.warning(f"[Aggregator] Poll request error: {e}")

        time.sleep(3)


def decode_final_output(job_id: str, aggregator_array: list) -> list:
    """
    Fetch schema from Redis, decode aggregator_array -> [
      { "featureName": <...>, "aggregatedNotNull": X, "aggregatedTrue": Y }, ...
    ]
    """
    job_info = redis_service.get_job_info(job_id)
    if not job_info:
        logging.warning(f"[decode_final_output] No job info for {job_id}.")
        return []

    schema = job_info.get("schema")
    if not schema:
        logging.warning(f"[decode_final_output] No schema stored for job {job_id}.")
        return []

    result = []
    for item in schema:
        feature_name = item["featureName"]
        offset = item["offset"]
        length = item["length"]
        slice_of_data = aggregator_array[offset : offset + length]
        if len(slice_of_data) < 2:
            logging.warning(f"[decode_final_output] aggregator_array too short at offset={offset}.")
            continue

        aggregated_not_null = slice_of_data[0]
        aggregated_true = slice_of_data[1]
        result.append({
            "featureName": feature_name,
            "aggregatedNotNull": aggregated_not_null,
            "aggregatedTrue": aggregated_true
        })
    return result

def send_final_output(output_data: list, updated_clients: list):
    """
    Send final decoded output to an external service.
    """
    _trigger_chaincode(updated_clients)

def _trigger_chaincode(updated_clients: list):
    url = "http://195.251.63.82:3000/invoke"
    headers = {"Content-Type": "application/json"}

    client_ids = ", ".join(f"'{client}'" for client in updated_clients)
    query = f"select * from table where id in ({client_ids})"

    payload = {
        "channelid": "dt4h",
        "chaincodeid": "dt4hCC",
        "function": "LogQuery",
        "args": [query]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            logging.info("Query invoked successfully with payload: %s", payload)
            # Optional: parse response
            logging.info("Response content: %s", response.text)
        else:
            logging.warning(
                "Unexpected status code when invoking chaincode: %d - %s",
                response.status_code,
                response.text
            )
    except requests.RequestException as e:
        logging.error("Error invoking chaincode: %s", e)