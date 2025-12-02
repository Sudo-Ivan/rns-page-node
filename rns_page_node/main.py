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


def load_config(config_file):
    """Load configuration from a plain text config file.

    Config format is simple key=value pairs, one per line.
    Lines starting with # are comments and are ignored.
    Empty lines are ignored.

    Args:
        config_file: Path to the config file

    Returns:
        Dictionary of configuration values

    """
    config = {}
    try:
        with open(config_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    RNS.log(
                        f"Invalid config line {line_num} in {config_file}: {line}",
                        RNS.LOG_WARNING,
                    )
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key and value:
                    config[key] = value
        RNS.log(f"Loaded configuration from {config_file}", RNS.LOG_INFO)
    except FileNotFoundError:
        RNS.log(f"Config file not found: {config_file}", RNS.LOG_ERROR)
    except Exception as e:
        RNS.log(f"Error reading config file {config_file}: {e}", RNS.LOG_ERROR)
    return config


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
            announce_interval: Minutes between announcements (default: 360) == 6 hours
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
        pages = self._scan_pages(self.pagespath)

        with self._lock:
            self.servedpages = pages

        pagespath = Path(self.pagespath)

        if not (pagespath / "index.mu").is_file():
            self.destination.register_request_handler(
                "/page/index.mu",
                response_generator=self.serve_default_index,
                allow=RNS.Destination.ALLOW_ALL,
            )

        for full_path in pages:
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
        files = self._scan_files(self.filespath)

        with self._lock:
            self.servedfiles = files

        filespath = Path(self.filespath)

        for full_path in files:
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
        """Return a list of page paths under the given directory, excluding .allowed files."""
        base_path = Path(base)
        if not base_path.exists():
            return []
        served = []
        for entry in base_path.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                served.extend(self._scan_pages(entry))
            elif entry.is_file() and not entry.name.endswith(".allowed"):
                served.append(str(entry))
        return served

    def _scan_files(self, base):
        """Return all file paths under the given directory."""
        base_path = Path(base)
        if not base_path.exists():
            return []
        served = []
        for entry in base_path.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                served.extend(self._scan_files(entry))
            elif entry.is_file():
                served.append(str(entry))
        return served

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
        is_script = False
        file_content = None
        try:
            with file_path.open("rb") as file_handle:
                first_line = file_handle.readline()
                is_script = first_line.startswith(b"#!")
                file_handle.seek(0)
                if not is_script:
                    return file_handle.read()
                file_content = file_handle.read()
        except FileNotFoundError:
            return DEFAULT_NOTALLOWED.encode("utf-8")
        except OSError as err:
            RNS.log(f"Error reading page {file_path}: {err}", RNS.LOG_ERROR)
            return DEFAULT_NOTALLOWED.encode("utf-8")

        if is_script and os.access(str(file_path), os.X_OK):
            try:
                env_map = os.environ.copy()
                if _link_id is not None:
                    env_map["link_id"] = RNS.hexrep(_link_id, delimit=False)
                if remote_identity is not None:
                    env_map["remote_identity"] = RNS.hexrep(
                        remote_identity.hash,
                        delimit=False,
                    )
                if data is not None and isinstance(data, dict):
                    for e in data:
                        if isinstance(e, str) and (
                            e.startswith("field_") or e.startswith("var_")
                        ):
                            env_map[e] = data[e]
                result = subprocess.run(  # noqa: S603
                    [str(file_path)],
                    stdout=subprocess.PIPE,
                    check=True,
                    env=env_map,
                )
                return result.stdout
            except Exception as e:
                RNS.log(f"Error executing script page: {e}", RNS.LOG_ERROR)
        if file_content is not None:
            return file_content
        try:
            return self._read_file_bytes(file_path)
        except FileNotFoundError:
            return DEFAULT_NOTALLOWED.encode("utf-8")
        except OSError as err:
            RNS.log(f"Error reading page fallback {file_path}: {err}", RNS.LOG_ERROR)
            return DEFAULT_NOTALLOWED.encode("utf-8")

    @staticmethod
    def _read_file_bytes(file_path):
        """Read a file's bytes and return the contents."""
        with file_path.open("rb") as file_handle:
            return file_handle.read()

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
        """Periodically announce the node until shutdown is requested."""
        interval_seconds = max(self.announce_interval, 0) * 60
        try:
            while not self._stop_event.is_set():
                now = time.time()
                if (
                    self.last_announce == 0
                    or now - self.last_announce >= interval_seconds
                ):
                    try:
                        if self.name:
                            self.destination.announce(
                                app_data=self.name.encode("utf-8"),
                            )
                        else:
                            self.destination.announce()
                        self.last_announce = time.time()
                    except (TypeError, ValueError) as announce_error:
                        RNS.log(
                            f"Error during announce: {announce_error}",
                            RNS.LOG_ERROR,
                        )
                wait_time = max(
                    (self.last_announce + interval_seconds) - time.time()
                    if self.last_announce
                    else 0,
                    1,
                )
                self._stop_event.wait(min(wait_time, 60))
        except Exception as e:
            RNS.log(f"Error in announce loop: {e}", RNS.LOG_ERROR)

    def _refresh_loop(self):
        """Refresh page and file registrations at configured intervals."""
        try:
            while not self._stop_event.is_set():
                now = time.time()
                if (
                    self.page_refresh_interval > 0
                    and now - self.last_page_refresh >= self.page_refresh_interval
                ):
                    self.register_pages()
                    self.last_page_refresh = time.time()
                if (
                    self.file_refresh_interval > 0
                    and now - self.last_file_refresh >= self.file_refresh_interval
                ):
                    self.register_files()
                    self.last_file_refresh = time.time()

                wait_candidates = []
                if self.page_refresh_interval > 0:
                    wait_candidates.append(
                        max(
                            (self.last_page_refresh + self.page_refresh_interval)
                            - time.time(),
                            0.5,
                        ),
                    )
                if self.file_refresh_interval > 0:
                    wait_candidates.append(
                        max(
                            (self.last_file_refresh + self.file_refresh_interval)
                            - time.time(),
                            0.5,
                        ),
                    )

                wait_time = min(wait_candidates) if wait_candidates else 1.0
                self._stop_event.wait(min(wait_time, 60))
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
        "node_config",
        nargs="?",
        help="Path to rns-page-node config file",
        default=None,
    )
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
        help="Announce interval in minutes",
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

    config = {}
    if args.node_config:
        config = load_config(args.node_config)

    def get_config_value(arg_value, arg_default, config_key, value_type=str):
        """Get value from CLI args, config file, or default.

        Priority: CLI arg > config file > default
        """
        if arg_value != arg_default:
            return arg_value
        if config_key in config:
            try:
                if value_type is int:
                    return int(config[config_key])
                return config[config_key]
            except ValueError:
                RNS.log(
                    f"Invalid {value_type.__name__} value for {config_key}: {config[config_key]}",
                    RNS.LOG_WARNING,
                )
        return arg_default

    configpath = get_config_value(args.configpath, None, "reticulum-config")
    pages_dir = get_config_value(args.pages_dir, str(Path.cwd() / "pages"), "pages-dir")
    files_dir = get_config_value(args.files_dir, str(Path.cwd() / "files"), "files-dir")
    node_name = get_config_value(args.node_name, None, "node-name")
    announce_interval = get_config_value(
        args.announce_interval,
        360,
        "announce-interval",
        int,
    )
    identity_dir = get_config_value(
        args.identity_dir,
        str(Path.cwd() / "node-config"),
        "identity-dir",
    )
    page_refresh_interval = get_config_value(
        args.page_refresh_interval,
        0,
        "page-refresh-interval",
        int,
    )
    file_refresh_interval = get_config_value(
        args.file_refresh_interval,
        0,
        "file-refresh-interval",
        int,
    )
    log_level = get_config_value(args.log_level, "INFO", "log-level")

    # Set RNS log level based on command line argument
    log_level_map = {
        "CRITICAL": RNS.LOG_CRITICAL,
        "ERROR": RNS.LOG_ERROR,
        "WARNING": RNS.LOG_WARNING,
        "INFO": RNS.LOG_INFO,
        "DEBUG": RNS.LOG_DEBUG,
    }
    RNS.loglevel = log_level_map.get(log_level.upper(), RNS.LOG_INFO)

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
