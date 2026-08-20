
# AdvisorGurus WordPress Homepage Update Log

**Date:** 2026-04-05  
**Repository:** `advisorgurus/advisorgurus`  
**Branch:** `claude/update-advisorgurus-wordpress-MYXSq`  
**Commit:** `33e8daf`

---

## What Was Done

Updated the AdvisorGurus WordPress site with a new homepage/landing page. The `advisor-gurus/` directory (previously a broken git submodule reference with no `.gitmodules` file) was converted to regular tracked files with three new WordPress theme files.

---

## Files Created

### `advisor-gurus/page-home.php`
Custom WordPress page template (Template Name: Homepage) with these sections:

1. **Hero Section** — Full-width banner with headline, subtitle, and two CTA buttons:
   - Primary: "Get Matched Now" → `/get-matched`
   - Secondary: "How It Works" → `/how-it-works`

2. **Trust Bar** — 4 stat callouts on a blue background:
   - 5,000+ Vetted Advisors
   - 50,000+ Clients Matched
   - 98% Satisfaction Rate
   - $0 Cost to Get Matched

3. **Services Grid** — 6 service cards, each with icon, title, description, and "Learn More" link:
   - Retirement Planning → `/services/retirement-planning`
   - Wealth Management → `/services/wealth-management`
   - Estate Planning → `/services/estate-planning`
   - Tax Planning → `/services/tax-planning`
   - Insurance Planning → `/services/insurance-planning`
   - Financial Planning → `/services/financial-planning`

4. **How It Works** — 3-step horizontal flow:
   5. Tell Us Your Goals
   6. Get Matched
   7. Start Your Journey

8. **CTA Section** — Dark gradient background with a prominent amber "Find My Advisor — It's Free" button and reassurance note.

---

### `advisor-gurus/style.css`
Full theme stylesheet with:
- CSS custom properties (color palette, spacing, shadows, typography)
- Responsive design with breakpoints at 1024px, 768px, and 480px
- Hover animations on service cards (lift + shadow)
- Mobile: hero image hidden, single-column grids, stacked CTAs

**Color palette:**
| Variable | Value | Use |
|---|---|---|
| `--color-primary` | `#1a56db` | Buttons, icons, trust bar |
| `--color-secondary` | `#0f766e` | Accents |
| `--color-accent` | `#f59e0b` | Main CTA button |
| `--color-bg-dark` | `#111827` | CTA section background |

---

### `advisor-gurus/functions.php`
Theme functions file with:
- Theme supports: thumbnails, title-tag, HTML5, custom logo
- Nav menu registration: `primary` and `footer`
- Google Fonts (Inter) enqueue
- **Customizer controls** under "Homepage Hero" section:
  - Hero Image (media upload)
  - Hero Title (text)
  - Hero Subtitle (textarea)
  - CTA Button Text (text)
  - CTA Button URL (url)

---

## How to Activate

1. Upload the `advisor-gurus/` directory to `/wp-content/themes/advisor-gurus/` on the WordPress server
2. In WordPress Admin → **Appearance → Themes**, activate **AdvisorGurus**
3. Go to **Pages → Add New**, create a page called "Home"
4. Under **Page Attributes → Template**, select **Homepage**
5. In **Settings → Reading**, set "Your homepage displays" to "A static page" and select the Home page
6. Optionally customize the hero image/text via **Appearance → Customize → Homepage Hero**

---

## Git Details

