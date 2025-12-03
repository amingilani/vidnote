#!/bin/bash

# Usage: ./run_processor.sh <path_to_video> <output_folder>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <path_to_video> <output_folder>"
    exit 1
fi

VIDEO_PATH=$(realpath "$1")
OUTPUT_PATH=$(realpath "$2")
VIDEO_DIR=$(dirname "$VIDEO_PATH")
VIDEO_FILENAME=$(basename "$VIDEO_PATH")

# Create local temp dir
mkdir -p ./tmp_data

# Build image if not exists
# Check if image exists, if not build it
if ! podman image exists video-textbook; then
    echo "Building container image..."
    podman build -t video-textbook .
fi

echo "Running container..."
# Run Container
# -v Mount the folder containing the video to /data/input
# -v Mount the output folder to /data/output
# -v Mount the local tmp folder to /data/tmp
podman run --rm -it \
  -v "$VIDEO_DIR":/data/input:Z \
  -v "$OUTPUT_PATH":/data/output:Z \
  -v "./tmp_data":/data/tmp:Z \
  video-textbook \
  --input_video "/data/input/$VIDEO_FILENAME" \
  --output_dir "/data/output" \
  --temp_dir "/data/tmp"
