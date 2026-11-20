import { SITE } from '../lib/site.js';

export async function GET() {
  const txt = `User-agent: *\nAllow: /\n\nSitemap: ${SITE.base}/sitemap.xml\n`;
  return new Response(txt, { headers: { 'Content-Type': 'text/plain' } });
}
