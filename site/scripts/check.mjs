// Smoke-check the built site in dist/ (run `npm run build` first): `npm test`.
//
//   header owner link carries the hub logo   (index + a docs page)
//   favicon link points at the hub favicon
//   site-kit CSS defines --sk-btn-line       (site-kit >= v0.1.2)
//
// Prints ok/FAIL per check; exits non-zero if any check fails. Node stdlib only.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const dist = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const BASE = '/claude-code-workflow';
let failed = 0;

function check(name, ok) {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}`);
  if (!ok) failed++;
}

function read(rel) {
  const p = join(dist, rel);
  return existsSync(p) ? readFileSync(p, 'utf8') : '';
}

// True if the <a class="owner ..."> element contains <img ... src=logo ... class="logo">.
function ownerHasLogo(html) {
  const m = html.match(/<a\b[^>]*class="owner\b[^"]*"[^>]*>([\s\S]*?)<\/a>/);
  if (!m) return false;
  const img = m[1].match(/<img\b[^>]*>/);
  return !!img
    && img[0].includes(`src="${BASE}/logo.jpg"`)
    && /class="(?:[^"]*\s)?logo(?:\s[^"]*)?"/.test(img[0]);
}

const index = read('index.html');
check('index.html: owner link contains the logo img', ownerHasLogo(index));
check('index.html: favicon link', index.includes(`<link rel="icon" href="${BASE}/favicon.png"`));

const astroDir = join(dist, '_astro');
const css = existsSync(astroDir)
  ? readdirSync(astroDir).filter((f) => f.endsWith('.css')).map((f) => readFileSync(join(astroDir, f), 'utf8'))
  : [];
const inline = [...index.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]);
check('CSS defines --sk-btn-line (site-kit >= v0.1.2)', [...css, ...inline].some((s) => /--sk-btn-line\s*:/.test(s)));

const doc = read('docs/skills/git-dev-execute/index.html');
check('docs/skills/git-dev-execute: owner link contains the logo img', ownerHasLogo(doc));

if (failed) {
  console.log(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log('\nall checks passed');
