const { app, BrowserWindow, ipcMain, dialog, Tray, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess;
let isQuitting = false;
let tray = null;

// Identify if we are in dev mode
const isDev = !app.isPackaged;
const API_PORT = 8000;

// Ensure Windows shows the correct app name in taskbar/start menu grouping
// (must match electron-builder appId)
try {
  app.setAppUserModelId('com.minecraft.localservergui');
} catch (_) { }
try {
  app.setName('Minecraft Local Server GUI');
} catch (_) { }

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 650,
    title: 'Minecraft Local Server GUI',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true, // Secure mode enabled
      preload: path.join(__dirname, 'preload.cjs')
    },
    frame: false, // Custom frame
    backgroundColor: '#0f0f0f',
    show: true // Force show immediately for debugging
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
  mainWindow.minimize();
});

ipcMain.handle('window:maximize', () => {
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow.maximize();
  }
});

ipcMain.handle('window:close', () => {
  mainWindow.close();
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

// Old handler removed - shutdown is now main-process driven


function startPythonBackend() {
  let scriptPath;
  let binaryPath;
  const isWin = process.platform === 'win32';
  let pythonCmd = isWin ? 'python' : 'python3';

  if (isDev) {
    scriptPath = path.join(__dirname, '../../backend/api_server.py');
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
    pythonProcess = spawn(binaryPath, [], {
      cwd: path.dirname(binaryPath),
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false
    });
  } else {
    console.log(`Starting Python Script: ${scriptPath}`);
    pythonProcess = spawn(pythonCmd, [scriptPath], {
      cwd: path.dirname(scriptPath),
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false
    });
  }

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python]: ${data}`);
  });

  let stderrOutput = '';
  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Err]: ${data}`);
    stderrOutput += data.toString();
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
    const req = http.get(`http://127.0.0.1:${API_PORT}/status`, (res) => {
      if (res.statusCode === 200) {
        resolve(true);
      } else {
        reject(false);
      }
    });
    req.on('error', (e) => {
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
      method: 'POST'
    }, (res) => {
      console.log(`Backend stop request status: ${res.statusCode}`);
      // The backend now waits for servers in a thread. 
      // We will wait up to 30s for the process to exit naturally.
      // But we'll give it a head start here.
      setTimeout(resolve, 3000);
    });

    req.on('error', (e) => {
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
      // Linux: use PNG for tray icon (ICO not always supported)
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
    const req = http.get(`http://127.0.0.1:${API_PORT}/servers/running`, (res) => {
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

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();
  createTray();

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
