# Projeto Viral 2 Wet Public Storefront Implementation Plan

> **For agentic workers:** Use the existing repository and Render static-site service. Steps use checkbox syntax for tracking.

**Goal:** Publish a separate public, indexable storefront for Projeto Viral 2 Wet while preserving the private Hermes Pro Command Center.

**Architecture:** Static HTML pages in `public-site/`, deployed as a separate Render Static Site from a dedicated branch. The first product CTA uses the existing active Kiwify checkout.

**Tech Stack:** HTML5, CSS, JSON-LD, Render Static Site, GitHub.

**Spec:** `docs/superpowers/specs/2026-11-23-projeto-viral-public-site-design.md`

## Global Constraints
- Do not modify the private Command Center or its authentication.
- No secrets or private data in public files.
- Only show a purchase CTA for a confirmed active Kiwify product.
- Do not add paid services, ads or tracking.
- Keep social links limited to handles supplied by the owner.

## Review Focus
- Mobile viewport: page remains readable and CTA usable.
- Checkout destination: CTA resolves to the exact verified Kiwify URL.
- SEO: title, description, canonical URL, robots and sitemap match the deployed URL.
- Privacy: no forms or payment collection on the static site.
- Social links: no guessed Facebook page URL or unconfirmed channel.

---

### Task 1: Create public storefront pages

**Files:**
- Create: `public-site/index.html`
- Create: `public-site/sobre.html`
- Create: `public-site/privacidade.html`
- Create: `public-site/termos.html`
- Create: `public-site/robots.txt`
- Create: `public-site/sitemap.xml`

- [ ] Create responsive public landing page with the active product and verified checkout URL.
- [ ] Add About, Privacy and Terms pages; avoid unsupported legal or performance claims.
- [ ] Add only the supplied YouTube, Instagram, TikTok and Pinterest profile links.
- [ ] Add crawl instructions and sitemap using the actual Render URL after service creation.
- [ ] Verify all internal links, product CTA, metadata and mobile layout after deployment.

### Task 2: Deploy isolated static site

**Files:** Render service only; no changes to existing service configuration.

- [ ] Create a free Render Static Site from this branch with publish path `public-site`.
- [ ] Wait for the initial deploy to finish.
- [ ] Open the public URL without authentication and verify the page, links and checkout CTA.

### Task 3: Prepare Google measurement

**Files:** Update `public-site/index.html` only after the correct GA4 property is confirmed.

- [ ] Connect the intended Google account through the user-mediated setup card.
- [ ] Create/confirm a GA4 property for the public storefront.
- [ ] Add the confirmed Google tag ID and verify Realtime traffic.
- [ ] Add the URL-prefix property to Search Console and complete ownership verification.
- [ ] Submit the deployed sitemap.
