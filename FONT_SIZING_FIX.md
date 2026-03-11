# Font Sizing Fix - Universal Schema

## Problem Analysis

The font sizing logic had inconsistent multipliers across different generators, causing text to render 30% larger than intended.

### Issues Found

1. **Booking** (CRITICAL):
   - Used `scale=1` export but applied `PILLOW_TO_RUSTTYPE_MULTIPLIER (1.3)` to font sizes
   - Result: 51px Figma → `51 * 1.3 = 66.3` in Scale::uniform() → **30% too large**
   - Export: `figma::export_frame_as_png(http, node_id, Some(1))`

2. **Gumtree**:
   - Coordinates scaled by `scale_factor=2.0` via `rel_box()`
   - Font sizes passed directly to `pillow_size_to_rusttype()` → `px * 1.3`
   - Then used in Scale::uniform()
   - Result: Double scaling - coordinates already at 2x, font sizes got additional 1.3x multiplier

3. **Markt**:
   - Applied environmental variable `TEXT_METRIC_COMPENSATION = 1.08` to all font sizes
   - Added unnecessary compensation factor beyond scale_factor

4. **Subito & Wallapop**:
   - Already correct - used `scale_factor * figma_size` directly without extra multipliers

## Correct Formula

```
effective_px = figma_fontSize_px * export_scale

Where:
- figma_fontSize_px: Font size from Figma (in CSS px at 96 DPI)
- export_scale: Scale at which frame is exported (1.0 or 2.0)
- effective_px: Value passed to Scale::uniform()

Coordinates follow the same rule:
- frame_coordinate_px: Coordinate from Figma
- effective_coordinate = frame_coordinate_px * export_scale
```

### Why This Works

1. **Figma Design**: Specifies fontSize in CSS px (assuming 96 DPI standard web resolution)
2. **Export Scale**: Controls both image resolution AND coordinate/size scaling
   - `scale=1`: 1 Figma pixel = 1 exported pixel
   - `scale=2`: 1 Figma pixel = 2 exported pixels
3. **rusttype Scale::uniform()**: Takes the final effective pixel size for rendering

## Changes Made

### 1. Booking (booking.rs)

**Before:**
```rust
const PILLOW_TO_RUSTTYPE_MULTIPLIER: f32 = 1.3;

fn pillow_size_to_rusttype(pillow_px: f32) -> f32 {
    pillow_px * PILLOW_TO_RUSTTYPE_MULTIPLIER
}

let name_px = pillow_size_to_rusttype(51.0);  // 51 * 1.3 = 66.3
```

**After:**
```rust
// Frame exported at scale=1.0 (coordinates preserved 1:1)
// Figma fontSize is used directly
let name_px = 51.0;
let confirm_px = 63.0;
let common_px = 47.0;
let confirm_small_px = 42.5;
```

**Reasoning**: Booking template is exported at `scale=1`, so Figma pixels map directly to screen pixels without scaling.

### 2. Gumtree (gumtree.rs)

**Before:**
```rust
const PILLOW_TO_RUSTTYPE_MULTIPLIER: f32 = 1.3;

fn text_width(font, px, text, spacing):
    let rusttype_px = pillow_size_to_rusttype(px);  // px * 1.3
    let scale = Scale::uniform(rusttype_px);
```

**After:**
```rust
// Frame exported at scale=2.0
// Coordinates already scaled via rel_box(): coord * 2.0
// Font sizes also scaled: fontSize * 2.0
// NO additional conversion needed
fn text_width(font, px, text, spacing):
    let scale = Scale::uniform(px);  // px already = figma_px * 2.0
```

**Reasoning**: `rel_box()` already multiplies coordinates by `scale_factor()=2.0`. Font sizes get the same treatment: `title_px = 45.0 * sf` means `45.0 * 2.0 = 90.0`, which is then used directly in Scale::uniform(90).

### 3. Markt (markt.rs)

**Before:**
```rust
fn text_metric_compensation() -> f32 {
    std::env::var("TEXT_METRIC_COMPENSATION").unwrap_or(1.08)
}

let price_px = 54.0 * sf * tc;  // 54 * 2.0 * 1.08 = 116.64
```

**After:**
```rust
// Removed text_metric_compensation() entirely
let price_px = 54.0 * sf;  // 54 * 2.0 = 108.0
```

**Reasoning**: The compensation factor was an incorrect attempt to fix the symptom. The correct formula is simple multiplication by scale_factor.

### 4. Subito & Wallapop

**No changes needed** - these already follow the correct formula.

## Verification

### Test Case 1: Booking with scale=1
```
Figma: font size 51px
Export scale: 1.0
effective_px = 51 * 1.0 = 51
Result: Scale::uniform(51) → text renders at ~51px visual size ✓
```

### Test Case 2: Gumtree with scale=2
```
Figma: font size 45px
Export scale: 2.0
effective_px = 45 * 2.0 = 90
Coordinates: x=100 → x_effective = 100 * 2.0 = 200
Result: Scale::uniform(90) at pixel 200 → text renders at ~45px visual size ✓
```

### Test Case 3: Markt with scale=2
```
Figma: font size 54px
Export scale: 2.0
effective_px = 54 * 2.0 = 108
Result: Scale::uniform(108) → text renders at ~54px visual size ✓
```

## DPI Considerations

Figma uses 96 DPI (standard web resolution). rusttype's `Scale::uniform()` uses logical pixels that map 1:1 to screen pixels. The conversion between Figma CSS pixels and rusttype logical pixels is handled implicitly by the scale_factor applied to both coordinates and font sizes. No explicit DPI conversion is needed.

## Summary

| Generator | Export Scale | Before | After | Formula |
|-----------|--------------|--------|-------|---------|
| Booking   | 1.0          | px*1.3 | px    | figma_px * 1.0 |
| Gumtree   | 2.0          | px*1.3*2.0 | px*2.0 | figma_px * 2.0 |
| Markt     | 2.0          | px*2.0*1.08 | px*2.0 | figma_px * 2.0 |
| Subito    | 2.0          | px*2.0 | px*2.0 | figma_px * 2.0 |
| Wallapop  | 2.0          | px*2.0 | px*2.0 | figma_px * 2.0 |

All generators now follow: **effective_px = figma_fontSize_px * export_scale**
