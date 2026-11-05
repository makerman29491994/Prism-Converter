# Build with: python -m PyInstaller --noconfirm app.spec
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata
from PIL import Image
root=Path(SPECPATH)
datas=[(str(root/"src"/'Converter-logo.png'),"."),(str(root/"THIRD_PARTY_LICENSES"),"THIRD_PARTY_LICENSES")]
for package in ['pillow', 'numpy']:datas+=copy_metadata(package)
# Produce the Windows executable icon from the app's own artwork.
icon=root/"build/app.ico";icon.parent.mkdir(parents=True,exist_ok=True)
with Image.open(root/"src"/'Converter-logo.png') as source:
    image=source.convert("RGBA");bounds=image.getchannel("A").point(lambda a:255 if a>128 else 0).getbbox()
    if bounds:image=image.crop(bounds)
    image.thumbnail((256,256),Image.Resampling.LANCZOS)
    square=Image.new("RGBA",(256,256));square.paste(image,((256-image.width)//2,(256-image.height)//2));square.save(icon,sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])
# NumPy's test utilities are not part of the preview renderer. Keep its full
# numerical runtime (including BLAS) and all Pillow image codecs.
a=Analysis([str(root/"src/main.py")],pathex=[str(root/"src")],datas=datas,binaries=[],hiddenimports=[],excludes=["pytest","IPython","notebook","amulet","PyMCTranslate","amulet_nbt","numpy.testing"],noarchive=False,optimize=1)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Prism Converter',console=False,icon=str(icon),upx=False)
