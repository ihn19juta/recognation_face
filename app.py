from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, send_file
from database import db, User, AccessLog, AccessSchedule, DoorLog
import json
import os
import base64
import pickle
import cv2
import face_recognition
import numpy as np
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image
import io




# var
global data_status;

app = Flask(__name__)

# Konfigurasi MySQL
app.config['SECRET_KEY'] = 'smart-door-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@localhost/smart_door_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_RECYCLE'] = 299
app.config['SQLALCHEMY_POOL_SIZE'] = 20
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ENCODINGS_FOLDER'] = 'encodings'
app.config['FACE_DATA_FOLDER'] = 'static/face_data'

# Inisialisasi database
db.init_app(app)

# Buat folder jika belum ada
os.makedirs(app.config['ENCODINGS_FOLDER'], exist_ok=True)
os.makedirs(app.config['FACE_DATA_FOLDER'], exist_ok=True)

# File untuk menyimpan encoding wajah
ENCODINGS_FILE = os.path.join(app.config['ENCODINGS_FOLDER'], 'faces.pkl')

# Inisialisasi data wajah
def load_face_encodings():
    """Load encoding wajah dari file"""
    
    try:
        if os.path.exists(ENCODINGS_FILE):
            with open(ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)
                print(f"✅ Loaded {len(data.get('names', []))} face encodings")
                return data
    except Exception as e:
        print(f"❌ Error loading face encodings: {e}")
    
    # Return data kosong jika file tidak ada
    return {"encodings": [], "names": [], "user_ids": []}

def save_face_encodings(data):
    """Simpan encoding wajah ke file"""
    try:
        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump(data, f)
        print(f"✅ Saved {len(data['names'])} face encodings")
        return True
    except Exception as e:
        print(f"❌ Error saving face encodings: {e}")
        return False

# Load data wajah saat startup
face_data = load_face_encodings()

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image_from_base64(base64_string, user_id="temp", filename_prefix="face"):
    """Simpan gambar dari base64 ke file"""
    try:
        # Decode base64 string
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
        
        image_data = base64.b64decode(base64_string)
        
        # Buat folder uploads jika belum ada
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Buat filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{user_id}_{timestamp}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Simpan gambar langsung tanpa PIL untuk menghindari error
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        # Verifikasi file berhasil disimpan
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"✅ Image saved: {filepath} ({os.path.getsize(filepath)} bytes)")
            return filename, filepath
        else:
            print(f"❌ Failed to save image: {filepath}")
            return None, None
        
    except Exception as e:
        print(f"❌ Error saving image: {e}")
        return None, None

@app.route('/api/enroll-face', methods=['POST'])
def enroll_face_api():
    """API endpoint untuk enroll wajah baru"""
    try:
        data = None
        image_data = None
        name = None
        email = None
        role = 'user'

        if request.is_json:
            data = request.get_json(silent=True) or {}
            name = data.get('name')
            email = data.get('email')
            role = data.get('role', 'user')
            image_data = data.get('image')
        else:
            name = request.form.get('name')
            email = request.form.get('email')
            role = request.form.get('role', 'user')

            if 'image' in request.files and request.files['image'].filename:
                image_file = request.files['image']
                if image_file and allowed_file(image_file.filename):
                    temp_filename = secure_filename(f"temp_face_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}")
                    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                    image_file.save(temp_path)
                    image_data = temp_path
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid image file'
                    }), 400
            else:
                image_data = request.form.get('image')
        
        if not name or not email:
            return jsonify({
                'status': 'error',
                'message': 'Name and email are required'
            }), 400
        
        if not image_data:
            return jsonify({
                'status': 'error',
                'message': 'No image data provided'
            }), 400
        
        # Cek apakah email sudah terdaftar
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'status': 'error',
                'message': 'Email already registered'
            }), 400
        
        # Simpan gambar temporer atau gunakan file upload langsung
        if isinstance(image_data, str) and os.path.exists(image_data):
            filepath = image_data
            saved_filename = os.path.basename(filepath)
        else:
            saved_filename, filepath = save_image_from_base64(image_data, "temp", "temp_face")
        
        if not saved_filename or not filepath:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save image'
            }), 500
        
        # Verifikasi file ada
        if not os.path.exists(filepath):
            return jsonify({
                'status': 'error',
                'message': 'Saved image file not found'
            }), 500
        
        try:
            # Extract face encoding
            face_encoding, error_message = extract_face_encoding(filepath)
           
            
            if error_message:
                # Hapus file temporer jika error
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 400
            
            # Cek apakah wajah sudah terdaftar
            is_registered, registered_name = is_face_already_registered(face_encoding)
            if is_registered:
                # Hapus file temporer
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({
                    'status': 'error',
                    'message': f'Face already registered as {registered_name}'
                }), 409
            
            # Buat user baru di database
            user = User(
                name=name,
                email=email,
                role=role,
                status='active',
                profile_picture=saved_filename
            )
            
            db.session.add(user)
            db.session.commit()
            
            print(f"✅ User created: {user.id} - {user.name}")
            
            # Buat nama file baru dengan user_id
            new_filename = f"face_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            
            # Cek apakah file lama ada sebelum rename
            if os.path.exists(filepath):
                try:
                    os.rename(filepath, new_filepath)
                    print(f"✅ File renamed: {filepath} -> {new_filepath}")
                except Exception as rename_error:
                    print(f"❌ Error renaming file: {rename_error}")
                    # Copy file sebagai fallback
                    import shutil
                    shutil.copy2(filepath, new_filepath)
                    print(f"✅ File copied as fallback")
            else:
                print(f"❌ Original file not found for renaming: {filepath}")
                # Buat file baru dari base64 langsung
                saved_filename, new_filepath = save_image_from_base64(image_data, user.id, "face")
                if not saved_filename:
                    raise Exception("Failed to save image for user")
            
            # Update user dengan filename baru
            user.profile_picture = new_filename
            user.face_encoding = json.dumps(face_encoding)
            db.session.commit()
            
            # Simpan encoding ke file pickle
            face_data["encodings"].append(face_encoding)
            face_data["names"].append(name)
            face_data["user_ids"].append(user.id)
            save_face_encodings(face_data)
            
            # Juga simpan encoding ke folder terpisah
            user_encoding_file = os.path.join(
                app.config['FACE_DATA_FOLDER'], 
                f"face_{user.id}.pkl"
            )
            with open(user_encoding_file, 'wb') as f:
                pickle.dump({
                    'name': name,
                    'encoding': face_encoding,
                    'user_id': user.id,
                    'email': email,
                    'timestamp': datetime.now().isoformat()
                }, f)
            
            print(f"✅ Face enrolled successfully for user {user.id}")
            
            return jsonify({
                'status': 'success',
                'message': 'Face enrolled successfully',
                'user_id': user.id,
                'user_name': user.name
            })
            
        except Exception as e:
            print(f"❌ Error in enroll process: {str(e)}")
            # Hapus file temporer jika ada
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            
            # Rollback database
            db.session.rollback()
            
            # Hapus user jika sudah dibuat
            if 'user' in locals():
                try:
                    db.session.delete(user)
                    db.session.commit()
                except:
                    db.session.rollback()
            
            raise e
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500

