from src.app import create_app
from src.workers import stop_worker
import atexit

app = create_app()

# Register cleanup handler
atexit.register(stop_worker)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        stop_worker()

