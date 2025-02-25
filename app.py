from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from pymongo import MongoClient
from mongoengine import Document, StringField, EmailField
from random import randint
from email_service import send_email_via_gmail
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import os

# === MONGOENGINE CONFIGURATION ===
class User(Document):
    name = StringField(required=True, max_length=50)
    family_name = StringField(required=True, max_length=50)
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)

class verification_codes(Document):
    email = EmailField(required=True, unique=True)
    code = StringField(required=True)

app = Flask(__name__, static_folder="dist")
CORS(app, origins='*')

# Use your actual MongoDB connection string
mongo_uri = os.environ.get("MONGO_URI", "mongodb+srv://tal:tubul1497@elysian0softech0task.t83qi7t.mongodb.net/")
client = MongoClient(mongo_uri)
db = client["elysian_db"]

# === FRONTEND ===

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    # If a file with the requested path exists in the dist folder, serve it.
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    # Otherwise, serve index.html (for client-side routing)
    return send_from_directory(app.static_folder, "index.html")

# === TEST ENDPOINT ===
@app.route("/api/test", methods=["GET"])
def test_api():
    return {"message": "Hello from "}

# === REGISTER ENDPOINT ===
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    familyName = data.get("familyName")
    email = data.get("email")
    password = data.get("password")

    # Check if user already exists
    existing_user = db.users.find_one({"email": email})
    if existing_user:
        return jsonify({"error": "User already exists"}), 400

    # Otherwise, create new user
    db.users.insert_one({"email": email, "password": password, "name": name, "familyName": familyName})
    return jsonify({"message": "User created successfully"}), 201


# === LOGIN ENDPOINT ===
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    # ... perform login validation here ...
    user = db.users.find_one({"email": email})
    if not user or user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({"message": "Login successful"}), 200

#=== Verify Email Endpoint ===
@app.route('/api/send_verification_code', methods=['POST'])
def send_verification_code():
    email = request.json.get('email')
    existing_user = db.users.find_one({"email": email})
    print(existing_user)
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    elif existing_user:
        return jsonify({"error": "User already exists"}), 400
    else:       
        code = '{:06d}'.format(randint(0, 999999))
        # Upsert the verification code for this email into the db.verification_codes collection.
        db.verification_codes.update_one(
            {"email": email},
            {"$set": {"code": code}},
            upsert=True
        )
        subject = "Verify Your Email"
        body = f"Your verification code is: {code}"  
    try:
        send_email_via_gmail(email, subject, body)
        return jsonify({'message': 'Verification code sent to ' + email}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/forgot_password', methods=['POST'])
def send_password():
    email = request.json.get('email')
    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"error": "User does not exist"}), 400  
    else:
        password = user["password"]

    subject = "Restore Password"
    body = f"Your password is: {password}"

    try:
        send_email_via_gmail(email, subject, body)
        return jsonify({'message': 'Verification code sent to ' + email}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    email = request.json.get('email')
    code = request.json.get('code')
    
    # Find the verification document by email
    verification_doc = db.verification_codes.find_one({"email": email})
    
    if verification_doc and verification_doc.get("code") == code:
        # If the code is correct, remove the verification record from the DB
        db.verification_codes.delete_one({"email": email})
        return jsonify({'message': 'Email verified successfully!'}), 200
    else:
        return jsonify({'error': 'Invalid verification code'}), 400

# === Google Auth ===
CLIENT_ID = "555947917035-hhid3sur2k74uf16uq9390o97ku4t7ug.apps.googleusercontent.com"

@app.route("/api/google_login", methods=["POST"])
def google_login():
    token = request.json.get("token")
    if not token:
        return jsonify({"error": "No token provided"}), 400

    try:
        # Verify the token using Google's library
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), CLIENT_ID)
        email = id_info.get("email")
        given_name = id_info.get("given_name", "")
        family_name = id_info.get("family_name", "")

        # Check if user already exists in the database
        existing_user = db.users.find_one({"email": email})
        if existing_user:
            # User exists: perform login
            return jsonify({
                "message": "Login successful",
                "user": {
                    "email": existing_user["email"],
                    "name": existing_user.get("name", ""),
                    "familyName": existing_user.get("familyName", "")
                }
            }), 200
        else:
            # User does not exist: register new user
            new_user = {
                "email": email,
                "name": given_name,
                "familyName": family_name,
                # You might store an empty password or generate one automatically
                "password": ""
            }
            db.users.insert_one(new_user)
            return jsonify({
                "message": "User registered successfully",
                "user": new_user
            }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
# === Facebook Auth ===
@app.route("/api/facebook_login", methods=["POST"])
def facebook_login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Extract the required fields from the frontend data.
    email = data.get("email")
    name = data.get("name")
    access_token = data.get("accessToken")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Check if the user already exists.
    existing_user = db.users.find_one({"email": email})
    if existing_user:
        return jsonify({
            "message": "Login successful",
            "user": {
                "email": existing_user["email"],
                "name": existing_user.get("name", ""),
            }
        }), 200
    else:
        # User does not exist: register a new user.
        new_user = {
            "email": email,
            "name": name,
            "accessToken": access_token
        }
        db.users.insert_one(new_user)
        return jsonify({
            "message": "User registered successfully",
            "user": new_user
        }), 201


# === RUN APP ===
if __name__ == "__main__":
    app.run()


#python -m venv venv
#venv\Scripts\activate
