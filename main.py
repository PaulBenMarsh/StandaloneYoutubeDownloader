

def main():

    import sys

    from PyQt5.QtWidgets import QApplication
    from window import MainWindow

    application = QApplication([])
    window = MainWindow()

    sys.excepthook = window.excepthook

    window.show()

    return application.exec()


if __name__ == "__main__":
    import sys
    sys.exit(main())
