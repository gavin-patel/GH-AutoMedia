import threading

from app import app
from ftps_server import serve


def main():
    ftps_thread = threading.Thread(target=serve, name="ftps-server", daemon=True)
    ftps_thread.start()
    print("Flask dashboard listening on 8080", flush=True)
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
