#!/bin/bash

# Usage: ./run_processor.sh <path_to_video> <output_folder> [threshold]

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <path_to_video> <output_folder> [threshold]"
    exit 1
fi

VIDEO_PATH=$(realpath "$1")
OUTPUT_PATH=$(realpath "$2")
THRESHOLD=${3:-10.0}
VIDEO_DIR=$(dirname "$VIDEO_PATH")
VIDEO_FILENAME=$(basename "$VIDEO_PATH")

# Create local temp dir
mkdir -p ./data/tmp

# Build image if not exists
# Check if image exists, if not build it
if ! podman image exists video-textbook; then
    echo "Building container image..."
    podman build -t video-textbook .
fi

echo "Running container with threshold $THRESHOLD..."
# Run Container
# -v Mount the folder containing the video to /data/input
# -v Mount the output folder to /data/output
# -v Mount the local tmp folder to /data/tmp
podman run --rm -it \
  -v "$VIDEO_DIR":/data/input:Z \
  -v "$OUTPUT_PATH":/data/output:Z \
  -v "./data/tmp":/data/tmp:Z \
  video-textbook \
  --input_video "/data/input/$VIDEO_FILENAME" \
  --output_dir "/data/output" \
  --temp_dir "/data/tmp" \
  --threshold "$THRESHOLD"
