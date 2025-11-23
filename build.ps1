pyinstaller.exe `
    --noconfirm `
    --onefile `
    --name psvr2toolkit-installer `
    --hidden-import winloop._noop `
    --collect-data mscerts `
    --collect-data signify `
    --splash Splash.png `
    --optimize 1 `
    --windowed `
    src\psvr2toolkit_installer\__main__.py &&
Remove-Item psvr2toolkit-installer.spec