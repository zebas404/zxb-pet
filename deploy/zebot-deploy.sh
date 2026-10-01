#!/usr/bin/env bash
# Despliega Zebot en zxb-app01: git pull + docker compose up.
#
# Instalación (como root, una vez):
#   install -o root -g root -m 755 deploy/zebot-deploy.sh /usr/local/bin/zebot-deploy
#   echo 'zeb ALL=(root) NOPASSWD: /usr/local/bin/zebot-deploy ""' > /etc/sudoers.d/80-zebot-deploy
#   chmod 440 /etc/sudoers.d/80-zebot-deploy && visudo -c
#
# Uso:  sudo zebot-deploy        (sin argumentos: la regla de sudo no admite ninguno)
#
# La copia instalada es de root: cambiar este archivo en el repo no cambia lo que
# se ejecuta hasta que alguien con root lo reinstala.
set -euo pipefail

REPO_DIR=/opt/zxb-pet
REPO_OWNER=zeb

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
