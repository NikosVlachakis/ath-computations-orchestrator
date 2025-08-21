# Computations Orchestrator

## 🎯 Overview
Coordinates multi-client job execution and manages secure aggregation workflows with Redis-based state management.

## 🏗️ Features
- **Multi-Client Coordination** - Tracks completion across multiple participants
- **Redis State Management** - Persistent job metadata and schemas
- **Aggregation Control** - Triggers secure aggregation when all clients complete
- **Aggregated Results Handler** - Send results to external APIs and save to filesystem
- **Centralized Logging** - All activities logged to `../logs/computations-orchestrator.log`

## 🚀 Quick Start

### Start Service
```powershell
docker-compose up -d
```

### Verify Running
```powershell
docker ps
# Should show: computations_orchestrator_container, computations_redis
```

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
5. **Result Storage** - Final aggregated results stored

## 🧪 Testing

### Centralized Logging Tests
```powershell
python test_centralized_logging.py
```
**Expected**: 9/9 tests pass ✅

**Test Coverage:**
- Log directory creation and permissions
- Container startup logging
- HTTP endpoint logging (GET /, GET /api/job-status)
- API update request logging with totalClients support
- Redis operations (job creation, schema storage, completion tracking)
- Error logging with clear marking
- Log format validation (timestamp, service identification)
- Log persistence on host machine
- Complete pipeline logging workflow

### Test Examples
```powershell
# Test single client scenario
curl -X POST http://localhost:5000/api/update \
  -H "Content-Type: application/json" \
  -d '{"jobId": "test_123", "clientId": "client_1", "totalClients": 1}'

# Test multi-client scenario
curl -X POST http://localhost:5000/api/update \
  -H "Content-Type: application/json" \
  -d '{"jobId": "test_123", "clientId": "client_1", "totalClients": 3}'

# Check job status
curl http://localhost:5000/api/job-status/test_123
```

## 📄 Centralized Logging

### Log Location
**File**: `../logs/computations-orchestrator.log`
**Format**: `timestamp LEVEL [component] [computations-orchestrator] message`

### What Gets Logged
- ✅ Service startup and Flask initialization
- ✅ Every HTTP request received
- ✅ Job creation and client registration with totalClients
- ✅ Redis operations (create, update, retrieve)
- ✅ Schema storage and validation
- ✅ Aggregation triggers and results
- ✅ Error conditions with full context

## 🔧 Configuration

### Environment Variables
- **Redis Host**: `redis` (automatic via docker-compose)
- **Port**: `5000` (configurable)

### Redis Schema
```
Keys:
- job:{jobId} → Hash with totalClients, doneCount, schema, finalResult
- job:{jobId}:updatedClients → Set of completed client IDs
```

## 🔧 Aggregated Results Configuration

### Environment Variables
Configure in `docker-compose.yml`:
```yaml
environment:
  - RESULTS_API_URL=http://external-api:8080/api/results  # API endpoint for results
  - RESULTS_SAVE_PATH=/app/results  # Filesystem path to save results  
  - ENABLE_API_SENDING=true  # Enable/disable API sending (default: true)
  - ENABLE_FILESYSTEM_SAVING=true  # Enable/disable filesystem saving (default: true)
```

### Results Handler Features
- **API Integration**: Send aggregated results to external services
- **Filesystem Persistence**: Save results as JSON or TXT files
- **Logging Fallback**: When both API and filesystem are disabled, results are logged
- **Flexible Configuration**: Enable/disable individual features
- **Error Handling**: Robust error handling with detailed logging
- **Batch Operations**: Combined API + filesystem operations

### Example Usage
```python
from services.aggregated_results_handler import AggregatedResultsHandler

handler = AggregatedResultsHandler(default_save_path="/app/results")

# Send to API and save to filesystem
results = handler.send_and_save(
    aggregated_data=decoded_features,
    job_id="job_123",
    client_list=["client1", "client2"],
    api_url="https://api.example.com/results"
)
```

### Testing
Run comprehensive tests with examples:
```bash
cd tests
python test_aggregated_results_handler.py
```

### Output Modes

**1. API + Filesystem (Both Enabled)**:
- Sends results to external API AND saves to filesystem
- Provides maximum persistence and integration

**2. Single Mode (One Enabled)**:
- Either API sending OR filesystem saving
- Choose based on your infrastructure needs

**3. Logging Mode (Both Disabled)**:
- Results are logged with detailed breakdown
- Perfect for debugging and monitoring
- Example log output:
```
[Aggregator] Feature 1/3: age (NUMERIC)
[Aggregator]   → NotNull: 1000, Sum: 45000, Avg: 45.0
[Aggregator] Feature 2/3: is_employed (BOOLEAN)  
[Aggregator]   → NotNull: 1000, True: 750, Percentage: 75.0%
```

### Output Formats
**JSON Format**: Complete structured data with metadata  
**TXT Format**: Human-readable summary with feature breakdowns  
**API Payload**: Structured JSON with job context and timestamps

## 📋 Dependencies
- Docker & Docker Compose
- Python Flask application
- Redis 6.2+ (included in docker-compose)

---
✅ **Independent orchestration service with Redis coordination and totalClients support**
