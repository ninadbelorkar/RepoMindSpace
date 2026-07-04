from flask import Blueprint, request, jsonify, current_app
import os
import uuid
import datetime
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from utils.parser import LocalParser
from routes.workspace import token_required

artifact_bp = Blueprint('artifact', __name__)

@artifact_bp.route('/generate', methods=['POST'])
@token_required
def generate_artifact():
    data = request.get_json()
    workspace_id = data.get('workspaceId')
    artifact_type = data.get('type')
    
    if not workspace_id or not artifact_type:
        return jsonify({'error': 'Workspace ID and Artifact Type are required.'}), 400
        
    db = current_app.config['DB']
    user_id = request.user_id
    
    # Retrieve workspace
    workspace = db.workspaces.find_one({'_id': workspace_id, 'user_id': user_id})
    if not workspace:
        return jsonify({'error': 'Workspace not found or unauthorized'}), 404
        
    local_path = workspace.get('local_path')
    if not local_path or not os.path.exists(local_path):
        return jsonify({'error': 'Repository files not found on server'}), 404
        
    try:
        # 1. Parse repository files
        parser = LocalParser(local_path)
        parsed_data = parser.parse()
        
        # Limit context to avoid token limits (take top files until char limit is reached)
        MAX_CHARS = 100000 # ~25,000 tokens to stay safely under 250k free tier limit
        context_string = ""
        
        for file_obj in parsed_data:
            if len(context_string) >= MAX_CHARS:
                context_string += "\n... (context truncated due to token limits) ...\n"
                break
                
            # If adding this entire file exceeds the limit, truncate the file itself
            file_content = file_obj['content']
            if len(context_string) + len(file_content) > MAX_CHARS:
                allowed_chars = MAX_CHARS - len(context_string)
                context_string += f"\n--- {file_obj['path']} ---\n{file_content[:allowed_chars]}\n... (file truncated) ...\n"
                break
            else:
                context_string += f"\n--- {file_obj['path']} ---\n{file_content}\n"
            
        # 2. Setup Gemini (Force reload .env to get the newest key)
        load_dotenv(override=True)
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            return jsonify({'error': 'Gemini API key is not configured on the server.'}), 500

        genai.configure(api_key=gemini_api_key)

        # 3. Build Prompt
        prompt = f"You are an expert software engineer. I need you to generate a {artifact_type} for the following codebase.\n\n"
        if artifact_type.lower() == 'readme':
            prompt += "Please write a comprehensive README.md. Include Project Title, Description, Features, Folder Structure, Setup Instructions, and Usage.\n"
        elif artifact_type.lower() == 'documentation':
            prompt += "Please write technical documentation focusing on architecture, modules, and data flow.\n"
        elif artifact_type.lower() == 'userstories':
            prompt += "Please write Agile User Stories based on the features found in the code. Include Acceptance Criteria.\n"
        elif artifact_type.lower() == 'testcases':
            prompt += "Please write a set of functional Test Cases and scenarios for this application.\n"
        elif artifact_type.lower() == 'buganalysis':
            prompt += "Please perform a Bug Analysis. Point out code smells, potential bugs, and security risks.\n"
        elif artifact_type.lower() == 'commitsummary':
            prompt += "Please write a summary of what this project does and the likely development progress based on the files.\n"
        else:
            prompt += f"Please write a {artifact_type} document.\n"

        prompt += f"\nHere is the codebase context:\n{context_string}"

        # 4. Generate with model fallback chain
        # Tries each model in order; moves to next if quota is hit
        MODEL_FALLBACK = [
            'gemini-2.0-flash',
            'gemini-2.0-flash-lite',
            'gemma-4-26b-a4b-it',
            'gemini-2.5-flash',
        ]
        generated_text = None
        last_error = None

        for model_name in MODEL_FALLBACK:
            try:
                print(f"[ARTIFACT] Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                generated_text = response.text
                print(f"[ARTIFACT] Success with model: {model_name}")
                break
            except ResourceExhausted as e:
                print(f"[ARTIFACT] Quota hit for {model_name}, trying next...")
                last_error = e
                continue
            except Exception as e:
                print(f"[ARTIFACT] Error with {model_name}: {e}")
                last_error = e
                continue

        if generated_text is None:
            return jsonify({'error': f'All AI models are currently rate-limited. Please try again in a few minutes. Details: {str(last_error)}'}), 429
        
        # 5. Save to DB
        artifact_id = str(uuid.uuid4())
        new_artifact = {
            '_id': artifact_id,
            'user_id': user_id,
            'workspace_id': workspace_id,
            'type': artifact_type,
            'title': f"{artifact_type} - {workspace.get('name')}",
            'content': generated_text,
            'created_at': datetime.datetime.utcnow()
        }
        
        db.artifacts.insert_one(new_artifact)
        
        return jsonify({
            'message': 'Artifact generated successfully',
            'artifact_id': artifact_id
        }), 201
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to generate artifact: {str(e)}'}), 500

@artifact_bp.route('/<artifact_id>', methods=['GET'])
@token_required
def get_artifact(artifact_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    artifact = db.artifacts.find_one({'_id': artifact_id, 'user_id': user_id})
    if not artifact:
        return jsonify({'error': 'Artifact not found'}), 404
        
    return jsonify({
        'id': artifact['_id'],
        'workspace_id': artifact['workspace_id'],
        'type': artifact['type'],
        'title': artifact['title'],
        'content': artifact['content'],
        'created_at': artifact['created_at'].isoformat()
    }), 200
    
@artifact_bp.route('/<artifact_id>', methods=['PUT'])
@token_required
def update_artifact(artifact_id):
    data = request.get_json()
    db = current_app.config['DB']
    user_id = request.user_id
    
    artifact = db.artifacts.find_one({'_id': artifact_id, 'user_id': user_id})
    if not artifact:
        return jsonify({'error': 'Artifact not found'}), 404
        
    content = data.get('content')
    if content is None:
        return jsonify({'error': 'Content is required'}), 400
        
    db.artifacts.update_one({'_id': artifact_id}, {'$set': {'content': content, 'updated_at': datetime.datetime.utcnow()}})
    return jsonify({'message': 'Artifact updated successfully'}), 200

@artifact_bp.route('/workspace/<workspace_id>', methods=['GET'])
@token_required
def get_workspace_artifacts(workspace_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    artifacts_cursor = db.artifacts.find({'workspace_id': workspace_id, 'user_id': user_id}).sort('created_at', -1)
    
    artifacts = []
    for art in artifacts_cursor:
        artifacts.append({
            'id': str(art['_id']),
            'type': art['type'],
            'title': art['title'],
            'created_at': art['created_at'].isoformat()
        })
        
    return jsonify({'artifacts': artifacts}), 200
