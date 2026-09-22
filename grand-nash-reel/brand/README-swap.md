# Swapping brand details

Everything customer-facing lives in `brand/brand.json`. Nothing else needs editing.

- **Phone / website** -> `phone`, `website`. They appear only on the end card.
- **CTA line** -> `cta`.
- **Logo** -> drop the file in `assets/logo/` and point `logo.path` at it.
  If it has transparency, set `logo.has_alpha: true` and the card stops
  matching its background to the logo's. Adjust `logo.width_px` to resize.
- **Colours** -> `palette`. The amber accent drives the end card's rule and CTA.

Per-ad copy (captions, voiceover, end-card headline) lives in that ad's
`ads/<id>/spec.json`, not here, so two ads can share a brand and differ in script.
