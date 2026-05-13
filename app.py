#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sqlite3
import time
import random
from functools import wraps

try:
    from flask import Flask, render_template_string, request, jsonify, session
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask'])
    from flask import Flask, render_template_string, request, jsonify, session

app = Flask(__name__)
app.secret_key = 'edu_app_secret_key_change_in_production'

DB_NAME = 'edu_app.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS schools
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS school_classes
                 (id INTEGER PRIMARY KEY, school_id INTEGER, level INTEGER,
                  FOREIGN KEY(school_id) REFERENCES schools(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY, name TEXT, school_id INTEGER, class_level INTEGER,
                  FOREIGN KEY(school_id) REFERENCES schools(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS lessons
                 (id INTEGER PRIMARY KEY, school_id INTEGER, class_level INTEGER,
                  name TEXT, description TEXT,
                  FOREIGN KEY(school_id) REFERENCES schools(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS questions
                 (id INTEGER PRIMARY KEY, lesson_id INTEGER,
                  type TEXT, text TEXT, options TEXT, correct_answer TEXT,
                  FOREIGN KEY(lesson_id) REFERENCES lessons(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS submissions
                 (id INTEGER PRIMARY KEY, student_id INTEGER, question_id INTEGER,
                  answer TEXT, is_correct INTEGER, timestamp REAL,
                  FOREIGN KEY(student_id) REFERENCES students(id),
                  FOREIGN KEY(question_id) REFERENCES questions(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS test_settings
                 (id INTEGER PRIMARY KEY, time_limit_minutes INTEGER DEFAULT 30)''')
    c.execute("INSERT OR IGNORE INTO test_settings (id, time_limit_minutes) VALUES (1, 30)")
    
    # Tạo lớp 7,8,9 cho mỗi trường hiện có
    schools = c.execute("SELECT id FROM schools").fetchall()
    for school in schools:
        for level in [7,8,9]:
            c.execute("INSERT OR IGNORE INTO school_classes (school_id, level) VALUES (?,?)",
                      (school[0], level))
    conn.commit()
    conn.close()

init_db()

def ensure_classes_for_school(school_id):
    conn = get_db()
    for level in [7,8,9]:
        conn.execute("INSERT OR IGNORE INTO school_classes (school_id, level) VALUES (?,?)",
                     (school_id, level))
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_NAME)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def query_db(query, args=(), one=False):
    conn = get_db()
    conn.row_factory = dict_factory
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cur = conn.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template_string(MAIN_PAGE)

@app.route('/admin')
def admin_panel():
    return render_template_string(ADMIN_PAGE)

@app.route('/student')
def student_panel():
    return render_template_string(STUDENT_PAGE)

# ----- API admin -----
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('password') == 'teacher123':
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})

@app.route('/api/admin/schools', methods=['GET'])
@admin_required
def get_schools():
    schools = query_db('SELECT * FROM schools ORDER BY name')
    return jsonify(schools)

@app.route('/api/admin/schools', methods=['POST'])
@admin_required
def add_school():
    data = request.json
    try:
        school_id = execute_db('INSERT INTO schools (name) VALUES (?)', (data['name'],))
        ensure_classes_for_school(school_id)
        return jsonify({'success': True})
    except:
        return jsonify({'success': False, 'error': 'Trường đã tồn tại'}), 400

@app.route('/api/admin/schools/<int:sid>', methods=['DELETE'])
@admin_required
def delete_school(sid):
    execute_db('DELETE FROM submissions WHERE student_id IN (SELECT id FROM students WHERE school_id=?)', (sid,))
    execute_db('DELETE FROM students WHERE school_id=?', (sid,))
    execute_db('DELETE FROM questions WHERE lesson_id IN (SELECT id FROM lessons WHERE school_id=?)', (sid,))
    execute_db('DELETE FROM lessons WHERE school_id=?', (sid,))
    execute_db('DELETE FROM school_classes WHERE school_id=?', (sid,))
    execute_db('DELETE FROM schools WHERE id=?', (sid,))
    return jsonify({'success': True})

@app.route('/api/admin/students', methods=['GET'])
@admin_required
def get_students():
    students = query_db('''SELECT s.*, sc.name as school_name 
                           FROM students s JOIN schools sc ON s.school_id = sc.id
                           ORDER BY sc.name, s.class_level, s.name''')
    return jsonify(students)

@app.route('/api/admin/students', methods=['POST'])
@admin_required
def add_student():
    data = request.json
    execute_db('INSERT INTO students (name, school_id, class_level) VALUES (?,?,?)',
               (data['name'], data['school_id'], data['class_level']))
    return jsonify({'success': True})

@app.route('/api/admin/students/<int:sid>', methods=['DELETE'])
@admin_required
def delete_student(sid):
    execute_db('DELETE FROM submissions WHERE student_id = ?', (sid,))
    execute_db('DELETE FROM students WHERE id = ?', (sid,))
    return jsonify({'success': True})

@app.route('/api/admin/lessons', methods=['GET'])
@admin_required
def get_lessons():
    lessons = query_db('''SELECT l.*, s.name as school_name 
                          FROM lessons l JOIN schools s ON l.school_id = s.id
                          ORDER BY s.name, l.class_level, l.name''')
    return jsonify(lessons)

@app.route('/api/admin/lessons', methods=['POST'])
@admin_required
def add_lesson():
    data = request.json
    execute_db('INSERT INTO lessons (school_id, class_level, name, description) VALUES (?,?,?,?)',
               (data['school_id'], data['class_level'], data['name'], data.get('description', '')))
    return jsonify({'success': True})

@app.route('/api/admin/lessons/<int:lid>', methods=['DELETE'])
@admin_required
def delete_lesson(lid):
    q = query_db('SELECT id FROM questions WHERE lesson_id = ? LIMIT 1', (lid,))
    if q:
        return jsonify({'success': False, 'error': 'Bài học có câu hỏi, không thể xóa'}), 400
    execute_db('DELETE FROM lessons WHERE id = ?', (lid,))
    return jsonify({'success': True})

@app.route('/api/admin/questions', methods=['GET'])
@admin_required
def get_questions():
    questions = query_db('''SELECT q.*, l.name as lesson_name, l.class_level, s.name as school_name
                            FROM questions q 
                            JOIN lessons l ON q.lesson_id = l.id
                            JOIN schools s ON l.school_id = s.id''')
    for q in questions:
        q['options'] = json.loads(q['options'])
        q['correct_answer'] = json.loads(q['correct_answer'])
    return jsonify(questions)

@app.route('/api/admin/questions', methods=['POST'])
@admin_required
def add_question():
    data = request.json
    execute_db('''INSERT INTO questions (lesson_id, type, text, options, correct_answer)
                  VALUES (?,?,?,?,?)''',
               (data['lesson_id'], data['type'], data['text'],
                json.dumps(data['options']), json.dumps(data['correct_answer'])))
    return jsonify({'success': True})

@app.route('/api/admin/questions/<int:qid>', methods=['DELETE'])
@admin_required
def delete_question(qid):
    execute_db('DELETE FROM submissions WHERE question_id = ?', (qid,))
    execute_db('DELETE FROM questions WHERE id = ?', (qid,))
    return jsonify({'success': True})

@app.route('/api/admin/settings', methods=['GET'])
@admin_required
def get_settings():
    settings = query_db('SELECT time_limit_minutes FROM test_settings WHERE id=1', one=True)
    return jsonify(settings)

@app.route('/api/admin/settings', methods=['POST'])
@admin_required
def update_settings():
    data = request.json
    execute_db('UPDATE test_settings SET time_limit_minutes = ? WHERE id=1',
               (data['time_limit_minutes'],))
    return jsonify({'success': True})

@app.route('/api/admin/scores', methods=['GET'])
@admin_required
def get_scores():
    scores = query_db('''SELECT s.id as student_id, s.name as student_name, sc.name as school_name, s.class_level,
                                l.id as lesson_id, l.name as lesson_name,
                                COUNT(q.id) as total_questions,
                                COALESCE(SUM(sub.is_correct),0) as correct_count
                         FROM students s
                         JOIN schools sc ON s.school_id = sc.id
                         CROSS JOIN lessons l
                         LEFT JOIN questions q ON q.lesson_id = l.id
                         LEFT JOIN submissions sub ON sub.student_id = s.id AND sub.question_id = q.id
                         WHERE s.school_id = l.school_id AND s.class_level = l.class_level
                         GROUP BY s.id, l.id
                         ORDER BY sc.name, s.class_level, s.name, l.name''')
    return jsonify(scores)

# ----- API học sinh -----
@app.route('/api/student/schools', methods=['GET'])
def student_get_schools():
    schools = query_db('SELECT id, name FROM schools ORDER BY name')
    return jsonify(schools)

@app.route('/api/student/students', methods=['POST'])
def student_get_students():
    data = request.json
    students = query_db('SELECT id, name FROM students WHERE school_id = ? AND class_level = ?',
                        (data['school_id'], data['class_level']))
    return jsonify(students)

@app.route('/api/student/login', methods=['POST'])
def student_login():
    data = request.json
    student = query_db('SELECT id, name, school_id, class_level FROM students WHERE id = ?',
                       (data['student_id'],), one=True)
    if not student:
        return jsonify({'success': False, 'error': 'Học sinh không tồn tại'}), 401
    session['student_id'] = student['id']
    session['student_name'] = student['name']
    session['school_id'] = student['school_id']
    session['class_level'] = student['class_level']
    return jsonify({'success': True})

@app.route('/api/student/lessons', methods=['GET'])
def student_get_lessons():
    if 'student_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 401
    school_id = session['school_id']
    level = session['class_level']
    normal_lessons = query_db('SELECT id, name, description FROM lessons WHERE school_id = ? AND class_level = ? ORDER BY name',
                              (school_id, level))
    ot_lessons = query_db('SELECT id FROM lessons WHERE school_id = ? AND class_level = ? AND name = "OT"',
                          (school_id, level))
    special = []
    if ot_lessons:
        special.append({'id': -1, 'name': '📚 Tổng hợp OT', 'description': 'Tất cả câu hỏi OT trong lớp', 'special': 'total_ot'})
        special.append({'id': -2, 'name': '🎲 Thi hỗn hợp OT', 'description': 'Trộn tất cả câu OT', 'special': 'mixed_ot'})
    return jsonify({'normal': normal_lessons, 'special': special})

@app.route('/api/student/test_data', methods=['POST'])
def student_test_data():
    if 'student_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 401
    data = request.json
    lesson_id = data.get('lesson_id')
    special = data.get('special')
    school_id = session['school_id']
    class_level = session['class_level']
    
    if special == 'total_ot':
        ot_lessons = query_db('SELECT id FROM lessons WHERE school_id = ? AND class_level = ? AND name = "OT"',
                              (school_id, class_level))
        if not ot_lessons:
            return jsonify({'error': 'Không có câu hỏi OT'}), 400
        lesson_ids = [l['id'] for l in ot_lessons]
        placeholders = ','.join('?' for _ in lesson_ids)
        questions = query_db(f'SELECT * FROM questions WHERE lesson_id IN ({placeholders})', lesson_ids)
    elif special == 'mixed_ot':
        ot_lessons = query_db('SELECT id FROM lessons WHERE school_id = ? AND class_level = ? AND name = "OT"',
                              (school_id, class_level))
        if not ot_lessons:
            return jsonify({'error': 'Không có câu hỏi OT'}), 400
        lesson_ids = [l['id'] for l in ot_lessons]
        placeholders = ','.join('?' for _ in lesson_ids)
        questions = query_db(f'SELECT * FROM questions WHERE lesson_id IN ({placeholders})', lesson_ids)
        random.shuffle(questions)
    else:
        questions = query_db('SELECT * FROM questions WHERE lesson_id = ?', (lesson_id,))
    
    for q in questions:
        q['options'] = json.loads(q['options'])
        q['correct_answer'] = json.loads(q['correct_answer'])
    
    answers = query_db('SELECT question_id, answer, is_correct FROM submissions WHERE student_id = ?',
                       (session['student_id'],))
    answered_map = {a['question_id']: {'answer': json.loads(a['answer']), 'is_correct': a['is_correct']}
                    for a in answers}
    
    settings = query_db('SELECT time_limit_minutes FROM test_settings WHERE id=1', one=True)
    time_limit = settings['time_limit_minutes'] * 60 if settings else 1800
    return jsonify({
        'questions': questions,
        'answered': answered_map,
        'time_limit': time_limit,
        'student_name': session['student_name']
    })

@app.route('/api/student/submit', methods=['POST'])
def submit_answer():
    if 'student_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 401
    data = request.json
    qid = data['question_id']
    answer = data['answer']
    q = query_db('SELECT type, correct_answer FROM questions WHERE id = ?', (qid,), one=True)
    correct = json.loads(q['correct_answer'])
    is_correct = 0
    if q['type'] == 'single_choice':
        if answer == correct:
            is_correct = 1
    elif q['type'] == 'multiple_choices':
        if set(answer) == set(correct):
            is_correct = 1
    elif q['type'] in ('drag_drop', 'match', 'choice_on_table'):
        if answer == correct:
            is_correct = 1
    existing = query_db('SELECT id FROM submissions WHERE student_id=? AND question_id=?',
                        (session['student_id'], qid), one=True)
    if existing:
        execute_db('UPDATE submissions SET answer=?, is_correct=?, timestamp=? WHERE id=?',
                   (json.dumps(answer), is_correct, time.time(), existing['id']))
    else:
        execute_db('INSERT INTO submissions (student_id, question_id, answer, is_correct, timestamp) VALUES (?,?,?,?,?)',
                   (session['student_id'], qid, json.dumps(answer), is_correct, time.time()))
    return jsonify({'success': True, 'is_correct': bool(is_correct)})

@app.route('/api/student/finish', methods=['POST'])
def finish_test():
    session.pop('student_id', None)
    session.pop('student_name', None)
    session.pop('school_id', None)
    session.pop('class_level', None)
    return jsonify({'success': True})

# ---------- Giao diện ----------
MAIN_PAGE = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hệ thống Thi Trắc nghiệm</title>
    <style>
        :root {
            --bg-gradient: linear-gradient(145deg, #2c3e50 0%, #1a2632 100%);
            --card-bg: #ffffff;
            --text: #1e2a3a;
            --btn-bg: #2c3e50;
            --btn-hover: #1a2a3a;
        }
        body.dark {
            --bg-gradient: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
            --card-bg: #0f172a;
            --text: #e2e8f0;
            --btn-bg: #3b82f6;
            --btn-hover: #2563eb;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-gradient);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            transition: background 0.3s;
        }
        .home-card {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 48px 40px;
            max-width: 520px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 35px -8px rgba(0,0,0,0.3);
            transition: background 0.3s;
        }
        h1 {
            font-size: 2.5rem;
            color: var(--text);
            margin-bottom: 12px;
        }
        .sub { color: #4a627a; margin-bottom: 32px; }
        .btn-group { display: flex; flex-direction: column; gap: 18px; margin: 30px 0; }
        .btn {
            background: var(--btn-bg);
            color: white;
            text-decoration: none;
            padding: 14px;
            border-radius: 8px;
            font-weight: 600;
            transition: 0.2s;
        }
        .btn:hover { background: var(--btn-hover); transform: translateY(-2px); }
        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.5);
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 30px;
            cursor: pointer;
        }
    </style>
</head>
<body>
<button class="theme-toggle" onclick="toggleTheme()">🌓 Chế độ tối/sáng</button>
<div class="home-card">
    <h1>📚 Thi Trắc nghiệm</h1>
    <div class="sub">Hệ thống kiểm tra theo trường, lớp, bài học</div>
    <div class="btn-group">
        <a href="/admin" class="btn">👩‍🏫 Giáo viên / Quản trị</a>
        <a href="/student" class="btn">✏️ Học sinh làm bài</a>
    </div>
</div>
<script>
    function toggleTheme() {
        document.body.classList.toggle('dark');
        localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
    }
    if (localStorage.getItem('theme') === 'dark') document.body.classList.add('dark');
</script>
</body>
</html>
'''

ADMIN_PAGE = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quản trị - Giáo viên</title>
    <style>
        :root {
            --bg: #f0f4f8;
            --card-bg: #ffffff;
            --text: #1e2a3a;
            --border: #cbd5e1;
            --header-bg: #1e2a3a;
            --header-text: white;
            --btn-primary: #2c6e9e;
            --btn-danger: #c0392b;
            --table-header: #eef2f7;
        }
        body.dark {
            --bg: #121826;
            --card-bg: #1e293b;
            --text: #e2e8f0;
            --border: #334155;
            --header-bg: #0f172a;
            --header-text: #f1f5f9;
            --btn-primary: #3b82f6;
            --btn-danger: #ef4444;
            --table-header: #1e293b;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: var(--bg);
            font-family: 'Segoe UI', Roboto, sans-serif;
            padding: 24px;
            transition: background 0.3s, color 0.2s;
            color: var(--text);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: var(--header-bg);
            color: var(--header-text);
            padding: 20px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .theme-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            padding: 6px 12px;
            border-radius: 30px;
            cursor: pointer;
            color: white;
        }
        .tabs {
            display: flex;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border);
            padding: 0 24px;
            gap: 4px;
        }
        .tab-btn {
            background: transparent;
            border: none;
            padding: 14px 24px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            color: var(--text);
            border-radius: 6px 6px 0 0;
        }
        .tab-btn.active {
            border-bottom: 3px solid var(--btn-primary);
            color: var(--btn-primary);
        }
        .tab-content { padding: 28px; display: none; }
        .tab-content.active { display: block; }
        .form-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 28px;
        }
        .form-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            align-items: flex-end;
        }
        .field {
            flex: 1;
            min-width: 180px;
        }
        label {
            font-weight: 600;
            font-size: 0.8rem;
            display: block;
            margin-bottom: 6px;
            color: var(--text);
        }
        input, select, textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--card-bg);
            color: var(--text);
        }
        button {
            background: var(--btn-primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
        }
        button.danger { background: var(--btn-danger); }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th { background: var(--table-header); }
        .badge {
            background: var(--border);
            padding: 4px 10px;
            border-radius: 30px;
            font-size: 0.75rem;
        }
        .login-box {
            max-width: 420px;
            margin: 80px auto;
            background: var(--card-bg);
            border-radius: 12px;
            padding: 32px;
            text-align: center;
        }
    </style>
</head>
<body>
<div id="loginSection" class="login-box" style="display:block">
    <h2>🔐 Đăng nhập Quản trị</h2>
    <input type="password" id="adminPass" placeholder="Mật khẩu" style="width:100%; margin:15px 0;">
    <button onclick="adminLogin()">Đăng nhập</button>
    <div id="loginError" style="color:red; margin-top:12px"></div>
</div>
<div id="adminPanel" style="display:none">
    <div class="container">
        <div class="header">
            <h2>📋 Bảng điều khiển Giáo viên</h2>
            <div>
                <button class="theme-toggle" onclick="toggleTheme()">🌓 Sáng/Tối</button>
                <button class="danger" onclick="adminLogout()" style="margin-left:10px">Đăng xuất</button>
            </div>
        </div>
        <div class="tabs">
            <button class="tab-btn active" data-tab="tab-schools">🏫 Trường học</button>
            <button class="tab-btn" data-tab="tab-lessons">📚 Bài học</button>
            <button class="tab-btn" data-tab="tab-questions">📝 Câu hỏi</button>
            <button class="tab-btn" data-tab="tab-students">👩‍🎓 Học sinh</button>
            <button class="tab-btn" data-tab="tab-scores">🏆 Bảng điểm</button>
            <button class="tab-btn" data-tab="tab-settings">⚙️ Cài đặt</button>
        </div>
        <!-- Tab Trường học -->
        <div id="tab-schools" class="tab-content active">
            <div class="form-card">
                <h3>➕ Thêm trường mới</h3>
                <div class="form-grid">
                    <div class="field"><label>Tên trường</label><input type="text" id="schoolName" placeholder="VD: THCS Nguyễn Du"></div>
                    <button onclick="addSchool()">Thêm</button>
                </div>
            </div>
            <h3>📋 Danh sách trường</h3>
            <div id="schoolsList"></div>
        </div>
        <!-- Tab Bài học -->
        <div id="tab-lessons" class="tab-content">
            <div class="form-card">
                <h3>➕ Thêm bài học</h3>
                <div class="form-grid">
                    <div class="field"><label>Trường</label><select id="lessonSchoolId"></select></div>
                    <div class="field"><label>Lớp</label><select id="lessonClassLevel"><option value="7">Lớp 7</option><option value="8">Lớp 8</option><option value="9">Lớp 9</option></select></div>
                    <div class="field"><label>Tên bài học</label><input type="text" id="lessonName" placeholder="VD: GM, OT, ..."></div>
                    <div class="field"><label>Mô tả</label><input type="text" id="lessonDesc"></div>
                    <button onclick="addLesson()">Thêm</button>
                </div>
            </div>
            <div id="lessonsList"></div>
        </div>
        <!-- Tab Câu hỏi -->
        <div id="tab-questions" class="tab-content">
            <div class="form-card">
                <h3>➕ Thêm câu hỏi mới</h3>
                <div class="form-grid">
                    <div class="field"><label>Bài học</label><select id="qLessonId"></select></div>
                    <div class="field"><label>Loại câu hỏi</label><select id="qType" onchange="updateOptionsUI()">
                        <option value="single_choice">Một lựa chọn</option>
                        <option value="multiple_choices">Nhiều lựa chọn</option>
                        <option value="drag_drop">Kéo thả</option>
                        <option value="match">Ghép đôi</option>
                        <option value="choice_on_table">Lựa chọn trên bảng</option>
                    </select></div>
                </div>
                <div class="field"><label>Nội dung câu hỏi</label><textarea id="qText" rows="2"></textarea></div>
                <div id="optionsContainer"></div>
                <button onclick="addQuestion()">💾 Lưu câu hỏi</button>
                <div id="questionMsg"></div>
            </div>
            <div id="questionsList"></div>
        </div>
        <!-- Tab Học sinh -->
        <div id="tab-students" class="tab-content">
            <div class="form-card">
                <h3>➕ Thêm học sinh</h3>
                <div class="form-grid">
                    <div class="field"><label>Trường</label><select id="studentSchoolId"></select></div>
                    <div class="field"><label>Lớp</label><select id="studentClassLevel"><option value="7">Lớp 7</option><option value="8">Lớp 8</option><option value="9">Lớp 9</option></select></div>
                    <div class="field"><label>Họ tên</label><input type="text" id="studentName"></div>
                    <button onclick="addStudent()">Thêm</button>
                </div>
            </div>
            <div id="studentsList"></div>
        </div>
        <!-- Tab Điểm -->
        <div id="tab-scores" class="tab-content">
            <button onclick="loadScores()">🔄 Làm mới</button>
            <div id="scoresTable" style="margin-top:20px; overflow-x:auto"></div>
        </div>
        <!-- Tab Cài đặt -->
        <div id="tab-settings" class="tab-content">
            <div class="form-card">
                <label>⏱️ Thời gian làm bài (phút)</label>
                <input type="number" id="timeLimitMin" value="30" style="width:200px">
                <button onclick="saveTimeLimit()" style="margin-left:15px">Lưu</button>
            </div>
        </div>
    </div>
</div>
<script>
    // Theme
    function toggleTheme() { document.body.classList.toggle('dark'); localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light'); }
    if (localStorage.getItem('theme') === 'dark') document.body.classList.add('dark');

    // Admin auth
    function adminLogin() {
        let pass = document.getElementById('adminPass').value;
        fetch('/api/admin/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass})})
        .then(r=>r.json()).then(data=>{
            if(data.success){
                document.getElementById('loginSection').style.display='none';
                document.getElementById('adminPanel').style.display='block';
                loadAllData();
            } else { document.getElementById('loginError').innerText='Sai mật khẩu'; }
        });
    }
    function adminLogout() { fetch('/api/admin/logout',{method:'POST'}).then(()=>location.reload()); }

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn=>{
        btn.addEventListener('click',()=>{
            document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(tc=>tc.classList.remove('active'));
            document.getElementById(btn.dataset.tab).classList.add('active');
            if(btn.dataset.tab === 'tab-scores') loadScores();
            if(btn.dataset.tab === 'tab-schools') loadSchools();
            if(btn.dataset.tab === 'tab-lessons') { loadSchoolsForSelect(); loadLessons(); }
            if(btn.dataset.tab === 'tab-questions') { loadLessonsForSelect2(); loadQuestions(); }
            if(btn.dataset.tab === 'tab-students') { loadSchoolsForSelect2(); loadStudents(); }
        });
    });

    function loadAllData() { loadSchools(); loadLessons(); loadStudents(); loadQuestions(); loadSettings(); loadSchoolsForSelect(); loadSchoolsForSelect2(); loadLessonsForSelect2(); }

    // Schools
    function loadSchools() {
        fetch('/api/admin/schools').then(r=>r.json()).then(schools=>{
            let html='<table><thead><tr><th>ID</th><th>Tên trường</th><th>Thao tác</th></tr></thead><tbody>';
            schools.forEach(s=>{html+=`<tr><td>${s.id}</td><td>${s.name}</td><td><button class="danger" onclick="deleteSchool(${s.id})">Xóa trường</button></td></tr>`;});
            html+='</tbody></table>';
            document.getElementById('schoolsList').innerHTML=html;
        });
    }
    function addSchool() { let name=document.getElementById('schoolName').value; fetch('/api/admin/schools',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}).then(()=>{loadSchools();});}
    function deleteSchool(id) { if(confirm('Xóa trường sẽ mất toàn bộ dữ liệu liên quan?')) fetch(`/api/admin/schools/${id}`,{method:'DELETE'}).then(()=>loadSchools()); }

    // Lessons
    function loadSchoolsForSelect() {
        fetch('/api/admin/schools').then(r=>r.json()).then(schools=>{
            let sel=document.getElementById('lessonSchoolId');
            sel.innerHTML='<option value="">Chọn trường</option>';
            schools.forEach(s=>{sel.innerHTML+=`<option value="${s.id}">${s.name}</option>`;});
        });
    }
    function loadLessons() {
        fetch('/api/admin/lessons').then(r=>r.json()).then(lessons=>{
            let html='<table><thead><tr><th>ID</th><th>Trường</th><th>Lớp</th><th>Tên bài học</th><th>Mô tả</th><th>Xóa</th></tr></thead><tbody>';
            lessons.forEach(l=>{html+=`<tr><td>${l.id}</td><td>${l.school_name}</td><td>${l.class_level}</td><td>${l.name}</td><td>${l.description||''}</td><td><button class="danger" onclick="deleteLesson(${l.id})">Xóa</button></td></tr>`;});
            html+='</tbody></table>';
            document.getElementById('lessonsList').innerHTML=html;
        });
    }
    function addLesson() { let school_id=document.getElementById('lessonSchoolId').value; let class_level=document.getElementById('lessonClassLevel').value; let name=document.getElementById('lessonName').value; let description=document.getElementById('lessonDesc').value; fetch('/api/admin/lessons',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({school_id,class_level,name,description})}).then(()=>{loadLessons();});}
    function deleteLesson(id) { if(confirm('Xóa bài học?')) fetch(`/api/admin/lessons/${id}`,{method:'DELETE'}).then(()=>loadLessons()); }

    // Questions
    function loadLessonsForSelect2() {
        fetch('/api/admin/lessons').then(r=>r.json()).then(lessons=>{
            let sel=document.getElementById('qLessonId');
            sel.innerHTML='<option value="">Chọn bài học</option>';
            lessons.forEach(l=>{sel.innerHTML+=`<option value="${l.id}">${l.school_name} - Lớp ${l.class_level} - ${l.name}</option>`;});
        });
    }
    function updateOptionsUI() {
        let type = document.getElementById('qType').value;
        let container = document.getElementById('optionsContainer');
        if(type === 'single_choice') {
            container.innerHTML = `
                <div class="field">
                    <label>📝 Các lựa chọn (mỗi dòng một đáp án)</label>
                    <textarea id="qOptions" rows="3" placeholder="Đáp án A&#10;Đáp án B&#10;Đáp án C"></textarea>
                </div>
                <div class="field">
                    <label>✅ Đáp án đúng (nhập chính xác nội dung đáp án)</label>
                    <input type="text" id="qCorrect" placeholder="Ví dụ: Đáp án A">
                </div>`;
        } else if(type === 'multiple_choices') {
            container.innerHTML = `
                <div class="field">
                    <label>📝 Các lựa chọn (mỗi dòng một đáp án)</label>
                    <textarea id="qOptions" rows="3" placeholder="Đáp án A&#10;Đáp án B&#10;Đáp án C"></textarea>
                </div>
                <div class="field">
                    <label>✅ Đáp án đúng (các đáp án cách nhau bằng dấu phẩy, ví dụ: Đáp án A, Đáp án C)</label>
                    <input type="text" id="qCorrect" placeholder="Đáp án A, Đáp án C">
                </div>`;
        } else if(type === 'drag_drop') {
            container.innerHTML = `
                <div class="field">
                    <label>🎯 Dữ liệu kéo thả (JSON) – ví dụ:</label>
                    <textarea id="qOptions" rows="2">{"keo1":"Toán","keo2":"Văn"}</textarea>
                </div>
                <div class="field">
                    <label>🔗 Ánh xạ đúng (JSON)</label>
                    <textarea id="qCorrect" rows="2">{"keo1":"Môn Toán","keo2":"Môn Văn"}</textarea>
                </div>
                <small style="color:gray">Mỗi mục kéo phải được thả đúng vào vùng có tên tương ứng.</small>`;
        } else if(type === 'match') {
            container.innerHTML = `
                <div class="field">
                    <label>🔀 Các cặp ghép (JSON)</label>
                    <textarea id="qOptions" rows="2">[{"trái":"Táo","phải":"Trái cây"},{"trái":"Cà rốt","phải":"Rau"}]</textarea>
                </div>
                <div class="field">
                    <label>✅ Đáp án đúng (JSON giống cặp ghép)</label>
                    <textarea id="qCorrect" rows="2">[{"trái":"Táo","phải":"Trái cây"},{"trái":"Cà rốt","phải":"Rau"}]</textarea>
                </div>`;
        } else if(type === 'choice_on_table') {
            container.innerHTML = `
                <div class="field">
                    <label>📊 Dữ liệu bảng (JSON)</label>
                    <textarea id="qOptions" rows="3">{"rows":["Hàng1","Hàng2"],"cols":["CộtA","CộtB"],"correct":[[1,0],[0,1]]}</textarea>
                </div>
                <div class="field">
                    <label>✅ Đáp án đúng (JSON – cấu trúc tương tự)</label>
                    <textarea id="qCorrect" rows="2">{"correct":[[1,0],[0,1]]}</textarea>
                </div>`;
        }
    }
    function addQuestion(){
        let lesson_id = document.getElementById('qLessonId').value;
        let type = document.getElementById('qType').value;
        let text = document.getElementById('qText').value;
        let options, correct;
        if(type === 'single_choice' || type === 'multiple_choices') {
            options = document.getElementById('qOptions').value.split('\\n').filter(s => s.trim().length > 0);
            if(type === 'multiple_choices') {
                correct = document.getElementById('qCorrect').value.split(',').map(s => s.trim());
            } else {
                correct = document.getElementById('qCorrect').value.trim();
            }
        } else {
            options = JSON.parse(document.getElementById('qOptions').value);
            correct = JSON.parse(document.getElementById('qCorrect').value);
        }
        fetch('/api/admin/questions', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({lesson_id, type, text, options, correct_answer:correct})
        })
        .then(()=>{
            document.getElementById('questionMsg').innerHTML='<span style="color:green">✓ Đã thêm</span>';
            loadQuestions();
        })
        .catch(err=>{
            document.getElementById('questionMsg').innerHTML='<span style="color:red">Lỗi: '+err.message+'</span>';
        });
    }
    function loadQuestions(){
        fetch('/api/admin/questions').then(r=>r.json()).then(questions=>{
            let html='<table><thead><tr><th>ID</th><th>Bài học</th><th>Loại</th><th>Nội dung</th><th>Xóa</th></tr></thead><tbody>';
            questions.forEach(q=>{html+=`<tr><td>${q.id}</td><td>${q.school_name} - Lớp ${q.class_level} - ${q.lesson_name}</td><td><span class="badge">${q.type}</span></td><td>${q.text.substring(0,60)}</td><td><button class="danger" onclick="deleteQuestion(${q.id})">Xóa</button></td></tr>`;});
            html+='</tbody></table>';
            document.getElementById('questionsList').innerHTML=html;
        });
    }
    function deleteQuestion(id){ if(confirm('Xóa câu hỏi?')) fetch(`/api/admin/questions/${id}`,{method:'DELETE'}).then(()=>loadQuestions()); }

    // Students
    function loadSchoolsForSelect2() {
        fetch('/api/admin/schools').then(r=>r.json()).then(schools=>{
            let sel=document.getElementById('studentSchoolId');
            sel.innerHTML='<option value="">Chọn trường</option>';
            schools.forEach(s=>{sel.innerHTML+=`<option value="${s.id}">${s.name}</option>`;});
        });
    }
    function loadStudents(){
        fetch('/api/admin/students').then(r=>r.json()).then(students=>{
            let html='<table><thead><tr><th>ID</th><th>Họ tên</th><th>Trường</th><th>Lớp</th><th>Xóa</th></tr></thead><tbody>';
            students.forEach(s=>{html+=`<tr><td>${s.id}</td><td>${s.name}</td><td>${s.school_name}</td><td>${s.class_level}</td><td><button class="danger" onclick="deleteStudent(${s.id})">Xóa</button></td></tr>`;});
            html+='</tbody></table>';
            document.getElementById('studentsList').innerHTML=html;
        });
    }
    function addStudent(){ let school_id=document.getElementById('studentSchoolId').value; let class_level=document.getElementById('studentClassLevel').value; let name=document.getElementById('studentName').value; fetch('/api/admin/students',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({school_id,class_level,name})}).then(()=>loadStudents());}
    function deleteStudent(id){ if(confirm('Xóa học sinh?')) fetch(`/api/admin/students/${id}`,{method:'DELETE'}).then(()=>loadStudents()); }

    // Scores
    function loadScores(){
        fetch('/api/admin/scores').then(r=>r.json()).then(scores=>{
            let html='<table><thead><tr><th>Học sinh</th><th>Trường</th><th>Lớp</th><th>Bài học</th><th>Điểm (đúng/tổng)</th><th>%</th></tr></thead><tbody>';
            scores.forEach(s=>{ let percent = s.total_questions ? Math.round(s.correct_count/s.total_questions*100) : 0; html+=`<tr><td>${s.student_name}</td><td>${s.school_name}</td><td>${s.class_level}</td><td>${s.lesson_name}</td><td>${s.correct_count}/${s.total_questions}</td><td>${percent}%</td></tr>`;});
            html+='</tbody></table>';
            document.getElementById('scoresTable').innerHTML=html;
        });
    }

    // Settings
    function loadSettings(){ fetch('/api/admin/settings').then(r=>r.json()).then(data=>{ document.getElementById('timeLimitMin').value=data.time_limit_minutes; });}
    function saveTimeLimit(){ let val=document.getElementById('timeLimitMin').value; fetch('/api/admin/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({time_limit_minutes:parseInt(val)})}).then(()=>alert('Đã lưu')); }
</script>
</body>
</html>
'''

STUDENT_PAGE = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Học sinh - Làm bài thi</title>
    <style>
        :root {
            --bg: #f0f4f8;
            --card-bg: #ffffff;
            --text: #1e2a3a;
            --border: #cbd5e1;
            --header-bg: #1e2a3a;
            --btn-primary: #2c6e9e;
            --btn-danger: #c0392b;
        }
        body.dark {
            --bg: #121826;
            --card-bg: #1e293b;
            --text: #e2e8f0;
            --border: #334155;
            --header-bg: #0f172a;
            --btn-primary: #3b82f6;
            --btn-danger: #ef4444;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: var(--bg);
            font-family: 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
            color: var(--text);
            transition: 0.2s;
        }
        .container {
            max-width: 1300px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: var(--header-bg);
            color: white;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .login-card, .lesson-list, .test-area { padding: 30px; }
        select, input, button {
            width: 100%;
            padding: 10px;
            margin: 8px 0;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--card-bg);
            color: var(--text);
        }
        button {
            background: var(--btn-primary);
            color: white;
            font-weight: bold;
            cursor: pointer;
        }
        .lesson-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px,1fr));
            gap: 16px;
            margin-top: 20px;
        }
        .lesson-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            cursor: pointer;
            transition: 0.1s;
        }
        .lesson-card:hover { background: var(--border); }
        .timer-bar {
            background: #2c3e50;
            color: #f1c40f;
            text-align: center;
            padding: 10px;
            font-size: 1.3rem;
            font-weight: bold;
        }
        .test-layout { display: flex; flex-wrap: wrap; }
        .summary-panel {
            width: 260px;
            background: var(--card-bg);
            border-right: 1px solid var(--border);
            padding: 20px;
        }
        .question-panel { flex: 1; padding: 20px; }
        .q-btn {
            background: #e2e8f0;
            border: none;
            padding: 8px;
            margin: 4px;
            width: 40px;
            border-radius: 6px;
            cursor: pointer;
        }
        .q-btn.answered { background: #27ae60; color: white; }
        .q-btn.current { background: var(--btn-primary); color: white; }
        .question-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .drag-item {
            background: #e2e8f0;
            display: inline-block;
            padding: 8px 16px;
            margin: 6px;
            border-radius: 30px;
            cursor: grab;
        }
        .dropzone {
            border: 2px dashed #94a3b8;
            padding: 12px;
            margin: 10px 0;
            border-radius: 8px;
        }
        .nav-buttons { display: flex; justify-content: space-between; margin-top: 20px; }
    </style>
</head>
<body>
<div id="loginView" class="container" style="max-width:500px">
    <div class="header"><h2>🔑 Đăng nhập</h2><button class="theme-toggle" onclick="toggleTheme()" style="width:auto;">🌓</button></div>
    <div class="login-card">
        <label>Chọn trường</label>
        <select id="schoolSelect" onchange="loadClasses()"></select>
        <label>Chọn lớp</label>
        <select id="classSelect" onchange="loadStudentsList()"></select>
        <label>Chọn học sinh</label>
        <select id="studentSelect"></select>
        <button onclick="studentLogin()">Vào làm bài</button>
        <div id="loginError" style="color:red; margin-top:10px"></div>
    </div>
</div>
<div id="lessonView" class="container" style="display:none">
    <div class="header"><h2>📚 Chọn bài học</h2><div><button class="theme-toggle" onclick="toggleTheme()" style="width:auto;">🌓</button><button onclick="logout()" style="background:#c0392b; margin-left:10px;">Đăng xuất</button></div></div>
    <div class="lesson-list" id="lessonListContainer"></div>
</div>
<div id="testView" style="display:none">
    <div class="container">
        <div class="timer-bar" id="timerDisplay">⏱️ Thời gian: --:--</div>
        <div class="test-layout">
            <div class="summary-panel">
                <h4>📌 Câu hỏi</h4>
                <div id="summaryButtons"></div>
                <button onclick="submitTest()" style="margin-top:20px; background:var(--btn-danger)">Nộp bài</button>
            </div>
            <div class="question-panel">
                <div id="questionsContainer"></div>
                <div class="nav-buttons">
                    <button onclick="prevQuestion()">◀ Trước</button>
                    <button onclick="nextQuestion()">Sau ▶</button>
                </div>
            </div>
        </div>
    </div>
</div>
<script>
    function toggleTheme() { document.body.classList.toggle('dark'); localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light'); }
    if (localStorage.getItem('theme') === 'dark') document.body.classList.add('dark');

    let currentQuestionIndex = 0, questionsData = [], userAnswers = {}, timerInterval = null, timeLeftSeconds = 0;

    function loadSchools() {
        fetch('/api/student/schools').then(r=>r.json()).then(schools=>{
            let sel=document.getElementById('schoolSelect');
            sel.innerHTML='<option value="">Chọn trường</option>';
            schools.forEach(s=>{ sel.innerHTML+=`<option value="${s.id}">${s.name}</option>`; });
        });
    }
    function loadClasses() {
        let schoolId=document.getElementById('schoolSelect').value;
        if(!schoolId) return;
        let sel=document.getElementById('classSelect');
        sel.innerHTML='<option value="">Chọn lớp</option><option value="7">Lớp 7</option><option value="8">Lớp 8</option><option value="9">Lớp 9</option>';
    }
    function loadStudentsList() {
        let schoolId=document.getElementById('schoolSelect').value;
        let classLevel=document.getElementById('classSelect').value;
        if(!schoolId || !classLevel) return;
        fetch('/api/student/students', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({school_id:schoolId, class_level:classLevel})})
        .then(r=>r.json()).then(students=>{
            let sel=document.getElementById('studentSelect');
            sel.innerHTML='<option value="">Chọn học sinh</option>';
            students.forEach(s=>{ sel.innerHTML+=`<option value="${s.id}">${s.name}</option>`; });
        });
    }
    function studentLogin() {
        let studentId=document.getElementById('studentSelect').value;
        if(!studentId) { alert('Chọn học sinh'); return; }
        fetch('/api/student/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_id:studentId})})
        .then(r=>r.json()).then(data=>{
            if(data.success){
                document.getElementById('loginView').style.display='none';
                loadLessonList();
            } else { document.getElementById('loginError').innerText=data.error; }
        });
    }
    function loadLessonList() {
        fetch('/api/student/lessons').then(r=>r.json()).then(data=>{
            let container=document.getElementById('lessonListContainer');
            let html='<h3>Bài học chính thức</h3><div class="lesson-grid">';
            data.normal.forEach(lesson=>{
                html+=`<div class="lesson-card" onclick="startTest(${lesson.id}, null)"><strong>${lesson.name}</strong><br><small>${lesson.description||''}</small></div>`;
            });
            html+='</div>';
            if(data.special.length){
                html+='<h3 style="margin-top:30px">Bài tổng hợp & thi</h3><div class="lesson-grid">';
                data.special.forEach(sp=>{
                    html+=`<div class="lesson-card" onclick="startTest(null, '${sp.special}')"><strong>${sp.name}</strong><br><small>${sp.description}</small></div>`;
                });
                html+='</div>';
            }
            container.innerHTML=html;
            document.getElementById('lessonView').style.display='block';
        });
    }
    function startTest(lessonId, special) {
        fetch('/api/student/test_data', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lesson_id:lessonId, special:special})})
        .then(r=>r.json()).then(data=>{
            questionsData = data.questions;
            userAnswers = data.answered;
            timeLeftSeconds = data.time_limit;
            startTimer();
            renderSummary();
            renderCurrentQuestion();
            document.getElementById('lessonView').style.display='none';
            document.getElementById('testView').style.display='block';
        });
    }
    function startTimer() { if(timerInterval) clearInterval(timerInterval); timerInterval=setInterval(()=>{ if(timeLeftSeconds<=0){clearInterval(timerInterval); alert('Hết giờ!'); submitTest();} else{ timeLeftSeconds--; let min=Math.floor(timeLeftSeconds/60); let sec=timeLeftSeconds%60; document.getElementById('timerDisplay').innerHTML=`⏱️ Thời gian còn lại: ${min}:${sec<10?'0'+sec:sec}`; } },1000);}
    function renderSummary() {
        let div=document.getElementById('summaryButtons');
        div.innerHTML='';
        questionsData.forEach((q,idx)=>{
            let btn=document.createElement('button');
            btn.innerText=`${idx+1}`;
            btn.className=`q-btn ${userAnswers[q.id]?'answered':''}`;
            if(currentQuestionIndex===idx) btn.classList.add('current');
            btn.onclick=()=>{currentQuestionIndex=idx; renderCurrentQuestion(); renderSummary();};
            div.appendChild(btn);
        });
    }
    function renderCurrentQuestion() {
        if(questionsData.length===0) return;
        let q=questionsData[currentQuestionIndex];
        let container=document.getElementById('questionsContainer');
        let saved=userAnswers[q.id]?userAnswers[q.id].answer:null;
        let html=`<div class="question-card"><h3>Câu ${currentQuestionIndex+1}: ${q.text}</h3>`;
        if(q.type === 'single_choice'){
            let shuffledOptions = [...q.options];
            for(let i = shuffledOptions.length - 1; i > 0; i--){
                let j = Math.floor(Math.random() * (i + 1));
                [shuffledOptions[i], shuffledOptions[j]] = [shuffledOptions[j], shuffledOptions[i]];
            }
            html += `<div>`;
            shuffledOptions.forEach(opt => {
                let checked = (saved === opt) ? 'checked' : '';
                html += `<label style="display:block"><input type="radio" name="q${q.id}" value="${opt}" ${checked} onchange="saveAnswer(${q.id}, this.value)"> ${opt}</label>`;
            });
            html += `</div>`;
        } else if(q.type === 'multiple_choices'){
            let shuffledOptions = [...q.options];
            for(let i = shuffledOptions.length - 1; i > 0; i--){
                let j = Math.floor(Math.random() * (i + 1));
                [shuffledOptions[i], shuffledOptions[j]] = [shuffledOptions[j], shuffledOptions[i]];
            }
            html += `<div>`;
            shuffledOptions.forEach(opt => {
                let checked = (saved && saved.includes(opt)) ? 'checked' : '';
                html += `<label><input type="checkbox" value="${opt}" ${checked} onchange="saveMultiple(${q.id}, this.value, this.checked)"> ${opt}</label><br>`;
            });
            html += `</div>`;
        } else if(q.type === 'drag_drop'){
            html += `<div id="dragdrop-${q.id}">Đang tải...</div>`;
            setTimeout(()=>initDragDrop(q, saved), 10);
        } else if(q.type === 'match'){
            html += `<div id="match-${q.id}">Đang tải...</div>`;
            setTimeout(()=>initMatch(q, saved), 10);
        } else if(q.type === 'choice_on_table'){
            html += `<div id="table-${q.id}">Đang tải...</div>`;
            setTimeout(()=>initChoiceTable(q, saved), 10);
        }
        html += `</div>`;
        container.innerHTML = html;
        renderSummary();
    }
    function saveAnswer(qid,val){ userAnswers[qid]={answer:val}; sendAnswer(qid,val); renderSummary(); }
    function saveMultiple(qid,val,checked){ let current=userAnswers[qid]?userAnswers[qid].answer:[]; if(checked){ if(!current.includes(val)) current.push(val); } else { current=current.filter(v=>v!==val); } userAnswers[qid]={answer:current}; sendAnswer(qid,current); renderSummary(); }
    function sendAnswer(qid,ans){ fetch('/api/student/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question_id:qid,answer:ans})}); }
    function initDragDrop(q,saved){ let container=document.getElementById(`dragdrop-${q.id}`); if(!container) return; let items=q.options; let mapping=saved||{}; let dragItems=Object.keys(items); let dropZones=Object.values(items); let html=`<div style="display:flex; flex-wrap:wrap"><div style="flex:1"><h4>Kéo:</h4><div>`; dragItems.forEach(key=>{html+=`<div draggable="true" ondragstart="dragStart(event)" data-key="${key}" class="drag-item">${items[key]}</div>`;}); html+=`</div></div><div style="flex:1"><h4>Thả:</h4>`; dropZones.forEach(zone=>{html+=`<div ondragover="allowDrop(event)" ondrop="drop(event, ${q.id})" data-zone="${zone}" class="dropzone"><strong>${zone}</strong>: <span id="dropval-${q.id}-${zone}">${mapping&&Object.keys(mapping).find(k=>mapping[k]===zone)?items[Object.keys(mapping).find(k=>mapping[k]===zone)]:'❌'}</span></div>`;}); html+=`</div></div>`; container.innerHTML=html; }
    function allowDrop(e){ e.preventDefault(); }
    function dragStart(e){ e.dataTransfer.setData("text/plain", e.target.getAttribute('data-key')); }
    function drop(e,qid){ e.preventDefault(); let dragKey=e.dataTransfer.getData("text/plain"); let dropZone=e.target.closest('.dropzone').getAttribute('data-zone'); let currentMap=userAnswers[qid]?userAnswers[qid].answer:{}; currentMap[dragKey]=dropZone; userAnswers[qid]={answer:currentMap}; sendAnswer(qid,currentMap); renderCurrentQuestion(); }
    function initMatch(q,saved){ let container=document.getElementById(`match-${q.id}`); let pairs=q.options; let savedMap=saved||{}; let html=`<table style="width:100%">`; pairs.forEach((pair,idx)=>{ html+=`<tr><td>${pair.trái}</td><td><select onchange="saveMatch(${q.id}, '${pair.trái}', this.value)"><option value="">Chọn</option>`; pairs.forEach(p=>{ html+=`<option value="${p.phải}" ${savedMap[pair.trái]===p.phải?'selected':''}>${p.phải}</option>`;}); html+=`</select></td></tr>`; }); html+=`</table>`; container.innerHTML=html; }
    function saveMatch(qid,leftVal,rightVal){ let current=userAnswers[qid]?userAnswers[qid].answer:{}; current[leftVal]=rightVal; userAnswers[qid]={answer:current}; sendAnswer(qid,current); renderSummary(); }
    function initChoiceTable(q,saved){ let container=document.getElementById(`table-${q.id}`); let tableData=q.options; let savedData=saved||{}; let correctMatrix=savedData.correct||[]; let html=`<table border="1">`; html+=`<tr><th></th>`; tableData.cols.forEach(col=>html+=`<th>${col}</th>`); html+=`</tr>`; tableData.rows.forEach((row,ri)=>{ html+=`<tr><td>${row}</td>`; tableData.cols.forEach((col,ci)=>{ let checked=(correctMatrix[ri]&&correctMatrix[ri][ci]===1)?'checked':''; html+=`<td style="text-align:center"><input type="checkbox" onchange="saveTableChoice(${q.id}, ${ri}, ${ci}, this.checked)" ${checked}></td>`; }); html+=`</tr>`; }); html+=`</table>`; container.innerHTML=html; }
    function saveTableChoice(qid,ri,ci,val){ let current=userAnswers[qid]?userAnswers[qid].answer:{correct:[]}; if(!current.correct) current.correct=[]; if(!current.correct[ri]) current.correct[ri]=[]; current.correct[ri][ci]=val?1:0; userAnswers[qid]={answer:current}; sendAnswer(qid,current); }
    function nextQuestion(){ if(currentQuestionIndex<questionsData.length-1){ currentQuestionIndex++; renderCurrentQuestion(); } }
    function prevQuestion(){ if(currentQuestionIndex>0){ currentQuestionIndex--; renderCurrentQuestion(); } }
    function submitTest(){ if(confirm('Nộp bài thi?')){ clearInterval(timerInterval); fetch('/api/student/finish',{method:'POST'}).then(()=>{ alert('Đã nộp bài'); location.reload(); }); } }
    function logout(){ location.reload(); }
    loadSchools();
    document.getElementById('classSelect').addEventListener('change', loadStudentsList);
</script>
</body>
</html>
'''

if __name__ == '__main__':
    print("="*60)
    print("✅ Máy chủ đã khởi động")
    print("📌 Giáo viên: http://localhost:5000/admin  (mật khẩu: teacher123)")
    print("🎓 Học sinh:  http://localhost:5000/student")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)