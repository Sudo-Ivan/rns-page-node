#!/usr/bin/env python3
"""
Minimal Reticulum Page Node
Serves .mu pages and files over RNS.
"""

import os
import time
import threading
import subprocess
import RNS
import argparse
import logging
import json
from collections import defaultdict, deque
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_INDEX = '''>Default Home Page

This node is serving pages using page node, but the home page file (index.mu) was not found in the pages directory. Please add an index.mu file to customize the home page.
'''

DEFAULT_NOTALLOWED = '''>Request Not Allowed

You are not authorised to carry out the request.
'''

class PageNode:
    def __init__(self, identity, pagespath, filespath, announce_interval=360, name=None, page_refresh_interval=0, file_refresh_interval=0, stats_file=None):
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self.logger = logging.getLogger(f"{__name__}.PageNode")
        self.identity = identity
        self.name = name
        self.pagespath = pagespath
        self.filespath = filespath
        self.stats_file = stats_file
        self.destination = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "nomadnetwork",
            "node"
        )
        self.announce_interval = announce_interval
        self.last_announce = 0
        self.page_refresh_interval = page_refresh_interval
        self.file_refresh_interval = file_refresh_interval
        self.last_page_refresh = time.time()
        self.last_file_refresh = time.time()

        # Initialize stats tracking
        self._init_stats()

        self.register_pages()
        self.register_files()

        self.destination.set_link_established_callback(self.on_connect)

        self._announce_thread = threading.Thread(target=self._announce_loop, daemon=True)
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
                allow=RNS.Destination.ALLOW_ALL
            )

        for full_path in self.servedpages:
            rel = full_path[len(self.pagespath):]
            request_path = f"/page{rel}"
            self.destination.register_request_handler(
                request_path,
                response_generator=self.serve_page,
                allow=RNS.Destination.ALLOW_ALL
            )

    def register_files(self):
        with self._lock:
            self.servedfiles = []
            self._scan_files(self.filespath)

        for full_path in self.servedfiles:
            rel = full_path[len(self.filespath):]
            request_path = f"/file{rel}"
            self.destination.register_request_handler(
                request_path,
                response_generator=self.serve_file,
                allow=RNS.Destination.ALLOW_ALL,
                auto_compress=32_000_000
            )

    def _scan_pages(self, base):
        for entry in os.listdir(base):
            if entry.startswith('.'):
                continue
            path = os.path.join(base, entry)
            if os.path.isdir(path):
                self._scan_pages(path)
            elif os.path.isfile(path) and not entry.endswith(".allowed"):
                self.servedpages.append(path)

    def _scan_files(self, base):
        for entry in os.listdir(base):
            if entry.startswith('.'):
                continue
            path = os.path.join(base, entry)
            if os.path.isdir(path):
                self._scan_files(path)
            elif os.path.isfile(path):
                self.servedfiles.append(path)

    def _init_stats(self):
        """Initialize statistics tracking"""
        self.stats = {
            'start_time': time.time(),
            'total_connections': 0,
            'active_connections': 0,
            'total_page_requests': 0,
            'total_file_requests': 0,
            'page_requests_by_path': defaultdict(int),
            'file_requests_by_path': defaultdict(int),
            'requests_by_peer': defaultdict(int),
            'recent_requests': deque(maxlen=100),  # Keep last 100 requests
            'connected_peers': {},  # link_id -> peer_info
            'hourly_stats': defaultdict(lambda: {'pages': 0, 'files': 0}),
            'daily_stats': defaultdict(lambda: {'pages': 0, 'files': 0}),
        }
        
        # Initialize stats file if specified
        if self.stats_file:
            self._init_stats_file()

    def _init_stats_file(self):
        """Initialize the stats file with basic structure"""
        try:
            # Ensure directory exists
            dir_path = os.path.dirname(os.path.abspath(self.stats_file))
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # Create initial stats file
            initial_stats = {
                'node_info': {
                    'name': self.name or 'Unnamed',
                    'hash': RNS.hexrep(self.destination.hash, delimit=False),
                    'start_time': datetime.fromtimestamp(self.stats['start_time']).isoformat()
                },
                'connections': [],
                'requests': [],
                'summary': {
                    'total_connections': 0,
                    'total_page_requests': 0,
                    'total_file_requests': 0,
                    'last_updated': datetime.now().isoformat()
                }
            }
            
            with open(self.stats_file, 'w') as f:
                json.dump(initial_stats, f, indent=2)
            
            self.logger.info(f"Initialized stats file: {self.stats_file}")
        except Exception as e:
            self.logger.error(f"Failed to initialize stats file {self.stats_file}: {e}")

    def _write_stats_event(self, event_type, event_data):
        """Write a single stats event to the file"""
        if not self.stats_file:
            return
            
        try:
            # Read current stats
            try:
                with open(self.stats_file, 'r') as f:
                    stats_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                # If file doesn't exist or is corrupted, reinitialize
                self._init_stats_file()
                with open(self.stats_file, 'r') as f:
                    stats_data = json.load(f)
            
            # Add the new event
            if event_type == 'connection':
                stats_data['connections'].append(event_data)
                stats_data['summary']['total_connections'] += 1
            elif event_type == 'request':
                stats_data['requests'].append(event_data)
                if event_data['type'] == 'page':
                    stats_data['summary']['total_page_requests'] += 1
                elif event_data['type'] == 'file':
                    stats_data['summary']['total_file_requests'] += 1
            
            # Update last_updated timestamp
            stats_data['summary']['last_updated'] = datetime.now().isoformat()
            
            # Keep only last 1000 events to prevent file from growing too large
            if len(stats_data['connections']) > 1000:
                stats_data['connections'] = stats_data['connections'][-1000:]
            if len(stats_data['requests']) > 1000:
                stats_data['requests'] = stats_data['requests'][-1000:]
            
            # Write back to file
            with open(self.stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2, default=str)
                
        except Exception as e:
            self.logger.error(f"Failed to write stats event to {self.stats_file}: {e}")

    def _record_request(self, request_type, path, remote_identity, requested_at):
        """Record a request in statistics"""
        with self._stats_lock:
            # Get peer identity hash with better fallback
            if remote_identity:
                peer_hash = RNS.hexrep(remote_identity.hash, delimit=False)
                # Try to get app_data name if available
                try:
                    app_data = RNS.Identity.recall_app_data(remote_identity.hash)
                    if app_data:
                        peer_display = app_data.decode('utf-8', errors='ignore')[:32]  # Limit length
                    else:
                        peer_display = peer_hash[:16] + "..."  # Show first 16 chars
                except:
                    peer_display = peer_hash[:16] + "..."
            else:
                peer_hash = "anonymous"
                peer_display = "anonymous"
            
            # Record basic stats
            if request_type == 'page':
                self.stats['total_page_requests'] += 1
                self.stats['page_requests_by_path'][path] += 1
            elif request_type == 'file':
                self.stats['total_file_requests'] += 1
                self.stats['file_requests_by_path'][path] += 1
            
            self.stats['requests_by_peer'][peer_hash] += 1
            
            # Record recent request
            request_info = {
                'type': request_type,
                'path': path,
                'peer': peer_display,
                'peer_hash': peer_hash,
                'timestamp': requested_at,
                'datetime': datetime.fromtimestamp(requested_at).isoformat()
            }
            self.stats['recent_requests'].append(request_info)
            
            # Record hourly and daily stats
            dt = datetime.fromtimestamp(requested_at)
            hour_key = dt.strftime('%Y-%m-%d %H:00')
            day_key = dt.strftime('%Y-%m-%d')
            
            if request_type == 'page':
                self.stats['hourly_stats'][hour_key]['pages'] += 1
                self.stats['daily_stats'][day_key]['pages'] += 1
            elif request_type == 'file':
                self.stats['hourly_stats'][hour_key]['files'] += 1
                self.stats['daily_stats'][day_key]['files'] += 1
            
            # Write to stats file immediately
            self._write_stats_event('request', request_info)

    def serve_default_index(self, path, data, request_id, link_id, remote_identity, requested_at):
        self._record_request('page', path, remote_identity, requested_at)
        return DEFAULT_INDEX.encode('utf-8')

    def serve_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        self._record_request('page', path, remote_identity, requested_at)
        file_path = path.replace("/page", self.pagespath, 1)
        try:
            with open(file_path, 'rb') as _f:
                first_line = _f.readline()
            is_script = first_line.startswith(b'#!')
        except Exception:
            is_script = False
        if is_script and os.access(file_path, os.X_OK):
            # Note: You can remove the following try-except block if  you just serve static pages.
            try:
                result = subprocess.run([file_path], stdout=subprocess.PIPE)
                return result.stdout
            except Exception:
                pass
        with open(file_path, 'rb') as f:
            return f.read()

    def serve_file(self, path, data, request_id, link_id, remote_identity, requested_at):
        self._record_request('file', path, remote_identity, requested_at)
        file_path = path.replace("/file", self.filespath, 1)
        return [open(file_path, 'rb'), {"name": os.path.basename(file_path).encode('utf-8')}]

    def on_connect(self, link):
        """Called when a new link is established"""
        connection_time = time.time()
        with self._stats_lock:
            self.stats['total_connections'] += 1
            self.stats['active_connections'] += 1
            
            # Get peer info with better identification
            if link.get_remote_identity():
                peer_hash = RNS.hexrep(link.get_remote_identity().hash, delimit=False)
                # Try to get app_data name if available
                try:
                    app_data = RNS.Identity.recall_app_data(link.get_remote_identity().hash)
                    if app_data:
                        peer_display = app_data.decode('utf-8', errors='ignore')[:32]  # Limit length
                    else:
                        peer_display = peer_hash[:16] + "..."  # Show first 16 chars
                except:
                    peer_display = peer_hash[:16] + "..."
            else:
                peer_hash = "anonymous"
                peer_display = "anonymous"
            
            # Convert link_id to hex string properly
            link_id_hex = RNS.hexrep(link.link_id, delimit=False) if hasattr(link, 'link_id') else "unknown"
            
            self.stats['connected_peers'][link_id_hex] = {
                'peer_hash': peer_hash,
                'peer_display': peer_display,
                'connected_at': connection_time,
                'link_id': link_id_hex
            }
            
            # Write connection event to stats file
            connection_info = {
                'event': 'connected',
                'peer': peer_display,
                'peer_hash': peer_hash,
                'timestamp': connection_time,
                'datetime': datetime.fromtimestamp(connection_time).isoformat(),
                'link_id': link_id_hex
            }
            self._write_stats_event('connection', connection_info)
            
        self.logger.info(f"New connection established from peer {peer_display}")
        
        # Set callback for when link closes
        link.set_link_closed_callback(self._on_link_closed)

    def _on_link_closed(self, link):
        """Called when a link is closed"""
        with self._stats_lock:
            if link.link_id in self.stats['connected_peers']:
                peer_info = self.stats['connected_peers'].pop(link.link_id)
                self.stats['active_connections'] = max(0, self.stats['active_connections'] - 1)
                self.logger.info(f"Connection closed from peer {peer_info['peer_hash'][:16]}...")

    def _announce_loop(self):
        while not self._stop_event.is_set():
            try:
                if time.time() - self.last_announce > self.announce_interval:
                    if self.name:
                        self.destination.announce(app_data=self.name.encode('utf-8'))
                    else:
                        self.destination.announce()
                    self.last_announce = time.time()
                time.sleep(1)
            except Exception:
                self.logger.exception("Error in announce loop")

    def _refresh_loop(self):
        while not self._stop_event.is_set():
            try:
                now = time.time()
                if self.page_refresh_interval > 0 and now - self.last_page_refresh > self.page_refresh_interval:
                    self.register_pages()
                    self.last_page_refresh = now
                if self.file_refresh_interval > 0 and now - self.last_file_refresh > self.file_refresh_interval:
                    self.register_files()
                    self.last_file_refresh = now
                time.sleep(1)
            except Exception:
                self.logger.exception("Error in refresh loop")

    def get_stats(self):
        """Get current statistics"""
        with self._stats_lock:
            # Calculate uptime
            uptime = time.time() - self.stats['start_time']
            
            # Get top requested pages and files
            top_pages = sorted(self.stats['page_requests_by_path'].items(), key=lambda x: x[1], reverse=True)[:10]
            top_files = sorted(self.stats['file_requests_by_path'].items(), key=lambda x: x[1], reverse=True)[:10]
            top_peers = sorted(self.stats['requests_by_peer'].items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'uptime_seconds': uptime,
                'uptime_formatted': self._format_duration(uptime),
                'start_time': datetime.fromtimestamp(self.stats['start_time']).isoformat(),
                'total_connections': self.stats['total_connections'],
                'active_connections': self.stats['active_connections'],
                'total_page_requests': self.stats['total_page_requests'],
                'total_file_requests': self.stats['total_file_requests'],
                'total_requests': self.stats['total_page_requests'] + self.stats['total_file_requests'],
                'top_pages': top_pages,
                'top_files': top_files,
                'top_peers': [(peer[:16] + "..." if len(peer) > 16 else peer, count) for peer, count in top_peers],
                'recent_requests': list(self.stats['recent_requests'])[-10:],  # Last 10 requests
                'connected_peers': len(self.stats['connected_peers']),
                'requests_per_hour': self._calculate_requests_per_hour(),
            }

    def _format_duration(self, seconds):
        """Format duration in human readable format"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m {secs}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def _calculate_requests_per_hour(self):
        """Calculate average requests per hour"""
        uptime_hours = (time.time() - self.stats['start_time']) / 3600
        if uptime_hours < 0.1:  # Less than 6 minutes
            return 0
        total_requests = self.stats['total_page_requests'] + self.stats['total_file_requests']
        return round(total_requests / uptime_hours, 2)

    def print_stats(self):
        """Print formatted statistics to console"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("RNS PAGE NODE STATISTICS")
        print("="*60)
        print(f"Node Name: {self.name or 'Unnamed'}")
        print(f"Started: {stats['start_time']}")
        print(f"Uptime: {stats['uptime_formatted']}")
        print(f"Node Hash: {RNS.hexrep(self.destination.hash, delimit=False)}")
        print()
        
        print("CONNECTION STATS:")
        print(f"  Total Connections: {stats['total_connections']}")
        print(f"  Active Connections: {stats['active_connections']}")
        print()
        
        print("REQUEST STATS:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Page Requests: {stats['total_page_requests']}")
        print(f"  File Requests: {stats['total_file_requests']}")
        print(f"  Requests/Hour: {stats['requests_per_hour']}")
        print()
        
        if stats['top_pages']:
            print("TOP REQUESTED PAGES:")
            for path, count in stats['top_pages']:
                print(f"  {count:4d} - {path}")
            print()
        
        if stats['top_files']:
            print("TOP REQUESTED FILES:")
            for path, count in stats['top_files']:
                print(f"  {count:4d} - {path}")
            print()
        
        if stats['top_peers']:
            print("TOP REQUESTING PEERS:")
            for peer, count in stats['top_peers']:
                print(f"  {count:4d} - {peer}")
            print()
        
        if stats['recent_requests']:
            print("RECENT REQUESTS:")
            for req in stats['recent_requests']:
                print(f"  {req['datetime']} - {req['type'].upper()} {req['path']} from {req['peer'][:16]}...")
        
        print("="*60)

    def save_stats_to_file(self, filepath):
        """Save statistics to JSON file"""
        try:
            stats = self.get_stats()
            
            # Ensure directory exists
            dir_path = os.path.dirname(os.path.abspath(filepath))
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # Convert defaultdict and other non-serializable objects to regular dicts
            with self._stats_lock:
                stats_copy = dict(stats)
                stats_copy['page_requests_by_path'] = dict(self.stats['page_requests_by_path'])
                stats_copy['file_requests_by_path'] = dict(self.stats['file_requests_by_path'])
                stats_copy['requests_by_peer'] = dict(self.stats['requests_by_peer'])
                stats_copy['hourly_stats'] = {k: dict(v) for k, v in self.stats['hourly_stats'].items()}
                stats_copy['daily_stats'] = {k: dict(v) for k, v in self.stats['daily_stats'].items()}
                stats_copy['connected_peers'] = dict(self.stats['connected_peers'])
                stats_copy['recent_requests'] = list(self.stats['recent_requests'])
            
            with open(filepath, 'w') as f:
                json.dump(stats_copy, f, indent=2, default=str)
            self.logger.info(f"Statistics saved to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save statistics to {filepath}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def reset_stats(self):
        """Reset all statistics"""
        with self._stats_lock:
            self._init_stats()
        self.logger.info("Statistics reset")

    def shutdown(self):
        self.logger.info("Shutting down PageNode...")
        self._stop_event.set()
        try:
            self._announce_thread.join(timeout=5)
            self._refresh_thread.join(timeout=5)
        except Exception:
            self.logger.exception("Error waiting for threads to shut down")
        try:
            if hasattr(self.destination, 'close'):
                self.destination.close()
        except Exception:
            self.logger.exception("Error closing RNS destination")


def main():
    parser = argparse.ArgumentParser(description="Minimal Reticulum Page Node")
    parser.add_argument('-c', '--config', dest='configpath', help='Reticulum config path', default=None)
    parser.add_argument('-p', '--pages-dir', dest='pages_dir', help='Pages directory', default=os.path.join(os.getcwd(), 'pages'))
    parser.add_argument('-f', '--files-dir', dest='files_dir', help='Files directory', default=os.path.join(os.getcwd(), 'files'))
    parser.add_argument('-n', '--node-name', dest='node_name', help='Node display name', default=None)
    parser.add_argument('-a', '--announce-interval', dest='announce_interval', type=int, help='Announce interval in seconds', default=360)
    parser.add_argument('-i', '--identity-dir', dest='identity_dir', help='Directory to store node identity', default=os.path.join(os.getcwd(), 'node-config'))
    parser.add_argument('--page-refresh-interval', dest='page_refresh_interval', type=int, default=0, help='Page refresh interval in seconds, 0 disables auto-refresh')
    parser.add_argument('--file-refresh-interval', dest='file_refresh_interval', type=int, default=0, help='File refresh interval in seconds, 0 disables auto-refresh')
    parser.add_argument('-l', '--log-level', dest='log_level', choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'], default='INFO', help='Logging level')
    parser.add_argument('--stats-interval', dest='stats_interval', type=int, default=0, help='Print stats every N seconds (0 disables)')
    parser.add_argument('--save-stats', dest='save_stats', help='Save stats to JSON file on shutdown')
    parser.add_argument('--stats-file', dest='stats_file', help='Actively write stats to JSON file (live updates)')
    args = parser.parse_args()

    configpath = args.configpath
    pages_dir = args.pages_dir
    files_dir = args.files_dir
    node_name = args.node_name
    announce_interval = args.announce_interval
    identity_dir = args.identity_dir
    page_refresh_interval = args.page_refresh_interval
    file_refresh_interval = args.file_refresh_interval
    stats_interval = args.stats_interval
    save_stats_file = args.save_stats
    stats_file = args.stats_file
    numeric_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format='%(asctime)s %(name)s [%(levelname)s] %(message)s')

    RNS.Reticulum(configpath)
    os.makedirs(identity_dir, exist_ok=True)
    identity_file = os.path.join(identity_dir, 'identity')
    if os.path.isfile(identity_file):
        identity = RNS.Identity.from_file(identity_file)
    else:
        identity = RNS.Identity()
        identity.to_file(identity_file)

    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(files_dir, exist_ok=True)

    node = PageNode(identity, pages_dir, files_dir, announce_interval, node_name, page_refresh_interval, file_refresh_interval, stats_file)
    logger.info("Page node running. Press Ctrl-C to exit.")
    
    if stats_interval > 0:
        logger.info(f"Stats will be printed every {stats_interval} seconds")

    last_stats_time = 0
    try:
        while True:
            current_time = time.time()
            
            # Print stats if interval is set and enough time has passed
            if stats_interval > 0 and current_time - last_stats_time >= stats_interval:
                node.print_stats()
                last_stats_time = current_time
            
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        
        # Print final stats
        node.print_stats()
        
        # Save stats if requested
        if save_stats_file:
            logger.info(f"Saving final statistics to {save_stats_file}")
            if node.save_stats_to_file(save_stats_file):
                logger.info(f"Statistics successfully saved to {save_stats_file}")
            else:
                logger.error(f"Failed to save statistics to {save_stats_file}")
        
        node.shutdown()
    finally:
        # Ensure stats are saved even if something goes wrong
        if save_stats_file and 'node' in locals():
            try:
                node.save_stats_to_file(save_stats_file)
                logger.info(f"Final attempt: Statistics saved to {save_stats_file}")
            except Exception as e:
                logger.error(f"Final save attempt failed: {e}")

if __name__ == '__main__':
    main()
