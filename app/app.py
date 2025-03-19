import logging
from flask import Flask
from orchestrator_service import orchestrator_bp

def create_app():
    # Configure logging to go to stdout, including INFO level
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    app = Flask(__name__)
    app.register_blueprint(orchestrator_bp)
    return app

if __name__ == "__main__":
    app = create_app()
    # Listen on all interfaces at port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
