import { cp, mkdir, lstat, readFile, rename, readdir, rm } from 'node:fs/promises';
import { resolve, dirname, join, relative, isAbsolute } from 'node:path';
import { homedir } from 'node:os';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const source = resolve(dirname(fileURLToPath(import.meta.url)), '../skills');
const names = ['frcstack', 'frcscout'];
const inside = (parent, child) => { const r = relative(parent, child); return r === '' || (!r.startsWith('..') && !isAbsolute(r)); };
async function stat(path) { try { return await lstat(path); } catch (e) { if (e.code === 'ENOENT') return null; throw e; } }
async function noLinks(path) {
  let p = resolve(path);
  while (true) { if ((await stat(p))?.isSymbolicLink()) throw Error('Refusing symlink directory'); const parent = dirname(p); if (p === parent) return; p = parent; }
}
async function checkTree(path) {
  for (const entry of await readdir(path, { withFileTypes: true })) {
    if (entry.isSymbolicLink()) throw Error('Source skill contains a symlink');
    if (entry.isDirectory()) await checkTree(join(path, entry.name));
  }
}
async function install() {
  const args = process.argv.slice(2), opts = {};
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (!['--host', '--target', '--replace', '--backup-dir'].includes(key) || key in opts) throw Error('Unknown or duplicate option: ' + key);
    if (key === '--replace') opts[key] = true;
    else { if (!args[i + 1] || args[i + 1].startsWith('--')) throw Error('Missing option value'); opts[key] = args[++i]; }
  }
  const hosts = { agents: '.agents', codex: '.codex', claude: '.claude' };
  if (opts['--host'] && !hosts[opts['--host']]) throw Error('Unknown host');
  if (!!opts['--host'] === !!opts['--target']) throw Error('Choose --host agents|codex|claude OR --target <skills-directory>');
  const target = resolve(opts['--target'] || join(homedir(), hosts[opts['--host']], 'skills'));
  const backupRoot = resolve(opts['--backup-dir'] || join(homedir(), '.frcstack', 'backups'));
  if (inside(source, target) || inside(target, source) || inside(target, backupRoot) || inside(source, backupRoot) || inside(backupRoot, source) || inside(backupRoot, target)) throw Error('Source, target and backup must not overlap');
  await noLinks(target); await noLinks(backupRoot); await checkTree(source);
  const existing = [];
  for (const name of names) {
    const path = join(target, name), s = await stat(path);
    if (!s) continue;
    if (!s.isDirectory() || s.isSymbolicLink()) throw Error('Destination is not a real skill directory');
    if (!opts['--replace']) throw Error('Skill exists; review update and use --replace');
    const definition = join(path, 'SKILL.md');
    if (!(await stat(definition))?.isFile() || (await stat(definition)).isSymbolicLink() || !new RegExp('^name:\\s*' + name + '\\s*$', 'm').test(await readFile(definition, 'utf8'))) throw Error('Refusing replacement of unrelated skill');
    existing.push(name);
  }
  await mkdir(target, { recursive: true });
  const staging = join(target, '.frcstack-staging-' + randomUUID());
  const backup = existing.length ? join(backupRoot, randomUUID()) : null;
  const moved = [], installed = [];
  try {
    await cp(source, staging, { recursive: true, filter: p => !p.split(/[\\/]/).includes('__pycache__') && !p.endsWith('.pyc') });
    if (backup) await mkdir(backup, { recursive: true });
    for (const name of existing) { await rename(join(target, name), join(backup, name)); moved.push(name); }
    for (const name of names) { await rename(join(staging, name), join(target, name)); installed.push(name); }
  } catch (error) {
    for (const name of installed.reverse()) await rename(join(target, name), join(staging, name));
    for (const name of moved.reverse()) await rename(join(backup, name), join(target, name));
    throw error;
  } finally { await rm(staging, { recursive: true, force: true }); }
  console.log(JSON.stringify({ installed: names.map(n => join(target, n)), backup, guide: [
    '/frcstack create <requirements>', '/frcstack scout <competition URL/name>', '/frcstack replicate <team> <competition/latest>',
    '/frcstack review|compare|bom <request>', '/frcscout replicate <team> <competition/latest>',
    'Restart the host if discovery is cached. Without slash support say: Use frcstack to <goal>.',
    'Optional Autopilot: /autopilot frc <request>. No CAD connector, live tracker, credentials, or paid services were installed.'
  ] }, null, 2));
}
install().catch(error => { console.error(error.message); process.exitCode = 1; });
