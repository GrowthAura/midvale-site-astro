#!/usr/bin/env python3
"""
Parse the Midvale Google Doc export (doc-raw.json) into src/data/pages.json.

Source of truth: ~/workspace/midvale-site-new/doc-raw.json (44 tabs).
The doc contains ZERO real hyperlink objects (textRun.link) — all 597 links
are plain-text parenthetical annotations of the form " (/some-slug/)".
Anchor spans are therefore derived by rule (see anchor_for() and BUILD-NOTES.md).

Output per tab:
  tab, slug, seo_title, meta_description, schema (raw string),
  blocks: ordered PAGE COPY blocks after the "PAGE COPY" line:
    h1 | h2 | h3 (text, faq flag when under an FAQ H2)
    p  (segments: [{t: text} | {t: anchor, href}] )
    ul (items: same segment lists)
    table (rows: list of cells; first row is the header; cells are segment lists)
    cta (buttons: [{label, href} | {label, tel}])
  word counts: total_words (extract.py-compatible, incl. SEO table),
               copy_words (PAGE COPY words, annotations/brackets stripped),
               link_annotations (raw count incl. dropped dup/self),
               body_links (kept links), dropped (log of dup/self drops)

Verification targets (from extracted.txt / extract.py):
  total words 40,699 | H1 44 | H2 338 | H3 391 | link annotations 597
  Tab 01 total 1425 words.
"""
import json, re, sys, os
from collections import Counter

SRC = os.path.expanduser('~/workspace/midvale-site-new/doc-raw.json')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'data', 'pages.json')

# Route list from the build order (cross-checked against the doc SEO table slugs).
ROUTES = [
    '/', '/burst-pipe-water-damage/', '/emergency-water-removal/',
    '/swamp-cooler-water-damage/', '/ice-dam-water-damage/', '/structural-drying/',
    '/basement-flooding-cleanup/', '/window-well-flooding/', '/sewage-cleanup/',
    '/mold-remediation/', '/flood-damage-restoration/', '/ceiling-water-damage/',
    '/water-heater-leak-cleanup/', '/appliance-leak-water-damage/',
    '/wet-carpet-drying/', '/hardwood-floor-water-damage/', '/water-damage-repair/',
    '/leak-detection/', '/commercial-water-damage/', '/fire-sprinkler-water-cleanup/',
    '/restoration-process/', '/insurance-claims-help/', '/about/', '/contact/',
    '/blog/prevent-frozen-pipes/', '/blog/what-to-do-when-a-pipe-bursts/',
    '/blog/winterize-swamp-cooler/', '/blog/water-damage-categories-classes/',
    '/blog/how-long-does-water-damage-take-to-dry/',
    '/blog/hidden-water-damage-signs/',
    '/blog/spring-snowmelt-basement-flooding/',
    '/service-areas/',
    '/areas/murray/', '/areas/sandy/', '/areas/cottonwood-heights/',
    '/areas/west-jordan/', '/areas/taylorsville/', '/areas/south-jordan/',
    '/areas/sandy/burst-pipe-water-damage/',
    '/areas/sandy/basement-flooding-cleanup/',
    '/areas/west-jordan/burst-pipe-water-damage/',
    '/areas/west-jordan/basement-flooding-cleanup/',
    '/areas/murray/burst-pipe-water-damage/',
    '/areas/south-jordan/basement-flooding-cleanup/',
]

PHONE = '(385) 488-1110'
ANNOT_RE = re.compile(r'\s*\((/[a-z0-9\-/]*?)\)')
BRACKET_RE = re.compile(r'\[[^\]]+\]')
STOP_WORDS = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'to', 'for',
              'with', 'our', 'your', 'how', 'what', 'when', 'is', 'are', 'it'}