def extract_face_encoding(image_path):
    """Extract face encoding dari gambar menggunakan face_recognition"""
    try:
        # Load gambar
        image = face_recognition.load_image_file(image_path)
        
        # Deteksi wajah
        face_locations = face_recognition.face_locations(image)
        
        if len(face_locations) == 0:
            return None, "No face detected"
        
        if len(face_locations) > 1:
            return None, "Multiple faces detected"
        
        # Extract encoding
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        if not face_encodings:
            return None, "Could not extract face features"
        
        face_encoding = face_encodings[0]
        return face_encoding.tolist(), None
        
    except Exception as e:
        print(f"Error extracting face encoding: {e}")
        return None, str(e)

# def is_face_already_registered(face_encoding):
#     """Cek apakah wajah sudah terdaftar"""
#     if not face_data["encodings"]:
#         return False, None
    
#     # Convert to numpy array
#     encoding_array = np.array(face_encoding)
#     known_encodings = np.array(face_data["encodings"])
    
#     # Compare dengan semua wajah yang sudah terdaftar
#     matches = face_recognition.compare_faces(known_encodings, encoding_array, tolerance=0.5)
    
#     if True in matches:
#         idx = matches.index(True)
#         return True, face_data["names"][idx]
    
#     return False, None

def is_face_already_registered(face_encoding):
    if not face_data["encodings"]:
        return False, None

    encoding_array = np.array(face_encoding)
    known_encodings = np.array(face_data["encodings"])

    # Hitung jarak wajah
    face_distances = face_recognition.face_distance(
        known_encodings,
        encoding_array
    )

    # Cari wajah paling mirip
    best_match_index = np.argmin(face_distances)

    # Threshold lebih ketat
    if face_distances[best_match_index] < 0.5:
        return True, face_data["names"][best_match_index]

    return False, None





def get_admin_user():
    """Get or create admin user"""
    admin = User.query.filter_by(email='admin@smartdoor.com').first()
    if not admin:
        admin = User(
            name='Administrator',
            email='admin@smartdoor.com',
            role='admin',
            status='active'
        )
        db.session.add(admin)
        db.session.commit()
    return admin

# ==================== ROUTES ====================

@app.route('/')
def dashboard():
    try:
        page = request.args.get('page', 1, type=int)
        total_users = User.query.count()
        active_users = User.query.filter_by(status='active').count()
        
        today = datetime.now().date()
        today_access = AccessLog.query.filter(
            db.func.date(AccessLog.access_time) == today
        ).count()
        
        access_logs = AccessLog.query.order_by(AccessLog.access_time.desc()).paginate(
            page=page,
            per_page=10,
            error_out=False
        )
        recent_access = access_logs.items
        
        return render_template('dashboard.html', 
                             total_users=total_users,
                             active_users=active_users,
                             today_access=today_access,
                             recent_access=recent_access,
                             pagination=access_logs)
    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        return render_template('dashboard.html', 
                             total_users=0,
                             active_users=0,
                             today_access=0,
                             recent_access=[],
                             pagination=None)

@app.route('/users')
def user_management():
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('user_management.html', users=users)
    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        return render_template('user_management.html', users=[])

