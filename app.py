from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-very-secure-key'  # Change to a strong key

# Google Sheets Setup
SPREADSHEET_ID = "1hyoQZpD17tsTjSh1XqgAUvfZ4Nt3kwV7zxphosruXeE"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Sheets
login_sheet = client.open_by_key(SPREADSHEET_ID).worksheet("USER")

# Decorator

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("⚠️ You must be logged in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # Get data with proper header handling
        all_data = login_sheet.get_all_values()
        headers = [h.strip() for h in all_data[0]]  # Clean headers
        users = []
        for row in all_data[1:]:
            users.append(dict(zip(headers, row)))

        for user in users:
            sheet_email = user.get('EmployeeMailId', '').strip().lower()
            sheet_password = user.get('Password', '').strip()  # Now works with cleaned header
            
            if email == sheet_email:
                if password == sheet_password:
                    session['logged_in'] = True
                    session['email'] = email
                    session['fullname'] = user.get('FullName', '')
                    session['role'] = user.get('Role', '').lower()
                    return redirect(url_for('admin_dashboard' if session['role'] == 'admin' else 'instructions'))
                else:
                    flash('Incorrect password', 'danger')
                    break
        else:
            flash('Email not found', 'danger')

        return redirect(url_for('login'))

    return render_template('login.html')



@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    return "<h2>📊 Admin Dashboard</h2>"


@app.route('/instructions')

def instructions():
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # Fetch instructions
        instructions_sheet = spreadsheet.worksheet("Instructions")
        instructions = instructions_sheet.col_values(1)

        # Fetch metadata
        meta_sheet = spreadsheet.worksheet("TIME")
        meta_records = meta_sheet.get_all_records()
        meta = meta_records[0] if meta_records else {}

        duration = meta.get('Duration', 'N/A')
        total_questions = meta.get('TotalQuestions', 'N/A')

    except Exception as e:
        instructions = ["❌ Failed to load instructions: " + str(e)]
        duration = "N/A"
        total_questions = "N/A"

    return render_template('instructions.html',
                           fullname=session.get('fullname'),
                           instructions=instructions,
                           duration=duration,
                           total_questions=total_questions)




@app.route('/exam')
@login_required
def exam():
    return render_template('exam.html', fullname=session.get('fullname'))




@app.route('/get_questions/<test_id>')
@login_required
def get_questions(test_id):
    try:
        # For TEST01 use Questions_TEST01
        worksheet_name = f"Questions_TEST{test_id}"
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        q_sheet = spreadsheet.worksheet(worksheet_name)
        questions = q_sheet.get_all_records(head=1)
        
        return jsonify(questions)
        
    except gspread.exceptions.WorksheetNotFound:
        return jsonify({'error': f'Worksheet {worksheet_name} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/submit_exam', methods=['POST'])
@login_required
def submit_exam():
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        email = session.get('email')
        time_taken = data.get('time_taken')  # Get time taken from frontend
        
        if not test_id or not email:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        
        # Get the test questions and answers
        worksheet_name = f"Questions_TEST{test_id}"
        q_sheet = client.open_by_key(SPREADSHEET_ID).worksheet(worksheet_name)
        questions = q_sheet.get_all_records(head=1)
        
        # Get all user answers
        user_answers = data.get('answers', {})
        
        # Calculate score
        correct = 0
        total = len(questions)
        
        for question in questions:
            qid = str(question['QID'])
            if qid in user_answers and user_answers[qid] == question['Answer']:
                correct += 1
        
        score = correct
        percentage = (correct / total) * 100 if total > 0 else 0
        
        # Get or create results sheet
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            results_sheet = spreadsheet.worksheet(f"Results_TEST{test_id}")
            # Check if headers exist
            headers = results_sheet.row_values(1)
            if "TimeTaken" not in headers:
                results_sheet.insert_cols([["TimeTaken"]], len(headers)+1)
        except gspread.exceptions.WorksheetNotFound:
            results_sheet = spreadsheet.add_worksheet(
                title=f"Results_TEST{test_id}", 
                rows=100, 
                cols=11
            )
            results_sheet.append_row([
                "Timestamp", "Email", "FullName", "Score", 
                "Correct", "Total", "Percentage", "TimeTaken"
            ])
        
        # Record the submission with time taken
        results_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email,
            session.get('fullname'),
            score,
            correct,
            total,
            f"{percentage:.2f}%",
            time_taken  # Store the time taken
        ])
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/logout')
def logout():
    session.clear()
    flash('✅ Logged out', 'info')
    return redirect(url_for('login'))
@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        qid = data.get('qid')
        selected_answers = data.get('selected_answers', [])
        status = data.get('status', 'answered')
        
        # In a real implementation, you'd store these answers in a session or database
        # For now, we'll just return success
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/log_violation', methods=['POST'])
@login_required
def log_violation():
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        email = session.get('email')
        violation = data.get('violation')
        violation_count = data.get('violation_count')
        
        if not all([test_id, email, violation, violation_count]):
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        
        # Get or create violations sheet
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            violations_sheet = spreadsheet.worksheet(f"Violations_TEST{test_id}")
        except gspread.exceptions.WorksheetNotFound:
            violations_sheet = spreadsheet.add_worksheet(
                title=f"Violations_TEST{test_id}", 
                rows=100, 
                cols=6
            )
            violations_sheet.append_row([
                "Timestamp", "Email", "FullName", "Violation", 
                "ViolationCount", "ActionTaken"
            ])
        
        # Record the violation
        violations_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email,
            session.get('fullname'),
            violation,
            violation_count,
            "Warning" if violation_count < 3 else "Exam Terminated"
        ])
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True,port = 5000)  # Change port if needed
