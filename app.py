from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import bcrypt
import google.generativeai as genai
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Database setup
DATABASE_URL = "mysql+pymysql://root:@localhost/ai_interview"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# User model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

# Add these models after the User model
class Interview(Base):
    __tablename__ = "interviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    role = Column(String(100), nullable=False)
    score = Column(Integer)
    duration = Column(Integer)
    completed_at = Column(String(100))

class InterviewResponse(Base):
    __tablename__ = "interview_responses"
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, nullable=False)
    question = Column(String(500), nullable=False)
    answer = Column(String(1000), nullable=False)
    feedback = Column(String(1000))

# Create tables
Base.metadata.create_all(bind=engine)

app = Flask(__name__)
app.secret_key = "123"

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

# Configure Gemini API
genai.configure(api_key='Place your api key')
model = genai.GenerativeModel('gemini-pro')

# Available roles for interview
ROLES = {
    'python_developer': 'Python Developer',
    'web_developer': 'Web Developer',
    'data_scientist': 'Data Scientist',
    'devops_engineer': 'DevOps Engineer'
}

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            
            # Hash password
           # hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Create database session
            db = get_db()
            
            # Check if user exists
            existing_user = db.query(User).filter(
                (User.email == email) | (User.username == username)
            ).first()
            
            if existing_user:
                flash('Username or email already exists!')
                return redirect('/signup')
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                password=password
            )
            
            db.add(new_user)
            db.commit()
            
            flash('Registration successful! Please login.')
            return redirect('/')
            
        except Exception as e:
            print(f"Error during signup: {e}")
            db.rollback()
            flash('Registration failed! Please try again.')
            return redirect('/signup')
        finally:
            db.close()
            
    return render_template('signup.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    
    db = get_db()
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect('/dashboard')
    
    flash('Invalid credentials!')
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('dashboard.html', roles=ROLES)

@app.route('/start_interview', methods=['POST'])
def start_interview():
    if 'user_id' not in session:
        return redirect('/')
    
    role = request.form['role']
    session['current_role'] = role
    session['interview_start_time'] = datetime.now().timestamp()
    session['questions'] = generate_questions(role)
    session['current_question'] = 0
    
    return redirect('/interview')

@app.route('/interview')
def interview():
    if 'user_id' not in session or 'current_role' not in session:
        return redirect('/')
    
    questions = session.get('questions', [])
    current_q = session.get('current_question', 0)
    
    if current_q >= len(questions):
        return redirect('/complete_interview')
    
    time_elapsed = int(datetime.now().timestamp() - session['interview_start_time'])
    time_remaining = max(1800 - time_elapsed, 0)  # 30 minutes = 1800 seconds
    
    return render_template('interview.html',
                         question=questions[current_q],
                         question_number=current_q + 1,
                         total_questions=len(questions),
                         time_remaining=time_remaining)

def generate_questions(role):
    prompt = f"Generate 5 interview questions for the role of {role}. Format: List of questions only."
    response = model.generate_content(prompt)
    questions = response.text.strip().split('\n')
    return [q.strip('1234567890. ') for q in questions if q.strip()]

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session:
        return redirect('/')
    
    try:
        answer = request.form['answer']
        question = session['questions'][session['current_question']]
        
        # Get AI feedback
        prompt = f"Question: {question}\nCandidate's Answer: {answer}\nProvide a brief feedback and correct answer for this question and score out of 10."
        feedback = model.generate_content(prompt)
        
        # Create database session
        db = get_db()
        
        if session['current_question'] == 0:
            # Create new interview record
            new_interview = Interview(
                user_id=session['user_id'],
                role=session['current_role']
            )
            db.add(new_interview)
            db.commit()
            session['interview_id'] = new_interview.id
        
        # Create new response record
        new_response = InterviewResponse(
            interview_id=session['interview_id'],
            question=question,
            answer=answer,
            feedback=feedback.text
        )
        db.add(new_response)
        db.commit()
        
        session['current_question'] += 1
        return redirect('/interview')
        
    except Exception as e:
        print(f"Error submitting answer: {e}")
        flash('Error submitting answer. Please try again.')
        return redirect('/interview')
    finally:
        db.close()

@app.route('/complete_interview')
def complete_interview():
    if 'user_id' not in session:
        return redirect('/')
    
    try:
        db = get_db()
        
        # Get all responses for this interview
        responses = db.query(InterviewResponse).filter(
            InterviewResponse.interview_id == session['interview_id']
        ).all()
        
        # Calculate average score
        total_score = 0
        valid_responses = 0
        for response in responses:
            feedback = response.feedback
            try:
                # Extract the score from feedback (assuming it's the last number in the text)
                score = int(feedback.split('Score:')[1].split('out of')[0].strip())
                print(score)
                if 0 <= score <= 10:  # Ensure score is valid
                    total_score += score
                    
                    valid_responses += 1
            except:
                continue
        
        # Calculate average (protect against division by zero)
        average_score = total_score 
        
        # Ensure score is between 0 and 10
        #average_score = min(10, max(0, average_score))
        
        # Update interview record
        duration = int(datetime.now().timestamp() - session['interview_start_time'])
        interview = db.query(Interview).filter(
            Interview.id == session['interview_id']
        ).first()
        
        if interview:
            interview.score = total_score
            interview.duration = duration
            interview.completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.commit()
        
        # Clear interview session data
        session.pop('current_role', None)
        session.pop('interview_start_time', None)
        session.pop('questions', None)
        session.pop('current_question', None)
        session.pop('interview_id', None)
        
        return render_template('result.html', 
                            score=total_score,
                            duration=duration,
                            responses=responses)
                            
    except Exception as e:
        print(f"Error completing interview: {e}")
        flash('Error completing interview. Please try again.')
        return redirect('/dashboard')
    finally:
        db.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True) 
