import { pages } from '../lib/site.js';
import { canonicalFor } from '../lib/site.js';

// Owner order 2026-11-21 03:26 PKT: sitemap lastmod split — the first
// half of the sitemap's URL order (22 URLs) is dated yesterday
// (2026-11-20, guzra hua kal) and the second half (22 URLs) today
// (2026-11-21, aj). Same yesterday+today convention as Lake Oswego.
const FIRST_HALF_DATE = '2026-11-20';
const SECOND_HALF_DATE = '2026-11-21';
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
