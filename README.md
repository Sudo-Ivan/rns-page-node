# RNS Page Node

A simple way to serve pages and files over the [Reticulum network](https://reticulum.network/). Drop-in replacement for [NomadNet](https://github.com/markqvist/NomadNet) nodes that primarily serve pages and files.

## Usage

```bash
pip install git+https://github.com/Sudo-Ivan/rns-page-node.git

# or

pipx install git+https://github.com/Sudo-Ivan/rns-page-node.git
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

## Page formats

- Micron `.mu`

## Options

```
-c, --config: The path to the Reticulum config file.
-n, --node-name: The name of the node.
-p, --pages-dir: The directory to serve pages from.
-f, --files-dir: The directory to serve files from.
-i, --identity-dir: The directory to persist the node's identity.
-a, --announce-interval: The interval to announce the node's presence.
```

## To-Do

- [ ] Pypi

## License

This project incorporates portions of the [NomadNet](https://github.com/markqvist/NomadNet) codebase, which is licensed under the GNU General Public License v3.0 (GPL-3.0). As a derivative work, this project is also distributed under the terms of the GPL-3.0. See the [LICENSE](LICENSE) file for full license.
