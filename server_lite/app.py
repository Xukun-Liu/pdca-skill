"""Flask 应用工厂"""
from flask import Flask, jsonify, send_from_directory
from .contracts import export_contracts
from .config import DefaultConfig, PACKAGE_DIR


def create_app(config=None):
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config.from_object(DefaultConfig)
    if config:
        app.config.update(config)

    # 注册 Blueprint
    from .api_docs import docs_bp
    from .api_skills import skills_bp
    from .api_knowledge import knowledge_bp
    from .api_settings import bp as settings_bp  # T010: 数据管理 API（路径遍历防护 + localhost）
    app.register_blueprint(docs_bp, url_prefix="/api")
    app.register_blueprint(skills_bp, url_prefix="/api")
    app.register_blueprint(knowledge_bp, url_prefix="/api")
    # T010: settings_bp 已在 api_settings.py 内置 url_prefix="/api/settings"，不再加 /api 前缀
    app.register_blueprint(settings_bp)

    # API 契约单源生成端点
    @app.route("/api/contracts.json")
    def contracts():
        return jsonify(export_contracts())

    # 健康检查
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": "v1.0.2"})

    # 前端入口
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    return app
