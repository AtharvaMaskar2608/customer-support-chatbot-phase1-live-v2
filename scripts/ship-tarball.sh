#!/usr/bin/env bash
# Ship a Jini image via docker build → save → scp (ECR push is IAM-blocked).
#
# Usage:
#   1. Edit the knobs under "EDIT ME".
#   2. From repo root:  ./scripts/ship-tarball.sh
#   3. Type the SSH password when scp/ssh prompts.
#
# Optional flags (override knobs for one run):
#   --component frontend|backend
#   --version 1.0.14
#   --no-scp              build + tarball only
#   --remote-load         after scp, ssh in and docker load + restart container
#   --no-compose-bump     leave docker-compose.yml alone
#   --dry-run             print steps, touch nothing remote
#
set -euo pipefail

# ── EDIT ME ──────────────────────────────────────────────────────────────────
COMPONENT=frontend          # frontend | backend
VERSION=1.0.14              # X.Y.Z only — becomes frontendv1.0.14 / backendv1.0.14

SCP_HOST=harsh@10.132.147.130
SCP_DIR=/home/harsh/jini
REMOTE_LOAD=0               # 1 = also ssh and replace the running container
# ── end EDIT ME ──────────────────────────────────────────────────────────────

DO_SCP=1
DO_COMPOSE_BUMP=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --component) COMPONENT=$2; shift 2 ;;
    --version) VERSION=$2; shift 2 ;;
    --no-scp) DO_SCP=0; shift ;;
    --remote-load) REMOTE_LOAD=1; shift ;;
    --no-compose-bump) DO_COMPOSE_BUMP=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

case "$COMPONENT" in
  frontend|backend) ;;
  *) echo "COMPONENT must be frontend or backend (got: $COMPONENT)" >&2; exit 1 ;;
esac

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "VERSION must look like X.Y.Z (got: $VERSION)" >&2
  exit 1
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

ECR=829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot
TAG="${COMPONENT}v${VERSION}"
IMAGE="${ECR}:${TAG}"
TARBALL="jini-${COMPONENT}-v${VERSION}.tar.gz"
CONTEXT="$COMPONENT"
COMPOSE="$ROOT/docker-compose.yml"

if [[ "$COMPONENT" == frontend ]]; then
  CONTAINER=jini-frontend
  RUN_EXTRA=(-p 8080:80)
else
  CONTAINER=jini-backend
  # env-file lives next to the tarball on the server
  RUN_EXTRA=(--network-alias backend --env-file "$SCP_DIR/.env" -p 8000:8000)
fi

echo "==> ship $TAG"
echo "    image:    $IMAGE"
echo "    tarball:  $ROOT/$TARBALL"
echo "    scp →     $SCP_HOST:$SCP_DIR/"
echo "    remote:   $([ "$REMOTE_LOAD" = 1 ] && echo load+restart || echo scp only)"
[[ "$DRY_RUN" = 1 ]] && echo "    mode:     DRY RUN"
echo

run() {
  if [[ "$DRY_RUN" = 1 ]]; then
    echo "DRY  $*"
  else
    echo "+ $*"
    "$@"
  fi
}

# 1. Mirror tag in docker-compose.yml
if [[ "$DO_COMPOSE_BUMP" = 1 ]]; then
  if [[ ! -f "$COMPOSE" ]]; then
    echo "Missing $COMPOSE" >&2
    exit 1
  fi
  if grep -qE "customer-support-chatbot:${COMPONENT}v[0-9]+\.[0-9]+\.[0-9]+" "$COMPOSE"; then
    if [[ "$DRY_RUN" = 1 ]]; then
      echo "DRY  sed bump ${COMPONENT}v* → $TAG in docker-compose.yml"
    else
      # portable in-place: write via temp (works on GNU + BSD sed)
      tmp=$(mktemp)
      sed -E "s|(customer-support-chatbot:)${COMPONENT}v[0-9]+\.[0-9]+\.[0-9]+|\1${TAG}|g" \
        "$COMPOSE" >"$tmp"
      mv "$tmp" "$COMPOSE"
      echo "+ bumped docker-compose.yml → $TAG"
      grep -E "image:.*${COMPONENT}v" "$COMPOSE" || true
    fi
  else
    echo "WARN: no ${COMPONENT}v* image line found in docker-compose.yml — skip bump" >&2
  fi
fi

# 2. Build
run docker build -t "$IMAGE" "$CONTEXT/"

# 3. Save tarball (gitignored as jini-*.tar.gz)
if [[ "$DRY_RUN" = 1 ]]; then
  echo "DRY  docker save $IMAGE | gzip > $TARBALL"
else
  echo "+ docker save $IMAGE | gzip > $TARBALL"
  docker save "$IMAGE" | gzip >"$TARBALL"
  ls -lh "$TARBALL"
fi

# 4. SCP
if [[ "$DO_SCP" = 1 ]]; then
  run scp "$TARBALL" "$SCP_HOST:$SCP_DIR/"
else
  echo "==> skipping scp (--no-scp)"
fi

# 5. Optional remote load + replace container
if [[ "$DO_SCP" = 1 && "$REMOTE_LOAD" = 1 ]]; then
  # shellcheck disable=SC2029
  remote_cmd=$(cat <<EOF
set -euo pipefail
cd '$SCP_DIR'
docker load < '$TARBALL'
docker rm -f '$CONTAINER'
docker run -d --name '$CONTAINER' --network jini-net --restart unless-stopped \
  ${RUN_EXTRA[*]} \
  '$IMAGE'
docker ps --filter name='$CONTAINER' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
EOF
)
  if [[ "$DRY_RUN" = 1 ]]; then
    echo "DRY  ssh $SCP_HOST <<'EOF'"
    echo "$remote_cmd"
    echo "EOF"
  else
    echo "+ ssh $SCP_HOST (docker load + restart $CONTAINER)"
    ssh -t "$SCP_HOST" "$remote_cmd"
  fi
fi

echo
echo "==> local done: $TAG"
if [[ "$DO_SCP" = 1 && "$REMOTE_LOAD" != 1 ]]; then
  cat <<EOF

On the server (if you skipped --remote-load):

  cd $SCP_DIR
  docker load < $TARBALL
  docker rm -f $CONTAINER
  docker run -d --name $CONTAINER --network jini-net --restart unless-stopped \\
    ${RUN_EXTRA[*]} \\
    $IMAGE

Verify:

  curl -s -o /dev/null -w "%{http_code}\\n" https://jini-chatbot.quanthm.com/
  curl -s -o /dev/null -w "%{http_code}\\n" https://jini-chatbot.quanthm.com/widget.js
  curl -s -o /dev/null -w "%{http_code}\\n" https://jini-chatbot.quanthm.com/api/greeting
EOF
fi

if [[ "$DO_COMPOSE_BUMP" = 1 && "$DRY_RUN" != 1 ]]; then
  echo
  echo "Remember to commit docker-compose.yml if you want the tag tracked on main:"
  echo "  git add docker-compose.yml && git commit -m \"CHO-XXX: bump ${COMPONENT} image to v${VERSION}\""
fi
