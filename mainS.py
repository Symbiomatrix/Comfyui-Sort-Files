"""
@author: SBM

Override model sort order by patching folder_paths.get_filename_list and get_filename_list_.
"""

import folder_paths
from folder_paths import *
#from .sbmnodes import * # My nodes. I don't like wildcard imports.
from .sbmsharedS import Store_Settings, sort_models
from .sbmnodesS import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
import os
join = os.path.join

comfy_path = os.path.dirname(folder_paths.__file__)

### Sort override.

class Once():
    """Calls main function once regardless of reimports."""
    called = False
    def __init__(self):
        if Once.called:
            return
        
        self.patch_sort() 
        
        Once.called = True
        
    def patch_sort(self):
        
        # Backup.
        Once.orig_get_filename_list = get_filename_list
        Once.orig_get_filename_list_ = get_filename_list_
        
        # SBM Call new sort and inner functions.
        def new_get_filename_list_(folder_name: str) -> tuple[list[str], dict[str, float], float]:
            folder_name = map_legacy(folder_name)
            global folder_names_and_paths
            output_list = set()
            folders = folder_names_and_paths[folder_name]
            output_folders = {}
            for x in folders[0]:
                files, folders_all = recursive_search(x, excluded_dir_names=[".git"])
                output_list.update(filter_files_extensions(files, folders[1]))
                output_folders = {**output_folders, **folders_all}
        
            # SBM Changed sort to custom.
            sorted_output = sort_models(output_list, output_folders)
            return sorted_output, output_folders, time.perf_counter()
            # return sorted(list(output_list)), output_folders, time.perf_counter()
        
        def new_get_filename_list(folder_name: str) -> list[str]:
            folder_name = map_legacy(folder_name)
            out = cached_filename_list_(folder_name)
            if (out is None
            or  Store_Settings.ANTICACHE.get(folder_name, True)): # SBM Anticacher node.
                out = new_get_filename_list_(folder_name)
                global filename_list_cache
                filename_list_cache[folder_name] = out
                Store_Settings.ANTICACHE[folder_name] = False # Alt: Delete from filename_list_cache directly.
            cache_helper.set(folder_name, out)
            return list(out[0])
        
        # Override backup.
        Once.new_get_filename_list = new_get_filename_list
        Once.new_get_filename_list_ = new_get_filename_list_
        # Override in comfy module.
        folder_paths.get_filename_list = new_get_filename_list
        folder_paths.get_filename_list_ = new_get_filename_list_

Once()
