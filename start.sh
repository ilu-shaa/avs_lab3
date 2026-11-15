#!/usr/bin/env bash
set -e

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
container=avs-lab3
rebuild=false

case "${1:-}" in
    --rebuild) rebuild=true ;;
    --help|-h)
        echo 'Usage: ./start.sh [--rebuild]'
        echo 'Starts the lab with two printers and opens Bash.'
        echo '--rebuild rebuilds the image and replaces the container, ending all sessions.'
        echo 'Files in /work are preserved in the avs-lab3-work volume.'
        exit 0 ;;
    '') ;;
    *) echo 'Unknown option. Use ./start.sh --help.' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    echo 'Too many arguments. Use ./start.sh --help.' >&2
    exit 2
fi

if [ ! -t 0 ] || [ ! -t 1 ]; then
    echo 'Run start.sh in an interactive terminal.' >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo 'Docker is not installed or is not available in PATH.' >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo 'Start Docker and try again.' >&2
    exit 1
fi

if [ "$rebuild" = true ]; then
    docker build -t avs-lab3-printer "$script_dir"
    if docker container inspect "$container" >/dev/null 2>&1; then
        docker stop --time 8 "$container" >/dev/null
        docker rm "$container" >/dev/null
    fi
elif ! docker container inspect "$container" >/dev/null 2>&1; then
    docker build -t avs-lab3-printer "$script_dir"
fi

if docker container inspect "$container" >/dev/null 2>&1; then
    docker start "$container" >/dev/null
else
    docker run -dit --name "$container" \
        --mount type=volume,source=avs-lab3-work,target=/work \
        avs-lab3-printer >/dev/null
fi

exec docker exec -it "$container" bash
