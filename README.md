# Computations Orchestrator

A microservice that manages and coordinates secure multi-party computation (SMPC) jobs. The service:

1. **Client Tracking**: Tracks each client's progress in vectorizing their data and submitting their updates to the smpc client.
2. **Update Management**: Collects and validates update notifications from clients when they complete their SMPC client updates
3. **Aggregation Coordination**: Initiates secure aggregation automatically once all participating clients in a job have submitted their updates
4. **Result Retrieval**: Polls the smpc coordinator until the computation is finished and retrieves the final result.

## How to Run

To start the orchestrator, simply execute:

```bash
docker-compose up --build
```

If you want to skip building and use the prebuilt image from Docker Hub:
```bash
docker run --rm -p 5000:5000 nikosvlah/computations-orchestrator:latest
```