$SitePackages = '.venv\Lib\site-packages'

pyinstaller.exe `
    --noconfirm `
    --onefile `
    --name psvr2toolkit-installer `
    --add-data $SitePackages\githubkit\rest\__init__.py:githubkit\rest `
    --add-data $SitePackages\githubkit\versions\v2022_11_28\models\__init__.py:githubkit\versions\v2022_11_28\models `
    --hidden-import winloop._noop `
    --collect-data mscerts `
    --collect-data signify `
    --splash Splash.png `
    --optimize 1 `
    --windowed `
    src\psvr2toolkit_installer\__main__.py &&
Remove-Item psvr2toolkit-installer.spec