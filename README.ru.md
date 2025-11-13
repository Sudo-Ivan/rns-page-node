# RNS Page Node

[English](README.md)

Простой способ для раздачи страниц и файлов через сеть [Reticulum](https://reticulum.network/). Прямая замена для узлов [NomadNet](https://github.com/markqvist/NomadNet), которые в основном служат для раздачи страниц и файлов.

## Особенности
- Раздача страниц и файлов.
- Простота

## Установка

```bash
# Pip
# Может потребоваться --break-system-packages
pip install rns-page-node

# Pipx
pipx install rns-page-node

# uv
uv venv
source .venv/bin/activate
uv pip install rns-page-node

# Pipx через Git
pipx install git+https://github.com/Sudo-Ivan/rns-page-node.git

```
## Использование
```bash
# будет использовать текущий каталог для страниц и файлов
rns-page-node
```

или
```bash
rns-page-node --node-name "Page Node" --pages-dir ./pages --files-dir ./files --identity-dir ./node-config --announce-interval 3600
```

### Docker/Podman
```bash
docker run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/root/.reticulum ghcr.io/sudo-ivan/rns-page-node:latest
```

### Docker/Podman без root-доступа
```bash
mkdir -p ./pages ./files ./node-config ./config
chown -R 1000:1000 ./pages ./files ./node-config ./config
podman run -it --rm -v ./pages:/app/pages -v ./files:/app/files -v ./node-config:/app/node-config -v ./config:/app/config ghcr.io/sudo-ivan/rns-page-node:latest-rootless
```

Монтирование томов необязательно, вы также можете скопировать страницы и файлы в контейнер с помощью `podman cp` или `docker cp`.

## Сборка
```bash
make build
```

Сборка wheels:
```bash
make wheel
```

### Сборка Wheels в Docker
```bash
make docker-wheels
```

## Страницы

Поддерживаются динамические страницы, но разбор данных запроса пока не реализован.

## Параметры

```
-c, --config: Путь к файлу конфигурации Reticulum.
-n, --node-name: Имя узла.
-p, --pages-dir: Каталог для раздачи страниц.
-f, --files-dir: Каталог для раздачи файлов.
-i, --identity-dir: Каталог для сохранения идентификационных данных узла.
-a, --announce-interval: Интервал анонсирования присутствия узла.
-r, --page-refresh-interval: Интервал обновления страниц.
-f, --file-refresh-interval: Интервал обновления файлов.
-l, --log-level: Уровень логирования.
```

## Лицензия

Этот проект включает части кодовой базы [NomadNet](https://github.com/markqvist/NomadNet), которая лицензирована под GNU General Public License v3.0 (GPL-3.0). Как производная работа, этот проект также распространяется на условиях GPL-3.0. Полный текст лицензии смотрите в файле [LICENSE](LICENSE).