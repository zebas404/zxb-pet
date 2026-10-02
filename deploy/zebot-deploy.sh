#!/usr/bin/env bash
# Despliega Zebot en zxb-app01 (git pull + docker compose up) o muestra sus logs.
#
# Instalación (como root, una vez):
#   install -o root -g root -m 755 deploy/zebot-deploy.sh /usr/local/bin/zebot-deploy
#   cat > /etc/sudoers.d/80-zebot-deploy <<'RULES'
#   zeb ALL=(root) NOPASSWD: /usr/local/bin/zebot-deploy ""
#   zeb ALL=(root) NOPASSWD: /usr/local/bin/zebot-deploy logs
#   RULES
#   chmod 440 /etc/sudoers.d/80-zebot-deploy && visudo -c
#
# Uso:  sudo zebot-deploy         despliega
#       sudo zebot-deploy logs    últimas 200 líneas del contenedor (solo lectura)
# Las reglas de sudo solo admiten esas dos formas exactas.
#
# La copia instalada es de root: cambiar este archivo en el repo no cambia lo que
# se ejecuta hasta que alguien con root lo reinstala.
set -euo pipefail

REPO_DIR=/opt/zxb-pet
REPO_OWNER=zeb
CONTAINER=zebot
LOG_LINES=200

case "${1-}" in
  "") ;;
  logs)
    exec docker logs --timestamps --tail "$LOG_LINES" "$CONTAINER"
    ;;
  *)
    echo "uso: zebot-deploy [logs]" >&2
    exit 2
    ;;
esac

cd "$REPO_DIR"
echo "==> git pull (como $REPO_OWNER)"
runuser -u "$REPO_OWNER" -- git -C "$REPO_DIR" pull --ff-only
runuser -u "$REPO_OWNER" -- git -C "$REPO_DIR" log --oneline -1

echo "==> docker compose up -d --build"
docker compose up -d --build

echo "==> limpieza de imágenes antiguas"
docker image prune -f >/dev/null

echo "==> estado"
docker compose ps
