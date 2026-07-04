import datetime
import bcrypt
from pymongo import MongoClient
import os

# The MongoDB client will be initialized in app.py, so we can just use a global or pass the db around.
# For simplicity, we'll assume a global 'db' object that gets set, or we can fetch the URI here.
# It's better to pass the db object to these functions.

def get_users_collection(db):
    return db['Users']

def create_user(db, first_name, last_name, email, password=None, google_id=None, profile_picture=None):
    users = get_users_collection(db)
    
    # Check if user exists
    if users.find_one({"email": email}):
        return None, "User with this email already exists"

    user_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "auth_provider": "google" if google_id else "local",
        "onboarding_completed": False,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow()
    }

    if google_id:
        user_data["google_id"] = google_id
        if profile_picture:
            user_data["profile_picture"] = profile_picture
    
    if password:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_data["password_hash"] = hashed.decode('utf-8')

    result = users.insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    return user_data, None

def get_user_by_email(db, email):
    users = get_users_collection(db)
    user = users.find_one({"email": email})
    if user:
        user["_id"] = str(user["_id"])
    return user

def get_user_by_id(db, user_id):
    from bson.objectid import ObjectId
    users = get_users_collection(db)
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None

def update_user(db, user_id, update_data):
    from bson.objectid import ObjectId
    users = get_users_collection(db)
    update_data["updated_at"] = datetime.datetime.utcnow()
    try:
        users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
        return True
    except Exception:
        return False

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def set_password(db, user_id, new_password):
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    return update_user(db, user_id, {"password_hash": hashed})
