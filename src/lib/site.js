import pagesData from '../data/pages.json';

export const SITE = {
  brand: 'Water Damage Restoration Midvale',
  domain: 'waterdamagerestorationmidvale.site',
  base: 'https://waterdamagerestorationmidvale.site',
  phone: '(385) 488-1110',
  tel: 'tel:+13854881110',
  city: 'Midvale',
  state: 'UT',
  zip: '84047',
  county: 'Salt Lake County',
};

export const pages = pagesData.pages;
export const bySlug = new Map(pages.map((p) => [p.slug, p]));

/** Canonical URL for a slug. Home is `...site/` (trailing slash, matching
 *  JSON-LD `url`); every other slug already ends in `/`. */
export function canonicalFor(slug) {
  return `${SITE.base}${slug === '/' ? '/' : slug}`;
}

const titleCase = (s) =>
  s.split('-').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

const CITY = {
  murray: 'Murray',
  sandy: 'Sandy',
  'cottonwood-heights': 'Cottonwood Heights',
  'west-jordan': 'West Jordan',
  taylorsville: 'Taylorsville',
  'south-jordan': 'South Jordan',
};

/** Short chrome label for a page, derived from its slug (no invented words). */
export function labelFor(page) {
  const slug = page.slug;
  if (slug === '/') return 'Home';
  if (slug === '/about/') return 'About';
  if (slug === '/contact/') return 'Contact';
  if (slug === '/service-areas/') return 'All Service Areas';
  const parts = slug.split('/').filter(Boolean);
  if (parts[0] === 'areas' && parts.length === 2) {
    return `Water Damage Restoration in ${CITY[parts[1]] ?? titleCase(parts[1])}`;
  }
  if (parts[0] === 'areas' && parts.length === 3) {
    return `${titleCase(parts[2])} in ${CITY[parts[1]] ?? titleCase(parts[1])}`;
  }
  return titleCase(parts[parts.length - 1]);
}

const at = (n) => pages[n - 1]; // tab number -> page (tabs are 1-based, in order)

/** 20 service pages, tabs 02-21, in doc order. */
export const servicePages = pages.slice(1, 21);
/** Header dropdown: first 10 service pages only. */
export const headerServices = servicePages.slice(0, 10);
/** 6 area pages, tabs 33-38. */
export const areaPages = pages.slice(32, 38);
/** 7 blog pages, tabs 25-31. */
export const blogPages = pages.slice(24, 31);
/** Guide pages: restoration process + insurance help + blogs. */
export const guidePages = [at(21), at(22), ...blogPages];
export const companyPages = [at(1), at(23), at(24)];

export const AREA_CITIES = [
  'Midvale',
  'Murray',
  'Sandy',
  'Cottonwood Heights',
  'West Jordan',
  'Taylorsville',
  'South Jordan',
];

export function plainText(segments) {
  return segments.map((s) => s.t).join('');
}

export function blockText(block) {
  if (block.type === 'p' || block.type === 'h1' || block.type === 'h2' || block.type === 'h3')
    return block.type === 'p' ? plainText(block.segments) : block.text;
  if (block.type === 'ul') return block.items.map(plainText).join(' ');
  if (block.type === 'table')
    return block.rows.map((r) => r.map(plainText).join(' ')).join(' ');
  if (block.type === 'cta') return block.buttons.map((b) => b.label).join(' ');
  return '';
}

/** FAQ pairs: H3 with faq:true + the paragraph that follows it. */
export function faqPairs(page) {
  const pairs = [];
  const blocks = page.blocks;
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (b.type === 'h3' && b.faq && blocks[i + 1]?.type === 'p') {
      pairs.push({ q: b.text, a: plainText(blocks[i + 1].segments) });
    }
  }
  return pairs;
}

function localBusiness(areaServed) {
  return {
    '@type': ['HomeAndConstructionBusiness', 'LocalBusiness'],
    name: SITE.brand,
    telephone: '+1-385-488-1110',
    url: `${SITE.base}/`,
    openingHoursSpecification: {
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
      opens: '00:00',
      closes: '23:59',
    },
    areaServed: areaServed.map((c) => ({
      '@type': 'City',
      name: c,
      addressRegion: 'UT',
      addressCountry: 'US',
    })),
  };
}

/** HowTo steps, derived ONLY from the page's own doc blocks (Fix Round 3).
 *  The doc Schema row names a HowTo on 10 tabs; the steps come from the
 *  step list already on that page — the UL under the named H2, or for
 *  /restoration-process/ the '5 Steps at a Glance' table. Returns null
 *  when no step list is found, so a HowTo is never invented. Step text
 *  is the page's own words (plainText of the list item / table row). */
function howToSteps(page) {
  const headingMatch = {
    '/burst-pipe-water-damage/': /first 5 minutes/i,
    '/emergency-water-removal/': /before our .* crew arrives/i,
    '/structural-drying/': /how we prove your home is dry/i,
    '/water-heater-leak-cleanup/': /shut it down safely/i,
    '/leak-detection/': /water meter test/i,
    '/restoration-process/': /5 steps at a glance/i,
    '/blog/prevent-frozen-pipes/': /10 steps to take before the cold snap/i,
    '/blog/what-to-do-when-a-pipe-bursts/': /7-step burst pipe checklist/i,
    '/blog/winterize-swamp-cooler/': /step-by-step swamp cooler shutdown/i,
    '/blog/spring-snowmelt-basement-flooding/': /spring prep list/i,
  }[page.slug];
  if (!headingMatch) return null;
  const blocks = page.blocks;
  const hi = blocks.findIndex((b) => b.type === 'h2' && headingMatch.test(b.text));
  if (hi < 0) return null;
  for (let j = hi + 1; j < blocks.length; j++) {
    const b = blocks[j];
    if (b.type === 'h2' || b.type === 'h1') break;
    if (b.type === 'ul') {
      return { name: blocks[hi].text, steps: b.items.map((it) => plainText(it)) };
    }
    if (b.type === 'table') {
      const rows = b.has_header === false ? b.rows : b.rows.slice(1);
      return {
        name: blocks[hi].text,
        steps: rows.map((r) => {
          const rest = r
            .slice(1)
            .map((c) => plainText(c))
            .filter(Boolean)
            .join('. ');
          return rest ? `${plainText(r[0])}: ${rest}` : plainText(r[0]);
        }),
      };
    }
  }
  return null;
}

