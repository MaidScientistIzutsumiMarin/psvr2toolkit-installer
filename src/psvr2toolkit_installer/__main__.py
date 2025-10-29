from functools import partial, wraps
from hashlib import sha256
from hmac import compare_digest
from json import dumps, loads
from operator import and_
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast
from webbrowser import open as webbrowser_open

from aiofiles import open as aiofiles_open
from aiofiles.os import replace, stat, unlink
from aiofiles.ospath import exists
from githubkit import GitHub
from nicegui import app, ui
from nicegui.binding import bindable_dataclass
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from githubkit.rest import Release
    from nicegui.events import ClickEventArguments, Handler

__version__ = "1.0.0"

PSVR2_APP = "PlayStation VR2 App"
STEAMVR = "SteamVR"

PSVR2_SETTINGS_KEY = "playstation_vr2_ex"
EYELID_ESIMATION_KEY = "enableEyelidEstimation"

PSVR2_TOOLKIT_INSTALLER_OWNER = "MaidScientistIzutsumiMarin"
PSVR2_TOOLKIT_INSTALLER_NAME = "psvr2toolkit-installer"

PSVR2_TOOLKIT_OWNER = "BnuuySolutions"
PSVR2_TOOLKIT_NAME = "PSVR2Toolkit"


class Drivers:
    installed_path: ClassVar = Path(get_game_path(get_steam_path(), "2580190", PSVR2_APP)) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"
    original_path: ClassVar = installed_path.with_name("driver_playstation_vr2_orig.dll")

    @staticmethod
    async def get_mtime(path: Path) -> float:
        stats = await stat(path)
        return stats.st_mtime

    @classmethod
    async def is_installed_driver_newer(cls) -> bool:
        # Signed is true if the installed driver exists, and the signature can be verified.
        if signed := await exists(cls.installed_path):
            async with aiofiles_open(cls.installed_path, "rb") as fp:
                signed = AuthenticodeFile.from_stream(fp.raw).explain_verify()[0] is AuthenticodeVerificationResult.OK

        original_exists = await exists(cls.original_path)

        # If the installed driver is not signed, and there is no original driver, the installation is fucked.
        if not signed and not original_exists:
            msg = f"Error: {PSVR2_APP} has invalid files. Please verify its integrity."
            raise RuntimeError(msg)

        # If the installed driver is signed, and it was modified more recently than the original driver, the installed driver is probably a newer version.
        # Alternatively, if the installed driver is signed, and there is no original driver, the install is normal.
        return signed and (not original_exists or await cls.get_mtime(cls.installed_path) > await cls.get_mtime(cls.original_path))


class SteamVR:
    settings_path: ClassVar = Path(get_steam_path()) / "config" / "steamvr.vrsettings"

    @classmethod
    async def load_settings(cls) -> dict[str, dict[str, str | float | bool]]:
        async with aiofiles_open(cls.settings_path, "rb") as fp:
            return loads(await fp.read())

    @classmethod
    async def is_eyelid_estimation_enabled(cls) -> bool:
        data = await cls.load_settings()
        return bool(data.get(PSVR2_SETTINGS_KEY, {}).get(EYELID_ESIMATION_KEY, False))

    @classmethod
    async def set_eyelid_estimation_enabled(cls, *, enabled: bool) -> None:
        data = await cls.load_settings()

        if enabled:
            data[PSVR2_SETTINGS_KEY] = {EYELID_ESIMATION_KEY: True}
        else:
            del data[PSVR2_SETTINGS_KEY]

        async with aiofiles_open(cls.settings_path, "w", encoding="utf-8") as fp:
            await fp.write(dumps(data, ensure_ascii=False, indent=3))


@bindable_dataclass
class Root:
    github: ClassVar = GitHub()

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

    async def setup(self) -> None:
        self.update_dialog = ui.dialog()

        with ui.splitter().classes("w-full") as splitter:
            with splitter.before:
                ui.button(f"Install {PSVR2_TOOLKIT_NAME}", on_click=self.install_toolkit).bind_enabled_from(self)
                ui.button(f"Uninstall {PSVR2_TOOLKIT_NAME}", on_click=self.uninstall_toolkit).bind_enabled_from(self)
            with splitter.after:
                ui.checkbox(
                    "Enable Experimental Eyelid Estimation",
                    value=await SteamVR.is_eyelid_estimation_enabled(),
                    on_change=lambda args: SteamVR.set_eyelid_estimation_enabled(enabled=args.value),
                ).bind_enabled_from(self)

        self.log = ui.log()

        with ui.row(align_items="center").classes("w-full"):
            ui.button("Check for Updates", on_click=self.check_for_updates).bind_enabled_from(self)
            ui.spinner(size="1.5em").bind_visibility_from(self, "spinner_visible")
            ui.space()
            ui.button("Quit", on_click=app.shutdown).bind_enabled_from(self)

    @modifies_installation(f"{PSVR2_TOOLKIT_NAME} installation")
    async def install_toolkit(self) -> None:
        if await Drivers.is_installed_driver_newer():
            self.log.push("Copying the installed driver...")
            await replace(Drivers.installed_path, Drivers.original_path)

        self.log.push(f"Downloading the latest {PSVR2_TOOLKIT_NAME} release...")
        async with GitHub() as github, github.get_async_client() as client:
            release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)
            response = await client.get(release.assets[0].browser_download_url)

            self.log.push("Installing the downloaded driver...")
            async with aiofiles_open(Drivers.installed_path, "wb") as fp:
                await fp.write(await response.aread())

    @modifies_installation(f"{PSVR2_TOOLKIT_NAME} uninstallation")
    async def uninstall_toolkit(self) -> None:
        if await Drivers.is_installed_driver_newer():
            self.log.push("The installed driver is newer than the original driver.\nOnly deleting the original driver...", classes="text-warning")
            await unlink(Drivers.original_path)
        else:
            self.log.push("Restoring the original driver...")
            await replace(Drivers.original_path, Drivers.installed_path)

        self.log.push(f"It is recommended to verify {PSVR2_APP} files through Steam.", classes="text-bold")

    async def check_for_updates(self) -> None:
        try:
            self.spinner_visible = True
            self.update_dialog.clear()
            with self.update_dialog, ui.card(), ui.grid(columns=3).classes("items-center"):
                release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)
                async with aiofiles_open(Drivers.installed_path, "rb") as fp:
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
                    up_to_date=__version__ == release.tag_name.lstrip("v"),
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
        Root().setup,
        title=PSVR2_TOOLKIT_INSTALLER_NAME,
        dark=None,
        window_size=(650, 500),
        reload=False,
    )
