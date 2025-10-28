from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial, wraps
from hashlib import sha256
from hmac import compare_digest
from json import dumps, loads
from operator import and_
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast
from webbrowser import open as webbrowser_open

from aiofiles import open as aiofiles_open
from aiofiles.os import replace, stat, unlink
from aiofiles.ospath import exists
from githubkit import GitHub, UnauthAuthStrategy
from githubkit.versions.v2022_11_28.models.group_0376 import Release
from nicegui import app, ui
from nicegui.binding import bindable_dataclass
from nicegui.events import ClickEventArguments, Handler, ValueChangeEventArguments  # noqa: TC002 Not sure why this is necessary, but it is.
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from aiofiles.threadpool.text import AsyncTextIOWrapper
    from githubkit.rest import Release

__version__ = "0.2.0"

PSVR2_APP = "PlayStation VR2 App"
STEAMVR = "SteamVR"

PSVR2_SETTINGS_KEY = "playstation_vr2_ex"
EYELID_ESIMATION_KEY = "enableEyelidEstimation"

PSVR2_TOOLKIT_INSTALLER_OWNER = "MaidScientistIzutsumiMarin"
PSVR2_TOOLKIT_INSTALLER_NAME = "psvr2toolkit-installer"

PSVR2_TOOLKIT_OWNER = "BnuuySolutions"
PSVR2_TOOLKIT_NAME = "PSVR2Toolkit"


def modifies_installation[**P](verb: str) -> Callable[[Callable[P, Awaitable[object]]], Callable[P, Awaitable[None]]]:
    # Takes an str in the decorator syntax, which then returns the function decorator, which then wraps the function and does its things.
    # The typing is very scary, we know.
    def decorator(function: Callable[P, Awaitable[object]]) -> Callable[P, Awaitable[None]]:
        @wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            self = cast("Root", args[0])
            notification = ui.notification(f"{verb}...", spinner=True, timeout=None)

            try:
                self.enabled = False

                self.log.clear()
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


@asynccontextmanager
async def open_steamvr_settings() -> AsyncGenerator[AsyncTextIOWrapper]:
    async with aiofiles_open(Path(get_steam_path()) / "config" / "steamvr.vrsettings", "r+", encoding="utf-8") as fp:
        yield fp


async def is_eyelid_estimation_enabled() -> bool:
    async with open_steamvr_settings() as fp:
        data: dict[str, dict[str, Any]] = loads(await fp.read())
    return data.get(PSVR2_SETTINGS_KEY, {}).get(EYELID_ESIMATION_KEY, False)


async def get_mtime(path: Path) -> float:
    stats = await stat(path)
    return stats.st_mtime


@dataclass
class DriverInfo:
    installed_path: Path
    original_path: Path
    signed: bool

    @classmethod
    async def get(cls) -> Self:
        installed_path = Path(get_game_path(get_steam_path(), "2580190", PSVR2_APP)) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"

        async with aiofiles_open(installed_path, "rb") as fp:
            file = AuthenticodeFile.from_stream(fp.raw)

            return cls(
                installed_path,
                installed_path.with_name("driver_playstation_vr2_orig.dll"),
                file.explain_verify()[0] is AuthenticodeVerificationResult.OK,
            )


