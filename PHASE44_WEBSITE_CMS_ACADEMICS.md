# Phase 44 — Website CMS, SEO/AEO, Hero Manager & Academic Pages

## Added
- Hero slider CRUD: image, kicker, title, description, CTA, URL, order, active/inactive.
- Homepage SEO/AEO controls: SEO title, meta description, keywords, canonical URL and organization name.
- AEO-ready academic pages with direct answer summary, FAQs and FAQPage structured data.
- `/robots.txt` and `/sitemap.xml` generated from published pages/news.
- Dedicated `/academics/elementary-school/`, `/academics/junior-school/`, `/academics/senior-school/` style routes (without the trailing slash requirement).
- Academic mega menu with image cards, zoom, large typography and responsive behavior.
- Separate admin controls for Elementary, Junior and Senior School content, subjects, curriculum, support, FAQ and SEO.
- `website_editor` role. This role is server-side restricted to website CMS operations only (plus login/logout/password change/public website access).
- Admin can create the Website Editor account from User Management.
- Demo seeder creates three hero slides, three academic pages and a website editor account.

## Demo credentials
Run:
`python seed_website_cms_demo.py`

Username: `website_editor`
Password: `Web@12345`

**Change this password immediately for production.**

## Inspiration
The academic information architecture follows the same broad pattern visible on Foundation Public School's public academics pages—separate Elementary, Junior and Senior pathways—while the visual implementation is original to Public School Gadap. citeturn1search0turn1search2turn1search1

## Validation
- Python compile/py_compile: passed.
- Jinja template parsing: passed for new/changed templates.
- ZIP integrity: to be checked after packaging.
- Full Flask/PostgreSQL runtime test was not possible in this build environment because Flask dependencies are not installed.
