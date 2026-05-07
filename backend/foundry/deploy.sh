#!/usr/bin/env bash
set -euo pipefail

# Build and deploy portfolio analysis agents to Foundry Agent Service
# Usage: ./foundry/deploy.sh [build|push|deploy|all]

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

REGISTRY="${AZURE_CONTAINER_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
AGENTS=("analysis" "candidate" "recommendation")

build() {
    echo "Building agent images..."
    cd "${PROJECT_ROOT}"
    for agent in "${AGENTS[@]}"; do
        echo "  Building ${agent}..."
        docker build -t "portfolio-${agent}-agent:${IMAGE_TAG}" \
            --build-arg AGENT_ROLE="${agent}" \
            -f foundry/Dockerfile .
    done
}

push() {
    if [ -z "${REGISTRY}" ]; then
        echo "Error: AZURE_CONTAINER_REGISTRY not set"
        exit 1
    fi
    cd "${PROJECT_ROOT}"
    echo "Pushing to ${REGISTRY}..."
    for agent in "${AGENTS[@]}"; do
        docker tag "portfolio-${agent}-agent:${IMAGE_TAG}" \
            "${REGISTRY}.azurecr.io/portfolio-${agent}-agent:${IMAGE_TAG}"
        docker push "${REGISTRY}.azurecr.io/portfolio-${agent}-agent:${IMAGE_TAG}"
    done
}

deploy() {
    cd "${PROJECT_ROOT}"
    echo "Deploying via azd..."
    azd deploy
}

ACTION="${1:-all}"
case "${ACTION}" in
    build) build ;;
    push) push ;;
    deploy) deploy ;;
    all) build && push && deploy ;;
    *) echo "Usage: $0 [build|push|deploy|all]"; exit 1 ;;
esac