@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
    """Tambah user baru dengan atau tanpa face enrollment"""
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            role = request.form['role']
            
            # Validasi input
            if not name or not email:
                flash('Name and email are required', 'error')
                return redirect(url_for('add_user'))
            
            # Cek apakah email sudah terdaftar
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already registered', 'error')
                return redirect(url_for('add_user'))
            
            user = User(
                name=name,
                email=email,
                role=role,
                status='active'
            )
            
            # Handle file upload (jika ada upload file)
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    user.profile_picture = filename
                    
                    # Coba extract face encoding dari gambar yang diupload
                    face_encoding, error_msg = extract_face_encoding(filepath)
                    if face_encoding:
                        user.face_encoding = json.dumps(face_encoding)
            
            db.session.add(user)
            db.session.commit()
            
            flash('User added successfully', 'success')
            return redirect(url_for('user_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding user: {str(e)}', 'error')
            return redirect(url_for('add_user'))
    
    return render_template('add_user.html')

@app.route('/enroll-face')
def enroll_face_page():
    """Halaman untuk enroll wajah baru"""
    return render_template('enroll_face.html')

@app.route('/face-recognition-demo')
def face_recognition_demo():
    """Halaman demo face recognition dengan webcam"""
    return render_template('face_recognition_demo.html')

@app.route('/video_feed')
def video_feed():
    """Stream video dengan face recognition real-time"""
    def generate_frames():
        camera = cv2.VideoCapture(0)
        
        # Set camera properties untuk performa lebih baik
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 30)
        
        while True:
            success, frame = camera.read()
            if not success:
                break
            
            try:
                # Resize frame untuk performa lebih cepat
                small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                
                # Convert frame ke RGB
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Deteksi wajah
                face_locations = face_recognition.face_locations(rgb_small_frame)
                
                # Scale kembali lokasi wajah ke ukuran frame asli
                face_locations = [(top * 2, right * 2, bottom * 2, left * 2) 
                                 for (top, right, bottom, left) in face_locations]
                
                # Extract encodings dari frame kecil untuk performa
                face_encodings = face_recognition.face_encodings(rgb_small_frame, 
                                                               [(t//2, r//2, b//2, l//2) 
                                                                for (t, r, b, l) in face_locations])
                
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    name = "Unknown"
                    color = (0, 0, 255)  # Merah untuk unknown
                    
                    if face_data["encodings"]:
                        # Convert to numpy array
                        known_encodings = np.array(face_data["encodings"])
                        
                        # Compare wajah
                        matches = face_recognition.compare_faces(
                            known_encodings, 
                            face_encoding, 
                            tolerance=0.5
                        )
                        
                        if True in matches:
                            first_match_index = matches.index(True)
                            name = face_data["names"][first_match_index]
                            color = (0, 255, 0)  # Hijau untuk recognized
                            
                            # Ambil user_id jika ada
                            if "user_ids" in face_data and first_match_index < len(face_data["user_ids"]):
                                user_id = face_data["user_ids"][first_match_index]
                    
                    # Gambar kotak dan nama
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                    cv2.putText(frame, name, (left + 6, bottom - 6), 
                               cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
            
            except Exception as e:
                print(f"Error in face recognition: {e}")
            
            # Encode frame ke JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        
        camera.release()
    
    return Response(generate_frames(), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/face-recognition', methods=['POST'])
def face_recognition_api():
    """API endpoint untuk face recognition dari gambar"""
    try:
        if 'image' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image provided'}), 400
        
        file = request.files['image']
        if file and allowed_file(file.filename):
            # Simpan file temporer
            temp_filename = f"temp_{datetime.now().timestamp()}.jpg"
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            file.save(temp_path)
            
            try:
                # Load dan proses gambar
                image = face_recognition.load_image_file(temp_path)
                face_locations = face_recognition.face_locations(image)
                
                if len(face_locations) == 0:
                    # Log denied access
                    access_log = AccessLog(
                        access_type='entry',
                        access_method='face',
                        status='denied',
                        confidence_score=0,
                        camera_location='API Endpoint'
                    )
                    db.session.add(access_log)
                    db.session.commit()
                    
                    os.remove(temp_path)
                    return jsonify({
                        'status': 'denied',
                        'message': 'No face detected'
                    }), 200
                
                # Extract encoding
                face_encodings = face_recognition.face_encodings(image, face_locations)
                
                for face_encoding in face_encodings:
                    if face_data["encodings"]:
                        known_encodings = np.array(face_data["encodings"])
                        matches = face_recognition.compare_faces(
                            known_encodings, 
                            face_encoding, 
                            tolerance=0.5
                        )
                        
                        if True in matches:
                            first_match_index = matches.index(True)
                            name = face_data["names"][first_match_index]
                            
                            # Ambil user_id jika ada
                            user_id = None
                            if "user_ids" in face_data and first_match_index < len(face_data["user_ids"]):
                                user_id = face_data["user_ids"][first_match_index]
                            
                            # Hitung confidence score
                            face_distances = face_recognition.face_distance(
                                known_encodings, 
                                face_encoding
                            )
                            confidence = float(1 - face_distances[first_match_index])
                            
                            # Log successful access
                            access_log = AccessLog(
                                user_id=user_id,
                                access_type='entry',
                                access_method='face',
                                status='granted',
                                confidence_score=confidence,
                                camera_location='API Endpoint'
                            )
                            db.session.add(access_log)
                            
                            # Update last access time
                            if user_id:
                                user = User.query.get(user_id)
                                if user:
                                    user.last_access = datetime.utcnow()
                            
                            db.session.commit()
                            
                            os.remove(temp_path)
                            return jsonify({
                                'status': 'granted',
                                'user_id': user_id,
                                'user_name': name,
                                'confidence': confidence
                            }), 200
                
                # Jika wajah tidak dikenali
                access_log = AccessLog(
                    access_type='entry',
                    access_method='face',
                    status='denied',
                    confidence_score=0,
                    camera_location='API Endpoint'
                )
                db.session.add(access_log)
                db.session.commit()
                
                os.remove(temp_path)
                return jsonify({
                    'status': 'denied',
                    'message': 'Face not recognized'
                }), 200
                
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        return jsonify({'status': 'error', 'message': 'Invalid file'}), 400
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500



@app.route('/api/capture-face/<int:user_id>', methods=['POST'])
def capture_face_api(user_id):
    """API untuk capture wajah dari webcam untuk user yang sudah ada"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({
                'status': 'error',
                'message': 'No image data provided'
            }), 400
        
        # Simpan gambar temporer
        saved_filename, filepath = save_image_from_base64(image_data, user_id, "face_capture")
        
        if not saved_filename or not filepath:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save image'
            }), 500
        
        try:
            # Extract face encoding
            face_encoding, error_message = extract_face_encoding(filepath)
            
            if error_message:
                os.remove(filepath)
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 400
            
            # Cek apakah wajah sudah terdaftar (untuk user lain)
            is_registered, registered_name = is_face_already_registered(face_encoding)
            if is_registered:
                registered_user_id = None
                if "user_ids" in face_data:
                    idx = face_data["encodings"].index(face_encoding)
                    if idx < len(face_data["user_ids"]):
                        registered_user_id = face_data["user_ids"][idx]
                
                # Jika sudah terdaftar untuk user lain
                if registered_user_id and registered_user_id != user_id:
                    os.remove(filepath)
                    return jsonify({
                        'status': 'error',
                        'message': f'Face already registered for user: {registered_name}'
                    }), 409
            
            # Update user data
            user.profile_picture = saved_filename
            user.face_encoding = json.dumps(face_encoding)
            db.session.commit()
            
            # Update atau tambah encoding ke file pickle
            if user.id in face_data.get("user_ids", []):
                # Update existing encoding
                idx = face_data["user_ids"].index(user.id)
                face_data["encodings"][idx] = face_encoding
                face_data["names"][idx] = user.name
            else:
                # Add new encoding
                face_data["encodings"].append(face_encoding)
                face_data["names"].append(user.name)
                face_data["user_ids"].append(user.id)
            
            save_face_encodings(face_data)
            
            return jsonify({
                'status': 'success',
                'message': 'Face captured and registered successfully',
                'user_id': user.id,
                'user_name': user.name
            })
            
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise e
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/recognize-single', methods=['GET'])
def recognize_single():
    """API untuk recognize satu wajah dari webcam"""
    try:
        camera = cv2.VideoCapture(0)
        success, frame = camera.read()
        camera.release()
        
        if not success:
            return jsonify({'status': 'error', 'message': 'Camera not accessible'}), 400
        
        # Convert frame ke RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Deteksi wajah
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if len(face_locations) == 0:
            return jsonify({
                'status': 'denied',
                'message': 'No face detected'
            }), 200
        
        if len(face_locations) > 1:
            return jsonify({
                'status': 'denied',
                'message': 'Multiple faces detected'
            }), 200
        
        # Extract encoding
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        if not face_encodings:
            return jsonify({
                'status': 'denied',
                'message': 'Could not extract face features'
            }), 200
        
        face_encoding = face_encodings[0]
        
        if face_data["encodings"]:
            known_encodings = np.array(face_data["encodings"])
            matches = face_recognition.compare_faces(
                known_encodings, 
                face_encoding, 
                tolerance=0.5
            )
            
            if True in matches:
                first_match_index = matches.index(True)
                name = face_data["names"][first_match_index]
                
                # Ambil user_id
                user_id = None
                if "user_ids" in face_data and first_match_index < len(face_data["user_ids"]):
                    user_id = face_data["user_ids"][first_match_index]
                
                # Hitung confidence
                face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                confidence = float(1 - face_distances[first_match_index])
                
                # Log access
                access_log = AccessLog(
                    user_id=user_id,
                    access_type='entry',
                    access_method='face',
                    status='granted',
                    confidence_score=confidence,
                    camera_location='Main Entrance'
                )
                db.session.add(access_log)
                
                # Update last access time
                if user_id:
                    user = User.query.get(user_id)
                    if user:
                        user.last_access = datetime.utcnow()
                        db.session.commit()
                
                return jsonify({
                    'status': 'granted',
                    'user_id': user_id,
                    'user_name': name,
                    'confidence': confidence
                }), 200
        
        return jsonify({
            'status': 'denied',
            'message': 'Face not recognized'
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get-registered-faces')
def get_registered_faces():
    """API untuk mendapatkan daftar wajah yang sudah terdaftar"""
    try:
        faces = []
        for i in range(len(face_data.get("names", []))):
            face_info = {
                'name': face_data["names"][i],
                'user_id': face_data.get("user_ids", [])[i] if i < len(face_data.get("user_ids", [])) else None
            }
            
            # Coba dapatkan info user dari database
            user_id = face_info['user_id']
            if user_id:
                user = User.query.get(user_id)
                if user:
                    face_info['email'] = user.email
                    face_info['role'] = user.role
                    face_info['status'] = user.status
                    face_info['profile_picture'] = user.profile_picture
            
            faces.append(face_info)
        
        return jsonify({
            'status': 'success',
            'count': len(faces),
            'faces': faces
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/delete-face/<int:user_id>', methods=['DELETE'])
def delete_face_api(user_id):
    """API untuk menghapus encoding wajah"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Hapus dari face_data
        if user_id in face_data.get("user_ids", []):
            idx = face_data["user_ids"].index(user_id)
            face_data["encodings"].pop(idx)
            face_data["names"].pop(idx)
            face_data["user_ids"].pop(idx)
            save_face_encodings(face_data)
        
        # Hapus file encoding terpisah
        user_encoding_file = os.path.join(
            app.config['FACE_DATA_FOLDER'], 
            f"face_{user_id}.pkl"
        )
        if os.path.exists(user_encoding_file):
            os.remove(user_encoding_file)
        
        # Clear face_encoding di database
        user.face_encoding = None
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Face encoding deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# @app.route('/access-control')
# def access_control():
#     try:
#         schedules = AccessSchedule.query.all()
#         door_logs = DoorLog.query.order_by(DoorLog.timestamp.desc()).limit(20).all()
        
#         today = datetime.now().date()
#         successful_access = AccessLog.query.filter(
#             db.func.date(AccessLog.access_time) == today,
#             AccessLog.status == 'granted'
           
#         ).count()
        
#         denied_access = AccessLog.query.filter(
#             db.func.date(AccessLog.access_time) == today,
#             AccessLog.status == 'denied'
#         ).count()
        
#         # Get all users for schedule dropdown
#         users = User.query.all()
        
#         return render_template('access_control.html', 
#                              schedules=schedules,
#                              door_logs=door_logs,
#                              successful_access=successful_access,
#                              denied_access=denied_access,
#                              users=users)
#     except Exception as e:
#         flash(f'Database error: {str(e)}', 'error')
#         return render_template('access_control.html', 
#                              schedules=[],
#                              door_logs=[],
#                              successful_access=0,
#                              denied_access=0,
#                              users=[])

@app.route('/access-control')
def access_control():
    try:
        # Ambil parameter page dari URL
        schedule_page = request.args.get('schedule_page', 1, type=int)
        log_page = request.args.get('log_page', 1, type=int)

        # Pagination schedules
        schedules = AccessSchedule.query.order_by(
            AccessSchedule.id.desc()
        ).paginate(page=schedule_page, per_page=5)

        # Pagination door logs
        door_logs = DoorLog.query.order_by(
            DoorLog.timestamp.desc()
        ).paginate(page=log_page, per_page=5)

        today = datetime.now().date()

        successful_access = AccessLog.query.filter(
            db.func.date(AccessLog.access_time) == today,
            AccessLog.status == 'granted'
        ).count()

        denied_access = AccessLog.query.filter(
            db.func.date(AccessLog.access_time) == today,
            AccessLog.status == 'denied'
        ).count()

        users = User.query.all()

        return render_template(
            'access_control.html',
            schedules=schedules,
            door_logs=door_logs,
            successful_access=successful_access,
            denied_access=denied_access,
            users=users
        )

    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        return render_template(
            'access_control.html',
            schedules=None,
            door_logs=None,
            successful_access=0,
            denied_access=0,
            users=[]
        )
@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
    except Exception as e:
        flash(f'User not found: {str(e)}', 'error')
        return redirect(url_for('user_management'))
    
    if request.method == 'POST':
        try:
            user.name = request.form['name']
            user.email = request.form['email']
            user.role = request.form['role']
            user.status = request.form['status']
            
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    user.profile_picture = filename
                    
                    # Update face encoding jika ada wajah baru
                    face_encoding, error_msg = extract_face_encoding(filepath)
                    if face_encoding:
                        user.face_encoding = json.dumps(face_encoding)
            
            db.session.commit()
            flash('User updated successfully', 'success')
            return redirect(url_for('user_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('edit_user.html', user=user)

@app.route('/users/delete/<int:user_id>')
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        
        # Hapus face encoding juga
        delete_face_api(user_id)
        
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('user_management'))

@app.route('/api/door-control', methods=['POST'])
def door_control():
    try:
        data = request.json
        action = data.get('action')
        door_id = data.get('door_id', 'main')
        reason = data.get('reason', 'Manual control')
        
        admin = get_admin_user()
        
        door_log = DoorLog(
            door_id=door_id,
            action=action,
            action_by=admin.name,
            reason=reason
        )
        db.session.add(door_log)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Door {action}ed successfully',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/add-schedule', methods=['POST'])
def add_schedule():
    try:
        data = request.json
        
        schedule = AccessSchedule(
            user_id=data['user_id'],
            day_of_week=data['day_of_week'],
            start_time=datetime.strptime(data['start_time'], '%H:%M').time(),
            end_time=datetime.strptime(data['end_time'], '%H:%M').time(),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(schedule)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Schedule added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/delete-schedule/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    try:
        schedule = AccessSchedule.query.get_or_404(schedule_id)
        db.session.delete(schedule)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Schedule deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/test-db')
def test_db():
    """Endpoint untuk testing koneksi database"""
    try:
        count = User.query.count()
        return jsonify({
            'status': 'success',
            'message': 'Database connection successful',
            'user_count': count,
            'face_encodings_count': len(face_data["names"])
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
# Tambahkan route ini di app.py setelah route yang ada

@app.route('/api/unlock-door-face', methods=['POST'])
def unlock_door_face_api():
    
    """API untuk membuka pintu berdasarkan face recognition"""
    try:
        data = request.json
        user_id = data.get('user_id')
        confidence = data.get('confidence', 0.0)
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            }), 400
        
        # Cari user di database
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Cek apakah user memiliki akses berdasarkan schedule
        current_time = datetime.now().time()
        current_day = datetime.now().strftime('%A')
        
        # Cek jadwal akses
        schedule = AccessSchedule.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        can_access = False
        reason = ""
        
        if schedule:
            # Cek hari
            if (schedule.day_of_week == 'Everyday' or 
                schedule.day_of_week == current_day or
                (schedule.day_of_week == 'Weekdays' and current_day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']) or
                (schedule.day_of_week == 'Weekend' and current_day in ['Saturday', 'Sunday'])):
                
                # Cek waktu
                if schedule.start_time <= current_time <= schedule.end_time:
                    can_access = True
                    reason = "Akses diberikan berdasarkan jadwal."
                else:
                    can_access = False
                    reason = "Akses ditolak: Di luar jam operasional"
            else:
                can_access = False
                reason = "Akses ditolak: Tidak dijadwalkan untuk hari ini"
        else:
            # Jika tidak ada schedule, default allow
            can_access = True
            reason = "Akses diberikan"
        
        if can_access:
            # Unlock door
            door_log = DoorLog(
                door_id='main',
                action='unlock',
                action_by=user.name,
                reason=f'Face recognition access - {confidence*100:.1f}% confidence'
            )
            db.session.add(door_log)
            
            # Log access
            access_log = AccessLog(
                user_id=user_id,
                access_type='entry',
                access_method='face',
                status='granted',
                confidence_score=confidence,
                camera_location='Main Entrance - Auto Unlock',
                reason=reason
            )
            db.session.add(access_log)
            
            # Update last access time
            user.last_access = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Door unlocked successfully',
                'user_name': user.name,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            # Log denied access
            access_log = AccessLog(
                user_id=user_id,
                access_type='entry',
                access_method='face',
                status='denied',
                confidence_score=confidence,
                camera_location='Main Entrance',
                reason=reason
            )
            db.session.add(access_log)
            db.session.commit()
            
            return jsonify({
                'status': 'denied',
                'message': reason,
                'user_name': user.name
            }), 403
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500



# ==================== AUTO FACE RECOGNITION ====================

# @app.route('/api/auto-detect', methods=['POST'])
@app.route('/api/auto-detect', methods=['POST'])
def auto_detect_api():

    try:
        data = request.json

        if not data or 'image' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No image data provided'
            }), 400

        # Decode base64 image
        image_data = data['image'].split(',')[1] if ',' in data['image'] else data['image']
        image_bytes = base64.b64decode(image_data)

        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({
                'status': 'error',
                'message': 'Failed to decode image'
            }), 400

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Deteksi wajah
        face_locations = face_recognition.face_locations(rgb_frame)

        # =========================
        # TIDAK ADA WAJAH
        # =========================
        if len(face_locations) == 0:

            access_log = AccessLog(
                access_type='entry',
                access_method='face_auto',
                status='no_face',
                confidence_score=0,
                camera_location='Auto Detection',
            )

            db.session.add(access_log)
            db.session.commit()

            return jsonify({
                'status': 'no_face',
                'message': 'No face detected'
            }), 200

        # Extract face encoding
        face_encodings = face_recognition.face_encodings(
            rgb_frame,
            [face_locations[0]]
        )

        if not face_encodings:
            return jsonify({
                'status': 'error',
                'message': 'Could not extract face features'
            }), 200

        face_encoding = face_encodings[0]

        # =========================
        # CEK WAJAH TERDAFTAR
        # =========================
        if face_data["encodings"]:

            known_encodings = np.array(face_data["encodings"])

            matches = face_recognition.compare_faces(
                known_encodings,
                face_encoding,
                tolerance=0.5
            )

            # =========================
            # WAJAH DIKENALI
            # =========================
            if True in matches:

                first_match_index = matches.index(True)

                name = face_data["names"][first_match_index]
                user_id = face_data["user_ids"][first_match_index]

                # Hitung confidence
                face_distances = face_recognition.face_distance(
                    known_encodings,
                    face_encoding
                )

                confidence = float(
                    1 - face_distances[first_match_index]
                )

                # =========================
                # CEK JADWAL AKSES
                # =========================
                can_access, access_reason = check_user_access(user_id)

                # =========================
                # AKSES DIIZINKAN
                # =========================
                if can_access:

                    access_log = AccessLog(
                        user_id=user_id,
                        access_type='entry',
                        access_method='face_auto',
                        status='granted',
                        confidence_score=confidence,
                        camera_location='Auto Detection',
                    )

                    db.session.add(access_log)

                    # Log buka pintu
                    door_log = DoorLog(
                        door_id='main',
                        action='unlock',
                        action_by=name,
                        reason=f'Auto detection - {confidence*100:.1f}% confidence - {access_reason}'
                    )

                    db.session.add(door_log)

                    # Update akses terakhir user
                    user = User.query.get(user_id)

                    if user:
                        user.last_access = datetime.utcnow()

                    db.session.commit()

                    return jsonify({
                        'status': 'granted',
                        'user_id': user_id,
                        'user_name': name,
                        'confidence': confidence,
                        'message': access_reason,
                        'door_action': 'unlock'
                    }), 200

                # =========================
                # JADWAL DITOLAK
                # =========================
                else:

                    access_log = AccessLog(
                        user_id=user_id,
                        access_type='entry',
                        access_method='face_auto',
                        status='schedule_denied',
                        confidence_score=confidence,
                        camera_location='Auto Detection',
                    )

                    db.session.add(access_log)
                    db.session.commit()

                    return jsonify({
                        'status': 'schedule_denied',
                        'user_name': name,
                        'message': access_reason
                    }), 403

        # =========================
        # WAJAH TIDAK DIKENALI
        # =========================
        access_log = AccessLog(
            access_type='entry',
            access_method='face_auto',
            status='unknown_face',
            confidence_score=0,
            camera_location='Auto Detection',
        )

        db.session.add(access_log)
        db.session.commit()

        return jsonify({
            'status': 'unknown_face',
            'message': 'Face not recognized'
        }), 200

    except Exception as e:

        print(f"❌ Error in auto detection: {e}")

        db.session.rollback()

        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500




def check_user_access(user_id):
    """Cek apakah user memiliki akses berdasarkan schedule"""
    print(f"Checking access for user_id: {user_id}")
    try:
        user = User.query.get(user_id)
        name = User.query.get(user_id)
        if not user or user.status != 'active':
            return False, "User inactive or not found"
        
        current_time = datetime.now().time()
        current_day = datetime.now().strftime('%A')
        
        schedules = AccessSchedule.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        # Jika tidak ada schedule → DITOLAK
        if not schedules:
            return False, f"Tidak terjadwal, {name.name}"
        
        for schedule in schedules:
            day_match = False
            if (schedule.day_of_week == 'Everyday' or 
                schedule.day_of_week == current_day or
                (schedule.day_of_week == 'Weekdays' and current_day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']) or
                (schedule.day_of_week == 'Weekend' and current_day in ['Saturday', 'Sunday'])):
                day_match = True
            
            time_match = schedule.start_time <= current_time <= schedule.end_time
            
            if day_match and time_match:
                return True, f"Akses diberikan sesuai jadwal: {schedule.day_of_week} {schedule.start_time.strftime('%H:%M')}-{schedule.end_time.strftime('%H:%M')}"
        
        return False, "Akses ditolak: Di luar jam operasional"
        
    except Exception as e:
        return False, f"Error checking access: {str(e)}"
# def check_user_access(user_id):
#     """Cek apakah user memiliki akses berdasarkan schedule"""
#     print(f"Checking access for user_id: {user_id}")
#     try:
#         user = User.query.get(user_id)
#         if not user or user.status != 'active':
#             return False, "User inactive or not found"
        
#         current_time = datetime.now().time()
#         current_day = datetime.now().strftime('%A')
        
#         # Cek semua schedule user
#         schedules = AccessSchedule.query.filter_by(
#             user_id=user_id,
#             is_active=True
#         ).all()
        
#         if not schedules:
#             # Jika tidak ada schedule, default allow
#             return True, "Access granted (no schedule restrictions)"
        
#         for schedule in schedules:
#             # Cek hari
#             day_match = False
#             if (schedule.day_of_week == 'Everyday' or 
#                 schedule.day_of_week == current_day or
#                 (schedule.day_of_week == 'Weekdays' and current_day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']) or
#                 (schedule.day_of_week == 'Weekend' and current_day in ['Saturday', 'Sunday'])):
#                 day_match = True
            
#             # Cek waktu
#             time_match = schedule.start_time <= current_time <= schedule.end_time
            
#             if day_match and time_match:
#                 return True, f"Access granted by schedule: {schedule.day_of_week} {schedule.start_time.strftime('%H:%M')}-{schedule.end_time.strftime('%H:%M')}"
        
#         return False, "Access denied: Outside schedule hours"
        
#     except Exception as e:
#         return False, f"Error checking access: {str(e)}"


    
@app.route('/auto-detection')
def auto_detection_page():
    """Halaman untuk auto face detection"""
    return render_template('auto_detection.html')

@app.route('/api/check-access-schedule/<int:user_id>')


@app.route('/api/kunci-pintu', methods=['GET'])
def lock_last_door_action():
    """API untuk mengubah action terakhir menjadi lock"""
    try:
        # Ambil data terakhir berdasarkan ID terbesar
        last_log = DoorLog.query.order_by(DoorLog.id.desc()).first()

        if not last_log:
            return jsonify({
                'status': 'error',
                'message': 'No door log found'
            }), 404

        # Update action menjadi lock
        last_log.action = 'lock'
        last_log.reason = 'Action updated to lock via API'
        
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Last door action updated to lock',
            'door_id': last_log.door_id,
            'action': last_log.action
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
@app.route('/api/buka-pintu', methods=['GET'])
def unlock_last_door_action():
    """API untuk mengubah action terakhir menjadi lock"""
    try:
        # Ambil data terakhir berdasarkan ID terbesar
        last_log = DoorLog.query.order_by(DoorLog.id.desc()).first()

        if not last_log:
            return jsonify({
                'status': 'error',
                'message': 'No door log found'
            }), 404

        # Update action menjadi lock
        last_log.action = 'unlock'
        last_log.reason = 'Action updated to lock via API'
        
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Last door action updated to lock',
            'door_id': last_log.door_id,
            'action': last_log.action
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    


@app.route('/api/status', methods=['GET'])
def api_status():
    """
    cek status alat
    """
    last_log = DoorLog.query.order_by(DoorLog.id.desc()).first()
    acc_log = AccessLog.query.order_by(AccessLog.id.desc()).first()
  
    if(acc_log.status == 'unknown_face'):
        name = "Unknown Face"; 
    else:
        name = last_log.action_by

    if not last_log:
        return {"message": "No data"}, 404
    
    return {
        "status": acc_log.status,
        # "door_id": last_log.door_id,
        "action": last_log.action,
        # "time": last_log.timestamp,
        "user": name
    }
    
def check_access_schedule(user_id):
    """API untuk cek schedule akses user"""
    try:
        user = User.query.get_or_404(user_id)
        current_time = datetime.now().time()
        current_day = datetime.now().strftime('%A')
        
        schedules = AccessSchedule.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        access_info = {
            'user_id': user_id,
            'user_name': user.name,
            'current_time': current_time.strftime('%H:%M:%S'),
            'current_day': current_day,
            'has_schedule': len(schedules) > 0,
            'schedules': [],
            'can_access_now': False,
            'reason': ''
        }
        
        for schedule in schedules:
            schedule_info = {
                'day_of_week': schedule.day_of_week,
                'start_time': schedule.start_time.strftime('%H:%M:%S'),
                'end_time': schedule.end_time.strftime('%H:%M:%S'),
                'is_active': schedule.is_active
            }
            access_info['schedules'].append(schedule_info)
            
            # Cek apakah schedule berlaku sekarang
            day_match = False
            if (schedule.day_of_week == 'Everyday' or 
                schedule.day_of_week == current_day or
                (schedule.day_of_week == 'Weekdays' and current_day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']) or
                (schedule.day_of_week == 'Weekend' and current_day in ['Saturday', 'Sunday'])):
                day_match = True
            
            time_match = schedule.start_time <= current_time <= schedule.end_time
            
            if day_match and time_match:
                access_info['can_access_now'] = True
                access_info['reason'] = f'Access allowed by schedule: {schedule.day_of_week} {schedule.start_time.strftime("%H:%M")}-{schedule.end_time.strftime("%H:%M")}'
        
        if not access_info['has_schedule']:
            access_info['can_access_now'] = True
            access_info['reason'] = 'No schedule restrictions'
        
        return jsonify({
            'status': 'success',
            'access_info': access_info
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def init_database():
    """Initialize database dengan sync ke face encodings"""
    try:
        with app.app_context():
            # Buat semua tabel
            db.create_all()
            print("✅ Tables created successfully")
            
            # Load face data
            global face_data
            face_data = load_face_encodings()
            
            # Sync dengan database
            users = User.query.all()
            for user in users:
                if user.face_encoding and user.id not in face_data.get("user_ids", []):
                    try:
                        encoding = json.loads(user.face_encoding)
                        face_data["encodings"].append(encoding)
                        face_data["names"].append(user.name)
                        face_data["user_ids"].append(user.id)
                    except:
                        pass
            
            save_face_encodings(face_data)
            
            # Cek apakah sudah ada admin
            admin = User.query.filter_by(email='admin@smartdoor.com').first()
            if not admin:
                admin = User(
                    name='Administrator',
                    email='admin@smartdoor.com',
                    role='admin',
                    status='active'
                )
                db.session.add(admin)
                
                db.session.commit()
                print("✅ Admin user created")
            else:
                print("✅ Database already initialized")
                
            print(f"✅ Face encodings: {len(face_data['names'])} registered faces")
                
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    print("🚀 Smart Door System with Real Face Recognition")
    print("📊 Direct access to dashboard")
    print("🌐 Access at: http://localhost:5000")
    print("\n🎯 Features:")
    print("   - Face Recognition Demo: /face-recognition-demo")
    print("   - Real-time Video Feed: /video_feed")
    print("   - Face Enrollment: /enroll-face")
    print("   - API Test: /api/test-db")
    
    # Initialize database
    init_database()
    
    app.run(debug=True, host='0.0.0.0', port=5000)