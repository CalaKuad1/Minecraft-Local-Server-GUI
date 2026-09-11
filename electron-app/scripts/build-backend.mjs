// Rebuilds the Python backend with PyInstaller before packaging the app.
//
// WHY THIS EXISTS
// ---------------
// electron-builder bundles the whole `backend/` folder via `extraResources`.
// If `backend/api_server.exe` is committed to git (it was), a local
// `npm run electron:build` will happily package that stale binary instead of
// the current Python source — shipping an outdated (and historically leaky)
// backend. CI rebuilt it, but local builds did not. This script makes the
// rebuild mandatory and explicit.

import { spawnSync } from 'node:child_process';
import { existsSync, renameSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.resolve(__dirname, '../../backend');
const isWin = process.platform === 'win32';
const python = process.env.PYTHON || (isWin ? 'python' : 'python3');

const run = (args, opts = {}) =>
  spawnSync(python, args, { encoding: 'utf8', ...opts });

// 1. PyInstaller must be available.
const check = run(['-m', 'PyInstaller', '--version']);
if (check.status !== 0) {
  console.error('\n[build-backend] PyInstaller is not available for: ' + python);
  console.error('Install it first:  pip install pyinstaller\n');
  process.exit(1);
}

// 2. Build. Flags intentionally mirror .github/workflows/release.yml.
const args = [
  '-m', 'PyInstaller',
  '--onefile',
  '--noconsole',
  '--noconfirm',
  '--collect-all', 'uvicorn',
  '--collect-all', 'fastapi',
  '--collect-all', 'wsproto',
  '--collect-all', 'requests',
  '--collect-all', 'pydantic',
  '--hidden-import=uvicorn.logging',
  '--hidden-import=uvicorn.loops',
  '--hidden-import=uvicorn.loops.auto',
  '--hidden-import=uvicorn.protocols',
  '--hidden-import=uvicorn.protocols.http',
  '--hidden-import=uvicorn.protocols.http.auto',
  '--hidden-import=uvicorn.protocols.websockets',
  '--hidden-import=uvicorn.protocols.websockets.auto',
  '--hidden-import=uvicorn.lifespan',
  '--hidden-import=uvicorn.lifespan.on',
  '--hidden-import=starlette',
  '--hidden-import=starlette.routing',
  '--hidden-import=starlette.middleware',
  '--hidden-import=starlette.requests',
  '--hidden-import=starlette.responses',
  '--hidden-import=multipart',
  '--hidden-import=python_multipart',
  'api_server.py',
];

console.log(`[build-backend] Building ${isWin ? 'api_server.exe' : 'api_server'} ...`);
const res = spawnSync(python, args, { cwd: backendDir, stdio: 'inherit' });
if (res.status !== 0) {
  console.error('[build-backend] PyInstaller failed.');
  process.exit(res.status || 1);
}

// 3. Move the fresh artifact next to the sources so electron-builder bundles it.
const built = path.join(backendDir, 'dist', isWin ? 'api_server.exe' : 'api_server');
const dest = path.join(backendDir, isWin ? 'api_server.exe' : 'api_server');

if (!existsSync(built)) {
  console.error(`[build-backend] Expected artifact not found: ${built}`);
  process.exit(1);
}

rmSync(dest, { force: true });
renameSync(built, dest);
console.log(`[build-backend] Backend updated -> ${dest}`);
