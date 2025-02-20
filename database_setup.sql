CREATE DATABASE ai_interview;
USE ai_interview;

CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE interviews (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    role VARCHAR(100),
    score INT,
    duration INT,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE interview_responses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    interview_id INT,
    question TEXT,
    answer TEXT,
    feedback TEXT,
    FOREIGN KEY (interview_id) REFERENCES interviews(id)
); 