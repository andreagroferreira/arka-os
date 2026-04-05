#!/usr/bin/env node

import { readFileSync } from 'fs';

const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
const versionFile = readFileSync('VERSION', 'utf8').trim();

if (pkg.version !== versionFile) {
  console.error(`Version mismatch: package.json=${pkg.version}, VERSION=${versionFile}`);
  process.exit(1);
}

console.log(`Version OK: ${pkg.version}`);
