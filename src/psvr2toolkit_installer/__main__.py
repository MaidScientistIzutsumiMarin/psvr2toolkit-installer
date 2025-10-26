from functools import partial
from pathlib import Path
from sys import exit as sys_exit
from typing import Literal
from urllib.request import urlopen

from nicegui import app
from nicegui.ui import button, checkbox, log, row, run, space, splitter  # pyright: ignore[reportUnknownVariableType]
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

type Verb = Literal["Install", "Uninstall"]


def get_driver_paths() -> tuple[Path, Path]:
    driver_path = Path(get_game_path(get_steam_path(), "2580190", "PlayStation VR2 App")) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"
    return driver_path, driver_path.with_name("driver_playstation_vr2_orig.dll")


def is_driver_signed(driver_path: Path) -> bool:
    with driver_path.open("rb") as fp:
        file = AuthenticodeFile.from_stream(fp)
        return file.explain_verify()[0] is AuthenticodeVerificationResult.OK


class Root:
    def __init__(self) -> None:
        with splitter().classes("w-full") as root_splitter:
            with root_splitter.before:
                self.install_toolkit_button = self.create_modify_toolkit_button("Install")
                self.uninstall_toolkit_button = self.create_modify_toolkit_button("Uninstall")
            with root_splitter.after:
                checkbox("Enable Experimental Eye Tracking").tooltip("Not implemented yet... sowwy").disable()

        self.log = log()

        with row().classes("w-full"):
            space()
            button("Quit", on_click=app.shutdown)

    def create_modify_toolkit_button(self, verb: Verb) -> button:
        return button(f"{verb} PSVR2 Toolkit", on_click=partial(self.modify_toolkit, verb))

    async def modify_toolkit(self, verb: Verb) -> None:
        self.install_toolkit_button.disable()
        self.uninstall_toolkit_button.disable()

        try:
            driver_paths = get_driver_paths()
            self.log.clear()
            self.log.push(f"Starting {verb}...")
            self.log.push("Installed driver: {}\nBackup driver: {}".format(*driver_paths), classes="text-grey")

            if verb == "Install":
                await self.install_toolkit(*get_driver_paths())
            else:
                await self.uninstall_toolkit(*get_driver_paths())

            self.log.push(f"{verb} succeeded!", classes="text-positive")
        except Exception as exc:  # noqa: BLE001
            self.log.push(f"{verb} failed!\n{exc}", classes="text-negative")
        finally:
            self.install_toolkit_button.enable()
            self.uninstall_toolkit_button.enable()

    async def install_toolkit(self, driver_path: Path, backup_driver_path: Path) -> None:
        if is_driver_signed(driver_path):
            driver_path.replace(backup_driver_path)
            self.log.push("Backed up the installed driver.")
        else:
            self.log.push("PSVR2 Toolkit has already been installed. The backup driver will not be touched.", classes="text-warning")

        self.log.push("Downloading the latest PSVR2 Toolkit release...")
        with urlopen("https://github.com/BnuuySolutions/PSVR2Toolkit/releases/latest/download/driver_playstation_vr2.dll") as response:  # noqa: ASYNC210
            driver_path.write_bytes(response.read())

    async def uninstall_toolkit(self, driver_path: Path, backup_driver_path: Path) -> None:
        if not is_driver_signed(driver_path) or driver_path.stat().st_mtime < backup_driver_path.stat().st_mtime:
            backup_driver_path.replace(driver_path)
            self.log.push("Restored the backup driver.")
        else:
            self.log.push("The installed driver is newer than the backup driver. Only deleting the backup driver.", classes="text-warning")
            backup_driver_path.unlink()

        self.log.push("It is recommended to verify PSVR2 App files through Steam.", classes="text-bold")


def main() -> None:
    run(Root, dark=None, native=True, reload=False)


if __name__ == "__main__":
    sys_exit(main())
