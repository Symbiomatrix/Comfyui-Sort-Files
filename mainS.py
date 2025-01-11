"""
@author: SBM

Override model sort order by patching folder_paths.get_filename_list and get_filename_list_.
"""

import os
from os.path import join
import folder_paths
from folder_paths import *

comfy_path = os.path.dirname(folder_paths.__file__)

DEF_SORT = "Date Modified"
DEF_REV = True

pony = "_mpony"
flux = "fxd"
sort_criteria = {
    "Name": lambda path, name: name.lower(),
    "Date Modified": lambda path, name: os.path.getmtime(path), # path.stat().st_mtime,
    "SBM Modified": lambda *args: sbm_sortprio(*args),
}

# Prio per keywords (+folder). The scale of dmod is ~1.6*10^9.
DPRIO = {
"top": 10**9,
"test": -10**9,
}
def sbm_sortprio(path, name, **kwargs):
    """Sort by date modified + prio additive.
    
    The baseline keywords can be modified via kwargs - currently a weight factor (*1/-1 for pos/neg, 0 for disable).
    """
    skey = os.path.getmtime(path) # path.stat().st_mtime
    for (prio, vmod) in DPRIO.items():
        vmod = vmod * kwargs.get(prio, 1)
        if prio in path.__str__().lower() or prio in name.lower():
            skey = skey + vmod
    return skey

def sort_models(output_list, output_folders, sort_method = DEF_SORT, sort_order = DEF_REV):
    """Sorts models according to setting.
    
    Input: List of filenames, list of potential locations, opt sort method + order (asc/desc). 
    Output: Model names sorted by key.
    Default sort is lexicographical, mdate is by file modification date.
    """
    if len(output_list) == 0:
        return output_list 
    # if sort_method is None:
    #     sort_method = fseti("modelSortOrder")
    # Get sorting method from dictionary
    sorter = sort_criteria.get(sort_method, "Name")

    # Sort.
    # Due to how comfy handles things, we apparently need to find the corresponding folder.
    dresults = {name: sorter(join(fld, name), name)
                for name in output_list
                for fld in output_folders
                if os.path.exists(join(fld, name))}
    lresults = sorted(dresults.keys(), key = lambda k: dresults[k], reverse = sort_order)
    return lresults

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
            if out is None:
                out = new_get_filename_list_(folder_name)
                global filename_list_cache
                filename_list_cache[folder_name] = out
            cache_helper.set(folder_name, out)
            return list(out[0])
        
        # Override backup.
        Once.new_get_filename_list = new_get_filename_list
        Once.new_get_filename_list_ = new_get_filename_list_
        # Override in comfy module.
        folder_paths.get_filename_list = new_get_filename_list
        folder_paths.get_filename_list_ = new_get_filename_list_

Once()
