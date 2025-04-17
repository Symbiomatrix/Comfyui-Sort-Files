"""
@author: SBM

Nodes I need and nobody did proper.

Changelog:
15/03/2025 Init - image saver.
01/04/2025 Added file sort node.
17/04/2025 Added file overwrite parm.
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
                "filename": ("STRING", {"default": "", "multiline": False,  # NEW PARAMETER
                                       "tooltip": "exact filename to use (overrides flprefix if specified)"}),
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

    def _generate_filename(self, save_dir, prefix, vext):
        """SBM simple serial filename. 
        
        Ignores index, Idc to preserve the order with multiple items.
        Much easier to follow single chronological trail.
        Also checks filenames all at once instead of looping till next gap,
        what a pos code.
        """
        # Use glob to find all files matching the pattern
        # SBM Detect any extensions for true series.
        # pattern = os.path.join(save_dir, f"{prefix}_*.{vext}")
        pattern = os.path.join(save_dir, f"{prefix}_*.*")
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
        filename = os.path.join(save_dir, f"{prefix}_{next_index}.{vext}")
        return filename

    def save_files(
        self,
        images,
        filename,
        flprefix,
        extension,
        quality,
        optimise,
        prompt=None,
        extra_pnginfo=None,
    ):
        results = []
        for image in images:
            if filename: # Constant, not auto incremented. Useful for self updating input.
                filename = os.path.join(self.output_dir, f"{filename}.{extension}")
            else:
                filename = self._generate_filename(self.output_dir, flprefix, extension)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            subfolder = os.path.normpath(os.path.dirname(filename))
            self.save_image(image, filename, extension, quality, optimise, prompt, extra_pnginfo)
            results.append({
                "filename": filename,
                "subfolder": subfolder,
                "type": "output",
            })
        
        return { "ui": { "images": results } }

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

NODE_CLASS_MAPPINGS = {
    "ImageSaverSBM": ImageSaverSBM,
    "SortControlSBM": SortControlSBM,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageSaverSBM": "SBM image saver",
    "SortControlSBM": "SBM Sort Control",
}
