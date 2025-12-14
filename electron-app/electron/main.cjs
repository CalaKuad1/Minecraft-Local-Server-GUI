const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess;
let isQuitting = false;

// Identify if we are in dev mode
const isDev = !app.isPackaged;
const API_PORT = 8000;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 650,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false, // Reverted to fix blank screen in dev mode
      preload: path.join(__dirname, 'preload.cjs')
    },
    titleBarStyle: 'hidden', // Custom title bar
    titleBarOverlay: {
      color: '#000000',
      symbolColor: '#ffffff'
    },
    backgroundColor: '#111111',
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
    e.preventDefault();
    performShutdown();
  });
}

// IPC Handlers
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
  let pythonCmd = 'python'; // Or python3, or a bundled executable

  if (isDev) {
    // In dev, backend is at ../../backend/api_server.py
    scriptPath = path.join(__dirname, '../../backend/api_server.py');
  } else {
    // In prod, simple path logic or bundled executable
    // TODO: Handle resource path in production
    scriptPath = path.join(process.resourcesPath, 'backend/api_server.py');
  }

  console.log(`Starting Python backend: ${scriptPath}`);

  pythonProcess = spawn(pythonCmd, [scriptPath], {
    cwd: path.dirname(scriptPath),
    stdio: ['ignore', 'pipe', 'pipe'] // Capture stdout/stderr
  });

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
      path: '/stop',
      method: 'POST'
    }, (res) => {
      console.log(`Backend stop request status: ${res.statusCode}`);
      // Give it a moment to save data
      setTimeout(resolve, 2000);
    });

    req.on('error', (e) => {
      console.log('Backend unreachable or already stopped.');
      resolve();
    });

    req.setTimeout(2000, () => {
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

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

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
