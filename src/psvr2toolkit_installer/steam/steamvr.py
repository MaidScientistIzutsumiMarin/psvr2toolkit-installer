from json import dumps, loads
from typing import ClassVar

from aiofiles import open as aiofiles_open

from psvr2toolkit_installer.steam.paths import get_steam_path
from psvr2toolkit_installer.vars import EYELID_ESIMATION_KEY, PSVR2_SETTINGS_KEY


class SteamVR:
    settings_path: ClassVar = get_steam_path() / "config" / "steamvr.vrsettings"

    @classmethod
    async def load_settings(cls) -> dict[str, dict[str, str | float | bool]]:
        async with aiofiles_open(cls.settings_path, "rb") as fp:
            content = await fp.read()
            return loads(content)

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
