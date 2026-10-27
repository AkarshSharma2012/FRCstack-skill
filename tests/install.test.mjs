import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, symlink, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const installer = resolve('scripts/install.mjs');
const run = (...args) => spawnSync(process.execPath, [installer, ...args], { encoding: 'utf8' });

test('installs both skills, refuses overwrite, backs up each replaced skill', async () => {
  const root = await mkdtemp(join(tmpdir(), 'frcstack-install-'));
  const target = join(root, 'skills');
  assert.equal(run('--target', target).status, 0);
  assert.match(await readFile(join(target, 'frcstack', 'SKILL.md'), 'utf8'), /^name: frcstack$/m);
  assert.match(await readFile(join(target, 'frcscout', 'SKILL.md'), 'utf8'), /^name: frcscout$/m);
  await writeFile(join(target, 'frcstack', 'my-note.txt'), 'keep this');
  assert.notEqual(run('--target', target).status, 0);
  assert.equal(await readFile(join(target, 'frcstack', 'my-note.txt'), 'utf8'), 'keep this');
  const replaced = run('--target', target, '--replace', '--backup-dir', join(root, 'backups'));
  assert.equal(replaced.status, 0, replaced.stderr);
  const result = JSON.parse(replaced.stdout);
  assert.equal(await readFile(join(result.backup, 'frcstack', 'my-note.txt'), 'utf8'), 'keep this');
  assert.equal((await readdir(target)).some(name => name.includes('staging')), false);
});

test('rejects missing arguments, unknown flags, source overlap, and nested backups', async () => {
  const root = await mkdtemp(join(tmpdir(), 'frcstack-input-'));
  for (const args of [[], ['--target'], ['--host', 'other'], ['--target', resolve('skills')], ['--target', root, '--wat'], ['--target', root, '--backup-dir', join(root, 'backups')]]) {
    assert.notEqual(run(...args).status, 0, JSON.stringify(args));
  }
});

test('refuses replacing an unrelated directory', async () => {
  const root = await mkdtemp(join(tmpdir(), 'frcstack-unrelated-'));
  await mkdir(join(root, 'frcstack'));
  await writeFile(join(root, 'frcstack', 'SKILL.md'), 'name: other\n');
  assert.notEqual(run('--target', root, '--replace').status, 0);
  assert.equal(await readFile(join(root, 'frcstack', 'SKILL.md'), 'utf8'), 'name: other\n');
});

test('refuses a symlink ancestor without modifying its destination', async t => {
  const root = await mkdtemp(join(tmpdir(), 'frcstack-link-'));
  const outside = join(root, 'outside');
  await mkdir(outside);
  try { await symlink(outside, join(root, 'linked'), process.platform === 'win32' ? 'junction' : 'dir'); }
  catch (error) { if (error.code === 'EPERM') return t.skip('host does not permit test symlinks'); throw error; }
  assert.notEqual(run('--target', join(root, 'linked', 'skills')).status, 0);
  assert.deepEqual(await readdir(outside), []);
});
