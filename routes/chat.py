from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import json
import os
import time
import datetime
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from utils.parser import LocalParser
from routes.workspace import token_required

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/ask', methods=['POST'])
@token_required
def ask_question():
    data = request.get_json()
    if not data or 'workspace_id' not in data or 'message' not in data:
        return jsonify({'error': 'Missing workspace_id or message'}), 400

    workspace_id = data['workspace_id']
    message = data['message']

    # 1. Get workspace info
    db = current_app.config['DB']
    user_id = request.user_id
    try:
        workspace = db.workspaces.find_one({'_id': workspace_id, 'user_id': user_id})
    except Exception:
        return jsonify({'error': 'Invalid workspace ID'}), 400

    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404

    local_path = workspace.get('local_path')
    if not local_path or not os.path.exists(local_path):
        return jsonify({'error': 'Local repository path not found. Please sync again.'}), 404

    try:
        # 2. Parse repository content
        parser = LocalParser(local_path)
        parsed_data = parser.parse()
        
        # Limit context to avoid token limits
        MAX_CHARS = 100000 
        context_string = ""
        
        for file_obj in parsed_data:
            if len(context_string) >= MAX_CHARS:
                context_string += "\n... (context truncated due to token limits) ...\n"
                break
                
            file_content = file_obj['content']
            if len(context_string) + len(file_content) > MAX_CHARS:
                allowed_chars = MAX_CHARS - len(context_string)
                context_string += f"\n--- {file_obj['path']} ---\n{file_content[:allowed_chars]}\n... (file truncated) ...\n"
                break
            else:
                context_string += f"\n--- {file_obj['path']} ---\n{file_content}\n"
            
        # 3. Setup Gemini (force load env)
        load_dotenv(override=True)
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            return jsonify({'error': 'Gemini API key is not configured.'}), 500

        genai.configure(api_key=gemini_api_key)

        # 4. Build Prompt
        prompt = f"You are an expert AI pair programmer. Answer the user's question about their codebase.\n\n"
        prompt += f"User Question: {message}\n\n"
        prompt += f"Here is the codebase context:\n{context_string}"

        # 5. Model fallback chain — stream directly, catch quota errors per model
        MODEL_FALLBACK = [
            'gemini-2.0-flash',
            'gemini-2.0-flash-lite',
            'gemma-4-26b-a4b-it',
            'gemini-2.5-flash',
        ]

        for model_name in MODEL_FALLBACK:
            try:
                print(f"[CHAT] Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, stream=True)

                # Peek at first chunk to detect quota errors before we start streaming
                first_chunk = None
                for chunk in response:
                    first_chunk = chunk
                    break

                print(f"[CHAT] Streaming with model: {model_name}")

                def generate(response=response, first_chunk=first_chunk):
                    full_text = ""
                    try:
                        # Yield the already-read first chunk
                        if first_chunk and first_chunk.text:
                            full_text += first_chunk.text
                            yield f"data: {json.dumps({'text': first_chunk.text})}\n\n"
                        # Continue with the rest
                        for chunk in response:
                            if chunk.text:
                                full_text += chunk.text
                                yield f"data: {json.dumps({'text': chunk.text})}\n\n"

                        # Save chat record after completion
                        db.chats.insert_one({
                            'workspace_id': workspace_id,
                            'user_id': user_id,
                            'question': message,
                            'created_at': datetime.datetime.utcnow()
                        })
                        yield "data: [DONE]\n\n"
                    except ResourceExhausted:
                        yield f"data: {json.dumps({'error': 'Rate limit hit during streaming. Please try again.'})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"

                return Response(stream_with_context(generate()), content_type='text/event-stream')

            except ResourceExhausted as e:
                print(f"[CHAT] Quota hit for {model_name}, trying next...")
                continue
            except Exception as e:
                import traceback
                print(f"[CHAT] Error with {model_name}: {type(e).__name__}: {e}")
                traceback.print_exc()
                continue

        return jsonify({'error': 'All AI models are currently rate-limited. Please try again in a few minutes.'}), 429

    except Exception as e:
        import traceback
        print(f"[CHAT][ERROR] Unhandled exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/recent/<workspace_id>', methods=['GET'])
@token_required
def get_recent_chats(workspace_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    # Fetch top 5 recent questions for this workspace
    recent_chats = list(db.chats.find({'workspace_id': workspace_id, 'user_id': user_id}).sort('created_at', -1).limit(5))
    
    # Serialize ObjectId and datetime
    serialized_chats = []
    for chat in recent_chats:
        serialized_chats.append({
            'id': str(chat['_id']),
            'question': chat['question'],
            'created_at': chat['created_at'].isoformat()
        })
        
    return jsonify({'recent_questions': serialized_chats}), 200

