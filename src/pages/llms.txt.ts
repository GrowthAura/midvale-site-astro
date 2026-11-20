import { pages, SITE } from '../lib/site.js';
import { canonicalFor } from '../lib/site.js';

export async function GET() {
  const lines = [
    `# ${SITE.brand}`,
    `# ${SITE.base}`,
    `# Water damage restoration in Midvale, Utah. Open 24/7. Call ${SITE.phone}.`,
    '',
  ];
  for (const p of pages) {
    lines.push(`- [${p.seo_title}](${canonicalFor(p.slug)})`);
  }
  return new Response(lines.join('\n') + '\n', {
    headers: { 'Content-Type': 'text/plain' },
  });
}
