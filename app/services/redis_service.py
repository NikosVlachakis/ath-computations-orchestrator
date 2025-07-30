# services/redis_service.py

import redis
import json
import logging
import sys

# Import self-contained logging (optional)
try:
    from logging_config import get_logger
    CENTRALIZED_LOGGING = True
except ImportError:
    CENTRALIZED_LOGGING = False

class RedisService:
    def __init__(self, host="redis", port=6379, db=0):
        self._client = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def create_job_record(self, job_id: str, total_clients: int):
        key = f"job:{job_id}"
        if not self._client.exists(key):
            self._client.hset(key, mapping={
                "totalClients": total_clients,
                "doneCount": 0,
                "schema": "",
                "finalResult": ""
            })
            self._client.delete(f"{key}:updatedClients")
            logging.info(f"[RedisService] Created job record for {job_id} with totalClients={total_clients}")

    def job_exists(self, job_id: str) -> bool:
        key = f"job:{job_id}"
        return self._client.exists(key) == 1

    def store_schema(self, job_id: str, schema):
        key = f"job:{job_id}"
        current_schema = self._client.hget(key, "schema")
        if not current_schema:
            self._client.hset(key, "schema", json.dumps(schema))
            logging.info(f"[RedisService] Stored schema for job {job_id}.")

    def increment_done_count(self, job_id: str, client_id: str):
        clients_key = f"job:{job_id}:updatedClients"
        already_member = self._client.sismember(clients_key, client_id)
        if not already_member:
            self._client.sadd(clients_key, client_id)
            self._client.hincrby(f"job:{job_id}", "doneCount", 1)

            done_count = int(self._client.hget(f"job:{job_id}", "doneCount"))
            total_clients = int(self._client.hget(f"job:{job_id}", "totalClients"))
            logging.info(f"[RedisService] job={job_id}, clientId={client_id}, doneCount={done_count}/{total_clients}")
        else:
            logging.info(f"[RedisService] job={job_id}, clientId={client_id} already updated. No increment.")

    def get_job_info(self, job_id: str) -> dict:
        key = f"job:{job_id}"
        if not self._client.exists(key):
            return {}
        data = self._client.hgetall(key)
        data["totalClients"] = int(data["totalClients"]) if data["totalClients"] else 0
        data["doneCount"] = int(data["doneCount"]) if data["doneCount"] else 0
        data["schema"] = json.loads(data["schema"]) if data["schema"] else None
        data["finalResult"] = json.loads(data["finalResult"]) if data["finalResult"] else None

        clients_key = f"{key}:updatedClients"
        data["updatedClients"] = self._client.smembers(clients_key)
        return data

    def set_final_result(self, job_id: str, final_result: dict):
        key = f"job:{job_id}"
        self._client.hset(key, "finalResult", json.dumps(final_result))
        logging.info(f"[RedisService] finalResult stored for job {job_id}.")

redis_service = RedisService(host="redis", port=6379)