def clean_editorial(text, log):
    """
    Remove the doc author's editorial placeholders from a content paragraph.
    These are NOT page copy and must never be published:
      E2: a 'Business details for the footer and schema:' meta line -> drop
      E3: a paragraph that is exactly one bracketed span (not a CTA)
          e.g. '[Send Photos]', '[Embed Google Map ...]' -> drop
      E4: inline bracketed spans: a span that starts a sentence drops the
          whole sentence ('[Owner name] leads the team ...'), otherwise
          only the span is removed ('[List each ...]' trailing instruction).
    Returns cleaned text, or None if the whole paragraph is dropped.
    CTA lines are handled by the caller BEFORE this runs.
    """
    t = text.strip()
    if t.startswith('Business details for the footer and schema:'):
        log.append({'type': 'meta-line-dropped', 'text': t[:100]})
        return None
    if re.fullmatch(r'\[[^\]]+\]', t):
        log.append({'type': 'placeholder-line-dropped', 'text': t})
        return None
    while True:
        m = BRACKET_RE.search(t)
        if not m:
            break
        span = m.group(0)
        before = t[:m.start()]
        last_bound = max(before.rfind('. '), before.rfind('? '), before.rfind('! '))
        seg_start = last_bound + 2 if last_bound >= 0 else 0
        if before[seg_start:].strip() == '':
            # span starts a sentence: drop the whole sentence
            after = t[m.end():]
            endm = re.search(r'[.!?](\s|$)', after)
            end = m.end() + (endm.end() if endm else len(after))
            t = (t[:seg_start] + t[end:]).strip()
            t = re.sub(r'\s+', ' ', t)
            log.append({'type': 'placeholder-sentence-dropped', 'text': span})
        else:
            t = (t[:m.start()] + t[m.end():]).strip()
            t = re.sub(r'\s+', ' ', t)
            log.append({'type': 'placeholder-span-removed', 'text': span})
    return t if t else None

def slug_words(href):
    """Keyword set from a link target, e.g. /blog/what-to-do-when-a-pipe-bursts/."""
    parts = [p for p in href.strip('/').split('/') if p]
    words = set()
    for p in parts:
        words.update(p.split('-'))
    return words

def clean_word(w):
    return w.strip('.,;:!?"\'').lower()

# --- Fix Round 3 anchor overrides -------------------------------------------
# (tab, href) -> replacement anchor text. Every value is a verbatim phrase
# from the doc sentence that carries that annotation (verified against
# doc-raw.json before this table was written); the verifier-suggested
# phrases were checked word-for-word and used as given, including the
# whole-sentence / whole-cell ones (Tabs 03 repair, 09, 11). The parser
# only applies an override when the phrase is actually present in the
# annotation's prefix (containment guard in anchor_for), except for the
# single lookback case (38, /ceiling-water-damage/) where the phrase sits
# in text already emitted before the second annotation in its sentence.
# Method recorded in pages.json: 'override' (or 'override-lookback').
ANCHOR_OVERRIDES = {
    (3, '/mold-remediation/'): 'Mold can start, hardwood may cup, repairs grow bigger',
    (3, '/water-damage-repair/'): 'Restoration is the repair work that follows',
    (4, '/mold-remediation/'): 'Mold on the back of drywall and on framing',
    (5, '/structural-drying/'): 'wall cavity drying',
    (9, '/basement-flooding-cleanup/'): 'Basement floor drains as the lowest exit point, so backups show up there first',
    (11, '/emergency-water-removal/'): 'Pump out water and mud with submersible pumps and truck-mounted extraction',
    (11, '/mold-remediation/'): 'Flood water carries mold spores and nutrients, so we check the wall cavities and framing',
    (13, '/water-damage-repair/'): 'Repair drywall and flooring',
    (14, '/ceiling-water-damage/'): 'ceiling of the room below',
    (15, '/basement-flooding-cleanup/'): 'Basement carpet',
    (17, '/hardwood-floor-water-damage/'): 'hardwood repair or refinish',
    (18, '/structural-drying/'): 'targeted drying',
    (18, '/mold-remediation/'): 'mold has started',
    (19, '/fire-sprinkler-water-cleanup/'): 'fire protection company',
    (19, '/structural-drying/'): 'Large-loss drying',
    (20, '/emergency-water-removal/'): 'Extract water from floors',
    (24, '/insurance-claims-help/'): 'file a claim',
    (25, '/insurance-claims-help/'): 'Claims can be denied',
    (27, '/ceiling-water-damage/'): 'against the ceiling',
    (28, '/insurance-claims-help/'): 'helps you follow the scope',
    (29, '/mold-remediation/'): 'prevent mold',
    (29, '/basement-flooding-cleanup/'): 'basements often need heat',
    (30, '/mold-remediation/'): 'hidden mold',
    (34, '/blog/spring-snowmelt-basement-flooding/'): 'pushed water into basements',
    (35, '/ceiling-water-damage/'): 'a ceiling stain one floor down',
    (36, '/appliance-leak-water-damage/'): 'water heater or washer hose',
    (36, '/water-heater-leak-cleanup/'): 'around the heater every few months',
    (36, '/areas/west-jordan/basement-flooding-cleanup/'): 'flooded basement cleanup',
    (37, '/commercial-water-damage/'): 'water through every affected unit',
    (37, '/basement-flooding-cleanup/'): 'groundwater seep into basements',
    (38, '/appliance-leak-water-damage/'): 'sends water through the floor',
    (38, '/ceiling-water-damage/'): 'into the ceiling and walls below',
    (38, '/leak-detection/'): 'leak at crimp fittings',
    (38, '/areas/south-jordan/basement-flooding-cleanup/'): 'flooded basement cleanup',
    (39, '/structural-drying/'): 'Ceiling and wall cavity drying',
    (40, '/window-well-flooding/'): 'around basement windows',
    (40, '/basement-flooding-cleanup/'): 'flooded basement cleanup',
    (41, '/leak-detection/'): 'PEX fitting leaks',
    (41, '/hardwood-floor-water-damage/'): 'LVP and hardwood',
    (41, '/burst-pipe-water-damage/'): 'burst pipe process',
    (43, '/burst-pipe-water-damage/'): 'burst pipe process',
    (44, '/appliance-leak-water-damage/'): 'Water heaters, upstairs laundry',
    # Weak 5-word tail anchors (verifier observations, Batch C O-C2 / D O2):
    # replaced with a descriptive phrase from the same sentence.
    (30, '/insurance-claims-help/'): 'Damage from a slow leak',
    (31, '/window-well-flooding/'): 'Snow fills them',
    (35, '/insurance-claims-help/'): 'Ice removal and roof wear',
    (36, '/insurance-claims-help/'): 'Burst pipes and water heater failures',
    (42, '/insurance-claims-help/'): 'Burst pipes and water heater failures',
}
# Tabs 16 + 21 /sewage-cleanup/ are covered by the generalised sewage rule
# in anchor_for() below (same rule as the homepage Round 1 override), not
# by this table: 'Sewage or outside flood water' / 'Sewage and flood water'.

