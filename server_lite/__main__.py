"""server_lite 启动入口：python -m server_lite"""
from .app import create_app
from .config import DefaultConfig

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=DefaultConfig.PORT, debug=False)
