"""Minimal Reticulum Page Node
Serves .mu pages and files over RNS.
"""

import argparse
import logging
import os
import subprocess
import threading
import time

import RNS

logger = logging.getLogger(__name__)

DEFAULT_INDEX = """>Default Home Page

This node is serving pages using rns-page-node, but the home page file (index.mu) was not found in the pages directory. Please add an index.mu file to customize the home page.
"""

DEFAULT_NOTALLOWED = """>Request Not Allowed

You are not authorised to carry out the request.
"""


class PageNode:
    def __init__(
        self,
        identity,
        pagespath,
        filespath,
        announce_interval=360,
        name=None,
        page_refresh_interval=0,
        file_refresh_interval=0,
    ):
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.logger = logging.getLogger(f"{__name__}.PageNode")
        self.identity = identity
        self.name = name
        self.pagespath = pagespath
        self.filespath = filespath
        self.destination = RNS.Destination(
            identity, RNS.Destination.IN, RNS.Destination.SINGLE, "nomadnetwork", "node",
        )
        self.announce_interval = announce_interval
        self.last_announce = 0
        self.page_refresh_interval = page_refresh_interval
        self.file_refresh_interval = file_refresh_interval
        self.last_page_refresh = time.time()
        self.last_file_refresh = time.time()

        self.register_pages()
        self.register_files()

        self.destination.set_link_established_callback(self.on_connect)

        self._announce_thread = threading.Thread(
            target=self._announce_loop, daemon=True,
        )
        self._announce_thread.start()
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()

    def register_pages(self):
        with self._lock:
            self.servedpages = []
            self._scan_pages(self.pagespath)

        if not os.path.isfile(os.path.join(self.pagespath, "index.mu")):
            self.destination.register_request_handler(
                "/page/index.mu",
                response_generator=self.serve_default_index,
                allow=RNS.Destination.ALLOW_ALL,
            )

        for full_path in self.servedpages:
            rel = full_path[len(self.pagespath) :]
            request_path = f"/page{rel}"
            self.destination.register_request_handler(
                request_path,
                response_generator=self.serve_page,
                allow=RNS.Destination.ALLOW_ALL,
            )

    def register_files(self):
        with self._lock:
            self.servedfiles = []
            self._scan_files(self.filespath)

        for full_path in self.servedfiles:
            rel = full_path[len(self.filespath) :]
            request_path = f"/file{rel}"
            self.destination.register_request_handler(
                request_path,
                response_generator=self.serve_file,
                allow=RNS.Destination.ALLOW_ALL,
                auto_compress=32_000_000,
            )

    def _scan_pages(self, base):
        for entry in os.listdir(base):
            if entry.startswith("."):
                continue
            path = os.path.join(base, entry)
            if os.path.isdir(path):
                self._scan_pages(path)
            elif os.path.isfile(path) and not entry.endswith(".allowed"):
                self.servedpages.append(path)

    def _scan_files(self, base):
        for entry in os.listdir(base):
            if entry.startswith("."):
                continue
            path = os.path.join(base, entry)
            if os.path.isdir(path):
                self._scan_files(path)
            elif os.path.isfile(path):
                self.servedfiles.append(path)

    @staticmethod
    def serve_default_index(
        path, data, request_id, link_id, remote_identity, requested_at,
    ):
        return DEFAULT_INDEX.encode("utf-8")

    def serve_page(
        self, path, data, request_id, link_id, remote_identity, requested_at,
    ):
        file_path = path.replace("/page", self.pagespath, 1)
        try:
            with open(file_path, "rb") as _f:
                first_line = _f.readline()
            is_script = first_line.startswith(b"#!")
        except Exception:
            is_script = False
        if is_script and os.access(file_path, os.X_OK):
            # Note: The execution of file_path is intentional here, as some pages are designed to be executable scripts.
            # This is acknowledged as a potential security risk if untrusted input can control file_path.
            try:
                result = subprocess.run([file_path], stdout=subprocess.PIPE, check=True)  # noqa: S603
                return result.stdout
            except Exception:
                self.logger.exception("Error executing script page")
        with open(file_path, "rb") as f:
            return f.read()

    def serve_file(
        self, path, data, request_id, link_id, remote_identity, requested_at,
    ):
        file_path = path.replace("/file", self.filespath, 1)
        return [
            open(file_path, "rb"),
            {"name": os.path.basename(file_path).encode("utf-8")},
        ]

    def on_connect(self, link):
        pass

    def _announce_loop(self):
        try:
            while not self._stop_event.is_set():
                if time.time() - self.last_announce > self.announce_interval:
                    if self.name:
                        self.destination.announce(app_data=self.name.encode("utf-8"))
                    else:
                        self.destination.announce()
                    self.last_announce = time.time()
                time.sleep(1)
        except Exception:
            self.logger.exception("Error in announce loop")

    def _refresh_loop(self):
        try:
            while not self._stop_event.is_set():
                now = time.time()
                if (
                    self.page_refresh_interval > 0
                    and now - self.last_page_refresh > self.page_refresh_interval
                ):
                    self.register_pages()
                    self.last_page_refresh = now
                if (
                    self.file_refresh_interval > 0
                    and now - self.last_file_refresh > self.file_refresh_interval
                ):
                    self.register_files()
                    self.last_file_refresh = now
                time.sleep(1)
        except Exception:
            self.logger.exception("Error in refresh loop")

    def shutdown(self):
        self.logger.info("Shutting down PageNode...")
        self._stop_event.set()
        try:
            self._announce_thread.join(timeout=5)
            self._refresh_thread.join(timeout=5)
        except Exception:
            self.logger.exception("Error waiting for threads to shut down")
        try:
            if hasattr(self.destination, "close"):
                self.destination.close()
        except Exception:
            self.logger.exception("Error closing RNS destination")


