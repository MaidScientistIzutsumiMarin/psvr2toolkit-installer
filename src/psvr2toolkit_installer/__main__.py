from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial, wraps
from hashlib import file_digest, sha256
from hmac import compare_digest
from json import dump, load
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from aiohttp import ClientSession
from github import Github
from nicegui import app, ui
from nicegui.binding import bindable_dataclass
from nicegui.events import ClickEventArguments, Handler, ValueChangeEventArguments  # noqa: TC002 Not sure why this is necessary, but it is.
from nicegui.run import io_bound
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

if TYPE_CHECKING:
    from _io import TextIOWrapper
    from collections.abc import Awaitable, Callable, Generator

    from github.GitRelease import GitRelease

__version__ = "0.2.0"

PSVR2_APP = "PSVR2 App"
PSVR2_TOOLKIT = "PSVR2 Toolkit"
PSVR2_TOOLKIT_INSTALLER = "PSVR2 Toolkit Installer"
STEAMVR = "SteamVR"

PSVR2_SETTINGS_KEY = "playstation_vr2_ex"
EYELID_ESIMATION_KEY = "enableEyelidEstimation"


@dataclass
class DriverInfo:
    signed: bool = field(init=False)
    original_path: Path = field(init=False)
    installed_path: Path = field(default_factory=lambda: Path(get_game_path(get_steam_path(), "2580190", "PlayStation VR2 App")) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll")

    def __post_init__(self) -> None:
        with self.installed_path.open("rb") as fp:
            file = AuthenticodeFile.from_stream(fp)
            self.signed = file.explain_verify()[0] is AuthenticodeVerificationResult.OK

        self.original_path = self.installed_path.with_name("driver_playstation_vr2_orig.dll")


@bindable_dataclass
class Root:
    enabled = True
    spinner_visible = False

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
    @contextmanager
    def open_steamvr_settings() -> Generator[TextIOWrapper]:
        with (Path(get_steam_path()) / "config" / "steamvr.vrsettings").open("r+", encoding="utf-8") as fp:
            yield fp

    @classmethod
    def is_eyelid_estimation_enabled(cls) -> bool:
        with cls.open_steamvr_settings() as fp:
            data: dict[str, dict[str, Any]] = load(fp)
        return data.get(PSVR2_SETTINGS_KEY, {}).get(EYELID_ESIMATION_KEY, False)

    def __post_init__(self) -> None:
        self.update_dialog = ui.dialog()

        with ui.splitter().classes("w-full") as splitter:
            with splitter.before:
                ui.button(f"Install {PSVR2_TOOLKIT}", on_click=self.install_toolkit).bind_enabled_from(self)
                ui.button(f"Uninstall {PSVR2_TOOLKIT}", on_click=self.uninstall_toolkit).bind_enabled_from(self)
                ui.separator()
                with ui.row(align_items="center"):
                    ui.button("Check for Updates", on_click=partial(io_bound, self.check_for_updates)).bind_enabled_from(self)
                    ui.spinner(size="2em").bind_visibility_from(self, "spinner_visible")

            with splitter.after:
                ui.checkbox("Enable Experimental Eyelid Estimation", value=self.is_eyelid_estimation_enabled(), on_change=self.toggle_eyelid_estimation).bind_enabled_from(self)

        self.log = ui.log()

        with ui.row().classes("w-full"):
            ui.space()
            ui.button("Quit", on_click=app.shutdown)

    @modifies_installation(f"{PSVR2_TOOLKIT} installation")
    async def install_toolkit(self) -> None:
        driver_info = DriverInfo()

        if driver_info.signed:
            self.log.push("Copying the installed driver...")
            driver_info.installed_path.replace(driver_info.original_path)
        elif not driver_info.original_path.exists():
            msg = f"Error: The {PSVR2_APP} has invalid files. Please verify its integrity."
            raise RuntimeError(msg)

        self.log.push(f"Downloading the latest {PSVR2_TOOLKIT} release...")
        async with ClientSession(raise_for_status=True) as session, session.get("https://github.com/BnuuySolutions/PSVR2Toolkit/releases/latest/download/driver_playstation_vr2.dll") as response:
            self.log.push("Installing the downloaded driver...")
            driver_info.installed_path.write_bytes(await response.read())

    @modifies_installation(f"{PSVR2_TOOLKIT} uninstallation")
    async def uninstall_toolkit(self) -> None:
        driver_info = DriverInfo()

        if not driver_info.signed or driver_info.installed_path.stat().st_mtime < driver_info.original_path.stat().st_mtime:
            self.log.push("Restoring the original driver...")
            driver_info.original_path.replace(driver_info.installed_path)
        else:
            self.log.push("The installed driver is newer than the original driver. Only deleting the original driver...", classes="text-warning")
            driver_info.original_path.unlink()

        self.log.push(f"It is recommended to verify {PSVR2_APP} files through Steam.", classes="text-bold")

    @modifies_installation("Toggling eyelid estimation")
    async def toggle_eyelid_estimation(self, handler: ValueChangeEventArguments) -> None:
        self.log.push(f"Loading {STEAMVR} settings...")
        with self.open_steamvr_settings() as fp:
            data: dict[str, dict[str, object]] = load(fp)

            self.log.push(f"Modifying {STEAMVR} settings...")
            if handler.value:
                data[PSVR2_SETTINGS_KEY] = {EYELID_ESIMATION_KEY: True}
            else:
                del data[PSVR2_SETTINGS_KEY]

            self.log.push(f"Saving modified {STEAMVR} settings...")

            # Seek to the start of the file then truncate to clear it.
            fp.seek(0)
            fp.truncate()

            # Don't know if ensure_ascii is necessary.
            # indent probably isn't as long as Steam has a normal JSON reader.
            # But this maintains the original structure as much as possible.
            dump(data, fp, ensure_ascii=False, indent=3)

    def check_for_updates(self) -> None:
        self.spinner_visible = True
        self.update_dialog.clear()

        try:
            with self.update_dialog, ui.card(), ui.grid(columns="auto 1fr 2fr").classes("items-center"), Github(lazy=True) as github:
                release = github.get_repo("BnuuySolutions/PSVR2Toolkit").get_latest_release()
                for asset in release.assets:
                    if asset.digest is not None and asset.name == "driver_playstation_vr2.dll":
                        with DriverInfo().installed_path.open("rb") as fp:
                            self.show_update(
                                PSVR2_TOOLKIT,
                                release,
                                self.install_toolkit,
                                has_update=not compare_digest(file_digest(fp, sha256).hexdigest(), asset.digest.lstrip("sha256:")),
                            )

                release = github.get_repo("MaidScientistIzutsumiMarin/psvr2toolkit-installer").get_latest_release()
                self.show_update(
                    PSVR2_TOOLKIT_INSTALLER,
                    release,
                    None,
                    has_update=__version__ != release.tag_name.lstrip("v"),
                )

            self.update_dialog.open()
        except Exception as exc:
            ui.notify(f"An error occurred while checking for updates: {exc}", color="red")
            raise
        finally:
            self.spinner_visible = False

    def show_update(self, name: str, release: GitRelease, on_click: Handler[ClickEventArguments] | None, *, has_update: bool) -> None:
        ui.label(name).classes("font-bold")
        ui.label(release.tag_name).classes("text-secondary")
        ui.button("Update", on_click=on_click).set_enabled(has_update)


def main() -> None:
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        Root,
        title="PSVR2Toolkit Installer",
        dark=None,
        native=True,
        reload=False,
    )
