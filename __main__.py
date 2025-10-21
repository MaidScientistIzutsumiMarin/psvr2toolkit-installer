import webbrowser
from enum import StrEnum
from functools import partial
from pathlib import Path

from nicegui import app, ui
from requests import get
from SteamPathFinder import get_game_path, get_steam_path  # pyright: ignore[reportUnknownVariableType]


class AppId(StrEnum):
    PSVR2_APP = "2580190"


def install_psvr2_toolkit() -> None:
    toolkit_button.disable()

    try:
        driver_path = Path(get_game_path(get_steam_path(), AppId.PSVR2_APP, "PlayStation VR2 App"), "SteamVR_Plug-In", "bin", "win64", "driver_playstation_vr2.dll")
        log.push(f"Found the PSVR2 driver at {driver_path}")

        original_driver_path = driver_path.with_name("driver_playstation_vr2_orig.dll")
        if original_driver_path.exists():
            log.push(f"The Toolkit driver has already been installed. {original_driver_path.name} will not be touched.", classes="text-warning")
        else:
            driver_path.rename(original_driver_path)
            log.push(f"Moved the original driver to {original_driver_path.name}")

        log.push("Downloading the latest PlayStation VR2 Toolkit driver...")
        with get("https://github.com/BnuuySolutions/PSVR2Toolkit/releases/latest/download/driver_playstation_vr2.dll", timeout=10) as response:
            response.raise_for_status()
            driver_path.write_bytes(response.content)

        log.push(f"Saved the Toolkit driver as {driver_path.name}")
        log.push("Toolkit installation complete!", classes="text-positive")
    except FileNotFoundError:
        psvr2_app_dialog.open()

    toolkit_button.enable()


def on_install(dialog: ui.dialog, app_id: str) -> None:
    webbrowser.open(f"steam://install/{app_id}")
    ui.notify("Starting installation... Please wait until it is complete to try again.")
    dialog.close()


with ui.dialog() as psvr2_app_dialog, ui.card():
    ui.label("It appears the PlayStation®VR2 App is not installed.")
    ui.label("This is required for installing the Toolkit driver!").classes("text-negative")
    with ui.row():
        ui.button("Install PlayStation®VR2 App", on_click=partial(on_install, psvr2_app_dialog, AppId.PSVR2_APP))
        ui.button("Close", on_click=psvr2_app_dialog.close)

toolkit_button = ui.button("Install/Update PlayStation VR2 Toolkit", on_click=install_psvr2_toolkit)
log = ui.log()

with ui.row().classes("w-full"):
    ui.space()
    ui.button("Quit", on_click=app.shutdown)

ui.run(dark=None)
