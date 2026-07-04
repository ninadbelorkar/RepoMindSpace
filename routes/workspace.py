from flask import Blueprint, request, jsonify, current_app
import os
import subprocess
import uuid
import zipfile
from werkzeug.utils import secure_filename
import datetime
import jwt
from functools import wraps
from utils.parser import LocalParser

workspace_bp = Blueprint('workspace', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check Authorization header
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=["HS256"])
            # Pass user_id to the route
            request.user_id = data['user_id']
        except Exception as e:
            return jsonify({'error': 'Token is invalid!'}), 401
            
        return f(*args, **kwargs)
    return decorated

@workspace_bp.route('/create', methods=['POST'])
@token_required
def create_workspace():
    # Support both JSON and multipart/form-data
    is_json = request.is_json
    if is_json:
        data = request.get_json()
        workspace_name = data.get('name')
        description = data.get('description', '')
        repo_url = data.get('repoUrl')
    else:
        workspace_name = request.form.get('name')
        description = request.form.get('description', '')
        repo_url = request.form.get('repoUrl', '')
        
    if not workspace_name:
        return jsonify({'error': 'Workspace name is required.'}), 400
        
    workspace_id = str(uuid.uuid4())
    user_id = request.user_id
    db = current_app.config['DB']

    # ── DEDUPLICATION: prevent double-submit creating two workspaces ──────────
    # If an identical workspace (same user + name + repo) was created in the
    # last 30 seconds, just return that one instead of inserting again.
    thirty_seconds_ago = datetime.datetime.utcnow() - datetime.timedelta(seconds=30)
    existing = db.workspaces.find_one({
        'user_id': user_id,
        'name': workspace_name,
        'repo_url': repo_url or '',
        'created_at': {'$gte': thirty_seconds_ago}
    })
    if existing:
        return jsonify({'workspace': {'id': existing['_id'], 'name': existing['name']}}), 200
    # ─────────────────────────────────────────────────────────────────────────
    
    # Base directory for workspaces
    workspaces_base_dir = os.path.join(os.getcwd(), 'data', 'workspaces')
    os.makedirs(workspaces_base_dir, exist_ok=True)
    
    # Specific workspace directory
    workspace_dir = os.path.join(workspaces_base_dir, workspace_id)
    os.makedirs(workspace_dir, exist_ok=True)
    
    if not is_json and 'file' in request.files:
        # Handle ZIP upload
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if file and file.filename.endswith('.zip'):
            filename = secure_filename(file.filename)
            zip_path = os.path.join(workspaces_base_dir, f"{workspace_id}_{filename}")
            file.save(zip_path)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(workspace_dir)
                os.remove(zip_path) # Clean up zip file
                repo_url = f"local_zip_{filename}" # Save dummy url for zip
            except Exception as e:
                return jsonify({'error': f'Failed to extract ZIP: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Only ZIP files are supported for upload.'}), 400
            
    elif repo_url:
        # Try to clone the repository
        try:
            github_token = os.getenv('GITHUB_TOKEN')
            clone_url = repo_url
            if github_token and 'github.com' in repo_url:
                if repo_url.startswith('https://github.com'):
                    clone_url = repo_url.replace('https://github.com', f'https://{github_token}@github.com')
                elif repo_url.startswith('http://github.com'):
                    clone_url = repo_url.replace('http://github.com', f'http://{github_token}@github.com')

            # Run git clone
            process = subprocess.run(
                ['git', 'clone', clone_url, workspace_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                return jsonify({'error': f'Failed to clone repository: {process.stderr}'}), 400
                
        except Exception as e:
            return jsonify({'error': f'Exception during clone: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Either Repository URL or ZIP file is required.'}), 400
        
    # Repository successfully cloned, save metadata to MongoDB
    new_workspace = {
        '_id': workspace_id,
        'user_id': user_id,
        'name': workspace_name,
        'description': description,
        'repo_url': repo_url,
        'local_path': workspace_dir,
        'status': 'ready',
        'created_at': datetime.datetime.utcnow()
    }
    
    try:
        db.workspaces.insert_one(new_workspace)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
        
    return jsonify({
        'message': 'Workspace created successfully',
        'workspace': {
            'id': workspace_id,
            'name': workspace_name,
            'status': 'ready'
        }
    }), 201

@workspace_bp.route('/<workspace_id>', methods=['GET'])
@token_required
def get_workspace(workspace_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    workspace = db.workspaces.find_one({'_id': workspace_id, 'user_id': user_id})
    if not workspace:
        return jsonify({'error': 'Workspace not found or unauthorized'}), 404
        
    local_path = workspace.get('local_path')
    
    total_files = 0
    technologies = []
    api_endpoints_count = 0
    detected_modules = set()
    folder_structure = "No folder structure available."
    
    def generate_tree(paths):
        tree = {}
        for path in paths:
            parts = path.replace('\\', '/').split('/')
            current = tree
            for part in parts:
                current = current.setdefault(part, {})
        def render_tree(d, prefix=""):
            lines = []
            entries = sorted(list(d.keys()))
            for i, key in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                lines.append(prefix + connector + key)
                extension = "    " if is_last else "│   "
                if d[key]:
                    lines.extend(render_tree(d[key], prefix + extension))
            return lines
        return "\n".join(render_tree(tree))

    if local_path and os.path.exists(local_path):
        try:
            parser = LocalParser(local_path)
            parsed_data = parser.parse()
            total_files = len(parsed_data)
            
            tech_count = {}
            file_paths = []
            
            import re, json
            
            for file_obj in parsed_data:
                lang = file_obj.get('language', 'Unknown')
                path = file_obj.get('path', '')
                content = file_obj.get('content', '')
                
                file_paths.append(path)
                
                if lang and lang.lower() != 'unknown':
                    tech_count[lang] = tech_count.get(lang, 0) + 1
                    
                # Basic API endpoint heuristic
                if lang in ['python', 'javascript', 'typescript', 'go', 'java', 'csharp']:
                    api_endpoints_count += len(re.findall(r'(@app\.route|router\.(get|post|put|delete)|app\.(get|post|put|delete)|http\.HandleFunc|@GetMapping|@PostMapping|[Hh]ttp[Gg]et|[Hh]ttp[Pp]ost)', content))
                
                # Module detection heuristic
                if path.endswith('package.json'):
                    try:
                        pkg = json.loads(content)
                        deps = list(pkg.get('dependencies', {}).keys())[:8]
                        detected_modules.update(deps)
                    except: pass
                elif path.endswith('requirements.txt'):
                    deps = [line.split('==')[0].split('>=')[0].strip() for line in content.split('\n') if line and not line.startswith('#')][:8]
                    detected_modules.update(deps)
                    
            folder_structure = generate_tree(file_paths) if file_paths else "Empty repository."

            # Sort technologies by frequency, take top 5
            sorted_tech = sorted(tech_count.items(), key=lambda item: item[1], reverse=True)
            technologies = [item[0] for item in sorted_tech[:5]]
        except Exception as e:
            print(f"Error parsing workspace: {e}")
            
    if not technologies:
        technologies = ['Unknown']
        
    return jsonify({
        'id': workspace['_id'],
        'name': workspace['name'],
        'description': workspace.get('description', ''),
        'repo_url': workspace.get('repo_url', ''),
        'status': workspace.get('status', 'unknown'),
        'total_files': total_files,
        'technologies': technologies,
        'api_endpoints_count': api_endpoints_count,
        'detected_modules': list(detected_modules),
        'folder_structure': folder_structure,
        'summary': workspace.get('summary')
    }), 200

@workspace_bp.route('/<workspace_id>/generate_summary', methods=['POST'])
@token_required
def generate_summary(workspace_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    workspace = db.workspaces.find_one({'_id': workspace_id, 'user_id': user_id})
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404
        
    local_path = workspace.get('local_path')
    if not local_path or not os.path.exists(local_path):
        return jsonify({'error': 'Workspace files not found'}), 404
        
    try:
        parser = LocalParser(local_path)
        parsed_data = parser.parse()
        
        # Build context
        context_string = ""
        for file_obj in parsed_data[:15]: # Limit to avoid huge tokens
            path = file_obj.get('path', '')
            content = file_obj.get('content', '')
            context_string += f"File: {path}\nContent:\n{content[:400]}\n\n"
            
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        
        prompt = f"""Analyze the following codebase and provide a concise 2-3 sentence high-level summary of what this repository does and what technologies it uses.

CRITICAL INSTRUCTIONS:
- Return ONLY the final 2-3 sentences.
- Do NOT include any bullet points, lists, headings, or markdown formatting (no asterisks).
- Do NOT include your internal thought process, drafts, or reasoning.
- Output MUST be a single plain text paragraph.

Codebase:
{context_string}"""
        
        MODEL_FALLBACK = ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemma-4-26b-a4b-it', 'gemini-2.5-flash']
        summary = None
        
        for model_name in MODEL_FALLBACK:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                summary = response.text
                if summary:
                    break
            except Exception as e:
                print(f"Model {model_name} failed: {e}")
                continue
                
        if not summary:
            return jsonify({'error': 'All models failed to generate summary'}), 500
        
        # Save to DB so we don't have to generate it again
        db.workspaces.update_one({'_id': workspace_id}, {'$set': {'summary': summary}})
        
        return jsonify({'summary': summary}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workspace_bp.route('/stats', methods=['GET'])
@token_required
def get_stats():
    db = current_app.config['DB']
    user_id = request.user_id
    
    total_workspaces = db.workspaces.count_documents({'user_id': user_id})
    repos_processed = db.workspaces.count_documents({'user_id': user_id, 'status': 'ready'})
    generated_artifacts = db.artifacts.count_documents({'user_id': user_id})
    total_chats = db.chat_sessions.count_documents({'user_id': user_id})
        
    now = datetime.datetime.utcnow()
    one_week_ago = now - datetime.timedelta(days=7)
    two_weeks_ago = now - datetime.timedelta(days=14)
    
    def get_growth(collection, date_field):
        this_week = collection.count_documents({'user_id': user_id, date_field: {'$gte': one_week_ago}})
        last_week = collection.count_documents({'user_id': user_id, date_field: {'$gte': two_weeks_ago, '$lt': one_week_ago}})
        if last_week == 0:
            return 100 if this_week > 0 else 0
        return round(((this_week - last_week) / last_week) * 100)

    growth = {
        'workspaces': get_growth(db.workspaces, 'created_at'),
        'repos': get_growth(db.workspaces, 'created_at'),
        'artifacts': get_growth(db.artifacts, 'created_at'),
        'chats': get_growth(db.chat_sessions, 'created_at')
    }
    
    # 7-day chart data for artifacts
    chart_data = []
    chart_labels = []
    # Start of today (midnight)
    today_start = datetime.datetime(now.year, now.month, now.day)
    for i in range(6, -1, -1):
        day_start = today_start - datetime.timedelta(days=i)
        day_end = day_start + datetime.timedelta(days=1)
        count = db.artifacts.count_documents({'user_id': user_id, 'created_at': {'$gte': day_start, '$lt': day_end}})
        chart_data.append(count)
        chart_labels.append(day_start.strftime('%a'))

    return jsonify({
        'total_workspaces': total_workspaces,
        'repos_processed': repos_processed,
        'generated_artifacts': generated_artifacts,
        'total_chats': total_chats,
        'growth': growth,
        'chart': {
            'labels': chart_labels,
            'data': chart_data
        }
    }), 200
@workspace_bp.route('/list', methods=['GET'])
@token_required
def list_workspaces():
    db = current_app.config['DB']
    user_id = request.user_id

    workspaces = list(db.workspaces.find({'user_id': user_id}).sort('created_at', -1))
    result = []
    for ws in workspaces:
        ws_id = ws['_id']
        artifact_count = db.artifacts.count_documents({'workspace_id': ws_id}) if 'artifacts' in db.list_collection_names() else 0
        chat_count = db.chat_sessions.count_documents({'workspace_id': ws_id}) if 'chat_sessions' in db.list_collection_names() else 0

        # Parse tech stack if local_path exists
        technologies = []
        local_path = ws.get('local_path', '')
        if local_path and os.path.exists(local_path):
            try:
                parser = LocalParser(local_path)
                parsed_data = parser.parse()
                tech_count = {}
                for f in parsed_data:
                    lang = f.get('language', '')
                    if lang and lang.lower() != 'unknown':
                        tech_count[lang] = tech_count.get(lang, 0) + 1
                technologies = [k for k, _ in sorted(tech_count.items(), key=lambda x: x[1], reverse=True)[:4]]
            except Exception:
                pass

        result.append({
            'id': ws_id,
            'name': ws.get('name', 'Untitled'),
            'description': ws.get('description', ''),
            'repo_url': ws.get('repo_url', ''),
            'status': ws.get('status', 'ready'),
            'technologies': technologies or ['Unknown'],
            'artifact_count': artifact_count,
            'chat_count': chat_count,
            'created_at': ws['created_at'].isoformat() if ws.get('created_at') else ''
        })

    return jsonify({'workspaces': result}), 200

@workspace_bp.route('/recent', methods=['GET'])
@token_required
def get_recent_workspace():
    db = current_app.config['DB']
    user_id = request.user_id

    workspace = db.workspaces.find_one(
        {'user_id': user_id},
        sort=[('created_at', -1)]
    )

    if workspace:
        return jsonify({
            'has_workspace': True,
            'workspace': {
                'id': workspace['_id'],
                'name': workspace.get('name', 'Untitled'),
                'status': workspace.get('status', 'ready'),
                'repo_url': workspace.get('repo_url', '')
            }
        }), 200
    else:
        return jsonify({'has_workspace': False}), 200


@workspace_bp.route('/<workspace_id>', methods=['DELETE'])
@token_required
def delete_workspace(workspace_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    workspace = db.workspaces.find_one({'_id': workspace_id, 'user_id': user_id})
    if not workspace:
        return jsonify({'error': 'Workspace not found or unauthorized'}), 404
        
    db.workspaces.delete_one({'_id': workspace_id})
    
    if 'artifacts' in db.list_collection_names():
        db.artifacts.delete_many({'workspace_id': workspace_id})
    if 'chat_sessions' in db.list_collection_names():
        db.chat_sessions.delete_many({'workspace_id': workspace_id})
        
    import shutil
    local_path = workspace.get('local_path')
    if local_path and os.path.exists(local_path):
        try:
            shutil.rmtree(local_path)
        except Exception:
            pass
            
    return jsonify({"message": "Workspace deleted successfully"}), 200
