/**
 * Post-build script to fix CommonJS output
 * Adds .cjs extension handling and creates package.json for CJS directory
 */

import { writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const cjsDir = join(__dirname, '..', 'dist', 'cjs');

// Create package.json for CJS directory to ensure proper module resolution
const cjsPackageJson = {
  type: 'commonjs',
};

if (!existsSync(cjsDir)) {
  mkdirSync(cjsDir, { recursive: true });
}

writeFileSync(join(cjsDir, 'package.json'), JSON.stringify(cjsPackageJson, null, 2));

console.log('✅ Created CJS package.json');
