# Font Sizing Fix - Summary of Changes

## Overview

Fixed inconsistent font sizing logic across all QR code generators. The universal formula is now:

```rust
effective_px = figma_fontSize_px * export_scale
```

Where coordinates, font sizes, and all dimensions are scaled uniformly by the export_scale factor.

## Files Modified

### 1. `rust/backend/src/generator/booking.rs`

**Changes:**
- Removed `PILLOW_TO_RUSTTYPE_MULTIPLIER = 1.3` constant
- Removed `pillow_size_to_rusttype()` function
- Replaced all calls from `pillow_size_to_rusttype(51.0)` with direct values like `51.0`

**Before (BROKEN):**
```rust
const PILLOW_TO_RUSTTYPE_MULTIPLIER: f32 = 1.3;
let name_px = pillow_size_to_rusttype(51.0);  // 51 * 1.3 = 66.3 (TOO LARGE)
```

**After (FIXED):**
```rust
// Frame exported at scale=1.0, Figma pixels map 1:1 to screen pixels
let name_px = 51.0;  // Scale::uniform(51) → ~51px visual size ✓
```

**Impact:**
- Name text: 51px → previously 66.3px (30% reduction)
- Confirm text: 63px → previously 81.9px (30% reduction)
- Common text: 47px → previously 61.1px (30% reduction)

---

### 2. `rust/backend/src/generator/gumtree.rs`

**Changes:**
- Removed `PILLOW_TO_RUSTTYPE_MULTIPLIER = 1.3` constant
- Removed `pillow_size_to_rusttype()` function
- Updated `text_width()` to use `Scale::uniform(px)` directly
- Updated `draw_text_with_letter_spacing()` to use `Scale::uniform(px)` directly
- Updated `draw_text_bold_with_letter_spacing()` comment

**Before (BROKEN):**
```rust
const PILLOW_TO_RUSTTYPE_MULTIPLIER: f32 = 1.3;
fn text_width(...):
    let rusttype_px = pillow_size_to_rusttype(px);  // Double scaling!
    let scale = Scale::uniform(rusttype_px);

// Usage:
let title_px = 45.0 * sf;  // 45 * 2.0 = 90
let width = text_width(..., title_px, ...);  // 90 * 1.3 = 117 (DOUBLE SCALED)
```

**After (FIXED):**
```rust
fn text_width(...):
    let scale = Scale::uniform(px);  // Single correct scale

// Usage:
let title_px = 45.0 * sf;  // 45 * 2.0 = 90
let width = text_width(..., title_px, ...);  // Scale::uniform(90) → ~45px visual ✓
```

**Impact:**
- Title text: 45px → previously 90 * 1.3 = 117px (23% reduction)
- Prices and summary: All reduced proportionally

**Reasoning:**
Frame is exported at `scale=2`. The `rel_box()` function already multiplies coordinates by `scale_factor()`. Font sizes get the same treatment: `title_px = 45.0 * sf = 45.0 * 2.0 = 90.0`. This 90 is then passed to Scale::uniform() directly - no additional conversion needed.

---

### 3. `rust/backend/src/generator/markt.rs`

**Changes:**
- Removed `text_metric_compensation()` function entirely
- Removed call to `text_metric_compensation()` in generate_markt()
- Removed all `* tc` multipliers from font size calculations
- Added explanatory comments about the correct formula

**Before (BROKEN):**
```rust
fn text_metric_compensation() -> f32 {
    std::env::var("TEXT_METRIC_COMPENSATION")
        .ok()
        .and_then(|s| s.parse::<f32>().ok())
        .unwrap_or(1.08)  // Default: 8% compensation
}

let tc = text_metric_compensation();
let price_px = 54.0 * sf * tc;  // 54 * 2.0 * 1.08 = 116.64 (TOO LARGE)
let detail_px = 49.0 * sf * tc;  // 49 * 2.0 * 1.08 = 105.84 (TOO LARGE)
let total_px = 54.0 * sf * tc;   // 54 * 2.0 * 1.08 = 116.64 (TOO LARGE)
```

**After (FIXED):**
```rust
let price_px = 54.0 * sf;  // 54 * 2.0 = 108.0 (CORRECT)
let detail_px = 49.0 * sf;  // 49 * 2.0 = 98.0 (CORRECT)
let total_px = 54.0 * sf;   // 54 * 2.0 = 108.0 (CORRECT)
```