def _clean_anchor(a):
    """Strip leading/trailing punctuation from a derived anchor (Fix Round 3).
    The stripped punctuation stays in the page as plain text (parse_segments
    splits prefix into pre + anchor + post), so no words change — this is
    what moves the ', ' separator out of the 'Serving Midvale and nearby'
    area anchors sitewide (', Sandy' -> 'Sandy')."""
    return a.strip().strip(' ,.;:·!?()[]"\'')

def _sewage_anchor(frag):
    """Generalised sewage-clause rule (Fix Round 3): any 'sewage or/and
    outside flood(ing| water)' phrase anchors whole. Covers the homepage
    ('sewage or outside flooding'), Tab 16 ('Sewage or outside flood
    water') and Tab 21 ('Sewage and flood water')."""
    m = re.search(r'sewage\s+(?:or|and)\s+(?:outside\s+)?flood(?:ing| water)',
                  frag, flags=re.I)
    return m.group(0) if m else None

def word_in_set(w, sw):
    """Slug-keyword match, singular/plural tolerant ('claim' == 'claims')."""
    cw = clean_word(w)
    if cw in sw:
        return True
    if cw + 's' in sw:
        return True
    if cw.endswith('s') and cw[:-1] in sw:
        return True
    return False

def anchor_for(prefix, href, is_list_item=False, tab=None):
    """
    Derive the anchor text for a ' (/href/)' annotation from the text that
    precedes it in the same paragraph (prefix, with earlier annotations
    already removed).
    Rule:
      0. Strip a leading 'and '/'or ' (second link in one list item).
      0a. Fix Round 3 overrides: (tab, href) in ANCHOR_OVERRIDES, applied
          only when the phrase is present in the prefix (containment guard),
          except (38, /ceiling-water-damage/) whose phrase sits in text
          already emitted before its annotation — returned with method
          'override-lookback' for parse_segments to resolve by lookback.
      0b. Generalised sewage-clause rule (see _sewage_anchor): any
          'sewage or/and outside flood(ing| water)' phrase anchors whole.
      1. fragment = text after the last delimiter in the prefix.
         Delimiters: sentence end (. ? ! + space), ': ', ' · ', ' (', ' — ',
         paragraph start.
      2. List items: the whole item text before the paren IS the anchor
         (the doc writes items as 'Name (/slug/): description').
      3. If fragment <= 6 words -> whole fragment.
      4. Else: longest contiguous run of slug-keywords in the fragment
         (>= 2 words) -> that run.
      5. Else: last slug-keyword occurrence in the fragment -> that word.
      6. Else: last 5 words of the fragment.
    Every returned anchor passes through _clean_anchor (Fix Round 3):
    leading/trailing punctuation (', ', '.', etc.) is stripped from the
    anchor text itself; the punctuation stays in the page as plain text.
    Returns (anchor, method).
    """
    frag = prefix.strip()
    frag = re.sub(r'^(and|or|·)\s+', '', frag, flags=re.I)
    # 0a. explicit (tab, href) overrides
    ov = ANCHOR_OVERRIDES.get((tab, href)) if tab is not None else None
    if ov:
        if (tab, href) == (38, '/ceiling-water-damage/'):
            return _clean_anchor(ov), 'override-lookback'
        # Return the phrase with the prefix's own casing (a duplicate
        # occurrence may capitalise it, e.g. 'Flooded basement cleanup...'
        # as a standalone line on Tabs 36/38 — a case-sensitive rfind of
        # the lowercase override would otherwise log anchor-mismatch).
        m = re.search(re.escape(ov), frag, flags=re.I)
        if m:
            return _clean_anchor(m.group(0)), 'override'
    # 0b. generalised sewage rule (homepage + Tabs 16/21)
    if href == '/sewage-cleanup/':
        s = _sewage_anchor(frag)
        if s:
            return _clean_anchor(s), 'override-sewage-clause'
    if is_list_item:
        # whole item text before the paren; if it still runs long, fall through
        if len(frag.split()) <= 8:
            return _clean_anchor(frag.rstrip('.,;:')), 'list-item'
    # find last delimiter
    cuts = [0]
    for m in re.finditer(r'[.!?]\s+|:\s+| · | \(| — ', frag):
        cuts.append(m.end())
    frag = frag[max(cuts):].strip()
    frag = frag.rstrip('.,;:').strip()
    words = frag.split()
    if len(words) <= 6:
        return _clean_anchor(frag), 'whole-fragment'
    sw = slug_words(href)
    # longest contiguous run of slug words anywhere in the fragment
    best, cur = [], []
    for w in words:
        if word_in_set(w, sw):
            cur.append(w)
        else:
            if len(cur) > len(best):
                best = cur
            cur = []
    if len(cur) > len(best):
        best = cur
    if len(best) >= 2:
        return _clean_anchor(' '.join(best)), 'slug-run'
    # last slug keyword occurrence
    for idx in range(len(words) - 1, -1, -1):
        if word_in_set(words[idx], sw):
            return _clean_anchor(words[idx]), 'slug-keyword'
    tail = ' '.join(words[-5:])
    return _clean_anchor(re.sub(r'^(and|or)\s+', '', tail, flags=re.I)), 'last-5'

