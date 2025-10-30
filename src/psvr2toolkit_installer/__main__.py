from contextlib import contextmanager
from functools import partial
from hashlib import sha256
from hmac import compare_digest
from json import dumps, loads
from operator import and_
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal
from webbrowser import open as webbrowser_open

from aiofiles import open as aiofiles_open
from aiofiles.os import replace, stat, unlink
from aiofiles.ospath import exists
from githubkit import GitHub
from nicegui import app
from nicegui.binding import bindable_dataclass
from nicegui.events import ValueChangeEventArguments  # noqa: TC002
from nicegui.ui import button, card, checkbox, dialog, expansion, grid, label, log, markdown, notification, notify, refreshable_method, row, run, space, spinner, splitter  # pyright: ignore[reportUnknownVariableType]
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator
    from types import CoroutineType

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
    setting_up = True

    @staticmethod
    def modifies_installation(function: Callable[[Root], Awaitable[None]]) -> refreshable_method[Root, [str], CoroutineType[object, object, None]]:
        @refreshable_method
        async def wrapper(self: Root, verb: str) -> None:
            with self.working():
                if self.setting_up:
                    return

                work_notification = notification(f"{verb}...", spinner=True, timeout=None)

                try:
                    self.log.clear()
                    self.log.push(f"{verb} starting...")

                    await function(self)

                    self.log.push(f"{verb} succeeded!", classes="text-positive")
                finally:
                    work_notification.message = f"{verb} done!"
                    work_notification.spinner = False
                    work_notification.timeout = 5

        return wrapper

    @contextmanager
    def working(self) -> Generator[None]:
        self.enabled = False
        work_spinner = spinner(size="1.5em")

        try:
            yield
        except Exception as exc:
            self.log.push(f"Operation failed!\n{exc}", classes="text-negative")
            raise
        finally:
            work_spinner.set_visibility(False)
            self.enabled = True

    async def setup(self) -> None:
        with splitter().classes("w-full") as root_splitter:
            with root_splitter.before:
                await self.create_modification_button("Install")
                await self.create_modification_button("Uninstall")

            with root_splitter.after:
                checkbox(
                    "Enable Experimental Eyelid Estimation",
                    value=await SteamVR.is_eyelid_estimation_enabled(),
                    on_change=self.set_eyelid_estimation,
                ).bind_enabled_from(self)

        self.log = log()

        with row(align_items="center").classes("w-full"):
            button("Check for Updates", on_click=self.check_for_updates.refresh).bind_enabled_from(self)
            await self.check_for_updates()

            space()
            button("Quit", on_click=app.shutdown).bind_enabled_from(self)

        self.setting_up = False

    async def create_modification_button(self, verb: Literal["Install", "Uninstall"]) -> None:
        function = self.install_toolkit if verb == "Install" else self.uninstall_toolkit

        with row(align_items="center"):
            button(f"{verb} {PSVR2_TOOLKIT_NAME}", on_click=partial(function.refresh, f"{PSVR2_TOOLKIT_NAME} {verb}")).bind_enabled_from(self)
            await function("")

    async def set_eyelid_estimation(self, args: ValueChangeEventArguments) -> None:
        await SteamVR.set_eyelid_estimation_enabled(enabled=args.value)
        notify(f"{'Enabled' if args.value else 'Disabled'} eyelid estimation!")

    @modifies_installation
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

    @modifies_installation
    async def uninstall_toolkit(self) -> None:
        if await Drivers.is_installed_driver_newer():
            self.log.push("The installed driver is newer than the original driver.\nOnly deleting the original driver...", classes="text-warning")
            await unlink(Drivers.original_path)
        else:
            self.log.push("Restoring the original driver...")
            await replace(Drivers.original_path, Drivers.installed_path)

        self.log.push(f"It is recommended to verify {PSVR2_APP} files through Steam.", classes="text-bold")

    @refreshable_method
    async def check_for_updates(self) -> None:
        with self.working():
            if self.setting_up:
                return

            with dialog().on("hide", lambda: update_dialog.clear()) as update_dialog, card(), grid(columns=3).classes("items-center"):
                release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)
                async with aiofiles_open(Drivers.installed_path, "rb") as fp:
                    self.show_update(
                        PSVR2_TOOLKIT_NAME,
                        release,
                        partial(self.install_toolkit.refresh, f"{PSVR2_TOOLKIT_NAME} update"),
                        up_to_date=compare_digest("sha256:" + sha256(await fp.read()).hexdigest(), release.assets[0].digest or ""),
                    )

                release = await self.get_latest_release(PSVR2_TOOLKIT_INSTALLER_OWNER, PSVR2_TOOLKIT_INSTALLER_NAME)
                self.show_update(
                    PSVR2_TOOLKIT_INSTALLER_NAME,
                    release,
                    partial(webbrowser_open, release.html_url),
                    up_to_date=__version__ == release.tag_name.lstrip("v"),
                )

            update_dialog.open()

    async def get_latest_release(self, owner: str, repo: str) -> Release:
        response = await self.github.rest.repos.async_get_latest_release(owner, repo)
        return response.parsed_data

    def show_update(self, name: str, release: Release, on_click: Handler[ClickEventArguments], *, up_to_date: bool) -> None:
        label(name).classes("font-bold")
        label(release.tag_name).classes("text-secondary")
        button("Update", on_click=on_click).bind_enabled_from(self, backward=partial(and_, not up_to_date))
        with expansion("Changelog").classes("col-span-full"):
            markdown(release.body or "No changelog provided.")


def main() -> None:
    run(
        Root().setup,
        title=PSVR2_TOOLKIT_INSTALLER_NAME,
        dark=None,
        window_size=(650, 500),
        reload=False,
    )
