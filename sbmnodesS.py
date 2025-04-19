"""
@author: SBM

Nodes I need and nobody did proper.

Changelog:
15/03/2025 Init - image saver.
01/04/2025 Added file sort node.
17/04/2025 Added file overwrite parm.
19/04/2025 Changed filename path to overwrite flag.
            Added simple string to float cast, kj and pygoss really dropping the ball on this.
            Added vid folder merge with last frame dropping (by gepetto) - basic pattern and filename support.
"""

from .sbmsharedS import Store_Settings, SORT_CRITERIA

import folder_paths
#import piexif
import piexif.helper
import os
join = os.path.join
import inspect
import glob
import json
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import numpy as np
import subprocess # Used for ffmpeg calls.

fconst = lambda v: v
# Dual sided linear percent - at 0% returns vmin, at 100% returns vmax. 
fpercent = lambda vprc, vmin = 0, vmax = 100: round(vmin + vprc / 100 * (vmax - vmin))
# Renames r arguemtns and sets the value for a arguments.
fswitcheroo = lambda f, r={}, a={}: lambda **kw: f(**{r.get(k, k): v for k, v in {**kw, **a}.items()})
# Variant which swallows redundant parms, but requires inspect.
try:
    fswitcheroo2 = lambda f, r={}, a={}: lambda **kw: f(**{r.get(k, k): v for k, v in {**kw, **a}.items()
                                                           if r.get(k, k) in inspect.signature(f).parameters})
except Exception:
    fswitcheroo2 = fswitcheroo

# Compression parms per image type. Each returns a func accepting qual, opt.
# Generally I pick slow and best compression, aside from qual.
# Png goes 9-0, webp's method goes 0-6.
DCOMPRESS = {
"jpg": {
    "quality": fswitcheroo2(fpercent, r = {"qual": "vprc"}),
    "optimize": fswitcheroo2(fconst, r = {"opt": "v"}),
    "subsampling": fswitcheroo2(fconst, a = {"v": 0})
},
"png": {
    "compress_level": fswitcheroo2(fpercent, r = {"qual": "vprc"}, a = {"vmin": 9, "vmax": 0}),
    "optimize": fswitcheroo2(fconst, r = {"opt": "v"})
},
"webp": {
    "quality": fswitcheroo2(fpercent, r = {"qual": "vprc"}),
    "method": fswitcheroo2(fconst, a = {"v": 6})
},
}

# Value which causes error instead of default in float cast. Comfy doesn't quite support null for widget.
FLOAT_ERROR = -555
VID_EXTENSIONS = ('mp4', 'mov', 'avi', 'mkv', 'webm') # Must be a tuple for endswith to work directly.

