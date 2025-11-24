from pathlib import Path
from typing import TYPE_CHECKING
from winreg import HKEY_CURRENT_USER, OpenKey, QueryValueEx

from aiofiles import open as aiofiles_open
from srctools.keyvalues import Keyvalues

if TYPE_CHECKING:
    from _typeshed import StrPath


def get_steam_path() -> Path:
    with OpenKey(HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
        return Path(QueryValueEx(key, "SteamPath")[0])


async def get_game_path(app_id: str, game_name: StrPath) -> Path:
    async with aiofiles_open(get_steam_path() / "steamapps" / "libraryfolders.vdf", encoding="utf-8") as file:
        file_contents = await file.read()

    app_path = None
    for folder in Keyvalues.parse(file_contents).find_block("libraryfolders"):
        if folder.find_block("apps").find_key(app_id, or_blank=True):
            app_path = folder.find_key("path").value
            break

    if app_path is None:
        msg = f"ERROR: Could not find the installation path for app {app_id}."
        raise FileNotFoundError(msg)

    return Path(app_path) / "steamapps" / "common" / game_name
