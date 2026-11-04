# Prism Converter

One small step for models, One giant leap for animators

Windows app for converting Blockbench and Bedrock models to Mine-imator. Current version: **1.3.12**.

Convert cube-based Blockbench and Bedrock models to named Mine-imator `.mimodel` bundles. Includes textured mouse-orbit preview, automatic texture matching, independent batch exports, fractional cubes and standalone bound models. Polygon meshes are preview-only; existing animation timelines are not transferred. Native Mine-imator rendering still needs direct validation.

## Features

- Export named `.mimodel` bundles with their textures.
- Preview textured cubes and polygon meshes with mouse rotation.
- Match textures using resource-pack references, model names and Blockbench texture paths.
- Export a folder or ZIP of models as separate bundles.
- Search model lists and view complete source paths.
- Convert fractional cube sizes and reversed cube bounds.

Polygon meshes are preview-only. Export supports cube geometry; animate the exported parts in Mine-imator.

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
python -m PyInstaller --noconfirm app.spec
```

The executable is written to `dist/Prism Converter.exe`. Alternatively, run **Build Windows app** manually from GitHub Actions; it uploads a downloadable build artifact and does not publish a release automatically.

## Licensing and public release

This repository is public. No open-source license has been selected for the application's source; public visibility does not grant a license to reuse or redistribute it. Third-party code remains under its own licenses; see [notices](THIRD_PARTY_NOTICES.md). Not an official Minecraft or Mine-imator product.

## AI Usage
Ai was used as the main programmer for this project. I don't really know how to code :( 
