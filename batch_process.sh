#!/bin/bash

# Trap SIGINT (Ctrl+C) to exit the script immediately
trap "echo 'Script interrupted by user'; exit 1" SIGINT

# Create transcripts directory if it doesn't exist
mkdir -p transcripts

# Loop through all mp4 files in vids directory
for f in vids/*.mp4; do
    # Check if file exists (in case of no matches)
    [ -e "$f" ] || continue

    filename=$(basename "$f" .mp4)
    output_dir="transcripts/$filename"
    transcript_file="$output_dir/transcript.md"

    # Check if transcript already exists
    if [ -f "$transcript_file" ]; then
        echo "Skipping $filename (already processed)"
        continue
    fi

    echo "========================================================"
    echo "Processing $filename..."
    echo "========================================================"
    
    # Create output directory for this video
    mkdir -p "$output_dir"
    
    # Run the processor
    ./run_processor.sh "$f" "$output_dir"
done

echo "Batch processing complete."
