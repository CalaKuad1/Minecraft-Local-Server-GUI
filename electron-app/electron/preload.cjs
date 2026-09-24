const { contextBridge, ipcRenderer } = require('electron');

// Shared API token, injected by the main process via additionalArguments.
const tokenArg = process.argv.find((a) => a.startsWith('--mlsg-token='));
const apiToken = tokenArg ? tokenArg.slice('--mlsg-token='.length) : '';

contextBridge.exposeInMainWorld('electron', {
    apiToken,
    getAppInfo: () => ipcRenderer.invoke('app:info'),
    openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
    openFile: () => ipcRenderer.invoke('dialog:openFile'),
    onCloseRequested: (callback) => {
        const listener = (_event, ...args) => callback(...args);
        ipcRenderer.on('app-close-requested', listener);
        return () => ipcRenderer.removeListener('app-close-requested', listener);
    },
    confirmClose: () => ipcRenderer.send('app-close-confirmed'),
    // Auto-update
    checkForUpdates: () => ipcRenderer.invoke('update:check'),
    installUpdate: () => ipcRenderer.invoke('update:install'),
    downloadUpdate: () => ipcRenderer.invoke('update:download'),
    setAutoUpdateMode: (mode) => ipcRenderer.invoke('update:setMode', mode),
    onUpdateStatus: (callback) => {
        const listener = (_event, status) => callback(status);
        ipcRenderer.on('update-status', listener);
        return () => ipcRenderer.removeListener('update-status', listener);
    },
    // Window Controls
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close')
});
