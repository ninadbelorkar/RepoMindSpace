from flask import Blueprint, request, jsonify, current_app
from models.user import create_user, get_user_by_email, verify_password, get_user_by_id, update_user, set_password
import jwt
import datetime
import os
import random
import pyotp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2 import id_token
from google.auth.transport import requests
from utils.auth_middleware import token_required

auth_bp = Blueprint('auth', __name__)


def send_otp_email(to_email: str, otp: str) -> bool:
    """
    Send a password reset OTP email via Gmail SMTP.
    Returns True on success, False on failure.
    Falls back to printing the OTP if SMTP is not configured.
    """
    smtp_email = os.environ.get('SMTP_EMAIL', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')

    if not smtp_email or not smtp_password or smtp_email == 'your_gmail_address@gmail.com':
        # Dev fallback — print to console
        print(f"\n[AUTH] Password reset OTP for {to_email}: {otp}  (SMTP not configured)\n")
        return True

    subject = "Your RepoMind Space Password Reset Code"
    html_body = f"""
    <html><body style="font-family: 'Inter', sans-serif; background: #1e1b2e; color: #e2e8f0; padding: 2rem;">
        <div style="max-width: 480px; margin: 0 auto; background: #2d2a3e; border-radius: 16px; padding: 2.5rem; border: 1px solid rgba(168,85,247,0.2);">
            <h1 style="color: #a855f7; font-size: 1.5rem; margin-bottom: 0.5rem;">RepoMind Space</h1>
            <h2 style="font-size: 1.25rem; color: #e2e8f0; margin-bottom: 1rem;">Password Reset Code</h2>
            <p style="color: #94a3b8; margin-bottom: 1.5rem;">You requested a password reset. Use the code below. It expires in <strong style='color:#e2e8f0;'>15 minutes</strong>.</p>
            <div style="background: #1e1b2e; border: 2px solid #a855f7; border-radius: 12px; padding: 1.5rem; text-align: center; margin-bottom: 1.5rem;">
                <span style="font-size: 2.5rem; font-weight: 700; letter-spacing: 0.4em; color: #a855f7; font-family: monospace;">{otp}</span>
            </div>
            <p style="color: #64748b; font-size: 0.85rem;">If you did not request this, you can safely ignore this email. Your password will not change.</p>
        </div>
    </body></html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"RepoMind Space <{smtp_email}>"
        msg['To'] = to_email
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
        print(f"[AUTH] OTP email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[AUTH][ERROR] Failed to send OTP email to {to_email}: {e}")
        # Still print OTP to console as fallback
        print(f"[AUTH] OTP (fallback console): {otp}")
        return False


def generate_jwt(user_id, mfa_verified=True):
    """Generate a JWT. If mfa_verified=False it is a restricted pre-MFA token."""
    secret = current_app.config['JWT_SECRET']
    payload = {
        'user_id': user_id,
        'mfa_verified': mfa_verified,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, secret, algorithm='HS256')


# ─────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    email = data.get('email')
    password = data.get('password')

    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "All fields are required"}), 400

    db = current_app.config['DB']

    # 4.2 — Check for existing Google account with same email → link accounts
    existing = get_user_by_email(db, email)
    if existing:
        if existing.get('auth_provider') == 'google' and not existing.get('password_hash'):
            import bcrypt
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            update_user(db, existing['_id'], {
                'password_hash': hashed,
                'auth_provider': 'both',
                'first_name': first_name,
                'last_name': last_name,
            })
            token = generate_jwt(existing['_id'])
            return jsonify({
                "message": "Account linked successfully. You can now log in with email/password or Google.",
                "token": token,
                "user": {"id": existing['_id'], "email": existing['email'],
                         "first_name": first_name, "last_name": last_name,
                         "onboarding_completed": existing.get('onboarding_completed', True)},
                "account_linked": True
            }), 200
        else:
            return jsonify({"error": "An account with this email already exists. Please log in instead."}), 409

    user, error = create_user(db, first_name, last_name, email, password=password)
    if error:
        return jsonify({"error": error}), 409

    token = generate_jwt(user['_id'])
    return jsonify({
        "message": "User registered successfully",
        "token": token,
        "user": {"id": user['_id'], "email": user['email'], "first_name": user['first_name'],
                 "last_name": user['last_name'], "onboarding_completed": user.get('onboarding_completed', False)}
    }), 201


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"error": "Email and password are required"}), 400

    db = current_app.config['DB']
    user = get_user_by_email(db, email)

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # 4.2 — Google-only account trying to use password login
    if not user.get('password_hash'):
        return jsonify({
            "error": "This account was created with Google Sign-In. Please use the Google button to log in, or register with a password to link your account.",
            "provider_hint": "google"
        }), 401

    if not verify_password(password, user['password_hash']):
        return jsonify({"error": "Invalid email or password"}), 401

    # 4.4 — MFA check: issue restricted pre-MFA token
    if user.get('mfa_enabled') and user.get('mfa_secret'):
        pre_token = generate_jwt(user['_id'], mfa_verified=False)
        return jsonify({
            "mfa_required": True,
            "pre_token": pre_token,
            "message": "MFA verification required"
        }), 200

    token = generate_jwt(user['_id'])
    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {"id": user['_id'], "email": user['email'], "first_name": user['first_name'],
                 "last_name": user['last_name'], "onboarding_completed": user.get('onboarding_completed', False)}
    }), 200


# ─────────────────────────────────────────────
# GOOGLE AUTH
# ─────────────────────────────────────────────
@auth_bp.route('/google', methods=['POST'])
def google_auth():
    data = request.get_json()
    token = data.get('credential')

    if not token:
        return jsonify({"error": "No token provided"}), 400

    client_id = current_app.config['GOOGLE_CLIENT_ID']

    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id, clock_skew_in_seconds=10)

        email = idinfo['email']
        google_id = idinfo['sub']
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture', '')

        db = current_app.config['DB']
        user = get_user_by_email(db, email)

        if user:
            # 4.2 — Existing local account → merge Google into it (silent account link)
            if user.get('auth_provider') == 'local':
                update_user(db, user['_id'], {
                    'google_id': google_id,
                    'auth_provider': 'both',
                    'profile_picture': picture or user.get('profile_picture', '')
                })
                user = get_user_by_id(db, user['_id'])
        else:
            user, error = create_user(db, first_name, last_name, email,
                                      google_id=google_id, profile_picture=picture)
            if error:
                return jsonify({"error": error}), 500

        # 4.4 — MFA check for Google logins too
        if user.get('mfa_enabled') and user.get('mfa_secret'):
            pre_token = generate_jwt(user['_id'], mfa_verified=False)
            return jsonify({
                "mfa_required": True,
                "pre_token": pre_token,
                "message": "MFA verification required"
            }), 200

        jwt_token = generate_jwt(user['_id'])
        return jsonify({
            "message": "Google Login successful",
            "token": jwt_token,
            "user": {"id": user['_id'], "email": user['email'], "first_name": user['first_name'],
                     "last_name": user['last_name'], "onboarding_completed": user.get('onboarding_completed', False)}
        }), 200

    except ValueError as e:
        return jsonify({"error": f"Invalid token: {str(e)}"}), 401


# ─────────────────────────────────────────────
# GET ME
# ─────────────────────────────────────────────
@auth_bp.route('/me', methods=['GET'])
@token_required
def get_me():
    db = current_app.config['DB']
    user = get_user_by_id(db, request.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user['_id'],
        "email": user['email'],
        "first_name": user.get('first_name', ''),
        "last_name": user.get('last_name', ''),
        "onboarding_completed": user.get('onboarding_completed', False),
        "profile_picture": user.get('profile_picture', ''),
        "auth_provider": user.get('auth_provider', 'local'),
        "mfa_enabled": user.get('mfa_enabled', False)
    }), 200


# ─────────────────────────────────────────────
# UPDATE PROFILE
# ─────────────────────────────────────────────
@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_my_profile():
    data = request.get_json()
    update_data = {}
    for field in ['first_name', 'last_name', 'email', 'onboarding_completed', 'profile_picture']:
        if data.get(field) is not None:
            update_data[field] = data[field]

    db = current_app.config['DB']
    if update_data.get('email'):
        existing = get_user_by_email(db, update_data['email'])
        if existing and existing['_id'] != request.user_id:
            return jsonify({"error": "Email is already in use by another account"}), 409

    success = update_user(db, request.user_id, update_data)
    if not success:
        return jsonify({"error": "Failed to update profile"}), 500

    return jsonify({"message": "Profile updated successfully"}), 200


# ─────────────────────────────────────────────
# FORGOT PASSWORD
# ─────────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    db = current_app.config['DB']
    user = get_user_by_email(db, email)
    if not user:
        return jsonify({"message": "If that email exists, a reset code has been sent."}), 200

    otp = str(random.randint(100000, 999999))
    exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    update_user(db, user['_id'], {"reset_otp": otp, "reset_otp_exp": exp})

    send_otp_email(email, otp)
    return jsonify({"message": "If that email exists, a reset code has been sent."}), 200


# ─────────────────────────────────────────────
# RESET PASSWORD
# ─────────────────────────────────────────────
@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    new_password = data.get('new_password')

    if not email or not otp or not new_password:
        return jsonify({"error": "Missing email, OTP, or new password"}), 400

    db = current_app.config['DB']
    user = get_user_by_email(db, email)
    if not user:
        return jsonify({"error": "Invalid email or OTP"}), 401

    user_otp = user.get('reset_otp')
    user_exp = user.get('reset_otp_exp')

    if not user_otp or not user_exp or str(user_otp) != str(otp):
        return jsonify({"error": "Invalid email or OTP"}), 401

    if datetime.datetime.utcnow() > user_exp:
        return jsonify({"error": "OTP has expired"}), 401

    set_password(db, user['_id'], new_password)
    update_user(db, user['_id'], {"reset_otp": None, "reset_otp_exp": None})
    return jsonify({"message": "Password reset successfully"}), 200


# ─────────────────────────────────────────────
# UPDATE PASSWORD (profile page)
# ─────────────────────────────────────────────
@auth_bp.route('/update-password', methods=['PUT'])
@token_required
def update_password_auth():
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"error": "Missing passwords"}), 400

    db = current_app.config['DB']
    user = get_user_by_id(db, request.user_id)

    if not user.get('password_hash'):
        return jsonify({"error": "You log in via Google. Use Forgot Password to establish a local password."}), 400

    if not verify_password(current_password, user['password_hash']):
        return jsonify({"error": "Incorrect current password"}), 401

    set_password(db, request.user_id, new_password)
    return jsonify({"message": "Password updated successfully"}), 200


# ─────────────────────────────────────────────
# DELETE ACCOUNT
# ─────────────────────────────────────────────
@auth_bp.route('/me', methods=['DELETE'])
@token_required
def delete_account():
    from bson.objectid import ObjectId
    db = current_app.config['DB']
    user_id = request.user_id  # string from JWT

    # Delete all user data across collections
    db.workspaces.delete_many({'user_id': user_id})
    if 'artifacts' in db.list_collection_names():
        db.artifacts.delete_many({'user_id': user_id})
    if 'chats' in db.list_collection_names():
        db.chats.delete_many({'user_id': user_id})

    # Delete the user document — must convert string → ObjectId
    try:
        result = db.Users.delete_one({'_id': ObjectId(user_id)})
        if result.deleted_count == 0:
            print(f"[AUTH][WARN] No user found to delete for id: {user_id}")
    except Exception as e:
        print(f"[AUTH][ERROR] Failed to delete user {user_id}: {e}")
        return jsonify({"error": "Failed to delete account"}), 500

    print(f"[AUTH] Account deleted for user_id: {user_id}")
    return jsonify({"message": "Account and associated data deleted successfully"}), 200



# ─────────────────────────────────────────────────────────────────────────────
# 4.4  MFA / TOTP  ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/mfa/setup', methods=['POST'])
@token_required
def mfa_setup():
    """Generate a TOTP secret and return the provisioning URI."""
    db = current_app.config['DB']
    user = get_user_by_id(db, request.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    secret = pyotp.random_base32()
    update_user(db, request.user_id, {"mfa_secret_pending": secret})

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.get('email', ''),
        issuer_name="RepoMind Space"
    )

    return jsonify({"secret": secret, "provisioning_uri": provisioning_uri}), 200


@auth_bp.route('/mfa/verify-setup', methods=['POST'])
@token_required
def mfa_verify_setup():
    """Confirm first TOTP code to enable MFA."""
    data = request.get_json()
    code = data.get('code', '').strip()

    db = current_app.config['DB']
    user = get_user_by_id(db, request.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    pending_secret = user.get('mfa_secret_pending')
    if not pending_secret:
        return jsonify({"error": "No pending MFA setup. Please start setup again."}), 400

    totp = pyotp.TOTP(pending_secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code. Please try again."}), 401

    update_user(db, request.user_id, {
        "mfa_secret": pending_secret,
        "mfa_secret_pending": None,
        "mfa_enabled": True
    })

    return jsonify({"message": "MFA enabled successfully."}), 200


@auth_bp.route('/mfa/disable', methods=['POST'])
@token_required
def mfa_disable():
    """Disable MFA after confirming current TOTP code."""
    data = request.get_json()
    code = data.get('code', '').strip()

    db = current_app.config['DB']
    user = get_user_by_id(db, request.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not user.get('mfa_enabled'):
        return jsonify({"error": "MFA is not enabled."}), 400

    totp = pyotp.TOTP(user['mfa_secret'])
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid code. MFA was not disabled."}), 401

    update_user(db, request.user_id, {
        "mfa_enabled": False,
        "mfa_secret": None,
        "mfa_secret_pending": None
    })

    return jsonify({"message": "MFA disabled successfully."}), 200


@auth_bp.route('/mfa/verify', methods=['POST'])
def mfa_verify_login():
    """
    Verify TOTP code during login.
    Accepts restricted pre-MFA JWT + TOTP code.
    Returns a full verified JWT on success.
    """
    data = request.get_json()
    pre_token = data.get('pre_token')
    code = data.get('code', '').strip()

    if not pre_token or not code:
        return jsonify({"error": "Missing token or code"}), 400

    try:
        secret = current_app.config['JWT_SECRET']
        payload = jwt.decode(pre_token, secret, algorithms=["HS256"])
        if payload.get('mfa_verified') is not False:
            return jsonify({"error": "Token is not a valid pre-MFA token"}), 401
        user_id = payload['user_id']
    except Exception:
        return jsonify({"error": "Invalid or expired token. Please log in again."}), 401

    db = current_app.config['DB']
    user = get_user_by_id(db, user_id)
    if not user or not user.get('mfa_secret'):
        return jsonify({"error": "MFA not configured for this account"}), 400

    totp = pyotp.TOTP(user['mfa_secret'])
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid authentication code"}), 401

    full_token = generate_jwt(user_id, mfa_verified=True)
    return jsonify({
        "message": "MFA verified successfully",
        "token": full_token,
        "user": {
            "id": user['_id'],
            "email": user['email'],
            "first_name": user.get('first_name', ''),
            "last_name": user.get('last_name', ''),
            "onboarding_completed": user.get('onboarding_completed', False)
        }
    }), 200