### Sort setting node.
class SortControlSBM:
    """Control the sorting method for model lists."""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sort_method": (list(SORT_CRITERIA.keys()), {"default": Store_Settings.DEF_SORT}),
                "reverse_order": ("BOOLEAN", {"default": Store_Settings.DEF_REV}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "update_sort"

    OUTPUT_NODE = True

    CATEGORY = "SBM Nodes"
    DESCRIPTION = "Control how models are sorted in the UI"

    def update_sort(self, sort_method, reverse_order): #, apply_now):
        Store_Settings.DEF_SORT = sort_method
        Store_Settings.DEF_REV = reverse_order
        Store_Settings.ANTICACHE["loras"] = True # Alt: Refresh everything by clearing dict.
        
        return {}

### Save image to png / jpg / webp with metadata and no online nonsense.
class ImageSaverSBM:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory() # folder_paths.output_directory

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "image(s) to save"}),
                "mode": (["serialise", "overwrite"], {
                    "default": "serialise",
                    "tooltip": "serialise=auto-numbered (usual behaviour), overwrite=replace existing"
                    }),
                "flprefix": ("STRING", {"default": '%time_%basemodelname_%seed', "multiline": False,
                                         "tooltip": ("filename (available variables: %date, %time, %model, %seed, "
                                                     "%counter, %sampler_name, %steps, %cfg, %scheduler, "
                                                     "%basemodelname, %denoise, %clip_skip)")}),
                "extension": (['png', 'jpg', 'webp'], {"tooltip": "file extension/type to save image as"}),
                "quality": ("INT", {"default": 85, "min": 1, "max": 100,
                                    "tooltip": "quality setting of JPG/WEBP, PNG is scaled"}),
                "optimise": ("BOOLEAN", {"default": True,
                                         "tooltip": "Optimise = extra compression"}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "save_files"

    OUTPUT_NODE = True

    CATEGORY = "ImageSaverSBM"
    DESCRIPTION = "Save images with format and compression and metadata."

    def _generate_filename(self, save_dir, prefix, vext, mode = "serialise"):
        """SBM simple serial filename. 
        
        Ignores index, Idc to preserve the order with multiple items.
        Much easier to follow single chronological trail.
        Also checks filenames all at once instead of looping till next gap,
        what a pos code.
        Mode overwrite will simply write the given filename, serialise will add a new index.
        """
        # Use glob to find all files matching the pattern
        # SBM Detect any extensions for true series.
        # pattern = os.path.join(save_dir, f"{prefix}_*.{vext}")
        base_path = join(save_dir, prefix)
        if mode == "overwrite":
            return f"{base_path}.{vext}"
        pattern = f"{base_path}_*.*"
        existing_files = glob.glob(pattern)
        
        # Extract the number between the underscore and the period
        indices = [
            os.path.splitext(os.path.basename(file))[0].split("_")[-1]
            for file in existing_files
        ]
        indices = [int(i) for i in indices if i.isdigit()]
        
        # Determine the next index
        next_index = max(indices) + 1 if indices else 1 # index
        
        # Generate the filename
        filename = f"{base_path}_{next_index}.{vext}"
        return filename

    def save_files(
        self,
        images,
        mode,
        flprefix,
        extension,
        quality,
        optimise,
        prompt=None,
        extra_pnginfo=None,
    ):
        results = []
        for image in images:
            filename = self._generate_filename(self.output_dir, flprefix, extension, mode = mode)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            subfolder = os.path.normpath(os.path.dirname(filename))
            self.save_image(image, filename, extension, quality, optimise, prompt, extra_pnginfo)
            results.append({
                "filename": filename,
                "subfolder": subfolder,
                "type": "output",
            })
        
        return { "ui": { "images": results }, "result": (filename, ) }

    def save_json(self, image_info, filename):
        workflow = None
        try:
            workflow = (image_info or {}).get('workflow')
            if workflow is not None:
                # print('No image info found, skipping saving of JSON')
                with open(filename, 'w') as workflow_file:
                    # SBM Better formatting.
                    # json.dump(workflow, workflow_file)
                    json.dump(workflow, workflow_file, indent = 4, ensure_ascii = False)
                    # print(f'Saved workflow to {filename}')
        except Exception as e:
            print(f'Failed to save workflow as json due to: {e}, proceeding with the remainder of saving execution')

    def save_image(self, image, flpt, vext, quality, optimise, prompt = None, extra_pnginfo = None):
        """Save image with metadata to given path.
        
        """
        img = Image.fromarray((255. * image.cpu().numpy()).clip(0, 255).astype(np.uint8))
        
        kwargs = DCOMPRESS[vext].copy()
        kwargs = {k: v(qual = quality, opt = optimise) for (k,v) in kwargs.items()}
        if vext == 'png':
            metadata = PngInfo()
            # metadata.add_text("parameters", prompt)
            # if extra_pnginfo:
            #     for k, v in extra_pnginfo.items():
            #         metadata.add_text(k, json.dumps(v))
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for (k, v) in extra_pnginfo.items():
                    metadata.add_text(k, json.dumps(v))
            img.save(flpt, pnginfo=metadata, **kwargs)
        else:
            exif_dict = {
                "Exif": {
                    piexif.ExifIFD.UserComment: piexif.helper.UserComment.dump(
                        json.dumps(extra_pnginfo.get("workflow", "")), encoding="unicode")
                },
            }
    
            # Insert EXIF metadata into the image
            exif_bytes = piexif.dump(exif_dict)
            img.save(flpt, exif = exif_bytes, **kwargs)
            piexif.insert(exif_bytes, flpt)
            
        # Only json is reliable.
        self.save_json(extra_pnginfo, os.path.splitext(flpt)[0] + ".json")
    
    # Sample exif reader.
    def read_metadata(self, flpt):
        """
        Read metadata from an image file.
    
        Args:
            flpt: Full file path to the image.
    
        Returns:
            A dictionary containing the metadata.
        """
        if flpt.lower().endswith(('.jpg', '.jpeg', '.webp')):
            # Read EXIF metadata
            exif_dict = piexif.load(flpt)
            user_comment = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment, b"")
            if user_comment:
                return json.loads(user_comment.decode("unicode_escape").strip("\x00"))
        elif flpt.lower().endswith('.png'):
            # Read PNG metadata
            img = Image.open(flpt)
            return img.text
        return None

