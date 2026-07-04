from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import json
import os
import datetime
from bson import ObjectId
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
    session_id = data.get('session_id')

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

    # 1. Session Management
    chat_session = None
    messages_history = []
    if session_id:
        try:
            chat_session = db.chat_sessions.find_one({'_id': ObjectId(session_id), 'workspace_id': workspace_id, 'user_id': user_id})
            if chat_session:
                messages_history = chat_session['messages']
        except:
            pass

    try:
        # 2. Parse repository content
        parser = LocalParser(local_path)
        parsed_data = parser.parse()
        
        # Limit context
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
            
        # 3. Setup Gemini
        load_dotenv(override=True)
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            return jsonify({'error': 'Gemini API key is not configured.'}), 500

        genai.configure(api_key=gemini_api_key)

        # 4. Build Prompt with History
        prompt = f"You are an expert AI pair programmer. Answer the user's question about their codebase.\n\n"
        prompt += f"Here is the codebase context:\n{context_string}\n\n"
        prompt += "--- Conversation History ---\n"
        for msg in messages_history:
            prompt += f"{msg['role'].upper()}: {msg['content']}\n\n"
        prompt += f"USER (latest message): {message}\n"

        MODEL_FALLBACK = ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemma-4-26b-a4b-it', 'gemini-2.5-flash']

        for model_name in MODEL_FALLBACK:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, stream=True)

                first_chunk = None
                for chunk in response:
                    first_chunk = chunk
                    break

                def generate(response=response, first_chunk=first_chunk, sid=session_id, cs=chat_session, msg=message):
                    full_text = ""
                    try:
                        if not cs:
                            title = msg[:30] + "..." if len(msg) > 30 else msg
                            res = db.chat_sessions.insert_one({
                                'workspace_id': workspace_id,
                                'user_id': user_id,
                                'title': title,
                                'messages': [{'role': 'user', 'content': msg}],
                                'created_at': datetime.datetime.utcnow(),
                                'updated_at': datetime.datetime.utcnow()
                            })
                            sid = str(res.inserted_id)
                        else:
                            db.chat_sessions.update_one(
                                {'_id': cs['_id']},
                                {
                                    '$push': {'messages': {'role': 'user', 'content': msg}},
                                    '$set': {'updated_at': datetime.datetime.utcnow()}
                                }
                            )

                        # Yield session_id so frontend knows which chat this is
                        yield f"data: {json.dumps({'session_id': sid})}\n\n"

                        if first_chunk and first_chunk.text:
                            full_text += first_chunk.text
                            yield f"data: {json.dumps({'text': first_chunk.text})}\n\n"
                            
                        for chunk in response:
                            if chunk.text:
                                full_text += chunk.text
                                yield f"data: {json.dumps({'text': chunk.text})}\n\n"

                        # Save AI response
                        db.chat_sessions.update_one(
                            {'_id': ObjectId(sid)},
                            {
                                '$push': {'messages': {'role': 'ai', 'content': full_text}},
                                '$set': {'updated_at': datetime.datetime.utcnow()}
                            }
                        )
                        yield "data: [DONE]\n\n"
                    except ResourceExhausted:
                        yield f"data: {json.dumps({'error': 'Rate limit hit during streaming.'})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"

                return Response(stream_with_context(generate()), content_type='text/event-stream')

            except ResourceExhausted:
                continue
            except Exception as e:
                import traceback
                traceback.print_exc()
                continue

        return jsonify({'error': 'All AI models are currently rate-limited. Please try again in a few minutes.'}), 429

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/history/<workspace_id>', methods=['GET'])
@token_required
def get_chat_history(workspace_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    # Fetch all chat sessions for this workspace, sorted by newest first
    sessions = list(db.chat_sessions.find(
        {'workspace_id': workspace_id, 'user_id': user_id},
        {'_id': 1, 'title': 1, 'updated_at': 1}
    ).sort('updated_at', -1))
    
    serialized_sessions = []
    for session in sessions:
        serialized_sessions.append({
            'id': str(session['_id']),
            'title': session['title'],
            'updated_at': session['updated_at'].isoformat()
        })
        
    return jsonify({'sessions': serialized_sessions}), 200

@chat_bp.route('/session/<session_id>', methods=['GET'])
@token_required
def get_chat_session(session_id):
    db = current_app.config['DB']
    user_id = request.user_id
    
    try:
        session = db.chat_sessions.find_one({'_id': ObjectId(session_id), 'user_id': user_id})
        if not session:
            return jsonify({'error': 'Session not found'}), 404
            
        return jsonify({
            'id': str(session['_id']),
            'title': session['title'],
            'messages': session['messages'],
            'created_at': session['created_at'].isoformat(),
            'updated_at': session['updated_at'].isoformat()
        }), 200
    except Exception as e:
        return jsonify({'error': 'Invalid session ID'}), 400
