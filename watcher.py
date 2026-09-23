import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from processor import process_photo


class PhotoHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        if event.src_path.lower().endswith((".jpg", ".jpeg", ".png")):
            print("New cloud photo detected!")

            time.sleep(2)

            process_photo(event.src_path)


folder_to_watch = "cloud_input"

event_handler = PhotoHandler()

observer = Observer()

observer.schedule(
    event_handler,
    folder_to_watch,
    recursive=False
)

observer.start()

print("GH AutoMedia cloud receiver is running...")
print("Waiting for incoming photos...")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    observer.stop()

observer.join()