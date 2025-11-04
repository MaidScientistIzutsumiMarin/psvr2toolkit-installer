from asyncio import Lock
from contextlib import asynccontextmanager
from functools import partial
from hashlib import sha256
from hmac import compare_digest
from operator import and_
from typing import TYPE_CHECKING, ClassVar, Literal
from webbrowser import open as webbrowser_open

from aiofiles import open as aiofiles_open
from aiofiles.os import replace, unlink
from aiofiles.ospath import exists
from githubkit import GitHub
from nicegui import app
from nicegui.events import ValueChangeEventArguments  # noqa: TC002
from nicegui.ui import button, card, checkbox, dialog, expansion, grid, label, log, markdown, notification, notify, refreshable_method, row, run, space, spinner, splitter  # pyright: ignore[reportUnknownVariableType]

from psvr2toolkit_installer.helpers import Drivers, SteamVR
from psvr2toolkit_installer.vars import PSVR2_APP, PSVR2_TOOLKIT_INSTALLER_NAME, PSVR2_TOOLKIT_INSTALLER_OWNER, PSVR2_TOOLKIT_NAME, PSVR2_TOOLKIT_OWNER, __version__

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable
    from types import CoroutineType

    from githubkit.rest import Release
    from nicegui.events import ClickEventArguments, Handler


class Root:
    github: ClassVar = GitHub()
    setting_up = True
    lock = Lock()

    @property
    def enabled(self) -> bool:
        return not self.lock.locked()

    @staticmethod
    def modifies_toolkit(function: Callable[[Root], Awaitable[object]]) -> refreshable_method[Root, [str], CoroutineType[object, object, None]]:
        @refreshable_method
        async def wrapper(self: Root, verb: str) -> None:
            async with self.working():
                if self.setting_up:
                    return

                work_notification = notification(f"{verb}...", spinner=True, timeout=None)

                try:
                    self.log.clear()
                    self.log.push(f"{verb} starting...")

                    self.log.push("Verifying relevant files...")
                    if not await exists(Drivers.original_path) and not await Drivers.is_installed_signed_and_newer():
                        msg = f"{PSVR2_APP} has invalid files. Please verify its integrity."
                        raise RuntimeError(msg)

                    await function(self)

                    self.log.push(f"{verb} succeeded!", classes="text-positive")
                finally:
                    work_notification.message = f"{verb} done!"
                    work_notification.spinner = False
                    work_notification.timeout = 5

        return wrapper

    @asynccontextmanager
    async def working(self) -> AsyncGenerator[None]:
        async with self.lock:
            work_spinner = spinner(size="1.5em")

            try:
                yield
            except Exception as exc:
                self.log.push(f"Operation failed!\n{exc}", classes="text-negative")
                raise
            finally:
                work_spinner.set_visibility(False)

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
            button(f"{verb} {PSVR2_TOOLKIT_NAME}", on_click=function.refresh).bind_enabled_from(self)
            await function(f"{verb}ing {PSVR2_TOOLKIT_NAME}")

    @modifies_toolkit
    async def install_toolkit(self) -> None:
        if await Drivers.is_installed_signed_and_newer():
            self.log.push("Copying installed driver...")
            await replace(Drivers.installed_path, Drivers.original_path)

        self.log.push("Finding latest release...")
        release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)

        self.log.push("Downloading latest release...")

        response = await self.github.arequest("GET", release.assets[0].browser_download_url)  # pyright: ignore[reportUnknownMemberType]

        self.log.push("Saving latest release as installed driver...")
        async with aiofiles_open(Drivers.installed_path, "wb") as fp:
            await fp.write(response.content)

    @modifies_toolkit
    async def uninstall_toolkit(self) -> None:
        if not await exists(Drivers.original_path):
            msg = f"{PSVR2_TOOLKIT_NAME} is not installed."
            raise RuntimeError(msg)

        if await Drivers.is_installed_signed_and_newer():
            self.log.push("Installed driver is newer. Deleting original driver...")
            await unlink(Drivers.original_path)
        else:
            self.log.push("Replacing installed driver with original driver...")
            await replace(Drivers.original_path, Drivers.installed_path)

        self.log.push(f"Please verify the integrity of {PSVR2_APP}'s files through Steam.", classes="text-bold")

    async def set_eyelid_estimation(self, args: ValueChangeEventArguments) -> None:
        try:
            await SteamVR.set_eyelid_estimation(enabled=args.value)
            notify(f"{'Enabled' if args.value else 'Disabled'} eyelid estimation!")
        except Exception as exc:
            self.log.push(f"Setting eyelid estimation failed!\n{exc}", classes="text-negative")
            raise

    @refreshable_method
    async def check_for_updates(self) -> None:
        async with self.working():
            if self.setting_up:
                return

            with dialog().on("hide", lambda: update_dialog.clear()) as update_dialog, card(), grid(columns=3).classes("items-center"):
                release = await self.get_latest_release(PSVR2_TOOLKIT_OWNER, PSVR2_TOOLKIT_NAME)
                async with aiofiles_open(Drivers.installed_path, "rb") as fp:
                    self.show_update(
                        PSVR2_TOOLKIT_NAME,
                        release,
                        partial(self.install_toolkit.refresh, f"Updating {PSVR2_TOOLKIT_NAME}"),
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
