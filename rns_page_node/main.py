"""Minimal Reticulum Page Node.

Serves .mu pages and files over RNS.
"""

import argparse
import os
import subprocess
import threading
import time
from pathlib import Path

import RNS

DEFAULT_INDEX = """>Default Home Page

This node is serving pages using rns-page-node, but index.mu was not found.
Please add an index.mu file to customize the home page.
"""

DEFAULT_NOTALLOWED = """>Request Not Allowed

You are not authorised to carry out the request.
"""


class PageNode:
    """A Reticulum page node that serves .mu pages and files over RNS."""

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
        """Initialize the PageNode.

        Args:
            identity: RNS Identity for the node
            pagespath: Path to directory containing .mu pages
            filespath: Path to directory containing files to serve
            announce_interval: Seconds between announcements (default: 360)
            name: Display name for the node (optional)
            page_refresh_interval: Seconds between page rescans (0 = disabled)
            file_refresh_interval: Seconds between file rescans (0 = disabled)

        """
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.identity = identity
        self.name = name
        self.pagespath = pagespath
        self.filespath = filespath
        self.destination = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "nomadnetwork",
            "node",
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
            target=self._announce_loop,
            daemon=True,
        )
        self._announce_thread.start()
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()

    def register_pages(self):
        """Scan pages directory and register request handlers for all .mu files."""
        with self._lock:
            self.servedpages = []
            self._scan_pages(self.pagespath)

        pagespath = Path(self.pagespath)

        if not (pagespath / "index.mu").is_file():
            self.destination.register_request_handler(
                "/page/index.mu",
                response_generator=self.serve_default_index,
                allow=RNS.Destination.ALLOW_ALL,
            )

        for full_path in self.servedpages:
            rel = full_path[len(str(pagespath)) :]
            if not rel.startswith("/"):
                rel = "/" + rel
            request_path = f"/page{rel}"
            self.destination.register_request_handler(
                request_path,
                response_generator=self.serve_page,
                allow=RNS.Destination.ALLOW_ALL,
            )

    def register_files(self):
        """Scan files directory and register request handlers for all files."""
        with self._lock:
            self.servedfiles = []
            self._scan_files(self.filespath)

        filespath = Path(self.filespath)

        for full_path in self.servedfiles:
            rel = full_path[len(str(filespath)) :]
            if not rel.startswith("/"):
                rel = "/" + rel
            request_path = f"/file{rel}"
            self.destination.register_request_handler(
                request_path,
                response_generator=self.serve_file,
                allow=RNS.Destination.ALLOW_ALL,
                auto_compress=32_000_000,
            )

    def _scan_pages(self, base):
        base_path = Path(base)
        for entry in base_path.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                self._scan_pages(str(entry))
            elif entry.is_file() and not entry.name.endswith(".allowed"):
                self.servedpages.append(str(entry))

    def _scan_files(self, base):
        base_path = Path(base)
        for entry in base_path.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                self._scan_files(str(entry))
            elif entry.is_file():
                self.servedfiles.append(str(entry))

    @staticmethod
    def serve_default_index(
        _path,
        _data,
        _request_id,
        _link_id,
        _remote_identity,
        _requested_at,
    ):
        """Serve the default index page when no index.mu file exists."""
        return DEFAULT_INDEX.encode("utf-8")

    def serve_page(
        self,
        path,
        data,
        _request_id,
        _link_id,
        remote_identity,
        _requested_at,
    ):
        """Serve a .mu page file, executing it as a script if it has a shebang."""
        pagespath = Path(self.pagespath).resolve()
        relative_path = path[6:] if path.startswith("/page/") else path[5:]
        file_path = (pagespath / relative_path).resolve()

        if not str(file_path).startswith(str(pagespath)):
            return DEFAULT_NOTALLOWED.encode("utf-8")
        try:
            with file_path.open("rb") as _f:
                first_line = _f.readline()
            is_script = first_line.startswith(b"#!")
        except Exception:
            is_script = False
        if is_script and os.access(str(file_path), os.X_OK):
            try:
                env = os.environ.copy()
                if remote_identity:
                    env["remote_identity"] = RNS.hexrep(
                        remote_identity.hash,
                        delimit=False,
                    )
                if data:
                    try:
                        RNS.log(f"Processing request data: {data} (type: {type(data)})", RNS.LOG_DEBUG)
                        if isinstance(data, dict):
                            RNS.log(f"Data is dictionary with {len(data)} items", RNS.LOG_DEBUG)
                            for key, value in data.items():
                                if isinstance(value, str):
                                    if key.startswith(("field_", "var_")):
                                        env[key] = value
                                        RNS.log(f"Set env[{key}] = {value}", RNS.LOG_DEBUG)
                                    elif key == "action":
                                        env["var_action"] = value
                                        RNS.log(f"Set env[var_action] = {value}", RNS.LOG_DEBUG)
                                    else:
                                        env[f"field_{key}"] = value
                                        RNS.log(f"Set env[field_{key}] = {value}", RNS.LOG_DEBUG)
                        elif isinstance(data, bytes):
                            data_str = data.decode("utf-8")
                            RNS.log(f"Data is bytes, decoded to: {data_str}", RNS.LOG_DEBUG)
                            if data_str:
                                if "|" in data_str and "&" not in data_str:
                                    pairs = data_str.split("|")
                                else:
                                    pairs = data_str.split("&")
                                for pair in pairs:
                                    if "=" in pair:
                                        key, value = pair.split("=", 1)
                                        if key.startswith(("field_", "var_")):
                                            env[key] = value
                                        elif key == "action":
                                            env["var_action"] = value
                                        else:
                                            env[f"field_{key}"] = value
                    except Exception as e:
                        RNS.log(f"Error parsing request data: {e}", RNS.LOG_ERROR)
                result = subprocess.run(  # noqa: S603
                    [str(file_path)],
                    stdout=subprocess.PIPE,
                    check=True,
                    env=env,
                )
                return result.stdout
            except Exception as e:
                RNS.log(f"Error executing script page: {e}", RNS.LOG_ERROR)
        with file_path.open("rb") as f:
            return f.read()

    def serve_file(
        self,
        path,
        _data,
        _request_id,
        _link_id,
        _remote_identity,
        _requested_at,
    ):
        """Serve a file from the files directory."""
        filespath = Path(self.filespath).resolve()
        relative_path = path[6:] if path.startswith("/file/") else path[5:]
        file_path = (filespath / relative_path).resolve()

        if not str(file_path).startswith(str(filespath)):
            return DEFAULT_NOTALLOWED.encode("utf-8")

        return [
            file_path.open("rb"),
            {"name": file_path.name.encode("utf-8")},
        ]

    def on_connect(self, link):
        """Handle new link connections."""

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
        except Exception as e:
            RNS.log(f"Error in announce loop: {e}", RNS.LOG_ERROR)

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
        except Exception as e:
            RNS.log(f"Error in refresh loop: {e}", RNS.LOG_ERROR)

    def shutdown(self):
        """Gracefully shutdown the PageNode and cleanup resources."""
        RNS.log("Shutting down PageNode...", RNS.LOG_INFO)
        self._stop_event.set()
        try:
            self._announce_thread.join(timeout=5)
            self._refresh_thread.join(timeout=5)
        except Exception as e:
            RNS.log(f"Error waiting for threads to shut down: {e}", RNS.LOG_ERROR)
        try:
            if hasattr(self.destination, "close"):
                self.destination.close()
        except Exception as e:
            RNS.log(f"Error closing RNS destination: {e}", RNS.LOG_ERROR)


