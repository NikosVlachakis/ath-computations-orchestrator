import os
import time
import requests
import logging

from services.redis_service import redis_service  # for job info
from services.aggregated_results_handler import AggregatedResultsHandler
import json

COORDINATOR_HOST = "195.251.63.193"
COORDINATOR_PORT = 12314

# Configuration for results handling
RESULTS_API_URL = os.getenv("RESULTS_API_URL", "http://195.251.63.82:3000/invoke")  # Default to chaincode URL
RESULTS_SAVE_PATH = os.getenv("RESULTS_SAVE_PATH", "/app/results")
ENABLE_API_SENDING = os.getenv("ENABLE_API_SENDING", "true").lower() == "true"
ENABLE_FILESYSTEM_SAVING = os.getenv("ENABLE_FILESYSTEM_SAVING", "true").lower() == "true"

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

                        # 5) Send final decoded output using the new results handler
                        handle_final_results(decoded_info, job_id, updated_clients)

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
    Enhanced decoder that handles boolean, numeric, and categorical features using schema information.
    
    Args:
        job_id: The job identifier
        aggregator_array: The aggregated results array from SMPC
        
    Returns:
        List of decoded feature results with appropriate fields for each data type
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
        data_type = item.get("dataType", "BOOLEAN")  # Default to boolean for backward compatibility
        fields = item.get("fields", ["numOfNotNull", "numOfTrue"])  # Default field names
        
        # Extract the slice of data for this feature
        slice_of_data = aggregator_array[offset : offset + length]
        
        if len(slice_of_data) < length:
            logging.warning(f"[decode_final_output] aggregator_array too short at offset={offset}, expected {length}, got {len(slice_of_data)}.")
            continue

        # Decode based on data type
        if data_type == "BOOLEAN":
            result.append(decode_boolean_feature(feature_name, slice_of_data, fields))
        elif data_type == "NUMERIC":
            result.append(decode_numeric_feature(feature_name, slice_of_data, fields))
        elif data_type in ["NOMINAL", "ORDINAL"]:
            result.append(decode_categorical_feature(feature_name, slice_of_data, fields))
        else:
            logging.warning(f"[decode_final_output] Unknown data type '{data_type}' for feature '{feature_name}'.")
            # Generic decode - just map fields to values
            result.append(decode_generic_feature(feature_name, data_type, slice_of_data, fields))
    
    return result


def decode_boolean_feature(feature_name: str, data: list, fields: list) -> dict:
    """
    Decode boolean feature data
    
    Args:
        feature_name: Name of the feature
        data: Aggregated data slice [numOfNotNull, numOfTrue]
        fields: Field names
        
    Returns:
        Decoded boolean feature information
    """
    if len(data) < 2:
        logging.warning(f"[decode_boolean_feature] Insufficient data for boolean feature '{feature_name}'.")
        return {
            "featureName": feature_name,
            "dataType": "BOOLEAN",
            "aggregatedNotNull": 0,
            "aggregatedTrue": 0,
            "percentage": 0.0
        }
    
    aggregated_not_null = data[0]
    aggregated_true = data[1]
    percentage = (aggregated_true / aggregated_not_null * 100.0) if aggregated_not_null > 0 else 0.0
    
    return {
        "featureName": feature_name,
        "dataType": "BOOLEAN",
        "aggregatedNotNull": aggregated_not_null,
        "aggregatedTrue": aggregated_true,
        "percentage": round(percentage, 2)
    }


def decode_numeric_feature(feature_name: str, data: list, fields: list) -> dict:
    """
    Decode numeric feature data
    
    Args:
        feature_name: Name of the feature
        data: Aggregated data slice [numOfNotNull, min, max, avg, q1, q2, q3]
        fields: Field names
        
    Returns:
        Decoded numeric feature information
    """
    if len(data) < 7:
        logging.warning(f"[decode_numeric_feature] Insufficient data for numeric feature '{feature_name}'.")
        return {
            "featureName": feature_name,
            "dataType": "NUMERIC",
            "aggregatedNotNull": 0
        }
    
    return {
        "featureName": feature_name,
        "dataType": "NUMERIC",
        "aggregatedNotNull": data[0],
        "aggregatedMin": data[1],
        "aggregatedMax": data[2],
        "aggregatedAvg": data[3],
        "aggregatedQ1": data[4],
        "aggregatedQ2": data[5],
        "aggregatedQ3": data[6]
    }


