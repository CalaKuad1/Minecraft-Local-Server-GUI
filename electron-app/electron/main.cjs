const { app, BrowserWindow, ipcMain, dialog, Tray, Menu } = require('electron');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess;
let isQuitting = false;
let tray = null;

// Prevent multiple instances: each instance would spawn its own backend
// (only one can bind port 8000), leaking processes and RAM.
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Identify if we are in dev mode
const isDev = !app.isPackaged;
const API_PORT = 8000;

// Shared secret between the renderer, Electron and the Python backend.
// Generated fresh on every launch; never written to disk.
const API_TOKEN = crypto.randomBytes(32).toString('hex');

// Auto-update (optional: only present once `npm install` pulled electron-updater)
let autoUpdater = null;
try {
  ({ autoUpdater } = require('electron-updater'));
} catch (_) {
  autoUpdater = null;
}

// Ensure Windows shows the correct app name in taskbar/start menu grouping
// (must match electron-builder appId)
try {
  app.setAppUserModelId('com.minecraft.localservergui');
} catch (_) { }
try {
  app.setName('Minecraft Local Server GUI');
} catch (_) { }

function createWindow() {
  const iconFile = process.platform === 'win32' ? 'icon.ico' : 'logo2.png';
  const iconPath = path.join(__dirname, isDev ? `../public/images/${iconFile}` : `../dist/images/${iconFile}`);

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 650,
    title: 'Minecraft Local Server GUI',
    icon: iconPath,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      preload: path.join(__dirname, 'preload.cjs'),
      // Expose the API token to the preload script (sandbox-safe, synchronous).
      additionalArguments: [`--mlsg-token=${API_TOKEN}`]
    },
    frame: false,
    backgroundColor: '#0f0f0f',
    show: true
  });

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // mainWindow.webContents.openDevTools(); 
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('close', (e) => {
    if (isQuitting) {
      // Already in shutdown sequence — let the window close
      return;
    }

    e.preventDefault();

    // Smart close: check if any server is running
    checkForRunningServers().then((hasRunning) => {
      if (hasRunning && process.platform === 'win32') {
        // Windows + servers running: hide to tray so servers keep running
        mainWindow.hide();
        if (tray) {
          try {
            tray.displayBalloon({
              title: 'Minecraft Server GUI',
              content: 'Servers still running. App minimized to tray.'
            });
          } catch (_) { /* displayBalloon is Windows-only */ }
        }
      } else {
        // No servers running OR Linux → perform clean shutdown
        performShutdown();
      }
    }).catch(() => {
      // Backend unreachable → just quit
      performShutdown();
    });
  });
}

// IPC Handlers
ipcMain.handle('window:minimize', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.minimize();
  }
});

ipcMain.handle('window:maximize', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('window:close', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.close();
  }
});

// --- App info (version + user paths) ---
ipcMain.handle('app:info', () => ({
  version: app.getVersion(),
  home: app.getPath('home'),
  documents: app.getPath('documents')
}));

// --- Auto-update IPC ---
ipcMain.handle('update:check', async () => {
  if (!autoUpdater || !app.isPackaged) return { state: 'disabled' };
  try {
    await autoUpdater.checkForUpdates();
    return { state: 'checking' };
  } catch (e) {
    return { state: 'error', message: String(e?.message || e) };
  }
});

ipcMain.handle('update:install', () => {
  if (autoUpdater) {
    isQuitting = true;
    autoUpdater.quitAndInstall();
  }
});

// Renderer applies the new auto-update policy immediately after settings save.
ipcMain.handle('update:setMode', (_e, mode) => {
  if (configureUpdater) configureUpdater(mode);
  return { ok: true };
});

// Used when the policy is 'ask': the user explicitly chose to download.
ipcMain.handle('update:download', async () => {
  if (!autoUpdater || !app.isPackaged || autoUpdateMode !== 'ask') return { state: 'disabled' };
  try {
    await autoUpdater.downloadUpdate();
    return { state: 'downloading' };
  } catch (e) {
    return { state: 'error', message: String(e?.message || e) };
  }
});

ipcMain.handle('dialog:openDirectory', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  if (canceled) {
    return null;
  } else {
    return filePaths[0];
  }
});

ipcMain.handle('dialog:openFile', async () => {
  const filters = [];
  if (process.platform === 'win32') {
    filters.push({ name: 'Executable', extensions: ['exe'] });
  }
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: filters.length > 0 ? filters : undefined
  });
  if (canceled) return null;
  return filePaths[0];
});

// Old handler removed - shutdown is now main-process driven


