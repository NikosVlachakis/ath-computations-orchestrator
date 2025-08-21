import logging
import sys
from flask import Blueprint, request, jsonify
from aggregator_manager import trigger_and_poll_aggregator
from threading import Thread
from services.redis_service import redis_service

# Import self-contained logging (optional)
try:
    from logging_config import get_logger
    CENTRALIZED_LOGGING = True
except ImportError:
    CENTRALIZED_LOGGING = False

orchestrator_bp = Blueprint("orchestrator_bp", __name__)

def _is_job_completed(job_info: dict) -> bool:
    """
    Checks whether a job's finalResult indicates the job is completed.
    """
    final_result = job_info.get("finalResult")
    return bool(final_result and final_result.get("status") == "COMPLETED")

@orchestrator_bp.route("/api/update", methods=["POST"])
def update_job():
    data = request.json
    job_id = str(data["jobId"])
    client_id = str(data["clientId"])
    
    # Get total clients from totalClients parameter
    total_clients = int(data["totalClients"])
    
    schema = data.get("schema")  # may be None
    
    logging.info(f"[Orchestrator] Received update request for job {job_id}, client {client_id}")

    # 1) Create job record if not exists
    if not redis_service.job_exists(job_id):
        redis_service.create_job_record(job_id, total_clients)

    # 2) Fetch job info
    job_info = redis_service.get_job_info(job_id)

    # 3) Early exit if job is already completed
    if _is_job_completed(job_info):
        msg = f"Job {job_id} is already completed. No further updates are needed."
        logging.info(f"[Orchestrator] {msg}")
        return jsonify({"message": msg}), 200

    # 4) If a schema is provided and not stored yet, store it
    if schema and not job_info.get("schema"):
        redis_service.store_schema(job_id, schema)

    # Refresh job info after possibly storing schema
    job_info = redis_service.get_job_info(job_id)

    # 5) If this client hasn't updated, increment doneCount
    if client_id not in job_info["updatedClients"]:
        redis_service.increment_done_count(job_id, client_id)
        job_info = redis_service.get_job_info(job_id)

        # 6) If all clients are done, trigger aggregator
        if job_info["doneCount"] >= job_info["totalClients"]:
            logging.info(f"[Orchestrator] All clients done for job {job_id}. Triggering aggregator in background.")
            Thread(target=aggregator_task, args=(job_id,)).start()
    else:
        logging.info(f"[Orchestrator] job={job_id}, clientId={client_id} already updated. No increment.")

    return jsonify({"message": f"Update for job {job_id}, client {client_id} recorded."}), 200

def aggregator_task(job_id: str):
    from datetime import datetime
    
    result_json = trigger_and_poll_aggregator(job_id)
    if result_json:
        # Add completion timestamp to final result
        result_json["completedAt"] = datetime.now().isoformat()
        result_json["timestamp"] = datetime.now().isoformat()  # For backward compatibility
        
        redis_service.set_final_result(job_id, result_json)
        logging.info(f"[Orchestrator] Final result stored for job {job_id} with timestamp")
    else:
        logging.warning(f"[Orchestrator] aggregator returned empty or error for job {job_id}.")


@orchestrator_bp.route("/api/job-status/<job_id>", methods=["GET"])
def get_job_status(job_id):
    # 1) Check if the job exists in Redis
    if not redis_service.job_exists(job_id):
        return jsonify({"error": f"Unknown jobId {job_id}"}), 404

    # 2) Fetch job info from Redis
    job_info = redis_service.get_job_info(job_id)

    # 3) Check if we have a finalResult and its status
    final_result = job_info.get("finalResult")
    if final_result and final_result.get("status") == "COMPLETED":
        # Job is fully completed (aggregator finished)
        
        # Extract aggregated results for polling nodes
        aggregated_results = final_result.get("decodedFeatures", [])
        
        return jsonify({
            "status": "COMPLETED",
            "jobId": job_id,
            "message": f"Job {job_id} is completed.",
            "aggregatedResults": aggregated_results,
            "metadata": {
                "totalFeatures": len(aggregated_results),
                "totalClients": job_info.get("totalClients", 0),
                "completedAt": final_result.get("completedAt") or final_result.get("timestamp"),
                "doneCount": job_info.get("doneCount", 0)
            },
            "jobInfo": job_info
        }), 200
    elif final_result and final_result.get("status") in ["FAILED", "ERROR"]:
        # Job failed
        return jsonify({
            "status": "FAILED", 
            "jobId": job_id,
            "message": f"Job {job_id} failed during aggregation.",
            "error": final_result.get("error", "Unknown error"),
            "jobInfo": job_info
        }), 200
    else:
        # Not completed yet - in progress
        done_count = job_info.get("doneCount", 0)
        total_clients = job_info.get("totalClients", 0)
        
        # Determine current status
        if done_count == 0:
            status = "WAITING"
        elif done_count < total_clients:
            status = "IN_PROGRESS"
        elif done_count >= total_clients:
            status = "AGGREGATING"  # All clients done, aggregation in progress
        else:
            status = "UNKNOWN"
            
        return jsonify({
            "status": status,
            "jobId": job_id,
            "message": f"Job {job_id} is {status.lower()} (doneCount={done_count}/{total_clients}).",
            "progress": {
                "doneCount": done_count,
                "totalClients": total_clients,
                "percentage": round((done_count / total_clients * 100), 1) if total_clients > 0 else 0
            },
            "jobInfo": job_info
        }), 200
