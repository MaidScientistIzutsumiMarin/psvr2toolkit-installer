$SitePackages = '.venv\Lib\site-packages'

# nicegui-pack just adds all of nicegui using --add-data
pyinstaller.exe `
    --noconfirm `
    --onefile `
    --name psvr2toolkit-installer `
    --add-binary $SitePackages\githubkit\rest\__init__.py:githubkit\rest `
    --add-binary $SitePackages\githubkit\versions\v2022_11_28\models\__init__.py:githubkit\versions\v2022_11_28\models `
    --hidden-import winloop._noop `
    --collect-data mscerts `
    --collect-data nicegui `
    --collect-data signify `
    --optimize 1 `
    --windowed `
    src\psvr2toolkit_installer\__main__.py