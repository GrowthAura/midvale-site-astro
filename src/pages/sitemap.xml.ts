import { pages } from '../lib/site.js';
import { canonicalFor } from '../lib/site.js';

const DATE = '2026-11-20';

export async function GET() {
  const urls = pages
    .map((p) => {
      const loc = canonicalFor(p.slug);
      return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${DATE}</lastmod>\n  </url>`;
    })
    .join('\n');
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml' } });
}
