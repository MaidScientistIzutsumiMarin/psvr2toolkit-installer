import sys

from nicegui import app, ui


def main() -> None:
    with ui.row().classes("w-full"):
        ui.space()
        ui.button("Quit", on_click=app.shutdown)

    ui.run(dark=None, reload=False)


if __name__ == "__main__":
    sys.exit(main())