def decode_categorical_feature(feature_name: str, data: list, fields: list) -> dict:
    """
    Decode categorical feature data
    
    Args:
        feature_name: Name of the feature
        data: Aggregated data slice [numOfNotNull, numUniqueValues, topValueCount]
        fields: Field names
        
    Returns:
        Decoded categorical feature information
    """
    if len(data) < 3:
        logging.warning(f"[decode_categorical_feature] Insufficient data for categorical feature '{feature_name}'.")
        return {
            "featureName": feature_name,
            "dataType": "CATEGORICAL",
            "aggregatedNotNull": 0
        }
    
    aggregated_not_null = data[0]
    num_unique_values = data[1]
    top_value_count = data[2]
    diversity = (num_unique_values / aggregated_not_null * 100.0) if aggregated_not_null > 0 else 0.0
    
    return {
        "featureName": feature_name,
        "dataType": "CATEGORICAL",
            "aggregatedNotNull": aggregated_not_null,
        "aggregatedUniqueValues": num_unique_values,
        "aggregatedTopValueCount": top_value_count,
        "diversity": round(diversity, 2)
    }


def decode_generic_feature(feature_name: str, data_type: str, data: list, fields: list) -> dict:
    """
    Generic decoder for unknown feature types
    
    Args:
        feature_name: Name of the feature
        data_type: Data type string
        data: Aggregated data slice
        fields: Field names
        
    Returns:
        Decoded feature information
    """
    result = {
        "featureName": feature_name,
        "dataType": data_type,
        "aggregatedNotNull": data[0] if len(data) > 0 else 0
    }
    
    # Map remaining fields to values
    for i, field in enumerate(fields[1:], 1):  # Skip first field (numOfNotNull)
        if i < len(data):
            result[f"aggregated{field.capitalize()}"] = data[i]
    
    return result

def handle_final_results(output_data: list, job_id: str, updated_clients: list):
    """
    Handle final decoded output using the new AggregatedResultsHandler.
    Supports both API sending and filesystem saving based on environment configuration.
    """
    # Initialize the results handler
    results_handler = AggregatedResultsHandler(default_save_path=RESULTS_SAVE_PATH)
    
    # Determine which operations to perform
    api_url = RESULTS_API_URL if ENABLE_API_SENDING else None
    
    if ENABLE_FILESYSTEM_SAVING or api_url:
        # Use the combined method for efficiency
        results = results_handler.send_and_save(
            aggregated_data=output_data,
            job_id=job_id,
            client_list=updated_clients,
            api_url=api_url,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        # Log results
        if api_url and not results['api_success']:
            logging.error(f"[Aggregator] Failed to send results to API for job {job_id}")
        if ENABLE_FILESYSTEM_SAVING and not results['save_success']:
            logging.error(f"[Aggregator] Failed to save results to filesystem for job {job_id}")
    else:
        # Both API sending and filesystem saving are disabled - log results instead
        logging.info(f"[Aggregator] Both API sending and filesystem saving disabled - logging results for job {job_id}")
        logging.info(f"[Aggregator] Job: {job_id}, Clients: {updated_clients}, Features: {len(output_data)}")
        
        for i, feature_data in enumerate(output_data, 1):
            feature_name = feature_data.get('featureName', 'Unknown')
            data_type = feature_data.get('dataType', 'Unknown')
            logging.info(f"[Aggregator] Feature {i}/{len(output_data)}: {feature_name} ({data_type})")
            
            # Log key aggregation results based on data type
            if data_type == "NUMERIC":
                avg = feature_data.get('aggregatedAvg', 'N/A')
                sum_val = feature_data.get('aggregatedSum', 'N/A')
                not_null = feature_data.get('aggregatedNotNull', 'N/A')
                logging.info(f"[Aggregator]   → NotNull: {not_null}, Sum: {sum_val}, Avg: {avg}")
            elif data_type == "BOOLEAN":
                not_null = feature_data.get('aggregatedNotNull', 'N/A')
                true_count = feature_data.get('aggregatedTrue', 'N/A')
                percentage = feature_data.get('percentageTrue', 'N/A')
                logging.info(f"[Aggregator]   → NotNull: {not_null}, True: {true_count}, Percentage: {percentage}%")
            elif data_type in ["CATEGORICAL", "NOMINAL", "ORDINAL"]:
                not_null = feature_data.get('aggregatedNotNull', 'N/A')
                unique = feature_data.get('aggregatedUniqueValues', 'N/A')
                diversity = feature_data.get('diversity', 'N/A')
                logging.info(f"[Aggregator]   → NotNull: {not_null}, Unique: {unique}, Diversity: {diversity}%")
            else:
                # Generic logging for unknown types
                not_null = feature_data.get('aggregatedNotNull', 'N/A')
                logging.info(f"[Aggregator]   → NotNull: {not_null}, Data: {feature_data}")
        
        logging.info(f"[Aggregator] Results logging completed for job {job_id}")


def send_final_output(output_data: list, updated_clients: list):
    """
    Legacy function - kept for backward compatibility.
    Uses chaincode for specific blockchain integration.
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