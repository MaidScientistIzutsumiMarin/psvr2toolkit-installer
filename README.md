# psvr2toolkit-installer

[psvr2toolkit-installer.exe]: https://github.com/MaidScientistIzutsumiMarin/psvr2toolkit-installer/releases/latest/download/psvr2toolkit-installer.exe

[Python]: https://python.org/download

[pip]: https://pypi.org

[PlayStation VR2 Toolkit]: https://github.com/BnuuySolutions/PSVR2Toolkit
[![PyPI - Version](https://img.shields.io/pypi/v/psvr2toolkit-installer)](https://python.org/pypi/psvr2toolkit-installer)

An unofficial tool that can install and configure the PlayStation VR2 Toolkit.

**Features:**

- A user interface.
- Installation button for [PlayStation VR2 Toolkit].
- Uninstallation button for [PlayStation VR2 Toolkit].
- Options to toggle experimental eyelid estimation.
- Update checkers for:
  - PlayStation VR2 Toolkit Installer.
  - [PlayStation VR2 Toolkit].
  
**Please submit an issue or contact us for features you want added/reimplemented.**

## Installation & Usage

### Downloadable Binary

| Pros | Cons |
| --- | --- |
| Easier to install | Harder to update |
| No risk of dependencies breaking | Dependencies may be older |

1. Download the latest release's [psvr2toolkit-installer.exe].
1. Launch `psvr2toolkit-installer.exe` in the install location.

### PyPi

| Pros | Cons |
| --- | --- |
| Easier to update | Harder to install |
| Dependencies may be newer | Dependencies may break |

1. Install the latest version of [Python]:
   - Windows: `winget install python3`
   - Linux (apt): `apt install python-pip`
   - Linux (pacman): `pacman install python-pip`
1. Install the [pip] package: `pip install psvr2toolkit-installer`
   - Alternatively, you can install from this repository: `pip install git+https://github.com/MaidScientistIzutsumiMarin/psvr2toolkit-installer.git`
   - On Linux, you will have to make a virtual environment or use the flag to install packages system-wide.
1. Run `psvr2toolkit-installer` from anywhere.
