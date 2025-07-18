from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'static/profile_images'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# -------------------- 모델 --------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    profile = db.Column(db.Text)
    profile_image = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, raw_password):
        self.password = bcrypt.generate_password_hash(raw_password).decode('utf-8')

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password, raw_password)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100))
    tags = db.Column(db.String(200))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    post = db.relationship('Post', backref=db.backref('comments', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- 폼 --------------------
class RegisterForm(FlaskForm):
    username = StringField('아이디', validators=[DataRequired()])
    email = StringField('이메일', validators=[DataRequired(), Email()])
    password = PasswordField('비밀번호', validators=[DataRequired()])
    profile = TextAreaField('자기소개')
    submit = SubmitField('가입하기')

class LoginForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(), Email()])
    password = PasswordField('비밀번호', validators=[DataRequired()])
    submit = SubmitField('로그인')

class PostForm(FlaskForm):
    title = StringField('제목', validators=[DataRequired()])
    content = TextAreaField('내용', validators=[DataRequired()])
    category = StringField('카테고리')
    tags = StringField('태그')
    submit = SubmitField('작성 완료')

class CommentForm(FlaskForm):
    content = TextAreaField('댓글', validators=[DataRequired()])
    submit = SubmitField('수정 완료')

class ProfileForm(FlaskForm):
    profile = TextAreaField('자기소개')
    image = FileField('프로필 이미지', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    submit = SubmitField('수정 완료')

# -------------------- 라우트 --------------------
@app.route('/')
def index():
    return redirect(url_for('posts'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            profile=form.profile.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('회원가입이 완료되었습니다!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('로그인 성공!', 'success')
            return redirect(url_for('posts'))
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('login'))

@app.route('/posts')
def posts():
    all_posts = Post.query.order_by(Post.id.desc()).all()
    return render_template('posts.html', posts=all_posts)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
            title=form.title.data,
            content=form.content.data,
            category=form.category.data,
            tags=form.tags.data,
            author=current_user
        )
        db.session.add(post)
        db.session.commit()
        flash('글이 작성되었습니다!', 'success')
        return redirect(url_for('posts'))
    return render_template('create_post.html', form=form)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('view_post.html', post=post)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    post = Post.query.get_or_404(id)
    if post.author != current_user:
        flash('수정 권한이 없습니다.', 'danger')
        return redirect(url_for('posts'))
    form = PostForm(obj=post)
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        post.category = form.category.data
        post.tags = form.tags.data
        db.session.commit()
        flash('글이 수정되었습니다!', 'success')
        return redirect(url_for('view_post', post_id=post.id))
    return render_template('edit.html', form=form, post=post)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_post(id):
    post = Post.query.get_or_404(id)
    if post.author != current_user:
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('posts'))
    db.session.delete(post)
    db.session.commit()
    flash('글이 삭제되었습니다.', 'info')
    return redirect(url_for('posts'))

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def create_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    if content:
        comment = Comment(content=content, post=post, author=current_user)
        db.session.add(comment)
        db.session.commit()
        flash('댓글이 작성되었습니다.', 'success')
    return redirect(url_for('view_post', post_id=post.id))

@app.route('/comment/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_comment(id):
    comment = Comment.query.get_or_404(id)
    if comment.author != current_user:
        flash('수정 권한이 없습니다.', 'danger')
        return redirect(url_for('view_post', post_id=comment.post_id))
    form = CommentForm(obj=comment)
    if form.validate_on_submit():
        comment.content = form.content.data
        db.session.commit()
        flash('댓글이 수정되었습니다.', 'success')
        return redirect(url_for('view_post', post_id=comment.post_id))
    return render_template('edit_comment.html', form=form, comment=comment)

@app.route('/comment/delete/<int:id>', methods=['POST'])
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if comment.author != current_user:
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('view_post', post_id=comment.post_id))
    db.session.delete(comment)
    db.session.commit()
    flash('댓글이 삭제되었습니다.', 'info')
    return redirect(url_for('view_post', post_id=comment.post_id))

@app.route('/user/<int:id>')
def view_profile(id):
    user = User.query.get_or_404(id)
    posts = Post.query.filter_by(author_id=user.id).order_by(Post.id.desc()).all()
    comments = Comment.query.filter_by(author_id=user.id).order_by(Comment.id.desc()).all()
    return render_template('profile.html', user=user, posts=posts