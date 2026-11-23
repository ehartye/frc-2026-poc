/**
 * Scan a checkout for personal machine paths and credentials. Run it on every pushed branch: a path or a key
 * is public the moment the branch is, whether or not a pull request ever opens.
 *
 *   node scan.mjs [FOLDER]
 *
 * This file stands alone: it needs Node and Git and nothing else. Copy it into a project and it belongs to the project.
 */
import {execFileSync} from 'node:child_process';
import {lstatSync, readFileSync, readdirSync} from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

// A home directory names its owner. Placeholders, service accounts and hosted-runner homes do not.
const placeholder = /^(?:name|user|username|you|your[-_]?(?:user)?[-_]?name|your[-_]?user|me|example|public|default|shared|all users|runner|runneradmin|lvuser|admin|root|ubuntu|pi|vscode|node)$/i;
const variable = /[<>$%{}*]/;
const owner = '([^\\\\/\\s"\'`|:?,;)]+)', end = '(?=[\\\\/\\s"\'`|:?,;)]|$)';
const homes = [
  // A drive, mount or URL-encoded drive before Users, in any case and with either or doubled separators.
  new RegExp('(?:[A-Za-z]:|[A-Za-z]%3A|/mnt/[a-z]|/[a-z])[\\\\/]+users[\\\\/]+' + owner + end, 'gi'),
  // A bare /Users or /home needs a boundary before it, so docs/Users/x and example.org/home/x are not home directories.
  new RegExp('(?<![A-Za-z0-9._~:-])/Users/' + owner + end, 'g'),
  new RegExp('(?<![A-Za-z0-9._~-])/home/' + owner + end, 'g'),
  // The folder name some tools derive from a working directory: C--Users-NAME-repos-project.
  /(?<![A-Za-z0-9])[A-Za-z]--Users-([A-Za-z0-9._]+)(?=-|[^A-Za-z0-9._]|$)/g
];
const credentials = [
  ['private-key', /-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----/],
  ['github-token', /\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b/],
  ['aws-access-key', /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/],
  ['slack-token', /\bxox[abprs]-[A-Za-z0-9-]{10,}/],
  ['api-key', /\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{32,}|AIza[0-9A-Za-z_-]{35}|npm_[A-Za-z0-9]{36})\b/],
  ['assigned-secret', /(?<![A-Za-z0-9])[A-Za-z0-9_-]*(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)[A-Za-z0-9_-]*["']?\s*[:=]\s*["']([^"'\s]{12,})["']/i]
];

/** Findings in one text: {line, kind, text}. A credential is reported by kind and position, never repeated. */
export function scanText(text) {
  const findings = [];
  for (const [index, line] of text.split('\n').entries()) {
    for (const pattern of homes) {
      for (const match of line.matchAll(pattern)) {
        // An owner name holds a letter; /Users/42/roles is a route, not a home directory.
        if (placeholder.test(match[1]) || variable.test(match[1]) || !/[A-Za-z]/.test(match[1])) continue;
        findings.push({line: index + 1, kind: 'machine-path', text: match[0]});
      }
    }
    for (const [kind, pattern] of credentials) {
      const match = pattern.exec(line);
      if (!match || kind === 'assigned-secret' && (variable.test(match[1]) || /your|example|placeholder|change-?me|xxxx/i.test(match[1]))) continue;
      findings.push({line: index + 1, kind, text: 'column ' + (match.index + 1)});
    }
  }
  return findings;
}

export function trackedFiles(root) {
  try {
    const options = {cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 256 * 1024 * 1024};
    execFileSync('git', ['rev-parse', '--git-dir'], options);
    return execFileSync('git', ['ls-files', '-z'], options).split('\0').filter(Boolean);
  } catch {
    const files = [];
    (function walk(folder, prefix) {
      for (const item of readdirSync(folder, {withFileTypes: true})) {
        if (item.name === '.git' || item.name === 'node_modules') continue;
        if (item.isDirectory()) walk(path.join(folder, item.name), prefix + item.name + '/');
        else if (item.isFile()) files.push(prefix + item.name);
      }
    })(root, '');
    return files;
  }
}

/** A file's text, or null for a binary file. A UTF-16 file, as a Windows shell redirect writes, is decoded by its byte-order mark. */
export function readText(file) {
  const bytes = readFileSync(file);
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return bytes.subarray(2).toString('utf16le');
  if (bytes[0] === 0xfe && bytes[1] === 0xff) return Buffer.from(bytes.subarray(2)).swap16().toString('utf16le');
  return bytes.subarray(0, 8000).includes(0) ? null : bytes.toString('utf8');
}

/**
 * Scan every tracked text file under root, as it stands at the checked-out commit. `.branch-scan.json` may hold {"ignore": ["folder/", "exact/file"]}
 * for fixtures that show a path or key on purpose; the list is reviewed like any other file.
 */
export function scanTree(root) {
  let ignore = [];
  try {
    ignore = JSON.parse(readFileSync(path.join(root, '.branch-scan.json'), 'utf8')).ignore ?? [];
  } catch (error) {
    if (error.code !== 'ENOENT') throw Error('Unreadable .branch-scan.json: ' + error.message);
  }
  if (!Array.isArray(ignore) || !ignore.every(entry => typeof entry === 'string' && entry.length))
    throw Error('.branch-scan.json needs "ignore" as a list of folder prefixes (ending in /) or exact files');
  const skipped = name => ignore.some(entry => entry.endsWith('/') ? name.startsWith(entry) : name === entry);
  const findings = [];
  let files = 0, skippedBinary = 0;
  for (const name of trackedFiles(root).sort()) {
    if (skipped(name)) continue;
    const full = path.join(root, name);
    if (!lstatSync(full, {throwIfNoEntry: false})?.isFile()) continue;
    const text = readText(full);
    if (text === null) { skippedBinary++; continue; }
    files++;
    for (const finding of scanText(text)) findings.push({file: name, ...finding});
  }
  return {files, skippedBinary, ignored: ignore, findings};
}

/** Run the scan as a command. Exit 0 when clean, 1 with findings, 2 when the scan could not run. */
export function main(args = process.argv.slice(2)) {
  try {
    if (args.length > 1) throw Error('Usage: scan.mjs [FOLDER]');
    const result = scanTree(path.resolve(args[0] ?? '.'));
    for (const f of result.findings) {
      console.error(f.file + ':' + f.line + ': ' + f.kind + ': ' + f.text);
      if (process.env.GITHUB_ACTIONS) console.log('::error file=' + f.file + ',line=' + f.line + ',title=' + f.kind + '::Remove this ' +
        (f.kind === 'machine-path' ? 'personal machine path; write paths relative to the repository' : 'credential and rotate it') + '.');
    }
    console.log(JSON.stringify({files: result.files, skippedBinary: result.skippedBinary, ignored: result.ignored, findings: result.findings.length}, null, 2));
    if (result.findings.length) {
      console.error(result.findings.length + ' finding(s). Remove each one, or list a deliberate fixture under "ignore" in .branch-scan.json.');
      process.exitCode = 1;
    }
  } catch (error) { console.error(error.message); process.exitCode = 2; }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main();
