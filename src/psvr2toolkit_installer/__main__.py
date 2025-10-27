from contextlib import contextmanager
from functools import wraps
from json import dump, load
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.request import urlopen

from nicegui import app, ui
from nicegui.binding import bindable_dataclass
from nicegui.events import ValueChangeEventArguments  # noqa: TC002 Not sure why this is necessary, but it is.
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

if TYPE_CHECKING:
    from _io import TextIOWrapper
    from collections.abc import Awaitable, Callable, Generator


@bindable_dataclass
class Root:
    enabled: bool = True

    @staticmethod
    def modifies_installation[**P](verb: str) -> Callable[[Callable[P, Awaitable[object]]], Callable[P, Awaitable[None]]]:
        # Takes an str in the decorator syntax, which then returns the function decorator, which then wraps the function and does its things.
        # The typing is very scary, we know.
        def decorator(function: Callable[P, Awaitable[object]]) -> Callable[P, Awaitable[None]]:
            @wraps(function)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
                self = cast("Root", args[0])

                self.enabled = False
                notification = ui.notification(f"{verb}...", spinner=True, timeout=None)

                try:
                    self.log.push("---", classes="text-accent")
                    self.log.push(f"{verb} starting...")

                    await function(*args, **kwargs)

                    self.log.push(f"{verb} succeeded!", classes="text-positive")
                except Exception as exc:
                    self.log.push(f"{verb} failed!\n{exc}", classes="text-negative")
                    raise
                finally:
                    notification.message = f"{verb} done!"
                    notification.spinner = False
                    notification.timeout = 5
                    self.enabled = True

            return wrapper

        return decorator

    @staticmethod
    def get_driver_information() -> tuple[Path, Path, bool]:
        installed_driver_path = Path(get_game_path(get_steam_path(), "2580190", "PlayStation VR2 App")) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"

        with installed_driver_path.open("rb") as fp:
            file = AuthenticodeFile.from_stream(fp)
            return installed_driver_path, installed_driver_path.with_name("driver_playstation_vr2_orig.dll"), file.explain_verify()[0] is AuthenticodeVerificationResult.OK

    @staticmethod
    @contextmanager
    def open_steamvr_settings() -> Generator[TextIOWrapper]:
        with (Path(get_steam_path()) / "config" / "steamvr.vrsettings").open("r+", encoding="utf-8") as fp:
            yield fp

    def __post_init__(self) -> None:
        with ui.splitter().classes("w-full") as splitter:
            with splitter.before:
                ui.button("Install PSVR2 Toolkit", on_click=self.install_toolkit).bind_enabled_from(self)
                ui.button("Uninstall PSVR2 Toolkit", on_click=self.uninstall_toolkit).bind_enabled_from(self)

            with splitter.after:
                ui.checkbox("Enable Experimental Eyelid Estimation", value=self.is_eyelid_estimation_enabled(), on_change=self.toggle_eyelid_estimation).bind_enabled_from(self)

        self.log = ui.log()

        with ui.row().classes("w-full"):
            ui.space()
            ui.button("Quit", on_click=app.shutdown)

    @classmethod
    def is_eyelid_estimation_enabled(cls) -> bool:
        with cls.open_steamvr_settings() as fp:
            data: dict[str, dict[str, Any]] = load(fp)
        return data.get("playstation_vr2_ex", {}).get("enableEyelidEstimation", False)

    @modifies_installation("PSVR2 Toolkit installation")
    async def install_toolkit(self) -> None:
        installed_driver_path, orig_driver_path, driver_signed = self.get_driver_information()

        if driver_signed:
            self.log.push("Copying the installed driver...")
            installed_driver_path.replace(orig_driver_path)
        elif not orig_driver_path.exists():
            msg = "Error: The PSVR2 App has invalid files. Please verify its integrity."
            raise RuntimeError(msg)

        self.log.push("Downloading the latest PSVR2 Toolkit release...")
        with urlopen("https://github.com/BnuuySolutions/PSVR2Toolkit/releases/latest/download/driver_playstation_vr2.dll") as response:  # noqa: ASYNC210
            self.log.push("Installing the downloaded driver...")
            installed_driver_path.write_bytes(response.read())

    @modifies_installation("PSVR2 Toolkit uninstallation")
    async def uninstall_toolkit(self) -> None:
        installed_driver_path, orig_driver_path, driver_signed = self.get_driver_information()

        if not driver_signed or installed_driver_path.stat().st_mtime < orig_driver_path.stat().st_mtime:
            self.log.push("Restoring the original driver...")
            orig_driver_path.replace(installed_driver_path)
        else:
            self.log.push("The installed driver is newer than the original driver. Only deleting the original driver...", classes="text-warning")
            orig_driver_path.unlink()

        self.log.push("It is recommended to verify PSVR2 App files through Steam.", classes="text-bold")

    @modifies_installation("Toggling eyelid estimation")
    async def toggle_eyelid_estimation(self, handler: ValueChangeEventArguments) -> None:
        self.log.push("Loading SteamVR settings...")
        with self.open_steamvr_settings() as fp:
            data: dict[str, dict[str, object]] = load(fp)

            self.log.push("Modifying SteamVR settings...")
            if handler.value:
                data["playstation_vr2_ex"] = {"enableEyelidEstimation": True}
            else:
                del data["playstation_vr2_ex"]

            self.log.push("Saving modified SteamVR settings...")

            # Seek to the start of the file then truncate to clear it.
            fp.seek(0)
            fp.truncate()

            # Don't know if ensure_ascii is necessary.
            # indent probably isn't as long as Steam has a normal JSON reader.
            # But this maintains the original structure as much as possible.
            dump(data, fp, ensure_ascii=False, indent=3)


def main() -> None:
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        Root,
        title="PSVR2Toolkit Installer",
        dark=None,
        native=True,
        reload=False,
    )
