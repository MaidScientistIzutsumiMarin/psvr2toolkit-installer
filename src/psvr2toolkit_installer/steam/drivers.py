from dataclasses import field
from hashlib import sha256
from typing import TYPE_CHECKING, Literal

from aiofiles import open as aiofiles_open
from aiofiles.os import replace, unlink
from aiofiles.ospath import exists
from nicegui.binding import bindable_dataclass
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult

from psvr2toolkit_installer.steam.paths import get_game_path
from psvr2toolkit_installer.vars import PSVR2_APP

if TYPE_CHECKING:
    from _typeshed import FileDescriptorOrPath, ReadableBuffer


@bindable_dataclass
class Drivers:
    status: Literal["Installed", "Uninstalled", "Invalid Driver Files"] = field(init=False)

    async def setup(self) -> None:
        self.current_path = await get_game_path("2580190", PSVR2_APP) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"
        self.original_path = self.current_path.with_name("driver_playstation_vr2_orig.dll")
        await self.validate_files()

    ### Read ###

    async def validate_files(self) -> bool:
        # Valid configurations:
        # - Current driver exists (a) and is signed (b)
        # - Current driver exists (a) and is unsigned (~b), and original driver exists (c) and is signed (d)
        # (a && b) or (a && ~b && c && d)
        if valid := await exists(self.current_path):
            is_current_signed = await self.is_signed(self.current_path)
            if valid := is_current_signed or (await self.original_exists() and await self.is_signed(self.original_path)):
                self.status = "Uninstalled" if is_current_signed else "Installed"
        if not valid:
            self.status = "Invalid Driver Files"
        return valid

    async def is_signed(self, driver: FileDescriptorOrPath) -> bool:
        async with aiofiles_open(driver, "rb") as fp:
            result, error = AuthenticodeFile.from_stream(fp.raw).explain_verify()
        if result is not AuthenticodeVerificationResult.NOT_SIGNED and error is not None:
            raise error
        return result is AuthenticodeVerificationResult.OK

    async def original_exists(self) -> bool:
        return await exists(self.original_path)

    async def get_digest(self) -> str:
        async with aiofiles_open(self.current_path, "rb") as fp:
            return "sha256:" + sha256(await fp.read()).hexdigest()

    ### Write ###

    async def copy_original(self) -> None:
        await replace(self.current_path, self.original_path)

    async def restore_original(self) -> None:
        await replace(self.original_path, self.current_path)

    async def unlink_original(self) -> None:
        await unlink(self.original_path)

    async def install_to_current(self, driver: ReadableBuffer) -> None:
        async with aiofiles_open(self.current_path, "wb") as fp:
            await fp.write(driver)
