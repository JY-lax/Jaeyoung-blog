import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from sqlalchemy import text

# ✅ 환경 변수 로딩
load_dotenv()

# ✅ Flask 앱 설정
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ✅ 확장 모듈 초기화
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)

# ✅ 데이터베이스 모델
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(300))
    tags = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

# ✅ 홈 → 메인 글 목록
@app.route('/')
def home():
    return redirect(url_for('main'))

@app.route('/main')
def main():
    posts = db.session.execute(text("""
        SELECT p.id, p.title, u.username, p.tags, p.created_at
        FROM post p
        JOIN user u ON p.author_id = u.id
        ORDER BY p.id DESC
    """)).fetchall()
    return render_template('main.html', posts=posts)

# ✅ 카테고리별 글 목록
@app.route('/category/<string:category>')
def category_posts(category):
    posts = db.session.execute(text("""
        SELECT p.id, p.title, u.username, p.tags, p.created_at
        FROM post p
        JOIN user u ON p.author_id = u.id
        WHERE LOWER(p.tags) LIKE :category
        ORDER BY p.id DESC
    """), {'category': f'%{category.lower()}%'}).fetchall()
    return render_template('category.html', category=category, posts=posts)

# ✅ 글 상세 보기
@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    author = User.query.get(post.author_id)
    comments_raw = db.session.execute(text("""
        SELECT u.username, c.content, c.created_at
        FROM comment c
        JOIN user u ON c.author_id = u.id
        WHERE c.post_id = :post_id
        ORDER BY c.id DESC
    """), {'post_id': post_id}).fetchall()

    likes = 12  # 임시 좋아요 수

    post_data = {
        'title': post.title,
        'author': author.username,
        'created_at': post.created_at.strftime('%Y-%m-%d %H:%M'),
        'content': post.content
    }

    return render_template('post_detail.html', post=post_data, comments=comments_raw, likes=likes, post_id=post_id)

# ✅ 좋아요 (임시)
@app.route('/like/<int:post_id>')
def like(post_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))
    flash('좋아요를 눌렀습니다! (기능은 아직 미구현)')
    return redirect(url_for('post_detail', post_id=post_id))

# ✅ 댓글 작성
@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    content = request.form.get('content')
    user = User.query.filter_by(username=session['user']).first()
    new_comment = Comment(content=content, post_id=post_id, author_id=user.id)
    db.session.add(new_comment)
    db.session.commit()
    flash('댓글이 작성되었습니다.')
    return redirect(url_for('post_detail', post_id=post_id))

# ✅ 카테고리 글 작성
@app.route('/write/<string:category>', methods=['GET', 'POST'])
def write_category(category):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        tags = category.lower()

        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.')
            return redirect(url_for('write_category', category=category))

        image_file = request.files.get('image')
        filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

        user = User.query.filter_by(username=session['user']).first()
        post = Post(title=title, content=content, image=filename, tags=tags, author_id=user.id)
        db.session.add(post)
        db.session.commit()
        flash(f'{category} 글이 작성되었습니다.')
        return redirect(url_for('category_posts', category=category))

    return render_template('write_category.html', category=category)

# ✅ 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        if User.query.filter_by(username=username).first():
            error = '이미 존재하는 아이디입니다.'
            return render_template('register.html', error=error)

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('회원가입 완료!')
        return redirect(url_for('login'))
    return render_template('register.html')

# ✅ 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            session['user'] = user.username
            flash('로그인 성공!')
            return redirect(url_for('main'))
        error = '아이디 또는 비밀번호가 올바르지 않습니다.'
        return render_template('login.html', error=error)
    return render_template('login.html')

# ✅ 로그아웃
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('main'))

# ✅ 프로필
@app.route('/profile')
def profile():
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['user']).first()
    return render_template('profile.html', username=user.username)

# ✅ 관리자 페이지
@app.route('/admin')
def admin():
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    current_user = User.query.filter_by(username=session['user']).first()
    if not current_user.is_admin:
        flash('관리자만 접근할 수 있습니다.')
        return redirect(url_for('main'))

    users = User.query.order_by(User.id).all()
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template('admin.html', users=users, posts=posts)

# ✅ 글 삭제 (관리자 전용)
@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    current_user = User.query.filter_by(username=session['user']).first()
    if not current_user.is_admin:
        flash('관리자만 삭제할 수 있습니다.')
        return redirect(url_for('main'))

    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('글이 삭제되었습니다.')
    return redirect(url_for('admin'))

# ✅ DB 연결 테스트
first_request_handled = False

@app.before_request
def init_once():
    global first_request_handled
    if not first_request_handled:
        try:
            db.session.execute(text('SELECT 1'))
            print("✅ DB 연결 성공")
        except Exception as e:
            print("❌ DB 연결 실패:", e)
        first_request_handled = True
