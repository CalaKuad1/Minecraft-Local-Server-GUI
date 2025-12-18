const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
    openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
    onCloseRequested: (callback) => {
        ipcRenderer.on('app-close-requested', (event, ...args) => {
            callback(event, ...args);
            // Do not return anything to avoid IPC race condition
        });
    },
    confirmClose: () => ipcRenderer.send('app-close-confirmed')
});