def main():
    """Run the RNS page node application."""
    parser = argparse.ArgumentParser(description="Minimal Reticulum Page Node")
    parser.add_argument(
        "-c",
        "--config",
        dest="configpath",
        help="Reticulum config path",
        default=None,
    )
    parser.add_argument(
        "-p",
        "--pages-dir",
        dest="pages_dir",
        help="Pages directory",
        default=str(Path.cwd() / "pages"),
    )
    parser.add_argument(
        "-f",
        "--files-dir",
        dest="files_dir",
        help="Files directory",
        default=str(Path.cwd() / "files"),
    )
    parser.add_argument(
        "-n",
        "--node-name",
        dest="node_name",
        help="Node display name",
        default=None,
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
        default=str(Path.cwd() / "node-config"),
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

    RNS.Reticulum(configpath)
    Path(identity_dir).mkdir(parents=True, exist_ok=True)
    identity_file = Path(identity_dir) / "identity"
    if identity_file.is_file():
        identity = RNS.Identity.from_file(str(identity_file))
    else:
        identity = RNS.Identity()
        identity.to_file(str(identity_file))

    Path(pages_dir).mkdir(parents=True, exist_ok=True)
    Path(files_dir).mkdir(parents=True, exist_ok=True)

    node = PageNode(
        identity,
        pages_dir,
        files_dir,
        announce_interval,
        node_name,
        page_refresh_interval,
        file_refresh_interval,
    )
    RNS.log("Page node running. Press Ctrl-C to exit.", RNS.LOG_INFO)
    RNS.log(f"Node address: {RNS.prettyhexrep(node.destination.hash)}", RNS.LOG_INFO)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        RNS.log("Keyboard interrupt received, shutting down...", RNS.LOG_INFO)
        node.shutdown()


if __name__ == "__main__":
    main()
