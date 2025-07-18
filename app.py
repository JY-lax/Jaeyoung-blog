from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import bcrypt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'static/profile_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 사용자 모델
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True)
    profile = db.Column(db.Text)
    profile_image = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 글 모델
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text)
    category = db.Column(db.String(50))
    tags = db.Column(db.String(200))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User', backref=db.backref('posts', lazy=True))

# 댓글 모델
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    post = db.relationship('Post', backref=db.backref('comments', lazy=True))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User', backref=db.backref('comments', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    return '❌ 회원가입은 관리자에게 문의하세요.'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            return redirect('/')
        else:
            return '❌ 로그인 실패'
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.username != 'admin':
        return '❌ 관리자만 글 작성이 가능합니다.', 403
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        tags = request.form['tags']
        post = Post(title=title, content=content, category=category, tags=tags, author=current_user)
        db.session.add(post)
        db.session.commit()
        return redirect('/')
    return render_template('create.html')

@app.route('/post/<int:id>')
@login_required
def post(id):
    post = Post.query.get_or_404(id)
    return render_template('post.html', post=post)

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment(post_id):
    content = request.form['content']
    new_comment = Comment(content=content, post_id=post_id, author=current_user)
    db.session.add(new_comment)
    db.session.commit()
    return redirect(f'/post/{post_id}')

@app.route('/user/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    posts = Post.query.filter_by(author_id=user.id).all()
    comments = Comment.query.filter_by(author_id=user.id).all()
    return render_template('profile.html', user=user, posts=posts, comments=comments)

@app.route('/upload_profile_image', methods=['POST'])
@login_required
def upload_profile_image():
    file = request.files['image']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        current_user.profile_image = filename
        db.session.commit()
    else:
        return '❌ 지원하지 않는 이미지 형식입니다.', 400
    return redirect(f'/user/{current_user.id}')

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.profile = request.form['profile']
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            current_user.profile_image = filename
        elif file and file.filename:
            return '❌ 지원하지 않는 이미지 형식입니다.', 400
        db.session.commit()
        return redirect(f'/user/{current_user.id}')
    return render_template('edit_profile.html', user=current_user)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)