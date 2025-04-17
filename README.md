# Comfyui modded sort + image saver nodes.

## V2
Sort is now changeable through SortControl node - run it with any input then refresh. It currently has an anticaching mechanism for loras only.

Created image saver node with uniform quality support for png, webp and jpg, and a parameter for exact filename instead of the usual pattern.

## V1
Monkeypatch file sort to date modified or custom sort instead of lexicographic.

Install as standard custom node.

Overrides folder_paths.get_filename_list functions, but does it a bit late so might not override for methods which import the functions directly earlier.
There appear to be no such calls in vanilla installation or the extensions I have.

## Potential upgrades:
- (V2) Control sort method with parameters rather than DEF_SORT, DEF_REV constants. I dunno whether comfy has easy access to client side settings like webui.
I guess one way could be to create a node containing the sort methods.
- (V2) Anti caching - if sort is changeable, need to empty cache_helper whenever the method is updated (or run a refresh) in order for it to take effect.
- Perform the sorting client side so that it's more convenient to multiple users.

![ComfyDatesort](https://github.com/user-attachments/assets/a791d007-e6c1-45e0-9dbd-c517cb920ba5)

![ComfyImageOverwriter](https://github.com/user-attachments/assets/9406f3a1-0d1e-4132-8dc2-8cf129effd40)

