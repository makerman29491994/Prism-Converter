# Prism Converter

Private standalone app, separated from the combined Prism project. Current version: **1.3.8**. No replay-to-world functionality or resource-pack assets are included.

Convert cube-based Blockbench and Bedrock models to named Mine-imator `.mimodel` bundles. Includes textured mouse-orbit preview, automatic texture matching, independent batch exports, fractional cubes and standalone bound models. Polygon meshes are preview-only; existing animation timelines are not transferred. Native Mine-imator rendering still needs direct validation.

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

## Repository scope

Only this app's Python modules, its own logo, isolated tests, build files and license notices are tracked. Game installations, private packs, exported models/skins, account data, test output and replay code are excluded.

## Licensing and public release

No open-source license has been selected for the application's source yet. Keep the repository private until the owner chooses the licensing and completes the public-release review. Third-party code remains under its own licenses; see [notices](THIRD_PARTY_NOTICES.md). Not an official Minecraft or Mine-imator product.

Version 1.3.8 fixes standalone Windows white fields and unreadable text by selecting the clam ttk theme before creating controls. A hand-drawn About button replaces the native white menu bar, and Windows title bars use the app palette.
