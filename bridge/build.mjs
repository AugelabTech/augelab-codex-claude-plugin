import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { readFile, writeFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const result = await build({
  absWorkingDir: root,
  entryPoints: ['src/index.mjs'],
  outfile: 'dist/augelab-mcp.mjs',
  bundle: true,
  platform: 'node',
  target: 'node22',
  format: 'esm',
  minify: true,
  sourcemap: false,
  legalComments: 'none', // Full upstream license texts are bundled below.
  metafile: true,
});

const packages = new Map();
for (const input of Object.keys(result.metafile.inputs).filter(p => p.startsWith('node_modules/'))) {
  let dir = path.dirname(path.join(root, input));
  while (dir !== root) {
    let manifest;
    try { manifest = JSON.parse(await readFile(path.join(dir, 'package.json'), 'utf8')); } catch {}
    if (manifest?.name && manifest?.version) {
      const key = `${manifest.name}@${manifest.version}`;
      if (!packages.has(key)) {
        const files = (await readdir(dir)).filter(name => /^(licen[cs]e|copying|notice)(\.|$)/i.test(name)).sort();
        if (!files.length) throw new Error(`License text missing for ${key}`);
        const texts = await Promise.all(files.map(async name => `${name}\n${await readFile(path.join(dir, name), 'utf8')}`));
        packages.set(key, { name: manifest.name, version: manifest.version,
          license: manifest.license ?? 'See license text', texts });
      }
      break;
    }
    dir = path.dirname(dir);
  }
}
const inventory = [...packages.values()].sort((a, b) => a.name.localeCompare(b.name, 'en'));
await writeFile(path.join(root, 'dist/THIRD_PARTY_NOTICES.txt'),
  'Bundled dependencies of the AugeLab local MCP bridge\n\n' + inventory.map(p =>
    `${p.name}@${p.version} (${p.license})\n${p.texts.join('\n')}\n`).join('\n'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const inputs = {};
for (const file of ['package.json', 'package-lock.json', 'build.mjs', 'src/index.mjs', 'src/bridge.mjs']) {
  inputs[file] = sha(await readFile(path.join(root, file)));
}
await writeFile(path.join(root, 'dist/build-info.json'), JSON.stringify({
  name: 'augelab-local-mcp-bridge', version: '0.1.6', node: '>=22', inputs,
  bundleSha256: sha(await readFile(path.join(root, 'dist/augelab-mcp.mjs'))),
  dependencies: inventory.map(({ texts, ...p }) => p),
}, null, 2) + '\n');
console.log(`Built standalone bridge with ${inventory.length} bundled dependencies and license texts.`);
