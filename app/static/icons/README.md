# variant1_notes_check icon pack

Included:
- `favicon.ico` (16/32/48)
- `favicon-16x16.png`, `favicon-32x32.png`
- `apple-touch-icon.png` (180)
- `android-chrome-192x192.png`, `android-chrome-512x512.png`
- `maskable-icon-192x192.png`, `maskable-icon-512x512.png`
- Extra `icon-<size>x<size>.png` sizes: 16, 32, 48, 64, 96, 128, 144, 152, 167, 180, 192, 256, 384, 512, 1024

## Recommended links (HTML)
```html
<link rel="icon" type="image/png" sizes="32x32" href="/icons/variant1_notes_check/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/icons/variant1_notes_check/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/variant1_notes_check/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
```

## Manifest icons example
```json
{
  "icons": [
    { "src": "/icons/variant1_notes_check/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/variant1_notes_check/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icons/variant1_notes_check/maskable-icon-192x192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
    { "src": "/icons/variant1_notes_check/maskable-icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```
