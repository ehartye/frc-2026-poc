/**
 * Check that a published site is intact before it is deployed:
 *
 *   1. Each design index lists exactly the design folders beside it, and opens a design it lists.
 *   2. Every file a design index or a design record names is there.
 *   3. Every relative link in a published HTML page leads to a file.
 *
 *   node site-check.mjs [SITE]        SITE is the published folder, docs by default
 *
 * This file stands alone: it needs Node and nothing else. Copy it into a project and it belongs to the project. It
 * checks that the site is whole. It does not judge a design.
 */
import {existsSync, readFileSync, readdirSync, statSync} from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

/** The design indexes a site may hold: the file, the key of its ID list and the folder of its design folders. */
const indexes = [['releases.json', 'releases', 'releases', 'release.json'], ['designs.json', 'designs', 'designs', 'design.json']];
const isFile = file => statSync(file, {throwIfNoEntry: false})?.isFile() ?? false;
const isFolder = file => statSync(file, {throwIfNoEntry: false})?.isDirectory() ?? false;

function filesUnder(root) {
  const found = [];
  (function walk(folder) {
    for (const item of readdirSync(folder, {withFileTypes: true})) {
      if (item.name.startsWith('.git')) continue;
      const full = path.join(folder, item.name);
      if (item.isDirectory()) walk(full); else if (item.isFile()) found.push(full);
    }
  })(root);
  return found;
}

/** Every value under a "file" key of a record, at any depth. */
function namedFiles(node, found = []) {
  if (Array.isArray(node)) for (const item of node) namedFiles(item, found);
  else if (node !== null && typeof node === 'object') for (const [key, value] of Object.entries(node)) {
    if (key === 'file' && typeof value === 'string') found.push(value); else namedFiles(value, found);
  }
  return found;
}

/** The relative links of a page: href and src of its tags, outside its scripts, styles and comments. */
export function relativeLinks(html) {
  const text = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, match => match.slice(0, match.indexOf('>') + 1));
  const links = [];
  for (const match of text.matchAll(/<[a-z][^>]*?\s(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi)) {
    const link = (match[1] ?? match[2]).trim();
    // Another site, a place on the same page, or an address the browser builds: nothing to find on disk.
    if (!link || /^(?:[a-z][a-z0-9+.-]*:|\/\/|#|\?)/i.test(link) || /[{}$<>]/.test(link)) continue;
    links.push(link);
  }
  return links;
}

/** The problems of a published site, each as one line. Empty when the site is whole. */
export function checkSite(site) {
  const problems = [], rel = full => path.relative(site, full).split(path.sep).join('/');
  if (!isFolder(site)) return ['No published folder at ' + site];
  const files = filesUnder(site);
  const json = file => { try { return JSON.parse(readFileSync(file, 'utf8').replace(/^﻿/, '')); } catch { problems.push(rel(file) + ' is not readable JSON'); return null; } };
  for (const file of files) for (const [name, key, folder, recordName] of indexes) {
    if (path.basename(file) !== name) continue;
    const index = json(file), tree = path.dirname(file);
    if (!index) continue;
    const ids = index[key];
    if (!Array.isArray(ids) || ids.some(id => typeof id !== 'string')) { problems.push(rel(file) + ' needs "' + key + '" as a list of design IDs'); continue; }
    if (new Set(ids).size !== ids.length) problems.push(rel(file) + ' lists a design twice');
    // A withdrawn design keeps its line in the index and may have left the site.
    const withdrawn = id => index.designStatus?.[id] === 'withdrawn';
    for (const id of ids) if (!withdrawn(id) && !isFolder(path.join(tree, folder, id))) problems.push(rel(file) + ' lists ' + id + ', and ' + rel(path.join(tree, folder, id)) + '/ is missing');
    const present = isFolder(path.join(tree, folder)) ? readdirSync(path.join(tree, folder), {withFileTypes: true}).filter(d => d.isDirectory() && !d.name.startsWith('.')).map(d => d.name) : [];
    for (const id of present) if (!ids.includes(id)) problems.push(rel(path.join(tree, folder, id)) + '/ is not listed in ' + rel(file));
    for (const field of ['current', 'beside']) if (typeof index[field] === 'string' && !ids.includes(index[field])) problems.push(rel(file) + ' opens ' + index[field] + ', which it does not list');
    for (const named of namedFiles(index)) if (!isFile(path.resolve(tree, named))) problems.push(rel(file) + ' names ' + named + ', which is missing');
    // Each design's record names files that sit beside it.
    for (const id of present) {
      const record = path.join(tree, folder, id, recordName);
      if (!isFile(record)) continue;
      for (const named of namedFiles(json(record))) if (!isFile(path.resolve(path.dirname(record), named))) problems.push(rel(record) + ' names ' + named + ', which is missing');
    }
  }
  for (const file of files.filter(name => /\.html?$/i.test(name))) for (const link of relativeLinks(readFileSync(file, 'utf8'))) {
    let target;
    try { target = decodeURIComponent(link.split(/[?#]/)[0]); } catch { target = link.split(/[?#]/)[0]; }
    const full = target.startsWith('/') ? null : path.resolve(path.dirname(file), target);
    // A link from the site root depends on where the site is served, so it is left to the browser.
    if (!full || !target) continue;
    if (!(isFile(full) || isFolder(full) && isFile(path.join(full, 'index.html')))) problems.push(rel(file) + ' links to ' + link + ', which is missing');
  }
  return [...new Set(problems)].sort();
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  if (args.length > 1) { console.error('Usage: site-check.mjs [SITE]'); process.exit(2); }
  const site = path.resolve(args[0] ?? 'docs'), problems = checkSite(site);
  for (const problem of problems) console.error(process.env.GITHUB_ACTIONS ? '::error title=Site check::' + problem : problem);
  console.log(problems.length ? problems.length + ' problem(s) in the published site.' : 'The published site is whole.');
  if (problems.length) process.exitCode = 1;
}
