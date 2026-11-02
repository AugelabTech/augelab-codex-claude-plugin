import { optionsFromArgs, runBridge } from './bridge.mjs';

try {
  if (Number(process.versions.node.split('.')[0]) < 22) {
    throw new Error('Node.js 22 or newer is required. Install an official supported Node.js LTS runtime.');
  }
  await runBridge(optionsFromArgs(process.argv.slice(2)));
} catch (error) {
  // Only locally authored argument/runtime errors reach here.
  process.stderr.write(`[augelab-mcp] ${error.message}\n`);
  process.exitCode = 1;
}