/** DefinedTermSet for Tab 28 (Fix Round 3): terms + definitions taken
 *  from the page's own categories and classes tables — first column is
 *  the term name, the other columns (labelled by the table header) are
 *  the definition. Returns null on any other page. */
function definedTermSet(page) {
  if (page.slug !== '/blog/water-damage-categories-classes/') return null;
  const terms = [];
  for (const b of page.blocks) {
    if (b.type !== 'table') continue;
    const header = b.has_header === false ? [] : b.rows[0].map((c) => plainText(c));
    const rows = b.has_header === false ? b.rows : b.rows.slice(1);
    for (const r of rows) {
      const desc = r
        .slice(1)
        .map((c, k) => {
          const label = header[k + 1];
          const text = plainText(c);
          return label ? `${label}: ${text}` : text;
        })
        .filter(Boolean)
        .join('. ');
      terms.push({ '@type': 'DefinedTerm', name: plainText(r[0]), description: desc });
    }
  }
  return terms.length
    ? { '@type': 'DefinedTermSet', name: page.seo_title, hasDefinedTerm: terms }
    : null;
}

export function jsonLd(page) {
  const slug = page.slug;
  const canonical = canonicalFor(slug);
  const graph = [];
  const isHome = slug === '/';
  const isBlog = slug.startsWith('/blog/');
  const areaCity = slug.startsWith('/areas/')
    ? CITY[slug.split('/').filter(Boolean)[1]]
    : null;

  if (isHome) {
    const biz = localBusiness(AREA_CITIES);
    biz.areaServed[0].postalCode = '84047';
    graph.push(biz);
    const faqs = faqPairs(page);
    if (faqs.length) {
      graph.push({
        '@type': 'FAQPage',
        mainEntity: faqs.map((f) => ({
          '@type': 'Question',
          name: f.q,
          acceptedAnswer: { '@type': 'Answer', text: f.a },
        })),
      });
    }
    return { '@context': 'https://schema.org', '@graph': graph };
  }

  if (isBlog) {
    graph.push({
      '@type': 'Article',
      headline: page.seo_title,
      description: page.meta_description,
      author: { '@type': 'Organization', name: SITE.brand, url: `${SITE.base}/` },
      publisher: { '@type': 'Organization', name: SITE.brand, url: `${SITE.base}/` },
      mainEntityOfPage: canonical,
    });
  } else if (slug === '/about/') {
    graph.push({
      '@type': 'AboutPage',
      name: page.seo_title,
      description: page.meta_description,
      mainEntity: { '@type': 'Organization', name: SITE.brand, url: `${SITE.base}/` },
    });
  } else if (slug === '/contact/') {
    graph.push(localBusiness(AREA_CITIES));
    graph.push({
      '@type': 'ContactPage',
      name: page.seo_title,
      description: page.meta_description,
      mainEntityOfPage: canonical,
    });
  } else if (slug === '/service-areas/') {
    graph.push({
      '@type': 'CollectionPage',
      name: page.seo_title,
      description: page.meta_description,
      mainEntityOfPage: canonical,
    });
    graph.push(localBusiness(AREA_CITIES));
  } else {
    // Service / area-service page
    const served = areaCity ? [areaCity, ...AREA_CITIES.filter((c) => c !== areaCity)] : AREA_CITIES;
    graph.push({
      '@type': 'Service',
      name: page.seo_title,
      description: page.meta_description,
      provider: localBusiness(served),
      areaServed: served.map((c) => ({ '@type': 'City', name: c, addressRegion: 'UT', addressCountry: 'US' })),
      url: canonical,
    });
  }

  // HowTo wherever the doc Schema row names one (Fix Round 3); steps
  // come only from the page's own step list — never invented.
  if (page.schema.includes('HowTo')) {
    const how = howToSteps(page);
    if (how) {
      graph.push({
        '@type': 'HowTo',
        name: how.name,
        step: how.steps.map((s) => ({ '@type': 'HowToStep', text: s })),
      });
    }
  }
  // DefinedTermSet wherever the doc Schema row names one (Tab 28 only).
  if (page.schema.includes('DefinedTermSet')) {
    const dts = definedTermSet(page);
    if (dts) graph.push(dts);
  }
  // FAQPage wherever the doc Schema row asks for it and the page has FAQs
  if (page.schema.includes('FAQPage')) {
    const faqs = faqPairs(page);
    if (faqs.length) {
      graph.push({
        '@type': 'FAQPage',
        mainEntity: faqs.map((f) => ({
          '@type': 'Question',
          name: f.q,
          acceptedAnswer: { '@type': 'Answer', text: f.a },
        })),
      });
    }
  }
  return { '@context': 'https://schema.org', '@graph': graph };
}
