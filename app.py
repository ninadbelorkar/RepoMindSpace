from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Project root directory (same folder as this file)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_app():
    app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
    CORS(app)

    # Configuration from .env
    app.config['MONGO_URI'] = os.getenv('MONGO_URI')
    app.config['MONGO_DB_NAME'] = os.getenv('MONGO_DB_NAME')
    app.config['JWT_SECRET'] = os.getenv('JWT_SECRET')
    app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')

    # Initialize MongoDB
    client = MongoClient(app.config['MONGO_URI'])
    db = client[app.config['MONGO_DB_NAME']]
    app.config['DB'] = db

    # Register API Blueprints
    from routes.auth import auth_bp
    from routes.workspace import workspace_bp
    from routes.artifact import artifact_bp
    from routes.chat import chat_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(workspace_bp, url_prefix='/api/workspace')
    app.register_blueprint(artifact_bp, url_prefix='/api/artifacts')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')

    # ── Serve static frontend ─────────────────────────────────────────────────
    @app.route('/')
    def serve_index():
        return send_from_directory(BASE_DIR, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        # API routes handle themselves — don't intercept them
        if path.startswith('api/'):
            return jsonify({'error': 'Not found'}), 404
        target = os.path.join(BASE_DIR, path)
        if os.path.isfile(target):
            return send_from_directory(BASE_DIR, path)
        # Fallback to index for any unknown route
        return send_from_directory(BASE_DIR, 'index.html')
    # ─────────────────────────────────────────────────────────────────────────

    return app

# Instantiate the app globally for WSGI servers like Gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
