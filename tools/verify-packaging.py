"""Exercise modules extracted from an actual one-file build without site-packages.

Usage: python tools/verify-packaging.py APP_ROOT EXE
Requires the same Python minor version as the build and PyInstaller.
The normal fixture checks still supply their own test-only stdlib dependencies.
"""
import importlib.util
import marshal
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader


def verify(app_root, executable):
    app_root = Path(app_root).resolve()
    executable = Path(executable).resolve()
    with tempfile.TemporaryDirectory(prefix="packaging-", dir=app_root / "work") as temporary:
        extracted = Path(temporary)
        archive = CArchiveReader(str(executable))
        for name, entry in archive.toc.items():
            if entry[-1] not in ("b", "x", "z"):
                continue
            target = extracted / name
            if not target.resolve().is_relative_to(extracted):
                raise ValueError(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extract(name))
        pyz = ZlibArchiveReader(str(extracted / "PYZ.pyz"))
        for name, entry in pyz.toc.items():
            if entry[0] not in (0, 1):
                continue
            target = extracted.joinpath(*name.split("."))
            target = target / "__init__.pyc" if entry[0] == 1 else target.with_suffix(".pyc")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(importlib.util.MAGIC_NUMBER + bytes(12) + marshal.dumps(pyz.extract(name)))
        # Isolated Python cannot import installed Pillow/NumPy/cryptography. The
        # path guard also prevents fixture scripts from importing app source.
        runner = extracted / "verify.py"
        runner.write_text('''
import os, sys
from pathlib import Path
bundle = Path(sys.argv[1]).resolve()
test = Path(sys.argv[2]).resolve()
class BundlePath(list):
    def insert(self, index, value):
        if Path(value).resolve() == Path("src").resolve():
            return
        super().insert(index, value)
sys.path = BundlePath([str(bundle), str(bundle / "base_library.zip")] + sys.path)
sys._MEIPASS = str(bundle)
handles = [os.add_dll_directory(str(path)) for path in (bundle, bundle / "numpy.libs") if path.is_dir()]
os.environ["TCL_LIBRARY"] = str(bundle / "_tcl_data")
os.environ["TK_LIBRARY"] = str(bundle / "_tk_data")
exec(compile(test.read_bytes(), str(test), "exec"), {"__name__": "__main__", "__file__": str(test)})
for name, module in list(sys.modules.items()):
    if name.startswith(("Prism", "PIL", "numpy", "cryptography")):
        location = getattr(module, "__file__", None)
        if location:
            assert Path(location).resolve().is_relative_to(bundle), (name, location)
''', encoding="utf-8")
        for test in sorted((app_root / "tools").glob("Check-*.py")):
            print("Packaged fixture:", test.name, flush=True)
            subprocess.run([sys.executable, "-I", "-S", str(runner), str(extracted), str(test)], cwd=app_root, check=True)
    print("Packaged fixtures passed:", executable, flush=True)


if __name__ == "__main__":
    verify(*sys.argv[1:])