class StringToFloatSBM:
    """
    String to float conversion.
    Fails explicitly on invalid input unless fallback is enabled.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": False,
                    "default": "0.0",
                    "tooltip": "Input string to convert (must be valid float)"
                }),
            },
            "optional": {
                "fallback_value": ("FLOAT", {
                    "default": FLOAT_ERROR,
                    "min": -6e12, # -3.4e38,
                    "max": 4e13, # 3.4e38,
                    "step": 0.0001,
                    "tooltip": "Value if string cannot be converted, -555 errs."
                }),
            },
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "convert"
    CATEGORY = "SBM Nodes"

    def convert(self, text, fallback_value=None):
        try:
            # First try direct conversion
            return (float(text),)
        except ValueError:
            # Attempt locale-aware conversion if direct fails
            try:
                cleaned = text.replace(',', '.').strip()
                return (float(cleaned),)
            except ValueError:
                if fallback_value is not None and fallback_value != FLOAT_ERROR:
                    return (fallback_value,)
                raise ValueError(f"StringToFloat: Invalid float value '{text}'")

class VideoSeriesMergerSBM:
    """
    Video Series Merger - Merges sequentially numbered videos in folder and drops last n frames.
    """
    def __init__(self):
            self.output_dir = folder_paths.get_output_directory() # folder_paths.output_directory
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["serialise", "overwrite"], {
                    "default": "serialise",
                    "tooltip": "serialise=auto-numbered (usual behaviour), overwrite=replace existing"
                    }),
                "input_pattern": ("STRING", {"default": "vid_*.mp4", "tooltip": "Video filenames pattern with * wildcard"}),
                "output_filename": ("STRING", {"default": "merged", "tooltip": "Output filename"}),
                "extension": (VID_EXTENSIONS, {"tooltip": "file extension/type to save image as"}),
                "cleanup": ("BOOLEAN", {"default": False, "tooltip": "Delete source files after merge"}),
                "skip_last_frames": ("INT", {"default": 0, "min": 0, "max": 300, "tooltip": "Skip N last frames"}),
                "fps_mode": (["autodetect", "manual"], {"default": "autodetect", "tooltip": "Frame rate handling mode"}),
                "crf": ("INT", {"default": 23, "min": 0, "max": 51, "tooltip": "Quality (0=lossless, 51=worst)"}),
                "preset": (["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], 
                          {"default": "medium", "tooltip": "Encoding speed/compression tradeoff"}),
            },
            "optional": {
                "manual_fps": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 300.0, "tooltip": "Manual FPS value"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    FUNCTION = "merge_videos"
    CATEGORY = "SBM Nodes"

    def _generate_filename(self, save_dir, prefix, vext, mode = "serialise"):
        """SBM simple serial filename. 
        
        Ignores index, Idc to preserve the order with multiple items.
        Much easier to follow single chronological trail.
        Also checks filenames all at once instead of looping till next gap,
        what a pos code.
        Mode overwrite will simply write the given filename, serialise will add a new index.
        """
        # Use glob to find all files matching the pattern
        # SBM Detect any extensions for true series.
        # pattern = os.path.join(save_dir, f"{prefix}_*.{vext}")
        base_path = join(save_dir, prefix)
        if mode == "overwrite":
            return f"{base_path}.{vext}"
        pattern = f"{base_path}_*.*"
        existing_files = glob.glob(pattern)
        
        # Extract the number between the underscore and the period
        indices = [
            os.path.splitext(os.path.basename(file))[0].split("_")[-1]
            for file in existing_files
        ]
        indices = [int(i) for i in indices if i.isdigit()]
        
        # Determine the next index
        next_index = max(indices) + 1 if indices else 1 # index
        
        # Generate the filename
        filename = f"{base_path}_{next_index}.{vext}"
        return filename

    def get_video_fps(self, video_path):
        """Extract FPS from video file using ffprobe"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            num, den = map(int, result.stdout.strip().split('/'))
            return num / den
        except Exception as e:
            print(f"Warning: Couldn't detect FPS for {video_path}, using fallback")
            return None

    def natural_sort_key(self, s):
        """Sort filenames by int assuming pattern blabla_{num}.ext ."""
        # Get the filename without path and extension
        filename = os.path.splitext(os.path.basename(s))[0]
        # Split on underscore and take the last part which should be the number
        num_part = filename.split('_')[-1]
        try:
            return int(num_part)
        except ValueError:
            return -1

    def merge_videos(self, mode, input_pattern, output_filename, extension, cleanup, skip_last_frames,
                     fps_mode, crf, preset, manual_fps=30.0):
        
        video_files = sorted(
            [f for f in glob.glob(os.path.join(self.output_dir, input_pattern)) 
             if f.lower().endswith(VID_EXTENSIONS)],
            key=self.natural_sort_key
        )
    
        if not video_files:
            raise ValueError(f"No videos found matching {input_pattern} in {self.output_dir}")
    
        # Determine FPS
        fps = None
        if fps_mode == "manual":
            fps = manual_fps
        else:
            # Try to detect FPS from first video
            fps = self.get_video_fps(video_files[0]) or manual_fps
            # print(f"Using detected FPS: {fps}")
    
        filename = self._generate_filename(self.output_dir, output_filename, extension, mode = mode)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    
        # Generate concat file with frame-accurate trimming
        concat_file = os.path.join(self.output_dir, "concat_list.txt")
        with open(concat_file, "w") as f:
            for vid in video_files:
                if skip_last_frames > 0 and fps:
                    try:
                        # Get precise duration in seconds
                        cmd = [
                            'ffprobe', '-v', 'error',
                            '-show_entries', 'format=duration',
                            '-of', 'default=noprint_wrappers=1:nokey=1',
                            vid
                        ]
                        duration = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip())
                        adjusted_duration = max(0.1, duration - (skip_last_frames / fps))
                        f.write(f"file '{os.path.abspath(vid)}'\n")
                        f.write(f"inpoint 0\n")
                        f.write(f"outpoint {adjusted_duration}\n")
                    except Exception as e:
                        print(f"Warning: Couldn't trim {vid}, using full video")
                        f.write(f"file '{os.path.abspath(vid)}'\n")
                else:
                    f.write(f"file '{os.path.abspath(vid)}'\n")
    
        # Build and execute ffmpeg command
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264',
            '-crf', str(crf),
            '-preset', preset,
            '-y', # '-y' if mode == "overwrite" else '-n',
            filename,
        ]
    
        try:
            subprocess.run(ffmpeg_cmd, check=True)
        finally:
            if os.path.exists(concat_file):
                os.remove(concat_file)
            if cleanup:
                for vid in video_files:
                    try:
                        os.remove(vid)
                    except Exception as e:
                        print(f"Warning: Couldn't delete {vid}: {e}")
    
        # Creep: Add vid preview. Not sure how vhs does it.
        return (filename,)

NODE_CLASS_MAPPINGS = {
    "ImageSaverSBM": ImageSaverSBM,
    "SortControlSBM": SortControlSBM,
    "StringToFloatSBM": StringToFloatSBM,
    "VideoSeriesMergerSBM": VideoSeriesMergerSBM,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageSaverSBM": "SBM image saver",
    "SortControlSBM": "SBM Sort Control",
    "StringToFloatSBM": "SBM Cast text to number",
    "VideoSeriesMergerSBM": "SBM Merge videos in folder",
}