def parse_segments(text, own_slug, linked, log, is_list_item=False, tab=None):
    """
    Split a paragraph's plain text into segments, turning ' (/href/)'
    annotations into link segments. Applies body-link rules:
      - self-link (href == own_slug): plain text, logged
      - duplicate target on this page: plain text, logged
    Returns (segments, kept_links, annotations_found).
    segments: [{'t': str} | {'t': str, 'href': str}]
    """
    segments = []
    kept = []
    found = 0
    pos = 0
    # work on a mutable copy; annotations are removed as processed so a
    # second annotation's prefix excludes the first one.
    remaining = text
    while True:
        m = ANNOT_RE.search(remaining)
        if not m:
            if remaining:
                segments.append({'t': remaining})
            break
        found += 1
        href = m.group(1)
        prefix = remaining[:m.start()]
        # anchor from the prefix text (with any already-emitted segment text
        # rejoined: prefix is exactly the unprocessed text before the paren)
        anchor, method = anchor_for(prefix, href, is_list_item, tab=tab)
        # Anchor may sit mid-prefix (slug-keyword rule); locate its last
        # occurrence and keep the surrounding text verbatim as plain text.
        idx = prefix.rfind(anchor) if anchor else -1
        if anchor and idx < 0 and method == 'override-lookback' and segments \
                and 'href' not in segments[-1]:
            # Fix Round 3, Tab 38: the sentence carries TWO annotations —
            # "...sends water through the floor into the ceiling and walls
            # below (/appliance-leak-water-damage/) and
            # (/ceiling-water-damage/)". The ceiling anchor's words sit in
            # text already emitted as a plain segment before the first
            # annotation. If the anchor is wholly inside that last plain
            # segment, split it: pre + link + post, so the concatenated
            # text is byte-identical (no words change, only link wrapping).
            last = segments[-1]['t']
            tidx = last.rfind(anchor)
            if tidx >= 0 and tidx + len(anchor) <= len(last):
                pre_tail, post_tail = last[:tidx], last[tidx + len(anchor):]
                segments[-1] = {'t': pre_tail} if pre_tail else None
                segments = [s for s in segments if s is not None]
                is_self = (href == own_slug)
                is_dup = (href in linked)
                if is_self:
                    log.append({'type': 'self-link', 'href': href, 'anchor': anchor})
                    segments.append({'t': anchor})
                elif is_dup:
                    log.append({'type': 'duplicate', 'href': href, 'anchor': anchor})
                    segments.append({'t': anchor})
                else:
                    linked.add(href)
                    kept.append({'anchor': anchor, 'href': href, 'method': method})
                    segments.append({'t': anchor, 'href': href})
                if post_tail + prefix:
                    segments.append({'t': post_tail + prefix})
                remaining = remaining[m.end():]
                continue
            log.append({'type': 'anchor-mismatch', 'href': href,
                        'prefix_tail': prefix[-60:]})
            if prefix:
                segments.append({'t': prefix})
            remaining = remaining[m.end():]
            continue
        if anchor and idx >= 0:
            pre = prefix[:idx]
            post = prefix[idx + len(anchor):]
            if pre:
                segments.append({'t': pre})
            is_self = (href == own_slug)
            is_dup = (href in linked)
            if is_self:
                log.append({'type': 'self-link', 'href': href, 'anchor': anchor})
                segments.append({'t': anchor})
            elif is_dup:
                log.append({'type': 'duplicate', 'href': href, 'anchor': anchor})
                segments.append({'t': anchor})
            else:
                linked.add(href)
                kept.append({'anchor': anchor, 'href': href, 'method': method})
                segments.append({'t': anchor, 'href': href})
            if post:
                segments.append({'t': post})
        else:
            # anchor derivation failed to match the prefix (should not happen);
            # keep the whole prefix as text and drop the annotation.
            log.append({'type': 'anchor-mismatch', 'href': href,
                        'prefix_tail': prefix[-60:]})
            if prefix:
                segments.append({'t': prefix})
        # continue after the annotation; keep any trailing punctuation/space
        remaining = remaining[m.end():]
    return segments, kept, found

