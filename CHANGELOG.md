# Changelog

## 1.5 — 2026-11-05

This release includes all changes since 1.3.12, including improvements previously committed without a new release.

### Texture matching and model appearances

- Keep separately named appearances associated with their textures when they share the same geometry.
- Follow local Bedrock render-controller geometry/texture aliases and texture arrays. Pair geometry and texture arrays that use the same selector.
- Use complete filenames and object-folder context to distinguish similarly named textures and inventory icons.
- Keep lookups inside the corresponding resource pack when a folder or ZIP contains multiple packs, including Blockbench texture references.
- Recognize complete model names with common color prefixes or suffixes in asset-only packs that omit texture-linking files.
- Automatically show one available texture in the viewer when several candidates exist. The texture selector can switch appearances, and manual choices are remembered while the pack is open.
- Report missing declared assets and unresolved layered or game-dependent appearances instead of silently substituting an unrelated texture.

### Texture sheets and rendering

- Use the first model-sized frame from recognized horizontal or vertical texture strips for static previews and exports.
- Prevent stacked frames and transparency from being stretched together, which could make solid models appear sliced apart or incomplete.
- Preserve uniform HD texture density and ordinary rectangular textures. Conversion reports identify inferred frame strips.

### Hand-drawn interface

- Retain the grayscale palette and add small pencil doodles beside the model, texture, and export-name fields.
- Give those fields distinct sketch outlines. The small cube remains hollow, with varying gray edge strokes.
- Draw scrollbar tracks, arrows, and handles in the same style. A single centered grip replaces the repeated marks that appeared on long handles.
- Replace standard dropdown arrows with pencil chevrons and remove the native boxes/bevels in normal, hovered, focused, and pressed states.
- Reduce header padding and place About in the header rather than reserving a separate top row.

### Cleaner model browser

- Show compact result labels, a result count, and a search field with Clear and Cancel controls.
- Search the full source label using multiple terms, even when result rows use shorter labels. Preserve the current selection when possible.
- Center the browser over the app and retain keyboard selection, Enter, Escape, double-click, and horizontal/vertical scrolling.
- Disable selection when a search has no results and preserve readable controls at the minimum window size.
- Remove the separate full-source details section and its extra scrollbar for a simpler browser.

### Packaging, documentation, and licensing

- Exclude unused NumPy testing utilities while retaining the numerical runtime and all Pillow image codecs.
- Add clean-build instructions and packaged-module verification to the local and manually triggered Windows build workflows.
- Expand regression coverage for texture associations, color variants, frame strips, pack isolation, browser controls, dropdown interactions, and scrollbar dragging.
- Add Apache License 2.0 and update the public licensing section to link to it; dependency and user-asset licenses remain separate.
- Refresh the README logo, feature documentation, and AI-usage disclosure.

### Previously unreleased commits

These earlier commits are included in a release for the first time, alongside the new interface changes:

- [bec1ccf](https://github.com/makerman29491994/Prism-Converter/commit/bec1ccf673934ff7a76f867f7a23d3661dcec769) — Improve resource-pack texture matching and static previews
- [fc2df2a](https://github.com/makerman29491994/Prism-Converter/commit/fc2df2a80d5df846d6dd93857364f67e1553be5e) — Reduce Converter packaging overhead and verify bundled modules
- [15dcea9](https://github.com/makerman29491994/Prism-Converter/commit/15dcea9e1a590bc07f1beaced297aa529e69e923) — Added logo image to README
- [223a95d](https://github.com/makerman29491994/Prism-Converter/commit/223a95ddb0f5274a810098e9b84c1a088cf0dada) — Added Apache License 2.0 to the project
- [978f930](https://github.com/makerman29491994/Prism-Converter/commit/978f930cf259c88828ca7b5da54f7971dc555622) — Focus documentation on current Converter features
- [fd8ab50](https://github.com/makerman29491994/Prism-Converter/commit/fd8ab50c32a796d017eada69b6aa086f60724b5c) — Documented AI usage

### Downloads and scope

Download the Windows executable and use SHA256SUMS.txt to verify it. No Python installation is required to run the executable.

Bedrock and Blockbench geometry remain supported. Cube models can be exported to Mine-imator; polygon meshes are preview-only. Java model JSON, existing animation timelines, animation playback, and full Minecraft material/runtime simulation are not converted. Texture strips use a static first frame rather than animation playback. No game models or textures are included.

[All commits since 1.3.12](https://github.com/makerman29491994/Prism-Converter/compare/v1.3.12...v1.5)
