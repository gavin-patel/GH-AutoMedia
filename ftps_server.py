import os
import queue
import re
import threading
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.handlers.ftp.dispatchers import PassiveDTP

from processor import process_photo, process_raw_photo

UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", "cloud_input"))
FTPS_CONTROL_PORT = int(os.environ.get("FTPS_CONTROL_PORT", "2121"))
PASSIVE_PORTS = tuple(range(30000, 30010))
PUBLIC_PASSIVE_PORTS = tuple(range(55968, 55978))
PUBLIC_HOST = os.environ.get("FTPS_PUBLIC_HOST", "138.199.236.200")
PUBLIC_CONTROL_PORT = os.environ.get("FTPS_PUBLIC_CONTROL_PORT", "55967")
CERT_FILE = Path(os.environ.get("FTPS_CERT_FILE", "ftps-cert.pem"))
KEY_FILE = Path(os.environ.get("FTPS_KEY_FILE", "ftps-key.pem"))

try:
    import rawpy
except ImportError as error:
    rawpy = None
    RAW_SUPPORT_ERROR = str(error)
else:
    RAW_SUPPORT_ERROR = ""


class TranslatedPassiveDTP(PassiveDTP):
    """Bind JustRunMy's internal passive ports and advertise its public ports."""

    def __init__(self, cmd_channel, extmode=False):
        original_respond = cmd_channel.respond

        def respond(message, *args, **kwargs):
            message = self._translate_response(message)
            return original_respond(message, *args, **kwargs)

        cmd_channel.respond = respond
        try:
            super().__init__(cmd_channel, extmode)
        finally:
            cmd_channel.respond = original_respond

    def _translate_response(self, message):
        match = re.search(r"^(227 .*?,)(\d+),(\d+)\)\.?$", message)
        if match:
            internal_port = int(match.group(2)) * 256 + int(match.group(3))
            external_port = self.cmd_channel.external_passive_port_map.get(
                internal_port,
                internal_port,
            )
            return f"{match.group(1)}{external_port // 256},{external_port % 256})."

        match = re.search(r"^(229 .*\|\|\|)(\d+)(\|)\)\.?$", message)
        if match:
            internal_port = int(match.group(2))
            external_port = self.cmd_channel.external_passive_port_map.get(
                internal_port,
                internal_port,
            )
            return f"{match.group(1)}{external_port}{match.group(3)})."

        return message


class UploadHandler(TLS_FTPHandler):
    passive_dtp = TranslatedPassiveDTP
    passive_ports = PASSIVE_PORTS
    tls_control_required = True
    tls_data_required = True
    permit_foreign_addresses = False
    external_passive_port_map = dict(zip(PASSIVE_PORTS, PUBLIC_PASSIVE_PORTS))
    upload_queue = None

    def on_file_received(self, file):
        suffix = Path(file).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".cr3"}:
            self.upload_queue.put(Path(file))
            print(f"FTPS upload complete: {file}", flush=True)
        else:
            print(f"Ignoring unsupported upload: {file}", flush=True)


def ensure_certificate():
    if CERT_FILE.exists() and KEY_FILE.exists():
        return "configured certificate"

    if os.environ.get("FTPS_AUTO_GENERATE_CERT", "1") != "1":
        raise RuntimeError(
            f"FTPS certificate files not found: {CERT_FILE} and {KEY_FILE}"
        )

    CERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, PUBLIC_HOST),
    ])
    names = [x509.DNSName(PUBLIC_HOST)]
    try:
        names.append(x509.IPAddress(ipaddress.ip_address(PUBLIC_HOST)))
    except ValueError:
        pass
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .sign(key, hashes.SHA256())
    )
    KEY_FILE.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    CERT_FILE.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    os.chmod(KEY_FILE, 0o600)
    return "self-signed certificate generated at startup"


def _process_uploads(upload_queue, stop_event):
    while not stop_event.is_set():
        try:
            path = upload_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            if path.suffix.lower() in {".jpg", ".jpeg"}:
                process_photo(str(path))
            elif path.suffix.lower() == ".cr3":
                if rawpy is None:
                    raise RuntimeError(
                        f"CR3 support unavailable: {RAW_SUPPORT_ERROR}"
                    )
                process_raw_photo(str(path))
        except Exception as error:
            print(f"Upload processing failed for {path}: {error}", flush=True)
        finally:
            upload_queue.task_done()


def create_server():
    username = os.environ.get("FTP_USERNAME")
    password = os.environ.get("FTP_PASSWORD")
    if not username or not password:
        raise RuntimeError("FTP_USERNAME and FTP_PASSWORD must be set")

    certificate_status = ensure_certificate()
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    upload_queue = queue.Queue()
    stop_event = threading.Event()

    authorizer = DummyAuthorizer()
    authorizer.add_user(username, password, str(UPLOAD_FOLDER), perm="elw")

    UploadHandler.certfile = str(CERT_FILE)
    UploadHandler.keyfile = str(KEY_FILE)
    UploadHandler.authorizer = authorizer
    UploadHandler.upload_queue = upload_queue
    UploadHandler.masquerade_address = PUBLIC_HOST

    server = FTPServer(("0.0.0.0", FTPS_CONTROL_PORT), UploadHandler)
    worker = threading.Thread(
        target=_process_uploads,
        args=(upload_queue, stop_event),
        name="photo-processing-worker",
        daemon=True,
    )
    server.upload_queue = upload_queue
    server.stop_event = stop_event
    server.worker = worker
    server.certificate_status = certificate_status
    return server


def serve():
    server = create_server()
    print(
        f"FTPS control listening on {FTPS_CONTROL_PORT} "
        f"(public {PUBLIC_HOST}:{PUBLIC_CONTROL_PORT})",
        flush=True,
    )
    print(
        f"FTPS passive internal ports {PASSIVE_PORTS}; "
        f"public ports {PUBLIC_PASSIVE_PORTS}",
        flush=True,
    )
    print(f"FTPS TLS: {server.certificate_status}", flush=True)
    if rawpy is None:
        print(f"CR3/RAW support unavailable: {RAW_SUPPORT_ERROR}", flush=True)
    else:
        print("CR3/RAW support initialized with rawpy", flush=True)

    server.worker.start()
    try:
        server.serve_forever()
    finally:
        server.stop_event.set()
        server.close_all()