function startPythonBackend() {
  let scriptPath;
  let binaryPath;
  const isWin = process.platform === 'win32';
  let pythonCmd = process.env.PYTHON || (isWin ? 'python' : 'python3');

  if (isDev) {
    scriptPath = path.join(__dirname, '../../backend/api_server.py');
    if (!process.env.PYTHON) {
      const fs = require('fs');
      const venvPythonWin = path.join(__dirname, '../../backend/venv/Scripts/python.exe');
      const venvPythonUnix = path.join(__dirname, '../../backend/venv/bin/python');
      const envPythonWin = path.join(__dirname, '../../backend/env/Scripts/python.exe');
      const envPythonUnix = path.join(__dirname, '../../backend/env/bin/python');
      if (isWin && fs.existsSync(venvPythonWin)) {
        pythonCmd = venvPythonWin;
      } else if (!isWin && fs.existsSync(venvPythonUnix)) {
        pythonCmd = venvPythonUnix;
      } else if (isWin && fs.existsSync(envPythonWin)) {
        pythonCmd = envPythonWin;
      } else if (!isWin && fs.existsSync(envPythonUnix)) {
        pythonCmd = envPythonUnix;
      }
    }
  } else {
    // Check for bundled binary in production
    const binaryName = isWin ? 'api_server.exe' : 'api_server';
    binaryPath = path.join(process.resourcesPath, 'backend', binaryName);
    scriptPath = path.join(process.resourcesPath, 'backend/api_server.py');
  }

  // Use bundled binary if it exists
  const useBinary = binaryPath && require('fs').existsSync(binaryPath);

  if (useBinary) {
    console.log(`Starting Bundled Backend: ${binaryPath}`);
    pythonProcess = spawn(binaryPath, ['--parent-pid', process.pid.toString()], {
      cwd: path.dirname(binaryPath),
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      env: { ...process.env, MLSG_TOKEN: API_TOKEN }
    });
  } else {
    console.log(`Starting Python Script: ${scriptPath} (using ${pythonCmd})`);
    pythonProcess = spawn(pythonCmd, [scriptPath, '--parent-pid', process.pid.toString()], {
      cwd: path.dirname(scriptPath),
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      env: { ...process.env, MLSG_TOKEN: API_TOKEN }
    });
  }

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python]: ${data}`);
  });

  let stderrOutput = '';
  pythonProcess.stderr.on('data', (data) => {
    const text = data.toString();
    console.error(`[Python Err]: ${text}`);
    // Keep only the tail: this previously grew for the whole app lifetime.
    stderrOutput = (stderrOutput + text).slice(-4000);
  });

  pythonProcess.on('error', (err) => {
    console.error('Failed to start python process:', err);
    dialog.showErrorBox('Backend Error', `Failed to start Python backend:\n${err.message}`);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python process exited with code ${code} and signal ${signal}`);
    if (code !== 0 && code !== null) {
      // Only show if it wasn't a clean exit (and not killed by us)
      if (!isQuitting) {
        dialog.showErrorBox('Backend Crashed', `Python backend exited unexpectedly (Code ${code}).\n\nLog:\n${stderrOutput.slice(-500)}`);
      }
    }
  });
}

const checkBackend = () => {
  return new Promise((resolve, reject) => {
    const req = http.get({
      hostname: '127.0.0.1',
      port: API_PORT,
      path: '/status',
      headers: { 'X-MLSG-Token': API_TOKEN }
    }, (res) => {
      if (res.statusCode === 200) {
        resolve(true);
      } else {
        reject(false);
      }
    });
    req.on('error', () => {
      reject(false);
    });
    req.end();
  });
};

// --- Robust Shutdown Logic ---
const shutdownBackend = () => {
  return new Promise((resolve) => {
    console.log('Sending STOP signal to backend...');

    // 1. Send POST /stop
    const req = http.request({
      hostname: '127.0.0.1',
      port: API_PORT,
      path: '/system/shutdown',
      method: 'POST',
      headers: { 'X-MLSG-Token': API_TOKEN }
    }, (res) => {
      console.log(`Backend stop request status: ${res.statusCode}`);
      // The backend now waits for servers in a thread. 
      // We will wait up to 30s for the process to exit naturally.
      // But we'll give it a head start here.
      setTimeout(resolve, 3000);
    });

    req.on('error', () => {
      console.log('Backend unreachable or already stopped.');
      resolve();
    });

    req.setTimeout(35000, () => {
      req.destroy();
      resolve();
    });

    req.end();
  });
};

const performShutdown = async () => {
  if (isQuitting) return;
  isQuitting = true;

  console.log('Starting graceful shutdown sequence...');

  // Notify frontend to show spinner (if window exists)
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('app-close-requested'); // Reuse this event name for "Show Spinner"
  }

  // Check/Stop Backend
  try {
    await shutdownBackend();
  } catch (err) {
    console.error('Error during backend shutdown:', err);
  }

  // Kill Python Process Forcefully if still alive
  if (pythonProcess) {
    console.log('Killing python process...');
    pythonProcess.kill();
  }

  console.log('Exiting Electron...');
  app.exit(0);
};

