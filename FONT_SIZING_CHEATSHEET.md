# Font Sizing Formula - Quick Reference

## The Universal Formula

```
effective_px = figma_fontSize_px × export_scale

Examples:
- Booking (scale=1): 51px × 1.0 = 51px
- Gumtree (scale=2): 45px × 2.0 = 90px
- Markt (scale=2): 54px × 2.0 = 108px
```

## How To Apply It

### 1. Get Figma Font Size
Look at the Figma design. Example: "51px" for Booking guest name.

### 2. Find Export Scale
Check the code for the `export_scale` parameter in `figma::export_frame_as_png()`:
- `Some(1)` → scale = 1.0
- `Some(2)` → scale = 2.0
- `None` → scale = 1.0 (default)

### 3. Calculate Effective Pixel Size
```rust
let effective_px = figma_size * scale_factor();
```

### 4. Pass to Scale::uniform()
```rust
let scale = Scale::uniform(effective_px);
// Then use this scale for all rusttype operations
```

## Common Mistakes to Avoid

### ❌ WRONG: Double multiplying
```rust
let title_px = 45.0 * 2.0;  // = 90
let rusttype_px = title_px * 1.3;  // = 117 (DOUBLE SCALED!)
let scale = Scale::uniform(rusttype_px);
```

### ✓ CORRECT: Single multiplication
```rust
let title_px = 45.0 * 2.0;  // = 90
let scale = Scale::uniform(title_px);  // Use directly
```

### ❌ WRONG: Applying compensation factor
```rust
let price_px = 54.0 * sf * 1.08;  // Extra 1.08 multiplier (WRONG!)
```

### ✓ CORRECT: Just scale factor
```rust
let price_px = 54.0 * sf;  // sf = 2.0
```

## Coordinates and Dimensions

**Same rule applies to ALL spatial dimensions:**

```rust
// In rel_box() function:
let scaled_x = (figma_x - frame_x) * scale_factor();
let scaled_y = (figma_y - frame_y) * scale_factor();
let scaled_w = figma_w * scale_factor();
let scaled_h = figma_h * scale_factor();

// These scaled coordinates work with scaled font sizes
let font_px = figma_font_size * scale_factor();
```

## Why It Works

1. **Figma** uses 96 DPI (standard web)
2. **rusttype** uses logical pixels (1:1 with screen pixels)
3. **Export scale** controls both:
   - Image resolution (pixels in PNG)
   - Coordinate/size scaling (Figma units → screen pixels)
4. **Font sizing** follows the same scale
5. Result: Everything is proportionally correct

## Generator Reference

| Generator | Export | Scale Factor | Rule |
|-----------|--------|--------------|------|
| Booking | 1 | 1.0 | `size * 1.0` |
| Gumtree | 2 | 2.0 | `size * 2.0` |
| Markt | 1 (or None) | 1.0 | `size * 1.0` |
| Subito | 2 | 2.0 | `size * 2.0` |
| Wallapop | None (custom) | 2.0 | `size * 2.0` |

## Code Template

```rust
fn generate_my_template(/* ... */) -> Result<Vec<u8>, GenError> {
    // ... load frame, template, fonts ...

    let sf = scale_factor();  // 1.0 or 2.0

    // CORRECT: Multiply Figma size by scale_factor once
    let title_px = 48.0 * sf;      // Figma size × scale
    let body_px = 32.0 * sf;       // Figma size × scale
    let small_px = 24.0 * sf;      // Figma size × scale

    // Coordinates are already scaled via rel_box()
    let (x, y, w, h) = rel_box(&node, &frame_node)?;

    // Use scaled font size directly
    draw_text(&mut out, &font, title_px, x as i32, y as i32, color, text, 0.0);

    // Text width calculation
    let width = text_width(&font, title_px, text, 0.0);
    // (text_width internally uses Scale::uniform(px) directly)

    // ... rest of generation ...
}
```

## Quick Checklist

- [ ] Font size = Figma size × scale_factor
- [ ] Coordinates already scaled in rel_box()
- [ ] No additional multipliers (no 1.3, no 1.08)
- [ ] Pass scaled px directly to Scale::uniform()
- [ ] Text width/height calculations use scaled px
- [ ] Result: Proportional to Figma design

## Still Confused?

Remember: **The scale_factor applies to EVERYTHING equally.**
- Figma coordinates → multiply by scale_factor
- Figma font sizes → multiply by scale_factor
- Figma dimensions → multiply by scale_factor

That's it! No special conversions, no compensation factors, no magic numbers.
