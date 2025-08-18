# RNS Page Node

[![Build and Publish Docker Image](https://github.com/Sudo-Ivan/rns-page-node/actions/workflows/docker.yml/badge.svg)](https://github.com/Sudo-Ivan/rns-page-node/actions/workflows/docker.yml)
[![Docker Build Test](https://github.com/Sudo-Ivan/rns-page-node/actions/workflows/docker-test.yml/badge.svg)](https://github.com/Sudo-Ivan/rns-page-node/actions/workflows/docker-test.yml)
[![DeepSource](https://app.deepsource.com/gh/Sudo-Ivan/rns-page-node.svg/?label=active+issues&show_trend=true&token=kajzd0SjJXSzkuN3z3kG9gQw)](https://app.deepsource.com/gh/Sudo-Ivan/rns-page-node/)

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
docker run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/root/.reticulum ghcr.io/sudo-ivan/rns-page-node:latest
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

## Options

```
-c, --config: The path to the Reticulum config file.
-n, --node-name: The name of the node.
-p, --pages-dir: The directory to serve pages from.
-f, --files-dir: The directory to serve files from.
-i, --identity-dir: The directory to persist the node's identity.
-a, --announce-interval: The interval to announce the node's presence.
-r, --page-refresh-interval: The interval to refresh pages.
-f, --file-refresh-interval: The interval to refresh files.
-l, --log-level: The logging level.
```

## License

This project incorporates portions of the [NomadNet](https://github.com/markqvist/NomadNet) codebase, which is licensed under the GNU General Public License v3.0 (GPL-3.0). As a derivative work, this project is also distributed under the terms of the GPL-3.0. See the [LICENSE](LICENSE) file for full license.
