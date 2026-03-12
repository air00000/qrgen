# Font Rendering vs Figma Parity — Research (branch: `research`)

## Context
Goal: understand why text rendered in backend generators (Rust/raster stack) differs from Figma even with the same nominal `font-size`, and define a practical universal approach for near-identical screenshots.

## Why sizes differ in practice (root causes)

1. **Different text engines and rasterizers**
   - Figma-side preview is tied to browser/Skia-like rendering behavior.
   - Backend stack (`rusttype`, `image`, custom layout) uses another raster path.
   - Same `font-size` does **not** guarantee identical glyph bitmaps/advances.

2. **Hinting / grid fitting differences**
   - FreeType docs: hinting can change glyph width/height and advances at small px sizes.
   - This can visibly shift line wraps and right-aligned blocks.

3. **AA mode + compositing path**
   - Subpixel vs grayscale AA, gamma, blend math (premultiplied vs straight alpha) changes perceived thickness and bounds.

4. **Font metrics source mismatch**
   - Different engines may derive line metrics from different tables (`OS/2`, `hhea`, etc.).
   - Baseline-to-baseline distance and vertical alignment drift.

5. **Line-height semantics mismatch**
   - CSS/UA `normal` is implementation-dependent (MDN, usually around 1.2).
   - If one side uses fixed px and another side uses heuristic multiplier, lines diverge.

6. **Letter spacing / kerning / OpenType features**
   - Spacing policy (between glyphs or grapheme clusters), kerning, ligatures, and features (`kern`, `liga`, etc.) affect final width.

7. **Shaping support gap**
   - `rusttype` docs explicitly note missing support areas (e.g., no ligatures, no hinting support in crate notes).
   - This is enough to produce non-trivial mismatch on real multilingual strings.

8. **DPI / scale / fractional coordinates**
   - Different DPR and fractional placement yield different rounding and wraps.

9. **Variable fonts / wrong font binary**
   - Same family name with different file version/axes (`wght`, `opsz`, etc.) changes metrics significantly.

---

## Observed project-level risk points for `qrgen`

- Historic usage of ad-hoc conversion multipliers (e.g., `1.3`) can hide root causes and break consistency across templates.
- Different generators had different size formulas (`scale_factor`, compensation multipliers), causing cross-template inconsistency.
- Wrap logic and line-height logic were partially heuristic-driven, likely diverging from Figma behavior for long strings/multilingual text.

---

## Universal strategy (recommended)

### Principle
No single “magic multiplier” can provide stable parity. Use a **tiered rendering strategy** with strict environment pinning.

### Tier A (default, fast, controlled)
- Rust-native pipeline with modern shaping-aware stack for text (prefer `cosmic-text + swash`-class approach over bare `rusttype` rendering for complex text).
- Unified line metrics policy and spacing semantics across all generators.
- Deterministic color/alpha compositing path.

### Tier B (high-fidelity templates)
- Skia-based backend (`skia-safe`) for templates requiring closer visual fidelity.

### Tier C (escape hatch for hardest cases)
- Headless Chromium screenshot rendering for complex layout/effects where strict Figma-like behavior is required.

This gives speed by default, fidelity when needed.

---

## Implementation plan

### Phase 0 — Quick wins (1–2 weeks)
1. **Single typography policy module** for all generators:
   - px formula,
   - line-height calculation,
   - letter-spacing policy,
   - wrapping policy.
2. **Pin fonts by exact file hash/version** in repo or artifact store.
3. **Disable hidden compensations** (`metric_compensation`, per-generator multipliers).
4. **Golden visual tests** vs approved references.

### Phase 1 — Reliability (2–4 weeks)
1. Add shaping-aware rendering path for multilingual text.
2. Add render profiles:
   - `fast`
   - `balanced`
   - `figma-close`
3. Add automatic per-template diff gates (pixel diff + text bbox diff + baseline diff).

### Phase 2 — Fidelity (4+ weeks)
1. Integrate Skia backend for marked templates.
2. Add Chromium fallback for unsupported/complex templates.
3. Introduce routing by capability matrix and SLA (latency vs fidelity budget).

---

## Validation checklist (must-have)

For each template and language:
- [ ] same font files (hash match) on all environments
- [ ] same explicit line-height policy
- [ ] same letter-spacing policy and kerning toggle
- [ ] no fractional coordinate drift where avoidable
- [ ] render at x2 and downsample test
- [ ] compare with reference using thresholds:
  - pixel diff %
  - text block bbox delta (px)
  - baseline delta (px)

Suggested acceptance targets:
- normal templates: <= 1.0% pixel diff
- figma-close templates: <= 0.3–0.5% pixel diff
- baseline drift: <= 1 px

---

## Notes on tooling during this research
- `ollama_web_search` was unavailable in this runtime due missing auth key (`~/.ollama/id_ed25519`).
- Research used direct web sources + multi-agent synthesis.

---

## Sources
- RustType crate docs: https://docs.rs/rusttype/latest/rusttype/
- FreeType glyph metrics/hinting notes: https://freetype.org/freetype2/docs/glyphs/glyphs-3.html
- MDN `line-height`: https://developer.mozilla.org/en-US/docs/Web/CSS/line-height
- MDN `letter-spacing`: https://developer.mozilla.org/en-US/docs/Web/CSS/letter-spacing
