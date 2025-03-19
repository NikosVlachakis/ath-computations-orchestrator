# Computations Orchestrator

A microservice that manages and coordinates secure multi-party computation (SMPC) jobs. The service:

1. **Client Tracking**: Tracks each client's progress in vectorizing their data and submitting their updates to the smpc client.
2. **Update Management**: Collects and validates update notifications from clients when they complete their SMPC client updates
3. **Aggregation Coordination**: Initiates secure aggregation automatically once all participating clients in a job have submitted their updates
4. **Result Retrieval**: Polls the smpc coordinator until the computation is finished and retrieves the final result.

## **How to Run**

The Computations Orchestrator can be deployed in **two different environments**:  
1. **Development Mode** (builds locally)  
2. **Production Mode** (uses prebuilt Docker Hub image)

### **Running in Development Mode**
This option is for testing or local development, where the image is built directly from the local codebase.

```bash
docker-compose -f docker-compose.dev.yml up --build
```

### **Running in Production Mode**
If you want to use the prebuilt image from Docker Hub, run:

```bash
docker-compose -f docker-compose.prod.yml up -d
```
