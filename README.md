# Computations Orchestrator

## 🎯 Overview
Coordinates multi-client job execution and manages secure aggregation workflows with Redis-based state management.

## 🏗️ Features
- **Multi-Client Coordination** - Tracks completion across multiple participants
- **Redis State Management** - Persistent job metadata and schemas
- **Aggregation Control** - Triggers secure aggregation when all clients complete
- **Aggregated Results Handler** - Send results to nodes and save to filesystem (optional)

## 🔌 API Endpoints

### Job Update (Client Completion)
**POST** `/api/update`
```json
{
  "jobId": "shared_job_123",
  "clientId": "client_A",
  "totalClients": 3,
  "schema": [
    {"name": "age", "dataType": "NUMERIC"},
    {"name": "isActive", "dataType": "BOOLEAN"}
  ]
}
```

**Response**:
```json
{
  "message": "Update for job shared_job_123, client client_A recorded."
}
```

### Job Status Check
**GET** `/api/job-status/{jobId}`

**Response**:
```json
{
  "message": "Job shared_job_123 is in progress (doneCount=2/3).",
  "jobInfo": {
    "totalClients": 3,
    "doneCount": 2,
    "schema": [...],
    "finalResult": null
  }
}
```

## 🔄 Workflow
1. **Client Registration** - First client creates job record
2. **Schema Storage** - Job schema stored on first update
3. **Progress Tracking** - Each client completion tracked via totalClients count
4. **Aggregation Trigger** - When all clients complete, triggers aggregator
5. **Result sending** - Results are sent to the nodes and saved to the filesystem (optional)


## 📄 Centralized Logging

### Log Location
**File**: `../logs/computations-orchestrator.log`
**Format**: `timestamp LEVEL [component] [computations-orchestrator] message`


### Output Formats
**JSON Format**: Complete structured data with metadata  
**TXT Format**: Human-readable summary with feature breakdowns  
**API Payload**: Structured JSON with job context and timestamps

## 📋 Dependencies
- Docker & Docker Compose
- Python Flask application
- Redis 6.2+ (included in docker-compose)
