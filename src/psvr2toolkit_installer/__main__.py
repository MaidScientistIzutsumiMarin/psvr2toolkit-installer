from functools import partial
from pathlib import Path
from random import choice
from sys import exit as sys_exit
from time import sleep
from typing import get_args
from urllib.request import urlopen
from webbrowser import open as webbrowser_open

from nicegui import app
from nicegui.elements.spinner import SpinnerTypes
from nicegui.run import io_bound
from nicegui.ui import button, card, dialog, label, log, row, run, space, spinner  # pyright: ignore[reportUnknownVariableType]
from SteamPathFinder import get_game_path, get_steam_path

PLAYSTATION_VR2_APP = "2580190"


class Root:
    @staticmethod
    def get_driver_path() -> Path:
        return Path(get_game_path(get_steam_path(), PLAYSTATION_VR2_APP, "PlayStation VR2 App")) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"

    def __init__(self) -> None:
        with dialog().props("persistent") as self.app_dialog, card().classes("w-full"):
            label("It appears the PlayStation®VR2 App is not installed.")
            label("This is required for installing the Toolkit driver!").classes("text-warning")
            with row(align_items="center"):
                self.app_install_button = button("Install PlayStation®VR2 App", on_click=partial(io_bound, self.install_app))
                self.app_close_button = button("Close", on_click=self.app_dialog.close)
                self.spinner = spinner(choice(get_args(SpinnerTypes)), size="2em")  # noqa: S311

        self.install_toolkit_button = button("Install PlayStation VR2 Toolkit", on_click=partial(io_bound, self.install_toolkit))
        self.log = log()

        with row().classes("w-full"):
            space()
            button("Quit", on_click=app.shutdown)

        self.spinner.set_visibility(False)

    def install_app(self) -> None:
        self.app_install_button.disable()
        self.app_close_button.disable()
        self.spinner.set_visibility(True)

        webbrowser_open(f"steam://install/{PLAYSTATION_VR2_APP}")
        while True:
            try:
                if self.get_driver_path().exists():
                    break
            except FileNotFoundError:
                sleep(1)

        self.app_close_button.enable()
        self.spinner.set_visibility(False)

    def install_toolkit(self) -> None:
        self.install_toolkit_button.disable()

        try:
            driver_path = self.get_driver_path()
            self.log.push(f"Starting installation...\nFound the driver at {driver_path}.")

            backup_driver_path = driver_path.with_name("driver_playstation_vr2_orig.dll")
            if backup_driver_path.exists():
                self.log.push(f"The Toolkit driver has already been installed. {backup_driver_path.name} will not be touched.", classes="text-warning")
            else:
                driver_path.rename(backup_driver_path)
                self.log.push(f"Moved the Sony driver to {backup_driver_path.name}.")

            self.log.push("Downloading the latest Toolkit driver...")
            with urlopen("https://github.com/BnuuySolutions/PSVR2Toolkit/releases/latest/download/driver_playstation_vr2.dll") as response:
                driver_path.write_bytes(response.read())

            self.log.push(f"Saved the Toolkit driver as {driver_path.name}.")
            self.log.push("Installation succeeded!", classes="text-positive")
        except FileNotFoundError:
            self.app_dialog.open()
        except Exception as exc:  # noqa: BLE001
            self.log.push(f"Installation failed due to: {exc}", classes="text-negative")

        self.install_toolkit_button.enable()


def main() -> None:
    run(Root, dark=None, native=True, reload=False)


if __name__ == "__main__":
    sys_exit(main())
