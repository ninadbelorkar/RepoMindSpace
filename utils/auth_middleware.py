import jwt
from flask import request, jsonify, current_app
from functools import wraps

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=["HS256"])
            request.user_id = data['user_id']
        except Exception as e:
            return jsonify({'error': 'Token is invalid!'}), 401
            
        return f(*args, **kwargs)
    return decorated
