import logging
import sys
import os
from flask import Flask
from orchestrator_service import orchestrator_bp

# Import self-contained logging configuration
try:
    from logging_config import setup_service_logging
    CENTRALIZED_LOGGING = True
except ImportError:
    CENTRALIZED_LOGGING = False

def create_app():
    if CENTRALIZED_LOGGING:
        # Setup centralized logging
        logger_instance = setup_service_logging('computations-orchestrator')
        logger_instance.log_action("Initializing Computations Orchestrator Flask Application")
    else:
        # Fallback to original logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
        logging.info("Initializing Computations Orchestrator Flask Application")

    app = Flask(__name__)
    app.register_blueprint(orchestrator_bp)
    
    if CENTRALIZED_LOGGING:
        logger_instance.log_success("Flask application created successfully")
    else:
        logging.info("Flask application created successfully")
    return app

if __name__ == "__main__":
    app = create_app()
    logging.info("Starting Computations Orchestrator on 0.0.0.0:5000")
    # Listen on all interfaces at port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
