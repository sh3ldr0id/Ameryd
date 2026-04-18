import os
import cv2
from PIL import Image, ImageOps

THUMB_SIZE = (400, 400)
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.3gp', '.m4v'}

def generate_thumbnail(media_path, thumb_path, quality=80):
    try:
        with Image.open(media_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail(THUMB_SIZE)
            img.save(thumb_path, "WEBP", quality=quality)
            return True
    except Exception as e:
        print(f"Failed to generate thumbnail for {media_path}: {e}")
        return False

def generate_video_thumbnail(video_path, thumb_path, quality=80):
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps))
            
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            
        cap.release()
        
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail(THUMB_SIZE)
            img.save(thumb_path, "WEBP", quality=quality)
            return True
    except Exception as e:
        print(f"Exception generating video thumbnail: {e}")
        return False

def generate_thumb_for_any(media_path, thumb_path, quality=80):
    ext = os.path.splitext(media_path)[1].lower()
    if ext in IMAGE_EXTS:
        return generate_thumbnail(media_path, thumb_path, quality=quality)
    elif ext in VIDEO_EXTS:
        return generate_video_thumbnail(media_path, thumb_path, quality=quality)
    return False

def get_media_dimensions(media_path):
    """Get dimensions (width, height) of an image or video."""
    ext = os.path.splitext(media_path)[1].lower()
    
    if ext in IMAGE_EXTS:
        try:
            with Image.open(media_path) as img:
                return img.size # (width, height)
        except:
            pass
            
    elif ext in VIDEO_EXTS:
        try:
            cap = cv2.VideoCapture(media_path)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    return (w, h)
        except:
            pass
            
    return (0, 0)

import math

def process_image_compress(input_path, output_path):
    try:
        from PIL import Image
        with Image.open(input_path) as img:
            width, height = img.size
            pixels = width * height
            max_pixels = 12500000
            
            if pixels > max_pixels:
                scale = math.sqrt(max_pixels / pixels)
                new_width = math.floor(width * scale)
                new_height = math.floor(height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            if img.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA" or img.mode == "LA":
                    background.paste(img, mask=img.split()[-1])
                else:
                    background = img.convert("RGB")
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
                
            exif = img.info.get('exif')
            icc = img.info.get('icc_profile')
            dpi = img.info.get('dpi')
            
            save_kwargs = {"quality": 90}
            if exif: save_kwargs["exif"] = exif
            if icc: save_kwargs["icc_profile"] = icc
            if dpi: save_kwargs["dpi"] = dpi
            
            img.save(output_path, "JPEG", **save_kwargs)
            return True
    except Exception as e:
        print(f"Image compress failed: {e}")
        return False

def process_video_compress(input_path, output_path):
    try:
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-map_metadata", "0",
            "-movflags", "use_metadata_tags",
            "-vf", "scale=-2:1080",
            "-c:v", "libx265",
            "-preset", "medium",
            "-crf", "26",
            "-threads", "1",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]
        # Run ffmpeg, timeout after a reasonable time or let it block
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print(f"Video compress failed: {e}")
        return False