function createTray() {
  let iconPath;
  try {
    if (process.platform === 'win32') {
      iconPath = path.join(__dirname, isDev ? '../public/images/icon.ico' : '../dist/images/icon.ico');
    } else {
      iconPath = path.join(__dirname, isDev ? '../public/images/logo2.png' : '../dist/images/logo2.png');
    }
    tray = new Tray(iconPath);
  } catch (err) {
    console.error('Failed to create tray icon:', err);
    return; // Tray not supported (e.g. Wayland without tray extension)
  }
  
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show App', click: () => { if (mainWindow) mainWindow.show(); } },
    { type: 'separator' },
    { label: 'Stop Server & Quit', click: () => { 
        performShutdown(); 
      } 
    }
  ]);
  
  tray.setToolTip('Minecraft Server GUI');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    if (mainWindow) mainWindow.show();
  });
}

// --- Helper: Check if any Minecraft server is running ---
const checkForRunningServers = () => {
  return new Promise((resolve, reject) => {
    const req = http.get({
      hostname: '127.0.0.1',
      port: API_PORT,
      path: '/servers/running',
      headers: { 'X-MLSG-Token': API_TOKEN }
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve(parsed.any_running === true);
        } catch {
          resolve(false);
        }
      });
    });
    req.on('error', () => reject(false));
    req.setTimeout(2000, () => { req.destroy(); reject(false); });
    req.end();
  });
};

// --- Auto-update: policy-controlled check / download / install ---
// Policy is stored by the backend (app_settings.auto_update) in one of three modes:
//   'auto' → check + download automatically, install on quit (previous behavior)
//   'ask'  → check automatically, but only download when the user confirms
//   'off'  → never check automatically
let autoUpdateMode = 'ask';
let autoUpdateTimer = null;
let configureUpdater = null; // set once setupAutoUpdater runs; used by update:setMode
const UPDATE_POLICY_DEFAULT = 'ask';
const UPDATE_INTERVAL_MS = 3 * 60 * 60 * 1000;

// Read a single key from the backend's app settings (the source of truth).
const fetchAppSetting = (key, fallback) => new Promise((resolve) => {
  const req = http.get({
    hostname: '127.0.0.1',
    port: API_PORT,
    path: '/app-settings',
    headers: { 'X-MLSG-Token': API_TOKEN }
  }, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        const parsed = JSON.parse(data);
        resolve(parsed[key] !== undefined ? parsed[key] : fallback);
      } catch {
        resolve(fallback);
      }
    });
  });
  req.on('error', () => resolve(fallback));
  req.setTimeout(3000, () => { req.destroy(); resolve(fallback); });
  req.end();
});

const isBackendUp = async () => {
  try {
    return await checkBackend();
  } catch {
    return false;
  }
};

function setupAutoUpdater() {
  if (!autoUpdater || !app.isPackaged) return;

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  const send = (status) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-status', status);
    }
  };

  autoUpdater.on('checking-for-update', () => send({ state: 'checking' }));
  autoUpdater.on('update-available', (info) => {
    // In 'ask' mode nothing is auto-downloaded; flag it so the renderer can
    // offer a download button instead of pretending it already started.
    send({ state: 'available', version: info?.version, manual: autoUpdateMode === 'ask' });
  });
  autoUpdater.on('update-not-available', () => send({ state: 'up-to-date' }));
  autoUpdater.on('download-progress', (p) => send({ state: 'downloading', percent: Math.round(p?.percent || 0) }));
  autoUpdater.on('update-downloaded', (info) => send({ state: 'downloaded', version: info?.version }));
  autoUpdater.on('error', (err) => {
    console.error('Auto-update error:', err);
    send({ state: 'error', message: String(err?.message || err) });
  });

  const check = () => {
    autoUpdater.checkForUpdatesAndNotify().catch((e) => {
      console.error('Auto-update check failed:', e?.message || e);
    });
  };

  // Apply the persisted policy: controls automatic download/install and whether
  // any background checks run at all.
  configureUpdater = (mode) => {
    if (mode !== 'auto' && mode !== 'ask' && mode !== 'off') mode = UPDATE_POLICY_DEFAULT;
    autoUpdateMode = mode;
    autoUpdater.autoDownload = mode === 'auto';
    autoUpdater.autoInstallOnAppQuit = mode === 'auto';
    if (autoUpdateTimer) {
      clearInterval(autoUpdateTimer);
      autoUpdateTimer = null;
    }
    if (mode === 'off') return;
    autoUpdateTimer = setInterval(check, UPDATE_INTERVAL_MS);
    check();
  };

  // Load the stored policy once the backend is reachable, then start.
  (async () => {
    for (let i = 0; i < 30 && !(await isBackendUp()); i++) {
      await new Promise((r) => setTimeout(r, 500));
    }
    configureUpdater(await fetchAppSetting('auto_update', UPDATE_POLICY_DEFAULT));
  })();
}

app.whenReady().then(() => {
  if (!gotTheLock) return;
  startPythonBackend();
  createWindow();
  createTray();
  setupAutoUpdater();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    performShutdown();
  }
});

// For safety, ensure we catch other exit signals
app.on('will-quit', () => {
  if (pythonProcess) pythonProcess.kill();
});
