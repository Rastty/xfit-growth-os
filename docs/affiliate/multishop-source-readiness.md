# XFIT multi-merchant readiness — source-local adapter boundary

2026-11-27. Do not fork the existing Prometheus Core exact-product matcher:
[Rastty/prometheus-growth-os exact multishop V1](https://github.com/Rastty/prometheus-growth-os/blob/8e26d12dc29e996d7485a17c7f1944e42d4a3293/lib/prometheus-exact-multishop-comparison-v1.mjs).
That module already requires two independent merchant/program identities, source-hash-bound GTIN and brand proofs, exact variant compatibility, verified destination, fresh evidence, and explicitly withholds public price and affiliate publishing authority. XFIT keeps its native writer and credentials isolated.

## Real first-source screen

The daily authorized NaMaximum feed workflow now checks checksum-valid GTIN strings (no integer conversion), explicit brand fields, global duplicate source IDs/zero-padded GTIN ambiguity, positive cent-precision price and dispatch screen. Counts are by broad existing shopping lane; not a shortlist or exact product proof. Normalized feed takes first available manufacturer/brand and EAN/GTIN fields, so this is not independent manufacturer verification. Only aggregate counts go to public logs/artifact. No raw EANs, IDs, brand names, URLs, full catalog, tracking or private data. No WP writes, affiliate clicks, or second-source access. A single merchant cannot establish any cross-shop matches.

## Merchant acquisition (no invented program access)

- **Suplementy.cz / Affial**, https://www.affial.com/suplementy/: 5% listed, 30 days, XML feed, public product-photo permission and multi-brand sport nutrition + equipment; same network as current merchant, separate program/affiliate proof required. Prioritize as candidate for exact matched items and broader supplement alternatives; actual GTIN overlap and approval UNKNOWN.
- **Fitness007.cz / eHUB**, https://ehub.cz/93a5387a-fitness007-cz : multibrand, regular content PPS 4% existing / 6% new, own SmartFuel 6% / 10%, S2S; catalog/feed availability and terms must be verified inside approved account; coupon-only promotion restricted. Candidate, not connected.
- **Sportago / Dognet**, https://www.dognet.cz/kampane/sportago-cz/: 12% for content per public terms, 30 days, XML, private-label equipment. Strong candidate for alternative products by purpose; don't pretend products from different brands are identical. Dognet 2.0 redirect links, never guess old data2/PAP schema. https://www.dognet.cz/xml-feedy/ — feed access in approved admin.

Owner action: approve XFIT for chosen program and provision authentic current feed plus program-specific exact example deeplink in encrypted site-specific secrets. Confirm CZK/VAT, image/price publication rights and permitted traffic. Never reuse NaMaximum's campaign identifier or another site's publisher identity. Once real second-source evidence exists, use existing Core matcher only for exact same variant, and separate alternative-purpose offers; obtain distinct native publish approval/readback. No fabricated feed credentials or links; no second merchant was connected by this change.
