-- Library Management System : database schema + sample data
-- Run in phpMyAdmin (XAMPP) or:  mysql -u root < schema.sql

CREATE DATABASE IF NOT EXISTS library_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE library_db;

DROP TABLE IF EXISTS issues;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS books;

-- Module 1: Books
CREATE TABLE books (
  book_id          INT AUTO_INCREMENT PRIMARY KEY,
  title            VARCHAR(200) NOT NULL,
  author           VARCHAR(120) NOT NULL,
  isbn             VARCHAR(20)  NOT NULL UNIQUE,
  category         VARCHAR(60)  NOT NULL,
  total_copies     INT NOT NULL DEFAULT 1 CHECK (total_copies >= 0),
  available_copies INT NOT NULL DEFAULT 1 CHECK (available_copies >= 0),
  added_on         DATE NOT NULL DEFAULT (CURRENT_DATE)
);

-- Module 2: Members
CREATE TABLE members (
  member_id   INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(120) NOT NULL,
  email       VARCHAR(120) NOT NULL UNIQUE,
  phone       VARCHAR(20),
  member_type ENUM('Student','Faculty','Staff') NOT NULL DEFAULT 'Student',
  joined_on   DATE NOT NULL DEFAULT (CURRENT_DATE)
);

-- Module 3: Issue & return (links books and members)
CREATE TABLE issues (
  issue_id    INT AUTO_INCREMENT PRIMARY KEY,
  book_id     INT NOT NULL,
  member_id   INT NOT NULL,
  issue_date  DATE NOT NULL,
  due_date    DATE NOT NULL,
  return_date DATE NULL,
  fine        DECIMAL(8,2) NOT NULL DEFAULT 0,
  CONSTRAINT fk_issue_book   FOREIGN KEY (book_id)   REFERENCES books(book_id)     ON DELETE RESTRICT,
  CONSTRAINT fk_issue_member FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE RESTRICT,
  CHECK (due_date >= issue_date)
);

CREATE INDEX idx_issues_open ON issues (return_date, due_date);

-- ---------- Sample data ----------
INSERT INTO books (title, author, isbn, category, total_copies, available_copies) VALUES
('Database System Concepts',        'Silberschatz, Korth, Sudarshan', '9780078022159', 'Computer Science', 4, 4),
('Fundamentals of Database Systems','Elmasri, Navathe',               '9780133970777', 'Computer Science', 3, 3),
('Introduction to Algorithms',      'Cormen, Leiserson, Rivest',      '9780262046305', 'Computer Science', 2, 2),
('Python Crash Course',             'Eric Matthes',                   '9781718502703', 'Programming',      3, 3),
('Clean Code',                      'Robert C. Martin',               '9780132350884', 'Programming',      2, 2),
('Thinking, Fast and Slow',         'Daniel Kahneman',                '9780374533557', 'Psychology',       2, 2),
('A Brief History of Time',         'Stephen Hawking',                '9780553380163', 'Science',          2, 2),
('Pather Panchali',                 'Bibhutibhushan Bandyopadhyay',   '9788129115898', 'Literature',       2, 2),
('Lajja',                           'Taslima Nasrin',                 '9780140240191', 'Literature',       1, 1),
('Principles of Economics',         'N. Gregory Mankiw',              '9781305585126', 'Economics',        3, 3);

INSERT INTO members (name, email, phone, member_type) VALUES
('Tahmid Rahman',  'tahmid@example.com',  '01711000001', 'Student'),
('Nusrat Jahan',   'nusrat@example.com',  '01711000002', 'Student'),
('Dr. Imran Hossain','imran@example.com', '01711000003', 'Faculty'),
('Farhana Akter',  'farhana@example.com', '01711000004', 'Staff'),
('Sakib Ahmed',    'sakib@example.com',   '01711000005', 'Student');

INSERT INTO issues (book_id, member_id, issue_date, due_date, return_date, fine) VALUES
(1, 1, CURDATE() - INTERVAL 25 DAY, CURDATE() - INTERVAL 11 DAY, NULL, 0),                         -- overdue
(4, 2, CURDATE() - INTERVAL 5 DAY,  CURDATE() + INTERVAL 9 DAY,  NULL, 0),                          -- active
(3, 3, CURDATE() - INTERVAL 30 DAY, CURDATE() - INTERVAL 16 DAY, CURDATE() - INTERVAL 10 DAY, 0),   -- returned
(6, 5, CURDATE() - INTERVAL 20 DAY, CURDATE() - INTERVAL 6 DAY,  CURDATE() - INTERVAL 2 DAY, 20),   -- returned late
(9, 4, CURDATE() - INTERVAL 2 DAY,  CURDATE() + INTERVAL 12 DAY, NULL, 0);                          -- active

-- keep available_copies consistent with open issues
UPDATE books b
SET available_copies = total_copies -
  (SELECT COUNT(*) FROM issues i WHERE i.book_id = b.book_id AND i.return_date IS NULL);
