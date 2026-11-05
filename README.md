<img width="1350" height="1165" alt="Converter-logo" src="https://github.com/user-attachments/assets/f4c867ef-a474-46be-9b6d-a9d37da16e77" />

# Prism Converter

One small step for models, One giant leap for animators

Windows app for converting Blockbench and Bedrock models to Mine-imator. Current version: **1.3.17**.

Convert cube-based Blockbench and Bedrock models to named Mine-imator `.mimodel` bundles. Includes textured mouse-orbit preview, automatic texture matching, independent batch exports, fractional cubes and standalone bound models. Polygon meshes are preview-only; existing animation timelines are not transferred. Native Mine-imator rendering still needs direct validation.

## Features

- Export named `.mimodel` bundles with their textures.
- Preview textured cubes and polygon meshes with mouse rotation.
- Match textures using resource-pack references, model names and Blockbench texture paths.
- Export a folder or ZIP of models as separate bundles.
- Search model lists and view complete source paths.
- Convert fractional cube sizes and reversed cube bounds.

Polygon meshes are preview-only. Export supports cube geometry; animate the exported parts in Mine-imator.

## Texture matching and previews

Texture matching follows resource-pack texture references, render-controller aliases and arrays, complete model names, and folder context. Shared geometry retains separate named appearances. Folder and ZIP lookups keep each pack's textures together, including Blockbench references.

When several textures fit a model, the preview selects one automatically. Use the texture selector to switch appearances; manual selections are remembered while the pack is open. Asset-only packs can match recognized color prefixes and suffixes even when texture-linking files are absent.

Horizontal and vertical texture strips use the first model-sized frame for static previews and exports, preserving HD density and rectangular textures. Conversion reports identify inferred frame strips. Missing declared assets still require the complete pack or a manually selected texture.

Supported geometry is Bedrock and Blockbench. Java model JSON, animation playback and full Minecraft material/runtime simulation are not supported. Complex texture layers or game-dependent states may require a manual texture selection for a simplified preview.

## Run from source (Windows)

Use Python 3.12 with Tkinter installed (the standard python.org Windows installer includes it).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src/main.py
```

## Test

From the repository root:

```powershell
python tools/check-startup.py
python tools/check.py
```

Tests use generated temporary fixtures. They do not modify a real Minecraft installation.

## Build a Windows executable

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean app.spec
python tools/verify-packaging.py . "dist/Prism Converter.exe"
```

The executable is written to `dist/Prism Converter.exe`. Alternatively, run **Build Windows app** manually from GitHub Actions; it uploads a downloadable build artifact and does not publish a release automatically.

The build excludes NumPy's development test utilities while retaining its numerical runtime and all Pillow image codecs. Packaging verification runs the fixture suite against modules extracted from the executable, with installed third-party packages and application source imports disabled.

## Licensing and public release

The application source is licensed under the [Apache License 2.0](LICENSE). Third-party dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). User-provided models and textures remain subject to their respective licenses. This is not an official Minecraft or Mine-imator product.

## AI Usage
Ai was used as the main programmer for this project. I don't really know how to code :(