CTA_RE = re.compile(r'^\[(.+)\]\s*\[(.+)\]$')
CTA_SINGLE_RE = re.compile(r'^\[(.+)\]$')

def parse_cta(text):
    """'[Call Now: (385) 488-1110] [Send Photos of the Damage (/contact/)]'
    -> list of button dicts. Returns None if the line is not a CTA line."""
    m = CTA_RE.match(text.strip()) or CTA_SINGLE_RE.match(text.strip())
    if not m:
        return None
    parts = [g for g in m.groups() if g is not None]
    buttons = []
    for part in parts:
        am = re.search(r'\((/[a-z0-9\-/]+/?)\)\s*$', part)
        if am:
            buttons.append({'label': part[:am.start()].strip(),
                            'href': am.group(1)})
        elif PHONE in part:
            # "Call Now: (385) 488-1110" -> number-only visible label
            buttons.append({'label': PHONE, 'tel': 'tel:+13854881110'})
        else:
            return None
    return buttons

def para_plain(p):
    return ''.join(e.get('textRun', {}).get('content', '')
                    for e in p.get('elements', [])).rstrip('\n')

def walk_content(content, out):
    """Yield ('para', style, text, bullet) or ('table', rows) in order."""
    for el in content:
        p = el.get('paragraph')
        if p:
            txt = para_plain(p)
            if txt.strip():
                out.append(('para', p.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT'),
                            txt, bool(p.get('bullet'))))
            continue
        t = el.get('table')
        if t:
            rows = []
            for row in t.get('tableRows', []):
                cells = []
                for cell in row.get('tableCells', []):
                    sub = []
                    walk_content(cell.get('content', []), sub)
                    cells.append(' '.join(x[2] for x in sub if x[0] == 'para'))
                rows.append(cells)
            out.append(('table', rows))
            continue

