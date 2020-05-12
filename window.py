
from PyQt5.QtWidgets import QMainWindow
from PyQt5.Qt import QSortFilterProxyModel, QThread
import logging


class PlainTextLogger(logging.Handler):

    def __init__(self, widget, *args, **kwargs):
        logging.Handler.__init__(self, 0, *args, **kwargs)
        self.widget = widget
        self.widget.setReadOnly(True)

    def emit(self, record):
        message = str(record)
        self.widget.appendPlainText(message)
        self.widget.viewport().update()


class FindStreamsThread(QThread):

    from PyQt5.QtCore import pyqtSignal
    from PyQt5.QtGui import QImage

    foundStreams = pyqtSignal(list, QImage, str)

    def __init__(self, url, on_complete, on_progress, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.url = url
        self.on_complete = on_complete
        self.on_progress = on_progress

    def __del__(self):
        self.wait()

    def run(self):
        from pytube import YouTube
        import requests
        from PyQt5.QtGui import QImage

        youtube = YouTube(url=self.url)
        image_data = requests.get(youtube.thumbnail_url).content
        image = QImage()
        image.loadFromData(image_data)

        youtube.register_on_complete_callback(self.on_complete)
        youtube.register_on_progress_callback(self.on_progress)
        self.foundStreams.emit(list(youtube.streams), image, youtube.title)


class DownloadStreamsThread(QThread):

    from PyQt5.QtCore import pyqtSignal

    downloadedAllStreams = pyqtSignal()

    def __init__(self, stream_infos, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.stream_infos = stream_infos

    def __del__(self):
        self.wait()

    def run(self):

        for stream, directory, prefix in self.stream_infos:
            stream.download(output_path=directory, filename_prefix=prefix)
        self.downloadedAllStreams.emit()


class SortFilterProxyModel(QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        QSortFilterProxyModel.__init__(self, *args, **kwargs)
        self.enable_progressive = True
        self.enable_adaptive = True
        self.enable_audio = True

    def filterAcceptsRow(self, row, model_index, *args, **kwargs):
        from PyQt5 import QtCore

        index = self.sourceModel().index(row, 0, model_index)
        item = index.data(QtCore.Qt.UserRole + 1)

        if type(item) is object:
            return True

        stream = item

        if stream.includes_video_track:
            if not self.enable_progressive and stream.is_progressive:
                return False
            if not self.enable_adaptive and stream.is_adaptive:
                return False
        else:
            if not self.enable_audio and stream.includes_audio_track:
                return False

        return QSortFilterProxyModel.filterAcceptsRow(self, row, model_index, *args, **kwargs)


class MainWindow(QMainWindow):

    from PyQt5.QtCore import pyqtSlot

    def __init__(self, *args, **kwargs):
        from PyQt5 import uic
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QIcon, QMovie

        QMainWindow.__init__(self, *args, **kwargs)

        def resource_path(relative_path):
            import sys
            import os
            try:
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)

        ui_path = resource_path("resources\\ui\\youtube_ui.ui")
        uic.loadUi(ui_path, self)

        self.setWindowFlag(Qt.MSWindowsFixedSizeDialogHint)

        window_icon_path = resource_path("resources\\icons\\window.ico")
        window_icon = QIcon(str(window_icon_path))
        self.setWindowIcon(window_icon)

        button_find_icon_path = resource_path("resources\\icons\\find.ico")
        self.button_find_icon = QIcon(str(button_find_icon_path))
        self.button_find.setIcon(self.button_find_icon)

        button_find_hourglass_path = resource_path("resources\\icons\\hourglass.gif")
        self.button_find_hourglass = QMovie(str(button_find_hourglass_path))
        self.button_find_hourglass.setCacheMode(QMovie.CacheAll)
        self.button_find_hourglass.frameChanged.connect(self.on_hourglass_frame_changed)

        button_download_icon_path = resource_path("resources\\icons\\download.ico")
        button_download_icon = QIcon(str(button_download_icon_path))
        self.button_download.setIcon(button_download_icon)

        check_box_progressive_icon_path = resource_path("resources\\icons\\progressive.ico")
        check_box_progressive_icon = QIcon(str(check_box_progressive_icon_path))
        self.check_box_progressive.setIcon(check_box_progressive_icon)

        check_box_adaptive_icon_path = resource_path("resources\\icons\\adaptive.ico")
        check_box_adaptive_icon = QIcon(str(check_box_adaptive_icon_path))
        self.check_box_adaptive.setIcon(check_box_adaptive_icon)

        check_box_audio_icon_path = resource_path("resources\\icons\\audio.ico")
        check_box_audio_icon = QIcon(str(check_box_audio_icon_path))
        self.check_box_audio.setIcon(check_box_audio_icon)

        self.log_handler = PlainTextLogger(self.log)
        logging.getLogger().addHandler(self.log_handler)

        self.button_find.setEnabled(False)
        self.check_box_progressive.setEnabled(False)
        self.check_box_adaptive.setEnabled(False)
        self.check_box_audio.setEnabled(False)
        self.button_download.setEnabled(False)

        self.label_image.setScaledContents(True)

        self.line_edit_url.returnPressed.connect(self.on_button_find_clicked)

    def excepthook(self, exctype, value, traceback):
        self.button_find.setText("Find Available Streams")
        self.button_find_hourglass.stop()
        self.button_find.setIcon(self.button_find_icon)
        self.line_edit_url.setEnabled(True)

        self.log_handler.emit(f"{exctype} {value} {traceback.tb_frame} {traceback.tb_lineno}")

    def on_hourglass_frame_changed(self):
        from PyQt5.QtGui import QIcon
        icon = QIcon(self.button_find_hourglass.currentPixmap())
        self.button_find.setIcon(icon)

    def on_line_edit_url_textChanged(self):
        text = self.line_edit_url.text()
        self.button_find.setEnabled(bool(text))

    def on_find_streams_thread_foundStreams(self, streams, image, title):
        from PyQt5.Qt import QStandardItemModel, QStandardItem, QVariant, QAbstractItemView
        from PyQt5.QtGui import QPixmap

        self.button_find.setText("Find Available Streams")
        self.button_find_hourglass.stop()
        self.button_find.setIcon(self.button_find_icon)

        self.model = QStandardItemModel(0, 1, self)
        self.model.setHorizontalHeaderLabels(["Streams"])
        for stream in streams:
            variant = QVariant(stream)
            item = QStandardItem()
            item.setData(variant)

            is_audio_stream = not stream.includes_video_track and stream.includes_audio_track

            text = [
                f"{stream.mime_type:<12} [{stream.resolution} @ {stream.fps}fps]",
                f"{stream.mime_type:<12} [Codec: {stream.audio_codec}]"
            ][is_audio_stream]

            item.setText(text)
            if stream.is_progressive:
                item.setIcon(self.check_box_progressive.icon())
            elif not stream.includes_audio_track and stream.is_adaptive:
                item.setIcon(self.check_box_adaptive.icon())
            elif is_audio_stream:
                item.setIcon(self.check_box_audio.icon())

            if not is_audio_stream:
                detail_variant_vc = QVariant(object())
                detail_variant_ac = QVariant(object())
                detail_child_vc = QStandardItem()
                detail_child_ac = QStandardItem()
                detail_child_vc.setData(detail_variant_vc)
                detail_child_ac.setData(detail_variant_ac)
                detail_child_vc.setText(f"Video Codec: {stream.video_codec}")
                detail_child_ac.setText(f"Audio Codec: {stream.audio_codec}")
                detail_child_vc.setSelectable(False)
                detail_child_ac.setSelectable(False)
                item.appendRow(detail_child_vc)
                item.appendRow(detail_child_ac)
            detail_variant_size = QVariant(object())
            detail_child_size = QStandardItem()
            detail_child_size.setData(detail_variant_size)
            detail_child_size.setText(f"File Size: {stream.filesize/1000000:.2f}MB")
            detail_child_size.setSelectable(False)
            item.appendRow(detail_child_size)
            self.model.appendRow(item)

        self.proxy_model = SortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setRootIsDecorated(True)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(False)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree_view.selectionModel().selectionChanged.connect(self.on_tree_view_selectionChanged)

        self.check_box_progressive.setEnabled(True)
        self.check_box_progressive.setChecked(True)
        self.check_box_adaptive.setEnabled(True)
        self.check_box_adaptive.setChecked(True)
        self.check_box_adaptive.setChecked(False)
        self.check_box_audio.setEnabled(True)
        self.check_box_audio.setChecked(True)
        self.line_edit_url.setEnabled(True)

        self.label_image.setPixmap(QPixmap(image))
        self.label_title.setText(title)

        self.log_handler.emit(f"Found {len(streams)} available streams for \"{title}\".")

    def on_tree_view_selectionChanged(self):
        indexes = self.tree_view.selectionModel().selectedIndexes()
        self.button_download.setEnabled(bool(indexes))

    @pyqtSlot()
    def on_button_find_clicked(self):
        from PyQt5.Qt import QStandardItemModel
        from PyQt5.QtGui import QPixmap

        self.button_find.setText("Finding Streams...")
        self.button_find_hourglass.start()

        url = str(self.line_edit_url.text()).strip()
        self.line_edit_url.clear()
        self.line_edit_url.setEnabled(False)

        self.label_image.setPixmap(QPixmap())
        self.label_title.setText("")

        self.model = QStandardItemModel()
        self.proxy_model = SortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.tree_view.setRootIsDecorated(False)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setModel(self.proxy_model)

        self.check_box_progressive.setEnabled(False)
        self.check_box_progressive.setChecked(False)
        self.check_box_adaptive.setEnabled(False)
        self.check_box_adaptive.setChecked(False)
        self.check_box_audio.setEnabled(False)
        self.check_box_audio.setChecked(False)
        self.button_download.setEnabled(False)

        try:
            url = url[:url.index("&")]
        except ValueError:
            pass

        self.find_streams_thread = FindStreamsThread(
            url,
            self.on_download_complete,
            self.on_download_progress
        )
        self.find_streams_thread.foundStreams.connect(self.on_find_streams_thread_foundStreams)

        self.find_streams_thread.start()

    def on_check_box_progressive_stateChanged(self):
        self.model.layoutAboutToBeChanged.emit()
        self.proxy_model.enable_progressive = self.sender().isChecked()
        self.model.layoutChanged.emit()

    def on_check_box_adaptive_stateChanged(self):
        self.model.layoutAboutToBeChanged.emit()
        self.proxy_model.enable_adaptive = self.sender().isChecked()
        self.model.layoutChanged.emit()

    def on_check_box_audio_stateChanged(self):
        self.model.layoutAboutToBeChanged.emit()
        self.proxy_model.enable_audio = self.sender().isChecked()
        self.model.layoutChanged.emit()

    @pyqtSlot()
    def on_button_download_clicked(self):
        from PyQt5 import QtCore
        from PyQt5.QtWidgets import QFileDialog
        from pathlib import Path

        self.button_download.setEnabled(False)

        indexes = self.tree_view.selectionModel().selectedIndexes()
        if not indexes:
            return

        directory = QFileDialog.getExistingDirectory(self, "Save", "C:/", QFileDialog.ShowDirsOnly)

        stream_infos = []
        for count, index in enumerate(indexes, start=1):
            stream = index.data(QtCore.Qt.UserRole + 1)
            prefix = [f"{count} - ", ""][len(indexes) == 1]
            stream_infos.append((stream, directory, prefix))

        path = Path(directory, prefix+stream.default_filename)
        self.log_handler.emit(f"Downloading \"{path}\"...")

        self.progress_bar.setTextVisible(True)

        self.download_streams_thread = DownloadStreamsThread(stream_infos)
        self.download_streams_thread.downloadedAllStreams.connect(self.on_downloadedAllStreams)
        self.download_streams_thread.start()

        self.button_find.setEnabled(False)
        self.line_edit_url.setEnabled(False)
        self.check_box_progressive.setEnabled(False)
        self.check_box_adaptive.setEnabled(False)
        self.check_box_audio.setEnabled(False)
        self.tree_view.setEnabled(False)

    def on_download_complete(self, stream, file_handle):
        self.log_handler.emit(f"Finished downloading \"{file_handle}\"")

    def on_download_progress(self, stream, chunk, bytes_remaining):
        maximum = self.progress_bar.maximum()
        if bytes_remaining == 0 or stream.filesize == 0:
            self.progress_bar.setValue(maximum)
        else:
            value = maximum // (stream.filesize / (stream.filesize - bytes_remaining))
            self.progress_bar.setValue(value)

    def on_downloadedAllStreams(self):
        self.button_download.setEnabled(True)
        minimum = self.progress_bar.minimum()
        self.progress_bar.setValue(minimum)
        self.progress_bar.setTextVisible(False)

        self.line_edit_url.setEnabled(True)
        self.check_box_progressive.setEnabled(True)
        self.check_box_adaptive.setEnabled(True)
        self.check_box_audio.setEnabled(True)
        self.tree_view.setEnabled(True)
