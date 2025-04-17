"""
Created on 01/04/2025

@author: SBM

Changelog:
01/04/2025 Separated sort, shared storage from main / sbmnodes.
"""

import os
join = os.path.join 

### Storage module.
class Store_Settings():
    DEF_SORT = "Name" # File sort order.
    DEF_REV = False # Sort in reverse.
    ANTICACHE = dict() # When flagged, will force refresh select lists (override handled in main). 

### Sort module.
# Will search in either orig or lcase - so using lcase will find either, any ucase only in orig.
xl = "XL"
pony = "_mpony"
flux = "FXD"
hyvid = "HY"
wan = "_mwan"
wan13 = "_mwan13"
SORT_CRITERIA = {
    "Name": lambda path, name: name.lower(),
    "Date Modified": lambda path, name: os.path.getmtime(path), # path.stat().st_mtime,
    "SBM Modified": lambda *args: sbm_sortprio(*args),
}
# lsortset = list(sort_criteria.keys()) # Might want to use an sorted dict.
# fseti = lambda x: shared.opts.data.get(EXTKEY + "_" + x, DEXTSETV[x])

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
        if (prio in path.__str__().lower() or prio in name.lower() # Lcase match.
        or  prio in path.__str__() or prio in name): # Exact match.
            skey = skey + vmod
    return skey

def sort_models(output_list, output_folders, sort_method = None, sort_order = None):
    """Sorts models according to setting.
    
    Input: List of filenames, list of potential locations, opt sort method + order (asc/desc). 
    Output: Model names sorted by key.
    Default sort is lexicographical, mdate is by file modification date.
    """
    if sort_method is None:
        sort_method = Store_Settings.DEF_SORT
    if sort_order is None:
        sort_order = Store_Settings.DEF_REV
    if len(output_list) == 0:
        return output_list 
    # if sort_method is None:
    #     sort_method = fseti("modelSortOrder")
    # Get sorting method from dictionary
    sorter = SORT_CRITERIA.get(sort_method, "Name")

    # Sort.
    # Due to how comfy handles things, we apparently need to find the corresponding folder.
    dresults = {name: sorter(join(fld, name), name)
                for name in output_list
                for fld in output_folders
                if os.path.exists(join(fld, name))}
    lresults = sorted(dresults.keys(), key = lambda k: dresults[k], reverse = sort_order)
    return lresults
