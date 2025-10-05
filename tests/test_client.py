#!/usr/bin/env python3
import os
import sys
import threading
import time

import RNS

# Determine base directory for tests
dir_path = os.path.abspath(os.path.dirname(__file__))
config_dir = os.path.join(dir_path, "config")
identity_dir = os.path.join(dir_path, "node-config")

# Initialize Reticulum with shared config
RNS.Reticulum(config_dir)

# Load server identity (created by the page node)
identity_file = os.path.join(identity_dir, "identity")
server_identity = RNS.Identity.from_file(identity_file)

# Create a destination to the server node
destination = RNS.Destination(
    server_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "nomadnetwork", "node",
)

# Ensure we know a path to the destination
if not RNS.Transport.has_path(destination.hash):
    RNS.Transport.request_path(destination.hash)
    while not RNS.Transport.has_path(destination.hash):
        time.sleep(0.1)

# Establish a link to the server
global_link = RNS.Link(destination)

# Containers for responses
responses = {}
done_event = threading.Event()

# Test data for environment variables
test_data_dict = {
    'var_field_test': 'dictionary_value',
    'var_field_message': 'hello_world',
    'var_action': 'test_action'
}
test_data_bytes = b'field_bytes_test=bytes_value|field_bytes_message=test_bytes|action=bytes_action'


# Callback for page response
def on_page(response):
    data = response.response
    if isinstance(data, bytes):
        text = data.decode("utf-8")
    else:
        text = str(data)
    print("Received page (no data):")
    print(text)
    responses["page"] = text
    check_responses()

# Callback for page response with dictionary data
def on_page_dict(response):
    data = response.response
    if isinstance(data, bytes):
        text = data.decode("utf-8")
    else:
        text = str(data)
    print("Received page (dict data):")
    print(text)
    responses["page_dict"] = text
    check_responses()

# Callback for page response with bytes data
def on_page_bytes(response):
    data = response.response
    if isinstance(data, bytes):
        text = data.decode("utf-8")
    else:
        text = str(data)
    print("Received page (bytes data):")
    print(text)
    responses["page_bytes"] = text
    check_responses()

def check_responses():
    if "page" in responses and "page_dict" in responses and "page_bytes" in responses and "file" in responses:
        done_event.set()


# Callback for file response
def on_file(response):
    data = response.response
    # Handle response as [fileobj, headers]
    if isinstance(data, list) and len(data) == 2 and hasattr(data[0], "read"):
        fileobj, headers = data
        file_data = fileobj.read()
        filename = headers.get(b"name", b"").decode("utf-8")
        print(f"Received file ({filename}):")
        print(file_data.decode("utf-8"))
        responses["file"] = file_data.decode("utf-8")
    # Handle response as a raw file object
    elif hasattr(data, "read"):
        file_data = data.read()
        filename = os.path.basename("text.txt")
        print(f"Received file ({filename}):")
        print(file_data.decode("utf-8"))
        responses["file"] = file_data.decode("utf-8")
    # Handle response as raw bytes
    elif isinstance(data, bytes):
        text = data.decode("utf-8")
        print("Received file:")
        print(text)
        responses["file"] = text
    else:
        print("Received file (unhandled format):", data)
        responses["file"] = str(data)
    check_responses()


# Request the pages and file once the link is established
def on_link_established(link):
    # Test page without data
    link.request("/page/index.mu", None, response_callback=on_page)
    # Test page with dictionary data (simulates MeshChat)
    link.request("/page/index.mu", test_data_dict, response_callback=on_page_dict)
    # Test page with bytes data (URL-encoded style)
    link.request("/page/index.mu", test_data_bytes, response_callback=on_page_bytes)
    # Test file serving
    link.request("/file/text.txt", None, response_callback=on_file)


# Register callbacks
global_link.set_link_established_callback(on_link_established)
global_link.set_link_closed_callback(lambda link: done_event.set())

# Wait for responses or timeout
if not done_event.wait(timeout=30):
    print("Test timed out.", file=sys.stderr)
    sys.exit(1)

# Validate test results
def validate_test_results():
    """Validate that all responses contain expected content"""

    # Check basic page response (no data)
    if "page" not in responses:
        print("ERROR: No basic page response received", file=sys.stderr)
        return False

    page_content = responses["page"]
    if "No parameters received" not in page_content:
        print("ERROR: Basic page should show 'No parameters received'", file=sys.stderr)
        return False
    if "33aff86b736acd47dca07e84630fd192" not in page_content:
        print("ERROR: Basic page should show mock remote identity", file=sys.stderr)
        return False

    # Check page with dictionary data
    if "page_dict" not in responses:
        print("ERROR: No dictionary data page response received", file=sys.stderr)
        return False

    dict_content = responses["page_dict"]
    if "var_field_test" not in dict_content or "dictionary_value" not in dict_content:
        print("ERROR: Dictionary data page should contain processed environment variables", file=sys.stderr)
        return False
    if "33aff86b736acd47dca07e84630fd192" not in dict_content:
        print("ERROR: Dictionary data page should show mock remote identity", file=sys.stderr)
        return False

    # Check page with bytes data
    if "page_bytes" not in responses:
        print("ERROR: No bytes data page response received", file=sys.stderr)
        return False

    bytes_content = responses["page_bytes"]
    if "field_bytes_test" not in bytes_content or "bytes_value" not in bytes_content:
        print("ERROR: Bytes data page should contain processed environment variables", file=sys.stderr)
        return False
    if "33aff86b736acd47dca07e84630fd192" not in bytes_content:
        print("ERROR: Bytes data page should show mock remote identity", file=sys.stderr)
        return False

    # Check file response
    if "file" not in responses:
        print("ERROR: No file response received", file=sys.stderr)
        return False

    file_content = responses["file"]
    if "This is a test file" not in file_content:
        print("ERROR: File content doesn't match expected content", file=sys.stderr)
        return False

    return True

if validate_test_results():
    print("All tests passed! Environment variable processing works correctly.")
    sys.exit(0)
else:
    print("Tests failed.", file=sys.stderr)
    sys.exit(1)
