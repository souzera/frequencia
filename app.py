import os

from flask import Flask, render_template
from media import bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=4096,
        MEDIA_TIMEOUT=int(os.environ.get('MEDIA_TIMEOUT', '180')),
        MEDIA_MAX_BYTES=200 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    app.register_blueprint(bp)

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
