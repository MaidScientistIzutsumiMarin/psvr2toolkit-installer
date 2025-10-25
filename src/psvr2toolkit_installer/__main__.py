from contextlib import contextmanager
from pathlib import Path
from sys import exit as sys_exit
from typing import TYPE_CHECKING
from urllib.request import urlopen
from webbrowser import open as webbrowser_open

from nicegui import app
from nicegui.ui import button, card, checkbox, dialog, label, log, notification, row, run, space, splitter  # pyright: ignore[reportUnknownVariableType]
from SteamPathFinder import get_game_path, get_steam_path

if TYPE_CHECKING:
    from collections.abc import Generator

    from nicegui.elements.mixins.disableable_element import DisableableElement

PLAYSTATION_VR2_APP = "2580190"


@contextmanager
def disable(*buttons: DisableableElement) -> Generator[None]:
    for b in buttons:
        b.disable()
    try:
        yield
    finally:
        for b in buttons:
            b.enable()


def get_driver_paths() -> tuple[Path, Path]:
    driver_path = Path(get_game_path(get_steam_path(), PLAYSTATION_VR2_APP, "PlayStation VR2 App")) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"
    return driver_path, driver_path.with_name("driver_playstation_vr2_orig.dll")


class Root:
    def __init__(self) -> None:
        with dialog() as self.app_dialog, card().classes("w-full"):
            label("It appears the PlayStation®VR2 App is not installed.")
            label("This is required for installing the Toolkit driver!").classes("text-warning")
            with row(align_items="center"):
                button("Install PlayStation®VR2 App", on_click=self.install_app)

        with splitter().classes("w-full") as root_splitter:
            with root_splitter.before:
                self.install_toolkit_button = button("Install PlayStation VR2 Toolkit", on_click=self.install_toolkit)
                self.uninstall_toolkit_button = button("Uninstall PlayStation VR2 Toolkit", on_click=self.uninstall_toolkit)
            with root_splitter.after:
                checkbox("Enable Experimental Eye Tracking")

        self.log = log()

        with row().classes("w-full"):
            space()
            button("Quit", on_click=app.shutdown)

    async def install_app(self) -> None:
        self.app_dialog.close()
        notification("Installing the PlayStation®VR2 App...", spinner=True)
        webbrowser_open(f"steam://install/{PLAYSTATION_VR2_APP}")

    async def install_toolkit(self) -> None:
        with disable(self.install_toolkit_button, self.uninstall_toolkit_button):
            try:
                driver_path, backup_driver_path = get_driver_paths()
                self.log.push(f"Starting installation...\nFound a driver at {driver_path}.")
                if backup_driver_path.exists():
                    self.log.push(f"The Toolkit driver has already been installed. {backup_driver_path.name} will not be touched.", classes="text-warning")
                else:
                    driver_path.rename(backup_driver_path)
                    self.log.push(f"Moved the Sony driver to {backup_driver_path.name}.")

                self.log.push("Downloading the latest Toolkit driver...")
                with urlopen("https://github.com/BnuuySolutions/PSVR2Toolkit/releases/latest/download/driver_playstation_vr2.dll") as response:  # noqa: ASYNC210
                    driver_path.write_bytes(response.read())

                self.log.push(f"Saved the Toolkit driver as {driver_path.name}.")
                self.log.push("Installation succeeded!", classes="text-positive")
            except FileNotFoundError:
                self.app_dialog.open()
            except Exception as exc:  # noqa: BLE001
                self.log.push(f"Installation failed!\n{exc}", classes="text-negative")

    async def uninstall_toolkit(self) -> None:
        with disable(self.install_toolkit_button, self.uninstall_toolkit_button):
            try:
                driver_path, backup_driver_path = get_driver_paths()
                self.log.push(f"Starting uninstallation...\nFound a driver at {driver_path}.")
                if backup_driver_path.exists():
                    backup_driver_path.replace(driver_path)
                    self.log.push(f"Moved the Sony driver to {driver_path.name} and deleted backup.")
                    self.log.push("Uninstallation succeeded!", classes="text-positive")
                else:
                    self.log.push(f"Could not find a Sony driver at {backup_driver_path.name}!\nThe Toolkit driver has probably not been installed.\nAborting uninstallation; no changes have been made!", classes="text-negative")
            except Exception as exc:  # noqa: BLE001
                self.log.push(f"Uninstallation failed!\n{exc}", classes="text-negative")


def main() -> None:
    run(Root, dark=None, native=True, reload=False)


if __name__ == "__main__":
    sys_exit(main())
