"""Exit the container after persistent HTTP failure so Compose can restart it."""
import os
import signal
import time
from urllib.request import urlopen


def healthy():
    try:
        with urlopen('http://127.0.0.1:8080/api/health/', timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def monitor(probe=healthy, sleep=time.sleep, terminate=None):
    terminate = terminate or (lambda: os.kill(os.getppid(), signal.SIGTERM))
    sleep(60)
    failures = 0
    while True:
        failures = 0 if probe() else failures + 1
        if failures >= 6:
            print('Persistent health failure; restarting application container.', flush=True)
            terminate()
            return
        sleep(10)


if __name__ == '__main__':
    monitor()
