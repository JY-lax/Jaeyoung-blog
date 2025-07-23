import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
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
    bio = db.Column(db.Text)  # ✅ 자기소개
    profile_image = db.Column(db.String(300))  # ✅ 프로필 이미지 경로

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(300))
    tags = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', lazy=True)


from datetime import datetime

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # ✅ 댓글 시간
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


# ✅ 홈 → 메인 글 목록
@app.route('/')
def home():
    return redirect(url_for('main'))

@app.route('/main')
def main():
    posts_raw = db.session.execute(text("""
        SELECT p.id, p.title, u.username, p.category, p.created_at
        FROM post p
        JOIN "user" u ON p.author_id = u.id
        ORDER BY p.id DESC
    """)).fetchall()

    posts = []
    for post in posts_raw:
        post_id = post[0]
        like_count = Like.query.filter_by(post_id=post_id).count()
        comment_count = Comment.query.filter_by(post_id=post_id).count()
        posts.append((post_id, post[1], post[2], post[3], post[4].strftime('%Y-%m-%d %H:%M'), like_count, comment_count))

    return render_template('main.html', posts=posts)

# ✅ 카테고리별 글 목록
@app.route('/category/<string:category>')
def category_posts(category):
    posts = db.session.execute(text("""
        SELECT p.id, p.title, u.username, p.tags, p.created_at
        FROM post p
        JOIN "user" u ON p.author_id = u.id
        WHERE LOWER(p.tags) LIKE :category
        ORDER BY p.id DESC
        LIMIT 10
    """), {'category': f'%{category.lower()}%'}).fetchall()
    return render_template('category.html', posts=posts, category=category)

# ✅ 무한스크롤용 글 로딩 API
@app.route('/load_posts')
def load_posts():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    posts = db.session.execute(text("""
        SELECT p.id, p.title, u.username, p.tags, p.created_at
        FROM post p
        JOIN "user" u ON p.author_id = u.id
        ORDER BY p.id DESC
        LIMIT :limit OFFSET :offset
    """), {'limit': per_page, 'offset': offset}).fetchall()

    return jsonify([{
        'id': post[0],
        'title': post[1],
        'username': post[2],
        'tags': post[3],
        'created_at': post[4].strftime('%Y-%m-%d %H:%M')
    } for post in posts])

# ✅ 카테고리별 무한스크롤 API
@app.route('/load_category_posts/<string:category>')
def load_category_posts(category):
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    posts = db.session.execute(text("""
        SELECT p.id, p.title, u.username, p.tags, p.created_at
        FROM post p
        JOIN "user" u ON p.author_id = u.id
        WHERE LOWER(p.tags) LIKE :category
        ORDER BY p.id DESC
        LIMIT :limit OFFSET :offset
    """), {
        'category': f'%{category.lower()}%',
        'limit': per_page,
        'offset': offset
    }).fetchall()

    return jsonify([{
        'id': post[0],
        'title': post[1],
        'username': post[2],
        'tags': post[3],
        'created_at': post[4].strftime('%Y-%m-%d %H:%M')
    } for post in posts])

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    author = User.query.get(post.author_id)

    comments_raw = db.session.execute(text("""
        SELECT u.username, c.content, c.created_at
        FROM comment c
        JOIN "user" u ON c.author_id = u.id
        WHERE c.post_id = :post_id
        ORDER BY c.id DESC
    """), {'post_id': post_id}).fetchall()

    likes = Like.query.filter_by(post_id=post_id).count()  # ✅ 실시간 좋아요 수

    post_data = {
        'title': post.title,
        'author': author.username,
        'created_at': post.created_at.strftime('%Y-%m-%d %H:%M'),
        'content': post.content
    }

    return render_template('post_detail.html',
                           post=post_data,
                           comments=comments_raw,
                           likes=likes,
                           post_id=post_id)
@app.route('/like/<int:post_id>')
def like(post_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('사용자를 찾을 수 없습니다.')
        return redirect(url_for('login'))

    existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
    if existing_like:
        flash('이미 좋아요를 누르셨습니다.')
    else:
        new_like = Like(user_id=user.id, post_id=post_id)
        db.session.add(new_like)
        db.session.commit()
        flash('좋아요가 반영되었습니다.')

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

@app.route('/profile')
def profile():
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('사용자를 찾을 수 없습니다.')
        return redirect(url_for('login'))

    return render_template('profile.html', username=user.username, user=user)

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
    return redirect(url_for('main'))
@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()

    if request.method == 'POST':
        new_username = request.form.get('username').strip()
        new_password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm_password').strip()
        bio = request.form.get('bio').strip()
        image_file = request.files.get('profile_image')

        # 아이디 변경
        if new_username:
            user.username = new_username
            session['user'] = new_username  # 세션도 갱신

        # 비밀번호 변경 (확인 포함)
        if new_password:
            if new_password != confirm_password:
                flash('비밀번호가 일치하지 않습니다.')
                return redirect(url_for('edit_profile'))
            user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        # 자기소개
        if bio:
            user.bio = bio

        # 프로필 이미지
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join('static/profile', filename)
            image_file.save(image_path)
            user.profile_image = filename

        db.session.commit()
        flash('프로필이 수정되었습니다.')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=user)
@app.route('/profile/<string:username>')
def view_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('view_profile.html', user=user)
@app.route('/admin/promote/<int:user_id>', methods=['POST'])
def promote_user(user_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    current_user = User.query.filter_by(username=session['user']).first()
    if not current_user.is_admin:
        flash('관리자만 승격할 수 있습니다.')
        return redirect(url_for('main'))

    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f'{user.username}님을 관리자로 승격했습니다.')
    return redirect(url_for('admin'))
@app.route('/admin/delete_post/<int:post_id>', methods=['POST'])
def admin_delete_post(post_id):
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
@app.context_processor
def inject_user():
    user = None
    is_admin = False
    if session.get('user'):
        user = User.query.filter_by(username=session['user']).first()
        if user:
            is_admin = user.is_admin
    return dict(current_user=user, is_admin=is_admin)