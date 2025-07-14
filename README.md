# RNS Page Node

A simple way to serve pages and files over the [Reticulum network](https://reticulum.network/). Drop-in replacement for [NomadNet](https://github.com/markqvist/NomadNet) nodes that primarily serve pages and files.

## Usage

```bash
pip install rns-page-node
```

```bash
rns-page-node
```

## Usage

```bash
rns-page-node --node-name "Page Node" --pages-dir ./pages --files-dir ./files --identity-dir ./node-config --announce-interval 360
```

### Docker/Podman

```bash
docker run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/app/config ghcr.io/sudo-ivan/rns-page-node:latest
```

### Docker/Podman Rootless

```bash
mkdir -p ./pages ./files ./node-config ./config
chown -R 1000:1000 ./pages ./files ./node-config ./config
podman run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/app/config ghcr.io/sudo-ivan/rns-page-node:latest-rootless
```

Mounting volumes are optional, you can also copy pages and files to the container `podman cp` or `docker cp`.

## Build

```bash
make build
```

Build wheels:

```bash
make wheel
```

### Build Wheels in Docker

```bash
make docker-wheels
```

## Pages

Supports Micron `.mu` and dynamic pages with `#!` in the micron files.

## Statistics Tracking

The node now includes comprehensive statistics tracking for monitoring peer connections and page/file requests:

### Command Line Options for Stats

```bash
# Print stats every 60 seconds
rns-page-node --stats-interval 60

# Save stats to JSON file on shutdown
rns-page-node --save-stats node_stats.json

# Actively write stats to file (live updates)
rns-page-node --stats-file stats.json

# Combined: live stats file + periodic display + final save
rns-page-node --stats-file stats.json --stats-interval 300 --save-stats final_stats.json
```

### Docker Stats Usage

```bash
# With periodic stats display
docker run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/app/config ghcr.io/sudo-ivan/rns-page-node:latest --stats-interval 60

# Save stats to mounted volume
docker run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/app/config -v ./stats:/app/stats ghcr.io/sudo-ivan/rns-page-node:latest --save-stats /app/stats/node_stats.json
```

### Tracked Metrics

- **Connection Statistics**: Total connections, active connections, peer tracking
- **Request Statistics**: Page requests, file requests, requests by path and peer
- **Performance Metrics**: Requests per hour, uptime, response patterns
- **Historical Data**: Recent request history, hourly/daily aggregations
- **Top Content**: Most requested pages and files, most active peers

## Options

```
-c, --config: The path to the Reticulum config file.
-n, --node-name: The name of the node.
-p, --pages-dir: The directory to serve pages from.
-f, --files-dir: The directory to serve files from.
-i, --identity-dir: The directory to persist the node's identity.
-a, --announce-interval: The interval to announce the node's presence.
--page-refresh-interval: The interval to refresh pages (seconds, 0 disables).
--file-refresh-interval: The interval to refresh files (seconds, 0 disables).
-l, --log-level: The logging level.
--stats-interval: Print stats every N seconds (0 disables).
--save-stats: Save stats to JSON file on shutdown.
```

## License

This project incorporates portions of the [NomadNet](https://github.com/markqvist/NomadNet) codebase, which is licensed under the GNU General Public License v3.0 (GPL-3.0). As a derivative work, this project is also distributed under the terms of the GPL-3.0. See the [LICENSE](LICENSE) file for full license.
