import os
import cv2
from PIL import Image, ImageOps

THUMB_SIZE = (400, 400)
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.3gp'}

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