def strip_annotations(text):
    """Word-count helper: remove ' (/path/)' annotations and brackets."""
    t = ANNOT_RE.sub('', text)
    return t.replace('[', '').replace(']', '')

def main():
    D = json.load(open(SRC))
    tabs = D['tabs']
    assert len(tabs) == 44, f'expected 44 tabs, got {len(tabs)}'
    pages = []
    stats = Counter()
    total_words_extract = 0
    all_logs = []
    for i, t in enumerate(tabs, 1):
        dt = t['documentTab']
        items = []
        walk_content(dt.get('body', {}).get('content', []), items)
        # --- extract.py-compatible total word count (all lines, SEO incl.) ---
        # extract.py emits ONE line per table ROW, cells joined by ' || '.
        extract_lines = []
        for kind, *rest in items:
            if kind == 'para':
                extract_lines.append(rest[1])
            else:
                for row in rest[0]:
                    extract_lines.append(' || '.join(row))
        total_words_extract += len('\n'.join(extract_lines).split())
        # --- split SEO table vs PAGE COPY ---
        # First table is the SEO table; PAGE COPY starts at the marker line.
        seo = {}
        blocks = []
        copy_started = False
        seen_table = 0
        linked = set()   # body-link targets already used on this page
        log = []
        annotations = 0
        root_annotations = 0
        kept_links = []
        current_h2 = ''
        seen_h1 = False
        pending_ul = None

        def flush_ul():
            nonlocal pending_ul
            if pending_ul:
                blocks.append({'type': 'ul', 'items': pending_ul})
                pending_ul = None

        for kind, *rest in items:
            if kind == 'table':
                rows = rest[0]
                seen_table += 1
                if not copy_started and seen_table == 1:
                    for r in rows:
                        if len(r) >= 2:
                            seo[r[0].strip().rstrip(':')] = r[1].strip()
                    continue
                # content table: drop all-empty rows; a table whose first
                # row was dropped as empty has no header row (Tab 24
                # contact table). Drop rows carrying the [Street address]
                # placeholder (Tab 24) — the address does not exist.
                trows = []
                has_header = True
                for r in rows:
                    if all(c.strip() == '' for c in r):
                        if not trows:
                            has_header = False
                        continue
                    if any('[Street address]' in c for c in r):
                        log.append({'type': 'address-row-dropped',
                                    'text': ' | '.join(r)[:100]})
                        continue
                    trow = []
                    for cell in r:
                        cell = clean_editorial(cell, log) or ''
                        segs, k, f = parse_segments(cell, seo.get('URL slug'), linked, log, tab=i)
                        annotations += f
                        kept_links.extend(k)
                        trow.append(segs)
                    trows.append(trow)
                flush_ul()
                blocks.append({'type': 'table', 'rows': trows, 'has_header': has_header})
                continue
            style, txt, bullet = rest
            if txt.startswith('PAGE COPY'):
                copy_started = True
                continue
            if txt.strip() == 'SEO SETUP':
                continue
            if not copy_started:
                continue
            if txt.strip() == '[Call Now: (385) 488-1110]' or txt.startswith('[Call Now:'):
                cta = parse_cta(txt)
                if cta:
                    # the CTA's /contact/ is a real doc annotation: count it
                    annotations += sum(1 for b in cta if 'href' in b)
                    flush_ul()
                    blocks.append({'type': 'cta', 'buttons': cta})
                    continue
            # E1: anything before the first H1 is an author instruction,
            # not page copy (Tab 23 'Before publishing, fill in ...').
            if not seen_h1 and style != 'HEADING_1':
                log.append({'type': 'pre-h1-skipped', 'text': txt[:100]})
                continue
            # E2/E3/E4: editorial placeholders (Tab 23/24/32)
            if style == 'NORMAL_TEXT':
                cleaned = clean_editorial(txt, log)
                if cleaned is None:
                    continue
                txt = cleaned
            if style == 'HEADING_1':
                seen_h1 = True
                stats['h1'] += 1
                flush_ul()
                blocks.append({'type': 'h1', 'text': txt.strip()})
            elif style == 'HEADING_2':
                stats['h2'] += 1
                current_h2 = txt.strip()
                flush_ul()
                blocks.append({'type': 'h2', 'text': current_h2})
            elif style == 'HEADING_3':
                stats['h3'] += 1
                flush_ul()
                faq = 'faq' in current_h2.lower()
                blocks.append({'type': 'h3', 'text': txt.strip(), 'faq': faq})
            else:
                segs, k, f = parse_segments(txt, seo.get('URL slug'), linked, log,
                                            is_list_item=bullet, tab=i)
                annotations += f
                kept_links.extend(k)
                if bullet:
                    if pending_ul is None:
                        pending_ul = []
                    pending_ul.append(segs)
                else:
                    flush_ul()
                    blocks.append({'type': 'p', 'segments': segs})
        flush_ul()
        slug = seo.get('URL slug', '?')
        if slug != ROUTES[i - 1]:
            print(f'TAB {i:02d} SLUG MISMATCH: doc={slug!r} routes={ROUTES[i-1]!r}')
            sys.exit(1)
        # PAGE COPY word count: annotations + brackets stripped; CTA labels
        # as rendered (call button is number-only, so 'Call Now:' drops 2 words)
        copy_text = []
        for b in blocks:
            if b['type'] in ('h1', 'h2', 'h3'):
                copy_text.append(b['text'])
            elif b['type'] == 'p':
                copy_text.append(''.join(s['t'] for s in b['segments']))
            elif b['type'] == 'ul':
                for it in b['items']:
                    copy_text.append(''.join(s['t'] for s in it))
            elif b['type'] == 'table':
                for r in b['rows']:
                    for c in r:
                        copy_text.append(''.join(s['t'] for s in c))
            elif b['type'] == 'cta':
                for btn in b['buttons']:
                    copy_text.append(btn['label'])
        copy_words = len(' '.join(copy_text).split())
        pages.append({
            'tab': i,
            'slug': slug,
            'seo_title': seo.get('SEO title', ''),
            'meta_description': seo.get('Meta description', ''),
            'schema': seo.get('Schema', ''),
            'blocks': blocks,
            'copy_words': copy_words,
            'annotations': annotations,
            'body_links': kept_links,
            'log': log,
        })
        for entry in log:
            all_logs.append((i, entry))
    stats['links'] = sum(p['annotations'] for p in pages)
    root_n = sum(1 for p in pages for l in p['body_links'] if l['href'] == '/')
    print(f"total words (extract-compatible): {total_words_extract} (target 40699)")
    print(f"H1: {stats['h1']} (44)  H2: {stats['h2']} (338)  H3: {stats['h3']} (391)")
    print(f"link annotations: {stats['links'] - root_n} path (597) + {root_n} root '/' (1) = {stats['links']}")
    print(f"Tab 01 copy words: {pages[0]['copy_words']} | Tab 01 annotations: {pages[0]['annotations']}")
    print(f"Tab 01 body links kept: {len(pages[0]['body_links'])}")
    print(f"Tab 23 copy words: {pages[22]['copy_words']} | Tab 24: {pages[23]['copy_words']} | Tab 32: {pages[31]['copy_words']}")
    print('--- parser log (dup/self/mismatch) ---')
    for tab, e in all_logs:
        print(f"Tab {tab:02d}: {e['type']} {e.get('href')} anchor={e.get('anchor')!r}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump({'pages': pages}, f, indent=1, ensure_ascii=False)
    print('wrote', OUT)

if __name__ == '__main__':
    main()
