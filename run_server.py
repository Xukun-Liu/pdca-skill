import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server_lite.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=app.config.get('PORT', 5210), debug=True)
