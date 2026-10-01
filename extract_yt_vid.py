import cv2
import yt_dlp
import os
import numpy as np

def parse_timestamp_to_seconds(timestamp):
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    parts = str(timestamp).strip().split(':')
    if len(parts) == 1:
        return float(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

def download_video(url, output_path="banana.mp4"):
    print("Downloading video...")
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return output_path

def resize_with_aspect_ratio(frame, target_w=1280, target_h=800, mode="letterbox"):
    """
    Resizes an image frame to target dimensions while maintaining aspect ratio.
    
    :param mode: 'letterbox' (add black padding) or 'crop' (fill screen by cropping edges)
    """
    h_src, w_src = frame.shape[:2]
    
    if mode == "letterbox":
        # Scale to fit INSIDE target bounds (preserves 100% of image, pads with black)
        scale = min(target_w / w_src, target_h / h_src)
        new_w, new_h = int(w_src * scale), int(h_src * scale)
        
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Create black canvas of target size
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        
        # Center the resized frame on the canvas
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        return canvas

    elif mode == "crop":
        # Scale to COVER target bounds completely (no black bars, crops overflow)
        scale = max(target_w / w_src, target_h / h_src)
        new_w, new_h = int(w_src * scale), int(h_src * scale)
        
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Crop from the center
        x_start = (new_w - target_w) // 2
        y_start = (new_h - target_h) // 2
        return resized[y_start:y_start + target_h, x_start:x_start + target_w]

    else:
        raise ValueError("Mode must be 'letterbox' or 'crop'")

def is_duplicate_frame(prev_frame, curr_frame, diff_threshold=3.0):
    if prev_frame is None:
        return False
    diff = cv2.absdiff(prev_frame, curr_frame)
    return np.mean(diff) < diff_threshold

def extract_unique_loop(video_path, output_dir="dlp_patterns", timestamp="00:03", target_unique_frames=8, resize_mode="letterbox"):
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    start_seconds = parse_timestamp_to_seconds(timestamp)
    start_frame = int(fps * start_seconds)
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    print(f"Seeking to {timestamp} (frame #{start_frame})...")
    print(f"Extracting {target_unique_frames} unique frames at 1140x912 resolution (Mode: '{resize_mode}')...\n")
    
    saved_count = 0
    prev_saved_frame = None
    frames_inspected = 0

    while saved_count < target_unique_frames:
        ret, frame = cap.read()
        if not ret:
            print("Reached end of video.")
            break
            
        frames_inspected += 1
        
        if is_duplicate_frame(prev_saved_frame, frame):
            continue

        # Correct aspect ratio and resize to native DLP resolution (1140x912)
        formatted_frame = resize_with_aspect_ratio(
            frame, 
            target_w=912,  
            target_h=1140, 
            mode=resize_mode
        )
        
        filename = os.path.join(output_dir, f"sluipschutters_frame_{saved_count:02d}.bmp")
        cv2.imwrite(filename, formatted_frame)
        
        print(f"Saved unique frame {saved_count+1}/{target_unique_frames}: {filename}")
        
        prev_saved_frame = frame
        saved_count += 1

    cap.release()
    print(f"\nDone! Saved {saved_count} perfectly scaled 1140x912 24-bit BMP frames.")

if __name__ == "__main__":
    youtube_url = "https://www.youtube.com/watch?v=z5Qs3v_ZJUk"
    video_file = "sluipschutters.mp4"
    
    download_video(youtube_url, video_file)
    
    # Options for resize_mode:
    # "letterbox" = Keeps entire video visible, adds black bars if needed
    # "crop"      = Fills 100% of 1140x912 screen, crops top/bottom or sides
    extract_unique_loop(
        video_path=video_file,
        output_dir="dlp_patterns",
        timestamp="00:58",
        target_unique_frames=8,
        resize_mode="letterbox"
    )