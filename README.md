# Comfyui-Sort-Files
Monkeypatch file sort to date modified or custom sort instead of lexicographic.

Install as standard custom node.

Overrides folder_paths.get_filename_list functions, but does it a bit late so might not override for methods which import the functions directly earlier.
There appear to be no such calls in vanilla installation or the extensions I have.

## Potential upgrades:
- Control sort method with parameters rather than DEF_SORT, DEF_REV constants. I dunno whether comfy has easy access to client side settings like webui.
I guess one way could be to create a node containing the sort methods.
- Perform the sorting client side so that it's more convenient to multiple users.

![ComfyDatesort](https://github.com/user-attachments/assets/a791d007-e6c1-45e0-9dbd-c517cb920ba5)
