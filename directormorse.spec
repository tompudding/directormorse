# -*- mode: python -*-
import PyInstaller

block_cipher = None


a = Analysis(
    ["directormorse.py"],
    pathex=["/home/pudding/Projects/ludum_dare_entries/directormorse"],
    binaries=None,
    datas=[
        ("*.png", "."),
        ("*.txt", "."),
        ("*.wav", "."),
        ("*.ogg", "."),
        # ("/usr/lib/x86_64-linux-gnu/libportaudio.so.2", "."),
        # ("/usr/lib/x86_64-linux-gnu/libjack.so.0", "."),
        # ("/usr/lib/x86_64-linux-gnu/libstdc++.so.6", "."),
    ],
    hiddenimports=PyInstaller.utils.hooks.collect_submodules("pkg_resources"),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
# image_tree = Tree("/src/dinosmustdie/", prefix="resource")
shader_tree = Tree("drawing", prefix="drawing")
resource = Tree("resource", prefix="resource")
# a.datas += image_tree
a.datas += shader_tree
a.datas += resource

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="director_morse",
    debug=False,
    strip=False,
    upx=True,
    console=True,
    exclude_binaries=0,
)
