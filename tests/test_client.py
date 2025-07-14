#!/usr/bin/env python3
import os
import sys
import time
import threading
import RNS

# Determine base directory for tests
dir_path = os.path.abspath(os.path.dirname(__file__))
config_dir = os.path.join(dir_path, 'config')
identity_dir = os.path.join(dir_path, 'node-config')

# Initialize Reticulum with shared config
RNS.Reticulum(config_dir)

# Load server identity (created by the page node)
identity_file = os.path.join(identity_dir, 'identity')
server_identity = RNS.Identity.from_file(identity_file)

# Create a destination to the server node
destination = RNS.Destination(
    server_identity,
    RNS.Destination.OUT,
    RNS.Destination.SINGLE,
    'nomadnetwork',
    'node'
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

# Callback for page response
def on_page(response):
    data = response.response
    if isinstance(data, bytes):
        text = data.decode('utf-8')
    else:
        text = str(data)
    print('Received page:')
    print(text)
    responses['page'] = text
    if 'file' in responses:
        done_event.set()

# Callback for file response
def on_file(response):
    data = response.response
    # Handle response as [fileobj, headers]
    if isinstance(data, list) and len(data) == 2 and hasattr(data[0], 'read'):
        fileobj, headers = data
        file_data = fileobj.read()
        filename = headers.get(b'name', b'').decode('utf-8')
        print(f'Received file ({filename}):')
        print(file_data.decode('utf-8'))
        responses['file'] = file_data.decode('utf-8')
    # Handle response as a raw file object
    elif hasattr(data, 'read'):
        file_data = data.read()
        filename = os.path.basename('text.txt')
        print(f'Received file ({filename}):')
        print(file_data.decode('utf-8'))
        responses['file'] = file_data.decode('utf-8')
    # Handle response as raw bytes
    elif isinstance(data, bytes):
        text = data.decode('utf-8')
        print('Received file:')
        print(text)
        responses['file'] = text
    else:
        print('Received file (unhandled format):', data)
        responses['file'] = str(data)
    if 'page' in responses:
        done_event.set()

# Request the page and file once the link is established
def on_link_established(link):
    link.request('/page/index.mu', None, response_callback=on_page)
    link.request('/file/text.txt', None, response_callback=on_file)

# Register callbacks
global_link.set_link_established_callback(on_link_established)
global_link.set_link_closed_callback(lambda l: done_event.set())

# Wait for responses or timeout
if not done_event.wait(timeout=30):
    print('Test timed out.', file=sys.stderr)
    sys.exit(1)

if responses.get('page') and responses.get('file'):
    print('Tests passed!')
    sys.exit(0)
else:
    print('Tests failed.', file=sys.stderr)
    sys.exit(1)