def main():
    parser = argparse.ArgumentParser(description="Minimal Reticulum Page Node")
    parser.add_argument(
        "-c", "--config", dest="configpath", help="Reticulum config path", default=None,
    )
    parser.add_argument(
        "-p",
        "--pages-dir",
        dest="pages_dir",
        help="Pages directory",
        default=os.path.join(os.getcwd(), "pages"),
    )
    parser.add_argument(
        "-f",
        "--files-dir",
        dest="files_dir",
        help="Files directory",
        default=os.path.join(os.getcwd(), "files"),
    )
    parser.add_argument(
        "-n", "--node-name", dest="node_name", help="Node display name", default=None,
    )
    parser.add_argument(
        "-a",
        "--announce-interval",
        dest="announce_interval",
        type=int,
        help="Announce interval in seconds",
        default=360,
    )
    parser.add_argument(
        "-i",
        "--identity-dir",
        dest="identity_dir",
        help="Directory to store node identity",
        default=os.path.join(os.getcwd(), "node-config"),
    )
    parser.add_argument(
        "--page-refresh-interval",
        dest="page_refresh_interval",
        type=int,
        default=0,
        help="Page refresh interval in seconds, 0 disables auto-refresh",
    )
    parser.add_argument(
        "--file-refresh-interval",
        dest="file_refresh_interval",
        type=int,
        default=0,
        help="File refresh interval in seconds, 0 disables auto-refresh",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    configpath = args.configpath
    pages_dir = args.pages_dir
    files_dir = args.files_dir
    node_name = args.node_name
    announce_interval = args.announce_interval
    identity_dir = args.identity_dir
    page_refresh_interval = args.page_refresh_interval
    file_refresh_interval = args.file_refresh_interval
    numeric_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level, format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    RNS.Reticulum(configpath)
    os.makedirs(identity_dir, exist_ok=True)
    identity_file = os.path.join(identity_dir, "identity")
    if os.path.isfile(identity_file):
        identity = RNS.Identity.from_file(identity_file)
    else:
        identity = RNS.Identity()
        identity.to_file(identity_file)

    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(files_dir, exist_ok=True)

    node = PageNode(
        identity,
        pages_dir,
        files_dir,
        announce_interval,
        node_name,
        page_refresh_interval,
        file_refresh_interval,
    )
    logger.info("Page node running. Press Ctrl-C to exit.")
    logger.info("Node address: %s", RNS.prettyhexrep(node.destination.hash))


    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        node.shutdown()


if __name__ == "__main__":
    main()
