from __future__ import annotations

import multiprocessing

from src.ui.app import CarixonApp


def main() -> None:
    multiprocessing.freeze_support()
    app = CarixonApp()
    app.mainloop()


if __name__ == "__main__":
    main()
