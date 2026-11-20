import { pages } from '../lib/site.js';
import { canonicalFor } from '../lib/site.js';

// Owner order 2026-11-21 00:05 PKT: sitemap lastmod split 50/50 — the first
// half of the sitemap's URL order (22 URLs) is dated today (2026-11-21) and
// the second half (22 URLs) tomorrow (2026-11-22). Half of the dates are
// therefore tomorrow's date, per his explicit order.
const FIRST_HALF_DATE = '2026-11-21';
const SECOND_HALF_DATE = '2026-11-22';
const SPLIT_AT = 22; // 44 URLs / 2

export async function GET() {
  const urls = pages
    .map((p, i) => {
      const loc = canonicalFor(p.slug);
      const lastmod = i < SPLIT_AT ? FIRST_HALF_DATE : SECOND_HALF_DATE;
      return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${lastmod}</lastmod>\n  </url>`;
    })
    .join('\n');
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml' } });
}
