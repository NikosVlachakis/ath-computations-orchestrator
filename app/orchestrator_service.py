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
    result_json = trigger_and_poll_aggregator(job_id)
    if result_json:
        redis_service.set_final_result(job_id, result_json)
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
        return jsonify({
            "message": f"Job {job_id} is completed.",
            "jobInfo": job_info
        }), 200
    else:
        # Not completed yet
        done_count = job_info.get("doneCount", 0)
        total_clients = job_info.get("totalClients", 0)
        return jsonify({
            "message": f"Job {job_id} is in progress (doneCount={done_count}/{total_clients}).",
            "jobInfo": job_info
        }), 200
