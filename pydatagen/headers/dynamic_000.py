# Make sure to set a method called "headers()" (dict)

# import time
import platform


def headers() -> dict:
    return {
        "program": "python",
        "version": platform.python_version(),
        "node": platform.node(),
        "environment": "test",
        # "time": time.time(),
    }