@bindable_dataclass
class Root:
    github: GitHub[UnauthAuthStrategy] = GitHub()
    enabled = True
    spinner_visible = False

    async def create_ui(self) -> None:
        self.update_dialog = ui.dialog()

        with ui.splitter().classes("w-full") as splitter:
            with splitter.before:
                ui.button(f"Install {PSVR2_TOOLKIT_NAME}", on_click=self.install_toolkit).bind_enabled_from(self)
                ui.button(f"Uninstall {PSVR2_TOOLKIT_NAME}", on_click=self.uninstall_toolkit).bind_enabled_from(self)

            with splitter.after:
                ui.checkbox("Enable Experimental Eyelid Estimation", value=await is_eyelid_estimation_enabled(), on_change=self.toggle_eyelid_estimation).bind_enabled_from(self)

        self.log = ui.log()

        with ui.row(align_items="center").classes("w-full"):
            ui.button("Check for Updates", on_click=self.check_for_updates).bind_enabled_from(self)
            ui.spinner(size="1.5em").bind_visibility_from(self, "spinner_visible")
            ui.space()
            ui.button("Quit", on_click=app.shutdown)

    @modifies_installation(f"{PSVR2_TOOLKIT_NAME} installation")
    async def install_toolkit(self) -> None:
        driver_info = await DriverInfo.get()

        if driver_info.signed:
            self.log.push("Copying the installed driver...")
            await replace(driver_info.installed_path, driver_info.original_path)
        elif not await exists(driver_info.original_path):
            msg = f"Error: The {PSVR2_APP} has invalid files. Please verify its integrity."
            raise RuntimeError(msg)

        self.log.push(f"Downloading the latest {PSVR2_TOOLKIT_NAME} release...")
        async with GitHub() as github, github.get_async_client() as client:
            release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)
            response = await client.get(release.assets[0].browser_download_url)

            self.log.push("Installing the downloaded driver...")
            async with aiofiles_open(driver_info.installed_path, "wb") as fp:
                await fp.write(await response.aread())

    @modifies_installation(f"{PSVR2_TOOLKIT_NAME} uninstallation")
    async def uninstall_toolkit(self) -> None:
        driver_info = await DriverInfo.get()

        if not driver_info.signed or await get_mtime(driver_info.installed_path) < await get_mtime(driver_info.original_path):
            self.log.push("Restoring the original driver...")
            await replace(driver_info.original_path, driver_info.installed_path)
        else:
            self.log.push("The installed driver is newer than the original driver. Only deleting the original driver...", classes="text-warning")
            await unlink(driver_info.original_path)

        self.log.push(f"It is recommended to verify {PSVR2_APP} files through Steam.", classes="text-bold")

    @modifies_installation("Toggling eyelid estimation")
    async def toggle_eyelid_estimation(self, handler: ValueChangeEventArguments) -> None:
        self.log.push(f"Loading {STEAMVR} settings...")
        async with open_steamvr_settings() as fp:
            data: dict[str, dict[str, object]] = loads(await fp.read())

            self.log.push(f"Modifying {STEAMVR} settings...")
            if handler.value:
                data[PSVR2_SETTINGS_KEY] = {EYELID_ESIMATION_KEY: True}
            else:
                del data[PSVR2_SETTINGS_KEY]

            self.log.push(f"Saving modified {STEAMVR} settings...")

            # Seek to the start of the file then truncate to clear it.
            await fp.seek(0)
            await fp.truncate()

            # Don't know if ensure_ascii is necessary.
            # indent probably isn't as long as Steam has a normal JSON reader.
            # But this maintains the original structure as much as possible.
            await fp.write(dumps(data, ensure_ascii=False, indent=3))

    async def check_for_updates(self) -> None:
        try:
            driver_info = await DriverInfo.get()

            self.spinner_visible = True
            self.update_dialog.clear()
            with self.update_dialog, ui.card(), ui.grid(columns=3).classes("items-center"):
                release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)
                async with aiofiles_open(driver_info.installed_path, "rb") as fp:
                    self.show_update(
                        PSVR2_TOOLKIT_NAME,
                        release,
                        self.install_toolkit,
                        up_to_date=compare_digest("sha256:" + sha256(await fp.read()).hexdigest(), release.assets[0].digest or ""),
                    )

                release = await self.get_latest_release(PSVR2_TOOLKIT_INSTALLER_OWNER, PSVR2_TOOLKIT_INSTALLER_NAME)
                self.show_update(
                    PSVR2_TOOLKIT_INSTALLER_NAME,
                    release,
                    partial(webbrowser_open, release.html_url),
                    up_to_date=__version__ == release.tag_name[1:],  # Trim the 'v'
                )

            self.update_dialog.open()
        except Exception as exc:
            ui.notify(f"An error occurred while checking for updates: {exc}", color="red")
            raise
        finally:
            self.spinner_visible = False

    async def get_latest_release(self, owner: str, repo: str) -> Release:
        response = await self.github.rest.repos.async_get_latest_release(owner, repo)
        return response.parsed_data

    def show_update(self, name: str, release: Release, on_click: Handler[ClickEventArguments], *, up_to_date: bool) -> None:
        ui.label(name).classes("font-bold")
        ui.label(release.tag_name).classes("text-secondary")
        ui.button("Update", on_click=on_click).bind_enabled_from(self, backward=partial(and_, not up_to_date))
        with ui.expansion("Changelog").classes("col-span-full"):
            ui.markdown(release.body or "No changelog provided.")


def main() -> None:
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        Root().create_ui,
        title=PSVR2_TOOLKIT_INSTALLER_NAME,
        dark=None,
        native=True,
        window_size=(650, 500),
        reload=False,
    )
