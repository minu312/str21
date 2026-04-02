import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, jsonify, g, redirect, url_for, session

app = Flask(__name__)
# Secret key for sessions/admin flash messages if needed later
app.secret_key = 'super_secret_dev_key'

DATABASE_URL = os.environ.get('DATABASE_URL')
DATABASE = 'database.db'
# Heroku uses postgres:// but SQLAlchemy/psycopg2 might prefer keeping it as is. psycopg2 accepts postgres://

def get_db():
    if 'db' not in g:
        if DATABASE_URL:
            import psycopg2
            import psycopg2.extras
            g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
            g.cursor = g.db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            g.db = sqlite3.connect(DATABASE)
            g.db.row_factory = sqlite3.Row
            g.cursor = g.db.cursor()
    return g.db, g.cursor

@app.teardown_appcontext
def close_connection(exception):
    db = g.pop('db', None)
    cursor = g.pop('cursor', None)
    if cursor is not None:
        cursor.close()
    if db is not None:
        db.close()

def execute_query(query, params=(), commit=False, fetchone=False, fetchall=False, executemany=False):
    db, cursor = get_db()
    if DATABASE_URL:
        # Convert SQLite syntax to Postgres syntax
        query = query.replace('?', '%s')
        query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    
    if executemany:
        cursor.executemany(query, params)
    else:
        cursor.execute(query, params)
    
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
        
    if commit:
        db.commit()
    return result

def init_db():
    with app.app_context():
        # Create table for Movies/TV Shows
        execute_query('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                poster_url TEXT,
                video_url TEXT,
                type TEXT DEFAULT 'Movie', -- 'Movie' or 'TV Show'
                category TEXT DEFAULT 'Action',
                views INTEGER DEFAULT 0
            )
        ''', commit=True)

        # Create table for general traffic
        execute_query('''
            CREATE TABLE IF NOT EXISTS traffic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                views INTEGER DEFAULT 0
            )
        ''', commit=True)
        
        # Seed initial data if empty
        count = execute_query('SELECT COUNT(*) FROM videos', fetchone=True)[0]
        if count == 0:
            seed_data = [
                ("The Great Adventure", "An epic journey through unknown lands.", "https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&q=80&w=800", "https://www.youtube.com/embed/dQw4w9WgXcQ", "Movie", "Action"),
                ("Space Frontiers", "Exploring the vast emptiness of space.", "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&q=80&w=800", "", "TV Show", "Sci-Fi"),
                ("Urban Legends", "Uncovering the truth behind city myths.", "https://images.unsplash.com/photo-1509347528160-9a9e33742cdb?auto=format&fit=crop&q=80&w=800", "", "TV Show", "Drama"),
                ("Comedy Nights", "Stand-up specials and hilarious skits.", "https://images.unsplash.com/photo-1585699324541-61012ab6eb8a?auto=format&fit=crop&q=80&w=800", "", "Movie", "Comedy"),
            ]
            execute_query('INSERT INTO videos (title, description, poster_url, video_url, type, category) VALUES (?, ?, ?, ?, ?, ?)', seed_data, commit=True, executemany=True)

def record_traffic(path):
    row = execute_query('SELECT id FROM traffic WHERE path = ?', (path,), fetchone=True)
    if row:
        execute_query('UPDATE traffic SET views = views + 1 WHERE id = ?', (row['id'],), commit=True)
    else:
        execute_query('INSERT INTO traffic (path, views) VALUES (?, 1)', (path,), commit=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != 'admin' or request.form['password'] != '4ebdMdc9mDKkJclZ':
            error = 'Invalid Credentials. Please try again.'
        else:
            session['logged_in'] = True
            return redirect(url_for('admin'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/')
def index():
    record_traffic('/')
    
    # Get featured video
    featured = execute_query("SELECT * FROM videos ORDER BY RANDOM() LIMIT 1", fetchone=True)
    
    # Get all categories
    cats = execute_query("SELECT DISTINCT category FROM videos", fetchall=True)
    categories = [row['category'] for row in cats]
    
    collection = {}
    for cat in categories:
        videos = execute_query("SELECT * FROM videos WHERE category = ?", (cat,), fetchall=True)
        collection[cat] = videos
        
    return render_template('index.html', featured=featured, collection=collection)

@app.route('/watch/<int:video_id>')
def watch(video_id):
    record_traffic(f'/watch/{video_id}')
    
    video = execute_query("SELECT * FROM videos WHERE id = ?", (video_id,), fetchone=True)
    if not video:
        return "Video not found", 404
        
    # Increment view count
    execute_query("UPDATE videos SET views = views + 1 WHERE id = ?", (video_id,), commit=True)
    
    return render_template('player.html', video=video)

@app.route('/admin')
@login_required
def admin():
    record_traffic('/admin')
    
    # Get total video views
    total_views_row = execute_query("SELECT SUM(views) as total FROM videos", fetchone=True)
    total_views = total_views_row['total'] if total_views_row and total_views_row['total'] else 0
    
    # Get traffic data
    traffic_data = execute_query("SELECT * FROM traffic ORDER BY views DESC", fetchall=True)
    
    # Get all videos
    all_videos = execute_query("SELECT * FROM videos ORDER BY id DESC", fetchall=True)
    
    return render_template('admin.html', traffic_data=traffic_data, all_videos=all_videos, total_views=total_views)

@app.route('/api/add_video', methods=['POST'])
@login_required
def add_video():
    data = request.json
    execute_query('''
        INSERT INTO videos (title, description, poster_url, video_url, type, category) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data.get('title'), data.get('description'), data.get('poster_url'), data.get('video_url'), data.get('type', 'Movie'), data.get('category', 'Uncategorized')), commit=True)
    return jsonify({"status": "success"})

@app.route('/api/delete_video/<int:video_id>', methods=['DELETE'])
@login_required
def delete_video(video_id):
    execute_query("DELETE FROM videos WHERE id = ?", (video_id,), commit=True)
    return jsonify({"status": "success"})

@app.cli.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    print("Database initialized.")

if __name__ == '__main__':
    # Initialize DB before running
    if not os.path.exists(DATABASE):
        with app.app_context():
            get_db() # creates the file
            
    init_db()
    app.run(debug=True, port=5000)
