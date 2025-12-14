const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
    openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
    onCloseRequested: (callback) => ipcRenderer.on('app-close-requested', callback),
    confirmClose: () => ipcRenderer.send('app-close-confirmed')
});