**Impact:**
- Price text: 54px → previously 116.64px (54% reduction)
- Detail text: 49px → previously 105.84px (53% reduction)
- Total text: 54px → previously 116.64px (54% reduction)

**Reasoning:**
The 1.08 compensation factor was an ad-hoc attempt to fix text sizing. It was based on a false assumption about rusttype vs Pillow/FreeType differences. The correct approach is the universal formula: `effective_px = figma_px * scale_factor`.

---

### 4. `rust/backend/src/generator/subito.rs`

**Status: NO CHANGES NEEDED** ✓

Already uses the correct formula:
```rust
let title_px = 62.0 * sf;  // 62 * 2.0 = 124 ✓
let price_px = 62.0 * sf;  // 62 * 2.0 = 124 ✓
```

---

### 5. `rust/backend/src/generator/wallapop.rs`

**Status: NO CHANGES NEEDED** ✓

Already uses the correct formula:
```rust
let title_px = 46.0 * sf;  // 46 * 2.0 = 92 ✓
let price_px = 64.0 * sf;  // 64 * 2.0 = 128 ✓
```

---

## Comparison Table

| Generator | Export Scale | Before Formula | After Formula | Example: 50px |
|-----------|--------------|----------------|---------------|---------------|
| **Booking** | 1.0 | `px * 1.3` | `px * 1.0` | 50 → 65 → 50 |
| **Gumtree** | 2.0 | `(px * 2.0) * 1.3` | `px * 2.0` | 50 → 130 → 100 |
| **Markt** | 2.0 | `(px * 2.0) * 1.08` | `px * 2.0` | 50 → 108 → 100 |
| **Subito** | 2.0 | `px * 2.0` | `px * 2.0` | 50 → 100 → 100 |
| **Wallapop** | 2.0 | `px * 2.0` | `px * 2.0` | 50 → 100 → 100 |

## Visual Impact

### Booking Template
- **Guest name**: -30% reduction (from ~66px to 51px)
- **Confirmation heading**: -30% reduction (from ~82px to 63px)
- **Body text**: -30% reduction (from ~61px to 47px)
- **Small text (PIN/Confirm)**: -30% reduction (from ~55px to 42.5px)

### Gumtree Template
- **Title**: -23% reduction (from ~117px to 90px)
- **Price text**: Reduced proportionally
- **Summary prices**: Reduced proportionally

### Markt Template
- **Price text**: -54% reduction (from ~117px to 54px)
- **Detail text**: -53% reduction (from ~106px to 49px)
- **Total text**: -54% reduction (from ~117px to 54px)

### Subito & Wallapop
- **No changes** - These templates already rendered correctly

## Why This Fix Works

1. **Unified Logic**: Same formula applies to all generators: `effective_px = figma_px * scale_factor`

2. **Coordinate-Font Consistency**: Both coordinates and font sizes scale uniformly, maintaining visual proportions

3. **No Magic Numbers**: Removed arbitrary multipliers (1.3, 1.08) that had no mathematical basis

4. **DPI Handling**: Figma's 96 DPI CSS px maps directly to rusttype's logical pixels through the uniform scale_factor

5. **Scalability**: Works for any export_scale value (1.0, 2.0, or higher)

## Testing Recommendations

1. **Booking**: Visual comparison of name/confirm text sizes against original Figma design
2. **Gumtree**: Check title and price text are proportionally correct at 2x scale
3. **Markt**: Verify price/detail text rendering is no longer oversized
4. **Subito/Wallapop**: Regression test to ensure no changes affected output

## Code Quality Improvements

- ✓ Removed misleading function `pillow_size_to_rusttype()`
- ✓ Removed misleading constant `PILLOW_TO_RUSTTYPE_MULTIPLIER`
- ✓ Removed misleading function `text_metric_compensation()`
- ✓ Added clear comments explaining the font sizing formula
- ✓ Reduced code complexity (fewer multiplications)
- ✓ Improved maintainability (one universal formula across all generators)

## Documentation

See `FONT_SIZING_FIX.md` for detailed technical explanation of the formula and reasoning.
