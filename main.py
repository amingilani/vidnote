import argparse
import os
import shutil
import whisper
import cv2
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
import numpy as np
import hashlib

def calculate_sha512(file_path):
    sha512_hash = hashlib.sha512()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha512_hash.update(byte_block)
    return sha512_hash.hexdigest()

def parse_args():
    parser = argparse.ArgumentParser(description="Video to Textbook Converter")
    parser.add_argument("--input_video", required=True, help="Path to video file inside container")
    parser.add_argument("--output_dir", required=True, help="Path to write results")
    parser.add_argument("--temp_dir", required=True, help="Path for intermediate files")
    parser.add_argument("--threshold", type=float, default=15.0, help="Scene detection threshold (default: 15.0)")
    return parser.parse_args()

def extract_audio(video_path, audio_path):
    # Use system ffmpeg call
    print(f"Extracting audio to {audio_path}...")
    ret = os.system(f"ffmpeg -i \"{video_path}\" -q:a 0 -map a \"{audio_path}\" -y")
    if ret != 0:
        raise RuntimeError("FFmpeg failed to extract audio")

def transcribe_audio(audio_path, model_size="base"):
    print(f"Transcribing audio with model {model_size}...")
    model = whisper.load_model(model_size)
    return model.transcribe(audio_path)

def extract_slides(video_path, output_dir, threshold=15.0):
    # Logic to detect scenes and save frames using scenedetect + cv2
    print(f"Detecting scenes with threshold {threshold}...")
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    
    scene_manager.detect_scenes(video, show_progress=True)
    scene_list = scene_manager.get_scene_list()
    
    print(f"Found {len(scene_list)} scenes.")
    
    slides = []
    cap = cv2.VideoCapture(video_path)
    
    for i, scene in enumerate(scene_list):
        start_time = scene[0].get_seconds()
        end_time = scene[1].get_seconds()
        
        # Motion-based stable frame detection
        # We will analyze frames in the scene to find the one with minimum motion.
        
        cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)
        
        # Online frame selection to save memory
        best_candidate = None # {frame, diff, content}
        min_diff_seen = float('inf')
        stability_buffer = 2.0
        
        frame_count = 0
        prev_frame = None
        
        while True:
            current_time_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            if current_time_msec > end_time * 1000:
                break
                
            success, frame = cap.read()
            if not success:
                break
            
            # Process every 5th frame to speed up
            if frame_count % 5 == 0:
                score = float('inf')
                if prev_frame is not None:
                    # Calculate difference
                    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray_prev = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                    score = cv2.mean(cv2.absdiff(gray_frame, gray_prev))[0]
                else:
                    # First frame, treat as 0 diff
                    score = 0.0
                
                # Update global min diff seen for this scene
                if score < min_diff_seen:
                    min_diff_seen = score
                
                # Calculate visual content (standard deviation)
                _, std_dev = cv2.meanStdDev(frame)
                content_score = np.mean(std_dev)
                
                # Decide if this frame is the new best
                is_better = False
                
                if best_candidate is None:
                    is_better = True
                else:
                    # Check if current best is still stable enough
                    if best_candidate['diff'] > min_diff_seen + stability_buffer:
                        # Current best is unstable compared to what we've seen.
                        # We must switch to something stable.
                        if score <= min_diff_seen + stability_buffer:
                            is_better = True
                    else:
                        # Current best is stable. Check if new frame is stable AND has better content.
                        if score <= min_diff_seen + stability_buffer:
                            if content_score > best_candidate['content']:
                                is_better = True
                
                if is_better:
                    best_candidate = {
                        'frame': frame.copy(),
                        'diff': score,
                        'content': content_score
                    }
                    # print(f"  New best: Diff={score:.2f}, Content={content_score:.2f}")
                
                prev_frame = frame.copy()
            
            frame_count += 1
            
        # Use the best candidate found
        if best_candidate is not None:
            best_frame = best_candidate['frame']
        else:
            # Fallback
            cap.set(cv2.CAP_PROP_POS_MSEC, (start_time + end_time) / 2 * 1000)
            _, best_frame = cap.read()

        if best_frame is not None:
            image_filename = f"scene_{i+1:03d}.jpg"
            image_path = os.path.join(output_dir, image_filename)
            cv2.imwrite(image_path, best_frame)
            
            slides.append({
                "timestamp": start_time,
                "image_filename": image_filename,
                "end_timestamp": end_time
            })
    
    cap.release()
    
    return slides

def generate_markdown(transcript, slides, output_file, video_filename, video_hash):
    print(f"Generating markdown to {output_file}...")
    
    with open(output_file, "w") as f:
        f.write("---\n")
        f.write(f"source_file: {video_filename}\n")
        f.write(f"sha512: {video_hash}\n")
        f.write("---\n\n")
        f.write("# Video Transcript\n\n")
        
        # We will iterate through transcript segments and insert images when appropriate
        # A simple strategy: Insert the slide image if the current text segment's start time 
        # is after the slide's start time, and we haven't inserted it yet.
        
        current_slide_idx = 0
        
        for segment in transcript["segments"]:
            start = segment["start"]
            text = segment["text"].strip()
            
            # Check if we should insert a slide
            # We insert a slide if the segment starts after the slide starts
            # But we should probably group text under the slide.
            
            while current_slide_idx < len(slides):
                slide = slides[current_slide_idx]
                if start >= slide["timestamp"]:
                    f.write(f"\n\n![Scene {current_slide_idx+1}](images/{slide['image_filename']})\n\n")
                    current_slide_idx += 1
                else:
                    break
            
            f.write(f"{text} ")

def main():
    args = parse_args()
    
    # Directory Prep
    images_dir = os.path.join(args.output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(args.temp_dir, exist_ok=True)

    print(f"Processing: {args.input_video}")
    
    # 1. Audio
    audio_temp = os.path.join(args.temp_dir, "extracted_audio.mp3")
    extract_audio(args.input_video, audio_temp)
    
    print("Transcribing...")
    transcript_result = transcribe_audio(audio_temp)
    
    # 2. Video
    print("Extracting slides...")
    slides = extract_slides(args.input_video, images_dir, threshold=args.threshold)
    
    # 3. Merge
    output_md = os.path.join(args.output_dir, "transcript.md")
    
    print("Calculating file hash...")
    video_hash = calculate_sha512(args.input_video)
    video_filename = os.path.basename(args.input_video)
    
    generate_markdown(transcript_result, slides, output_md, video_filename, video_hash)
    print("Done!")

if __name__ == "__main__":
    main()
