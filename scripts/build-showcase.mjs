// Build the public site: the independent field pages, the design status pages and an entry page that
// features the current preliminary design release. The rough-draft showcase is withdrawn and is not built.
import {createHash} from 'node:crypto';
import {cp, mkdir, readFile, readdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';

const [plugin, output] = process.argv.slice(2);
if (!plugin || !output) throw Error('Usage: node scripts/build-showcase.mjs FIELD_BUILDER_ROOT NEW_SITE_DIRECTORY');
const root = fileURLToPath(new URL('../', import.meta.url));
const at = file => path.join(root, file);
const json = async file => JSON.parse(await readFile(at(file), 'utf8'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const destination = path.resolve(output);
await mkdir(destination, {recursive: false});

// The field lab, the alliance role comparison, the depot lanes and the match data need no robot model.
execFileSync(process.execPath, [at('kickoff/rehearsal/build.mjs'), plugin, destination], {stdio: 'inherit'});
const fieldFiles = ['alliance-roles.html', 'depot-lanes/index.html', 'depot-lanes/results.json', 'field-lab.html',
  'match-profile.json', 'match-series.json', 'match-summary.json'];
const built = (await readdir(destination, {withFileTypes: true, recursive: true})).filter(item => item.isFile())
  .map(item => path.relative(destination, path.join(item.parentPath, item.name)).split(path.sep).join('/')).sort();
if (JSON.stringify(built) !== JSON.stringify(fieldFiles)) throw Error('Unexpected field pages: ' + built.join(', '));

// The design status of each phase, as committed.
const designs = await json('docs/detailed-design/designs.json');
const shown = designs.designs.filter(id => ['in-progress', 'effective'].includes(designs.designStatus[id]));
if (designs.current !== null || shown.length)
  throw Error('A current detailed design needs its own entry page: this builder publishes the preliminary design as the primary view');
const withdrawn = designs.designs.find(id => designs.designStatus[id] === 'withdrawn');
if (!withdrawn || !designs.reason?.[withdrawn] || !designs.lastCommit?.[withdrawn])
  throw Error('The detailed design index must record the withdrawn showcase with its reason and last commit');
await cp(at('docs/detailed-design'), path.join(destination, 'detailed-design'), {recursive: true});
await cp(at('docs/preliminary-design'), path.join(destination, 'preliminary-design'), {recursive: true});

// The entry page and its still follow the primary view: the current preliminary design release.
const releases = await json('docs/preliminary-design/releases.json');
const release = releases.current, state = releases.designStatus?.[release];
const status = {'in-progress': 'in progress', effective: 'effective'}[state];
const statusNote = {'in-progress': 'It is in progress and still changing.',
  effective: 'It is the effective preliminary design that detailed design builds on.'}[state];
if (!releases.releases.includes(release) || !status) throw Error('The entry page needs a current in-progress or effective preliminary design release');
const record = await json('docs/robot/preliminary-' + release + '.json');
const still = await readFile(at('docs/robot/preliminary-' + release + '.png'));
const served = name => readFile(at('docs/preliminary-design/releases/' + release + '/' + name));
const packed = await served('review-scene.json.gz');
if (record.release !== release || sha(still) !== record.imageSha256 || sha(await served('receipt.json')) !== record.receiptSha256 ||
    sha(await served('release.json')) !== record.releaseRecordSha256 || sha(packed) !== record.sceneSha256)
  throw Error('The preliminary still differs from the current release. Regenerate it with scripts/preliminary-still.py.');
await mkdir(path.join(destination, 'assembly'));
await writeFile(path.join(destination, 'assembly/assembly.png'), still);
const text = value => String(value).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
const fields = {status, statusNote, release, reason: designs.reason[withdrawn], lastCommit: designs.lastCommit[withdrawn],
  lastShort: designs.lastCommit[withdrawn].slice(0, 7), receipt: record.receiptSha256.slice(0, 10),
  headline: JSON.parse(gunzipSync(packed)).title, title: record.caption.title, alt: record.caption.alt, pose: record.caption.pose,
  scope: record.caption.scope};
const template = await readFile(at('docs/showcase/front-page.html'), 'utf8');
for (const key of Object.keys(fields)) if (!template.includes('{{' + key + '}}')) throw Error('The front page no longer uses the field ' + key);
const page = template.replace(/\{\{(\w+)\}\}/g, (match, key) => {
  if (!(key in fields)) throw Error('Unknown front page field: ' + key);
  return text(fields[key]);
});
await writeFile(path.join(destination, 'index.html'), page);
console.log('Built the field pages, the design status pages and the ' + release + ' preliminary design entry page');
