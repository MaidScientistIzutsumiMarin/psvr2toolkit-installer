from asyncio import Lock
from json import dumps, loads
from pathlib import Path
from typing import ClassVar

from aiofiles import open as aiofiles_open
from aiofiles.os import stat
from aiofiles.ospath import exists
from nicegui.binding import BindableProperty
from signify.authenticode import AuthenticodeFile, AuthenticodeVerificationResult
from SteamPathFinder import get_game_path, get_steam_path

from psvr2toolkit_installer.vars import EYELID_ESIMATION_KEY, PSVR2_APP, PSVR2_SETTINGS_KEY


class Drivers:
    installed_path: ClassVar = Path(get_game_path(get_steam_path(), "2580190", PSVR2_APP)) / "SteamVR_Plug-In" / "bin" / "win64" / "driver_playstation_vr2.dll"
    original_path: ClassVar = installed_path.with_name("driver_playstation_vr2_orig.dll")

    @staticmethod
    async def get_mtime(path: Path) -> float:
        stats = await stat(path)
        return stats.st_mtime

    @classmethod
    async def is_installed_signed_and_newer(cls) -> bool:
        # Signed is true if the installed driver exists, and the signature can be verified.
        if signed := await exists(cls.installed_path):
            async with aiofiles_open(cls.installed_path, "rb") as fp:
                signed = AuthenticodeFile.from_stream(fp.raw).explain_verify()[0] is AuthenticodeVerificationResult.OK

        # If the installed driver is signed, and it was modified more recently than the original driver, the installed driver is probably a newer version.
        # Alternatively, if the installed driver is signed, and there is no original driver, the install is normal. In this case, we can just treat it as newer.
        return signed and (not await exists(cls.original_path) or await cls.get_mtime(cls.installed_path) > await cls.get_mtime(cls.original_path))


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
    async def set_eyelid_estimation(cls, *, enabled: bool) -> None:
        data = await cls.load_settings()

        if enabled:
            data[PSVR2_SETTINGS_KEY] = {EYELID_ESIMATION_KEY: True}
        else:
            del data[PSVR2_SETTINGS_KEY]

        async with aiofiles_open(cls.settings_path, "w", encoding="utf-8") as fp:
            await fp.write(dumps(data, ensure_ascii=False, indent=3))


class BindableLock(Lock):
    _locked = BindableProperty()
