from __future__ import annotations

import flet as ft

from app.app import LedgerApp


def main(page: ft.Page):
    LedgerApp(page)


if __name__ == "__main__":
    ft.run(main)
