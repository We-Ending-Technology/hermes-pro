# Projeto Viral 2 Wet — Public Storefront Design

## Intent
Create a public, indexable storefront for Projeto Viral 2 Wet without exposing the private Hermes Pro Command Center. The first offer is the already-active Kiwify product “Gestão Inteligente de Estoque”.

## Goals
- Publish a responsive public website with clear brand identity and social destinations.
- Present only products with a confirmed active checkout.
- Send purchases to the existing Kiwify checkout; never collect payment data on this site.
- Include basic SEO metadata, structured product data, sitemap and robots instructions.
- Keep the private Hermes Pro Command Center unchanged and separate.

## Non-goals
- Do not expose admin APIs, Hermes API keys, Supabase credentials or private dashboards.
- Do not claim sales, rankings, audience size, guaranteed outcomes or AdSense approval.
- Do not list draft offers as purchasable.
- Do not add paid tracking, ads, AI video generation or analytics until their accounts and cost permissions are confirmed.

## Approaches
1. Add public pages to the existing authenticated Command Center: rejected because its root route is intentionally private and not indexable.
2. Build a separate static site in the existing repository and Render workspace: selected because it isolates public SEO pages from the private dashboard, has no new database dependency and uses the existing free static hosting.
3. Move the brand to a new CMS: rejected for now because it adds account and maintenance complexity without improving the immediate launch path.

## Chosen architecture
A separate static site built from `public-site/` on Render. Product checkout remains on Kiwify. The first public product card points to the verified Kiwify checkout for “Gestão Inteligente de Estoque” at R$ 29,90. Analytics and Search Console will be attached only after the correct Google account is connected and the public URL is known.

## Operational constraints
- Keep the Hermes Command Center private.
- No paid ads, paid video generation, paid APIs, or paid hosting changes.
- Only the already-active Kiwify product may appear with a purchase CTA.
- New channel/account creation remains subject to platform verification and user-mediated OAuth/2FA where required.
