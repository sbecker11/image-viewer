import sys
import os
import json
import logging
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QSizePolicy, QDesktopWidget, QComboBox, QSlider
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, QRect, QDir
from PIL import Image

CONFIG_FILE = 'image_viewer_config.json'

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            self.setWindowTitle("Image Slideshow")
            
            logging.debug("Loading config")
            self.config = self.load_config()
            self.last_folder = self.config.get('last_folder', '')
            
            logging.debug("Setting up desktop and geometry")
            self.desktop = QDesktopWidget()
            self.validate_and_set_geometry()

            logging.debug("Setting up UI components")
            self.setup_ui()

            logging.debug("Setting up timers")
            self.setup_timers()

            logging.debug("Loading images")
            if self.last_folder and os.path.isdir(self.last_folder):
                self.load_images(self.last_folder)

            self.update_direction_label()

            logging.debug("Moving to saved screen")
            self.move_to_saved_screen()
            
            logging.debug("Initialization complete")
        except Exception as e:
            logging.error(f"Error during initialization: {str(e)}")
            raise

    def load_config(self):
        logging.debug("Loading configuration")
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_config(self):
        logging.debug("Saving configuration")
        config = {
            'last_folder': self.last_folder,
            'window_geometry': [self.x(), self.y(), self.width(), self.height()],
            'current_slide': self.current_image,
            'slide_direction': self.slideshow_direction,
            'slide_delay': self.slide_delay,
            'screen_number': self.desktop.screenNumber(self)
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.dir_label = QLabel(self)
        self.layout.addWidget(self.dir_label)
        
        self.file_label = QLabel(self)
        self.layout.addWidget(self.file_label)

        self.slide_number_label = QLabel(self)
        self.layout.addWidget(self.slide_number_label)

        self.direction_label = QLabel(self)
        self.layout.addWidget(self.direction_label)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.image_label)

        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)

        self.select_folder_button = QPushButton("Select Folder", self)
        self.select_folder_button.clicked.connect(self.select_folder)
        self.button_layout.addWidget(self.select_folder_button)

        self.prev_button = QPushButton("Previous", self)
        self.prev_button.clicked.connect(self.show_previous_image)
        self.button_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next", self)
        self.next_button.clicked.connect(self.show_next_image)
        self.button_layout.addWidget(self.next_button)

        self.start_stop_button = QPushButton("Start Slideshow", self)
        self.start_stop_button.clicked.connect(self.toggle_slideshow)
        self.button_layout.addWidget(self.start_stop_button)

        self.delay_combo = QComboBox(self)
        self.delay_combo.addItems([f"{i} second{'s' if i > 1 else ''}" for i in range(1, 6)])
        self.delay_combo.currentIndexChanged.connect(self.change_slide_delay)
        self.button_layout.addWidget(self.delay_combo)

        self.slide_slider = QSlider(Qt.Horizontal)
        self.slide_slider.setTickPosition(QSlider.TicksBelow)
        self.slide_slider.setTickInterval(1)
        self.slide_slider.sliderMoved.connect(self.slider_moved)
        self.slide_slider.sliderReleased.connect(self.slider_released)
        self.slide_slider.setFixedWidth(self.width() - 40)  # Set fixed width based on initial window size
        self.layout.addWidget(self.slide_slider)

    def setup_timers(self):
        self.images = []
        self.current_image = self.config.get('current_slide', 0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_slideshow)
        self.slideshow_running = False
        self.slideshow_direction = self.config.get('slide_direction', 1)
        self.slide_delay = self.config.get('slide_delay', 4000)

        self.slider_timer = QTimer(self)
        self.slider_timer.setSingleShot(True)
        self.slider_timer.timeout.connect(self.update_image_after_slider)

        self.delay_combo.setCurrentIndex((self.slide_delay // 1000) - 1)

    def validate_and_set_geometry(self):
        if 'window_geometry' in self.config:
            geometry = self.config['window_geometry']
            screen = self.desktop.screenNumber(self)
            screen_geometry = self.desktop.screenGeometry(screen)
            
            # Check if the saved geometry fits within the current screen
            if (geometry[0] < 0 or  # Left position is negative
                geometry[1] < 0 or  # Top position is negative
                geometry[0] + geometry[2] > screen_geometry.width() or
                geometry[1] + geometry[3] > screen_geometry.height()):
                # If not, center the window on the current screen
                width = min(geometry[2], screen_geometry.width())
                height = min(geometry[3], screen_geometry.height())
                x = (screen_geometry.width() - width) // 2
                y = (screen_geometry.height() - height) // 2
                self.setGeometry(x, y, width, height)
            else:
                self.setGeometry(QRect(*geometry))
        else:
            self.set_default_geometry()

    def set_default_geometry(self):
        screen = self.desktop.screenGeometry()
        width = int(screen.width() * 0.8)
        height = int(screen.height() * 0.8)
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)

    def move_to_saved_screen(self):
        screen_number = self.config.get('screen_number', 0)
        if screen_number < self.desktop.screenCount():
            screen_geometry = self.desktop.screenGeometry(screen_number)
            self.move(screen_geometry.x(), screen_geometry.y())

    def select_folder(self):
        default_folder = self.last_folder if self.last_folder else QDir.homePath()
        parent_folder = os.path.dirname(default_folder) if self.last_folder else default_folder
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", parent_folder)
        if folder:
            self.load_images(folder)
            self.last_folder = folder
            self.save_config()

    def load_images(self, folder):
        self.images = []
        for filename in os.listdir(folder):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                self.images.append(os.path.join(folder, filename))
        if self.images:
            self.current_image = min(self.current_image, len(self.images) - 1)
            self.slide_slider.setRange(0, len(self.images) - 1)
            self.slide_slider.setValue(self.current_image)
            self.show_current_image()
        else:
            self.slide_slider.setRange(0, 0)
        self.update_dir_label()

    def show_image(self, image_path):
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)
            
            scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        
        self.update_file_label(image_path)
        self.update_slide_number_label()

    def show_current_image(self):
        if self.images and 0 <= self.current_image < len(self.images):
            self.show_image(self.images[self.current_image])
            self.slide_slider.setValue(self.current_image)

    def show_next_image(self):
        if self.images:
            self.slideshow_direction = 1
            self.advance_slideshow()

    def show_previous_image(self):
        if self.images:
            self.slideshow_direction = -1
            self.advance_slideshow()

    def advance_slideshow(self):
        if self.images:
            self.current_image = (self.current_image + self.slideshow_direction) % len(self.images)
            self.show_current_image()
        self.update_direction_label()
        self.save_config()

    def toggle_slideshow(self):
        if self.slideshow_running:
            self.timer.stop()
            self.start_stop_button.setText("Start Slideshow")
            self.slideshow_running = False
        else:
            if self.images:
                self.timer.start(self.slide_delay)
                self.start_stop_button.setText("Stop Slideshow")
                self.slideshow_running = True

    def update_dir_label(self):
        if self.images:
            self.dir_label.setText(f"Current Directory: {os.path.dirname(self.images[0])}")
        else:
            self.dir_label.setText("No directory selected")

    def update_file_label(self, image_path):
        self.file_label.setText(f"Current Image: {os.path.basename(image_path)}")

    def update_slide_number_label(self):
        if self.images:
            self.slide_number_label.setText(f"Slide: {self.current_image + 1}/{len(self.images)}")
        else:
            self.slide_number_label.setText("No images loaded")

    def update_direction_label(self):
        direction = "Forward" if self.slideshow_direction == 1 else "Backward"
        self.direction_label.setText(f"Direction: {direction}")

    def change_slide_delay(self, index):
        self.slide_delay = (index + 1) * 1000
        if self.slideshow_running:
            self.timer.stop()
            self.timer.start(self.slide_delay)
        self.save_config()

    def slider_moved(self, value):
        self.slider_timer.stop()
        self.slider_timer.start(500)  # Increased delay to 500ms

    def slider_released(self):
        self.slider_timer.stop()
        self.update_image_after_slider()

    def update_image_after_slider(self):
        if self.images:
            new_index = self.slide_slider.value()
            if new_index != self.current_image:
                self.current_image = new_index
                self.show_current_image()
                self.save_config()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image_display()
        self.save_config()

    def showEvent(self, event):
        super().showEvent(event)
        if self.images and 0 <= self.current_image < len(self.images):
            QTimer.singleShot(100, self.show_current_image)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.save_config()

    def update_image_display(self):
        if self.images and 0 <= self.current_image < len(self.images):
            self.show_current_image()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    try:
        logging.debug("Creating ImageViewer instance")
        viewer = ImageViewer()
        logging.debug("Showing ImageViewer")
        viewer.show()
        logging.debug("Entering event loop")
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Unhandled exception: {str(e)}")
        sys.exit(1)