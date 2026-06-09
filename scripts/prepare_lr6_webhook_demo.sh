#!/usr/bin/env sh
set -eu

# Prepares a safe Git repository only inside the running API container.
# The host repository is not mounted or modified.

DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/docker-config}"
export DOCKER_CONFIG

docker compose exec -T api sh -lc '
set -eu

cd /app
rm -rf .git /tmp/lr6_demo_origin.git /tmp/lr6_demo_seed

git init -q
git config user.email "lr6-demo@example.com"
git config user.name "LR6 Demo"
git add app alembic alembic.ini
git commit -q -m "Initial LR6 demo app state"
git branch -M main

git clone --bare /app /tmp/lr6_demo_origin.git >/dev/null 2>&1
git remote add origin /tmp/lr6_demo_origin.git

git clone /tmp/lr6_demo_origin.git /tmp/lr6_demo_seed >/dev/null 2>&1
cd /tmp/lr6_demo_seed
git config user.email "lr6-demo@example.com"
git config user.name "LR6 Demo"
date -u +"LR6 webhook demo pull marker: %Y-%m-%dT%H:%M:%SZ" > DEMO_WEBHOOK_MARKER.txt
git add DEMO_WEBHOOK_MARKER.txt
git commit -q -m "Add LR6 webhook demo marker"
git push origin main >/dev/null 2>&1

cd /app
echo "LR6 webhook demo repository is ready."
echo "origin: /tmp/lr6_demo_origin.git"
echo "branch: main"
echo "Expected after webhook: /app/DEMO_WEBHOOK_MARKER.txt"
'
