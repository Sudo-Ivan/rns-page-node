#!/usr/bin/env python3
import os
import sys
import threading
import time

import RNS

dir_path = os.path.abspath(os.path.dirname(__file__))
config_dir = os.path.join(dir_path, "config")

RNS.Reticulum(config_dir)

DESTINATION_HEX = (
    "49b2d959db8528347d0a38083aec1042"  # Ivans Node that runs rns-page-node
)

dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH // 8) * 2
if len(DESTINATION_HEX) != dest_len:
    print(
        f"Invalid destination length (got {len(DESTINATION_HEX)}, expected {dest_len})",
        file=sys.stderr,
    )
    sys.exit(1)
destination_hash = bytes.fromhex(DESTINATION_HEX)

if not RNS.Transport.has_path(destination_hash):
    print("Requesting path to server...")
    RNS.Transport.request_path(destination_hash)
    while not RNS.Transport.has_path(destination_hash):
        time.sleep(0.1)

server_identity = RNS.Identity.recall(destination_hash)
print(f"Recalled server identity for {DESTINATION_HEX}")

destination = RNS.Destination(
    server_identity,
    RNS.Destination.OUT,
    RNS.Destination.SINGLE,
    "nomadnetwork",
    "node",
)
link = RNS.Link(destination)

done_event = threading.Event()


def on_page(response):
    data = response.response
    if isinstance(data, bytes):
        text = data.decode("utf-8")
    else:
        text = str(data)
    print("Fetched page content:")
    print(text)
    done_event.set()


link.set_link_established_callback(
    lambda link: link.request("/page/index.mu", None, response_callback=on_page),
)
link.set_link_closed_callback(lambda link: done_event.set())

if not done_event.wait(timeout=30):
    print("Timed out waiting for page", file=sys.stderr)
    sys.exit(1)

print("Done fetching page.")
sys.exit(0)
