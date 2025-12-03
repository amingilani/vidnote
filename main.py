import argparse
import os
import shutil
import whisper
import cv2
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

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
        # We want the first frame of the scene. 
        # Note: scene[0] is start frame/time, scene[1] is end frame/time.
        
        # Set capture to the start of the scene
        cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)
        success, frame = cap.read()
        
        if success:
            image_filename = f"scene_{i+1:03d}.jpg"
            image_path = os.path.join(output_dir, image_filename)
            cv2.imwrite(image_path, frame)
            
            slides.append({
                "timestamp": start_time,
                "image_filename": image_filename,
                "end_timestamp": scene[1].get_seconds()
            })
    
    cap.release()
    
    return slides

def generate_markdown(transcript, slides, output_file):
    print(f"Generating markdown to {output_file}...")
    
    with open(output_file, "w") as f:
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
                    f.write(f"**[{int(slide['timestamp'] // 60)}:{int(slide['timestamp'] % 60):02d}]**\n\n")
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
    generate_markdown(transcript_result, slides, output_md)
    print("Done!")

if __name__ == "__main__":
    main()
