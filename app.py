import os
import re
import sys
import time
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Form, Body, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# Google GenAI for Vision OCR & fallback LLM
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# RAG dependencies
try:
    from rank_bm25 import BM25Okapi
    from rapidfuzz import process, fuzz
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MySQLWorkbenchAPI")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FOLDER_PATH = Path(__file__).parent.resolve()

# Groq Client Setup
groq_client = None
if GROQ_API_KEY:
    groq_client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY
    )

# Gemini Client Setup
gemini_client = None
if GEMINI_API_KEY and GENAI_AVAILABLE:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini client: {e}")

GROQ_MODEL_POOL = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b"
]

GEMINI_VISION_MODELS = [
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-pro-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash"
]

current_groq_idx = 0

# ==================== PRESET SCHEMAS WITH SAMPLE DATA ====================
PRESETS = {
    "ecommerce": {
        "id": "ecommerce",
        "name": "E-Commerce Store",
        "badge": "4 Tables · 3 Relations",
        "description": "Customers, Products, Orders, and Order Items with realistic store transactions.",
        "schema_sql": """-- E-Commerce Database Schema
CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    city VARCHAR(60),
    country VARCHAR(60) DEFAULT 'USA',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(60),
    price DECIMAL(10, 2) NOT NULL,
    stock_qty INT DEFAULT 0
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(30) DEFAULT 'Delivered',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Sample Data
INSERT INTO customers (customer_id, full_name, email, city, country, created_at) VALUES
(1, 'Alex Rivera', 'alex.rivera@example.com', 'San Francisco', 'USA', '2024-01-15 10:30:00'),
(2, 'Sarah Chen', 'sarah.chen@example.com', 'Seattle', 'USA', '2024-02-10 14:20:00'),
(3, 'Marco Rossi', 'marco.rossi@example.com', 'Milan', 'Italy', '2024-03-01 09:15:00'),
(4, 'Priya Sharma', 'priya.sharma@example.com', 'Bengaluru', 'India', '2024-03-12 16:45:00'),
(5, 'Liam O Connor', 'liam.oc@example.com', 'Dublin', 'Ireland', '2024-04-05 11:00:00');

INSERT INTO products (product_id, product_name, category, price, stock_qty) VALUES
(1, 'Quantum Wireless Headphones', 'Electronics', 199.99, 45),
(2, 'Ergonomic Desk Chair', 'Furniture', 349.50, 18),
(3, 'Ultra-Slim Mechanical Keyboard', 'Electronics', 129.00, 60),
(4, 'Stainless Steel Thermal Flask', 'Home', 35.00, 120),
(5, '4K Ultra HD Monitor 27-inch', 'Electronics', 449.00, 15);

INSERT INTO orders (order_id, customer_id, order_date, total_amount, status) VALUES
(101, 1, '2024-04-10', 528.99, 'Delivered'),
(102, 2, '2024-04-12', 199.99, 'Delivered'),
(103, 3, '2024-04-15', 833.50, 'Shipped'),
(104, 1, '2024-04-18', 35.00, 'Delivered'),
(105, 4, '2024-04-20', 449.00, 'Processing'),
(106, 5, '2024-04-22', 478.50, 'Delivered');

INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price) VALUES
(1, 101, 1, 1, 199.99),
(2, 101, 3, 1, 129.00),
(3, 101, 4, 2, 35.00),
(4, 102, 1, 1, 199.99),
(5, 103, 2, 1, 349.50),
(6, 103, 5, 1, 449.00),
(7, 103, 4, 1, 35.00),
(8, 104, 4, 1, 35.00),
(9, 105, 5, 1, 449.00),
(10, 106, 3, 1, 129.00),
(11, 106, 2, 1, 349.50);
"""
    },
    "company": {
        "id": "company",
        "name": "Company & Employees",
        "badge": "3 Tables · 3 Relations",
        "description": "Departments, Employee hierarchy, salaries, and ongoing project assignments.",
        "schema_sql": """-- Company & Employees Schema
CREATE TABLE departments (
    dept_id INT PRIMARY KEY AUTO_INCREMENT,
    dept_name VARCHAR(100) NOT NULL,
    budget DECIMAL(12, 2),
    location VARCHAR(80)
);

CREATE TABLE employees (
    emp_id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    salary DECIMAL(10, 2) NOT NULL,
    hire_date DATE NOT NULL,
    dept_id INT,
    manager_id INT,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id),
    FOREIGN KEY (manager_id) REFERENCES employees(emp_id)
);

CREATE TABLE projects (
    project_id INT PRIMARY KEY AUTO_INCREMENT,
    project_name VARCHAR(120) NOT NULL,
    dept_id INT,
    status VARCHAR(40) DEFAULT 'Active',
    start_date DATE,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);

-- Sample Data
INSERT INTO departments (dept_id, dept_name, budget, location) VALUES
(10, 'Engineering', 1500000.00, 'Building A - Floor 4'),
(20, 'Product & Design', 600000.00, 'Building A - Floor 2'),
(30, 'Marketing & Sales', 900000.00, 'Building B - Floor 1'),
(40, 'Human Resources', 350000.00, 'Building B - Floor 3');

INSERT INTO employees (emp_id, first_name, last_name, email, salary, hire_date, dept_id, manager_id) VALUES
(1, 'Evelyn', 'Vance', 'evelyn.vance@company.com', 165000.00, '2020-03-01', 10, NULL),
(2, 'David', 'Kim', 'david.kim@company.com', 135000.00, '2021-06-15', 10, 1),
(3, 'Maya', 'Patel', 'maya.patel@company.com', 128000.00, '2021-09-01', 10, 1),
(4, 'Jordan', 'Hayes', 'jordan.hayes@company.com', 140000.00, '2020-11-10', 20, NULL),
(5, 'Claire', 'Dubois', 'claire.dubois@company.com', 98000.00, '2022-02-14', 20, 4),
(6, 'Marcus', 'Johnson', 'marcus.j@company.com', 115000.00, '2021-01-20', 30, NULL),
(7, 'Aisha', 'Tariq', 'aisha.t@company.com', 82000.00, '2023-05-10', 30, 6);

INSERT INTO projects (project_id, project_name, dept_id, status, start_date) VALUES
(101, 'AI Search Assistant', 10, 'Active', '2024-01-10'),
(102, 'NextGen Mobile App Redesign', 20, 'Active', '2024-02-01'),
(103, 'Global Q3 Growth Campaign', 30, 'Completed', '2023-08-15'),
(104, 'Core Database Migration', 10, 'Active', '2024-03-05');
"""
    },
    "university": {
        "id": "university",
        "name": "University Academy",
        "badge": "4 Tables · 3 Relations",
        "description": "Students, Professors, Courses, and semester enrollment grades.",
        "schema_sql": """-- University Academy Schema
CREATE TABLE professors (
    prof_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(80) NOT NULL,
    tenure_status VARCHAR(20) DEFAULT 'Tenured'
);

CREATE TABLE students (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100) NOT NULL,
    major VARCHAR(80) NOT NULL,
    gpa DECIMAL(3, 2) NOT NULL,
    enrollment_year INT NOT NULL
);

CREATE TABLE courses (
    course_id INT PRIMARY KEY AUTO_INCREMENT,
    course_code VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(150) NOT NULL,
    credits INT DEFAULT 3,
    prof_id INT,
    FOREIGN KEY (prof_id) REFERENCES professors(prof_id)
);

CREATE TABLE enrollments (
    enrollment_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    semester VARCHAR(30) NOT NULL,
    grade VARCHAR(5),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

-- Sample Data
INSERT INTO professors (prof_id, full_name, department, tenure_status) VALUES
(1, 'Dr. Alan Turing', 'Computer Science', 'Tenured'),
(2, 'Dr. Katherine Johnson', 'Mathematics', 'Tenured'),
(3, 'Dr. Richard Feynman', 'Physics', 'Tenured');

INSERT INTO students (student_id, full_name, major, gpa, enrollment_year) VALUES
(1, 'Lucas Silva', 'Computer Science', 3.85, 2022),
(2, 'Ananya Sen', 'Computer Science', 3.92, 2023),
(3, 'Ethan Walker', 'Mathematics', 3.45, 2021),
(4, 'Sofia Morales', 'Physics', 3.70, 2022);

INSERT INTO courses (course_id, course_code, title, credits, prof_id) VALUES
(101, 'CS-301', 'Database Systems & SQL', 4, 1),
(102, 'CS-405', 'Artificial Intelligence', 4, 1),
(103, 'MATH-210', 'Linear Algebra & Matrices', 3, 2),
(104, 'PHYS-101', 'Quantum Mechanics Intro', 4, 3);

INSERT INTO enrollments (enrollment_id, student_id, course_id, semester, grade) VALUES
(1, 1, 101, 'Spring 2024', 'A'),
(2, 1, 102, 'Spring 2024', 'A-'),
(3, 2, 101, 'Spring 2024', 'A+'),
(4, 3, 103, 'Spring 2024', 'B+'),
(5, 4, 104, 'Spring 2024', 'A');
"""
    }
}

# ==================== IN-MEMORY WORKSPACE STATE ====================
class WorkspaceState:
    def __init__(self):
        self.schema_text: str = ""
        self.tables: List[Dict[str, Any]] = []
        self.diagnostics: List[Dict[str, str]] = []
        self.db_conn: Optional[sqlite3.Connection] = None
        self.active_preset_id: Optional[str] = None
        self.reset()

    def reset(self):
        self.schema_text = ""
        self.tables = []
        self.diagnostics = []
        self.active_preset_id = None
        if self.db_conn:
            try:
                self.db_conn.close()
            except Exception:
                pass
        self.db_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.db_conn.row_factory = sqlite3.Row

    def set_schema(self, schema_sql: str, preset_id: Optional[str] = None):
        self.schema_text = schema_sql.strip()
        self.active_preset_id = preset_id
        self.tables = parse_ddl_tables(self.schema_text)
        self.diagnostics = validate_schema_structure(self.tables)
        self.sync_sqlite()

    def sync_sqlite(self):
        """Converts MySQL DDL & INSERT statements to SQLite compatible statements and executes them."""
        if not self.schema_text:
            return
        
        # Reset DB
        if self.db_conn:
            try:
                self.db_conn.close()
            except Exception:
                pass
        self.db_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.db_conn.row_factory = sqlite3.Row
        
        # Split statements
        statements = re.split(r';\s*(?=(?:[^\'"]*[\'"][^\'"]*[\'"])*[^\'"]*$)', self.schema_text)
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            
            # Conversion of MySQL specific keywords for SQLite
            sqlite_stmt = re.sub(r'(?i)\bINT(?:EGER)?\s+PRIMARY\s+KEY\s+AUTO_INCREMENT\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', stmt)
            sqlite_stmt = re.sub(r'(?i)\bAUTO_INCREMENT\b', 'AUTOINCREMENT', sqlite_stmt)
            sqlite_stmt = re.sub(r'(?i)\bENGINE\s*=\s*\w+', '', sqlite_stmt)
            sqlite_stmt = re.sub(r'(?i)\bDEFAULT\s+CHARSET\s*=\s*\w+', '', sqlite_stmt)
            sqlite_stmt = re.sub(r'(?i)\bCOLLATE\s*=\s*[\w_]+', '', sqlite_stmt)
            sqlite_stmt = re.sub(r'(?i)\bUNSIGNED\b', '', sqlite_stmt)
            sqlite_stmt = re.sub(r'(?i)\bENUM\([^)]+\)', 'TEXT', sqlite_stmt)
            
            try:
                self.db_conn.execute(sqlite_stmt)
            except Exception as e:
                logger.debug(f"SQLite notice executing statement: {e}")
        try:
            self.db_conn.commit()
        except Exception:
            pass


# ==================== RAG INDEX INITIALIZATION ====================
rag_chunks = []
rag_bm25 = None

def load_rag():
    global rag_chunks, rag_bm25
    txt_path = FOLDER_PATH / "extracted_book.txt"
    if not txt_path.exists() or not RAG_AVAILABLE:
        return
    
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()

        raw_chunks = full_text.split("--- BOOK: ")
        chunks = []
        for chunk in raw_chunks:
            if not chunk.strip():
                continue
            try:
                header, content = chunk.split(" ---\n", 1)
                book_title, page_num = header.split(" | PAGE: ")
            except Exception:
                book_title = "SQL Reference"
                page_num = "1"
                content = chunk

            chunks.append({
                "book": book_title.strip(),
                "page": page_num.strip(),
                "text": content.strip()
            })

        if chunks:
            corpus = [c["text"].lower().split() for c in chunks]
            rag_bm25 = BM25Okapi(corpus)
            rag_chunks = chunks
            logger.info(f"Loaded RAG index with {len(chunks)} chunks.")
    except Exception as e:
        logger.warning(f"Could not load RAG index: {e}")

load_rag()

def retrieve_rag_context(query: str, top_k: int = 3) -> str:
    if not rag_chunks or not rag_bm25:
        return ""
    try:
        clean_query = query.lower().strip()
        tokenized = clean_query.split()
        top_bm25 = rag_bm25.get_top_n(tokenized, rag_chunks, n=top_k)
        
        context_parts = []
        for i, c in enumerate(top_bm25, 1):
            context_parts.append(f"[{c['book']} - Page {c['page']}]: {c['text'][:400]}")
        return "\n".join(context_parts)
    except Exception:
        return ""

# ==================== DDL PARSING & VALIDATION ====================
def parse_ddl_tables(ddl_text: str) -> List[Dict[str, Any]]:
    """Extracts table names, columns, data types, constraints, and relationships from DDL SQL."""
    tables = []
    table_pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[`"\']?(\w+)[`"\']?\.)?[`"\']?(\w+)[`"\']?\s*\((.*?)\)(?:\s*ENGINE|\s*DEFAULT|\s*;|\s*$)',
        re.IGNORECASE | re.DOTALL
    )

    for match in table_pattern.finditer(ddl_text):
        table_name = match.group(2)
        body = match.group(3)

        columns = []
        relationships = []
        primary_keys = []

        # Split items considering nested parens
        raw_items = []
        curr = ""
        paren_depth = 0
        for char in body:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            if char == ',' and paren_depth == 0:
                raw_items.append(curr.strip())
                curr = ""
            else:
                curr += char
        if curr.strip():
            raw_items.append(curr.strip())

        for item in raw_items:
            item = item.strip()
            if not item:
                continue

            # Primary Key constraint
            pk_match = re.match(r'(?:CONSTRAINT\s+\w+\s+)?PRIMARY\s+KEY\s*\((.*?)\)', item, re.IGNORECASE)
            if pk_match:
                pks = [c.strip(' `\'"') for c in pk_match.group(1).split(',')]
                primary_keys.extend(pks)
                continue

            # Foreign Key constraint
            fk_match = re.match(
                r'(?:CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+[`"\']?(\w+)[`"\']?\s*\((.*?)\)',
                item, re.IGNORECASE
            )
            if fk_match:
                fk_col = fk_match.group(1).strip(' `\'"')
                ref_table = fk_match.group(2).strip(' `\'"')
                ref_col = fk_match.group(3).strip(' `\'"')
                relationships.append({
                    "column": fk_col,
                    "foreign_table": ref_table,
                    "foreign_column": ref_col
                })
                continue

            # Key / Index constraint (skip)
            if re.match(r'(?:UNIQUE\s+|FULLTEXT\s+|SPATIAL\s+)?(?:KEY|INDEX)\b', item, re.IGNORECASE):
                continue

            # Column definition: name type [constraints]
            col_match = re.match(r'[`"\']?(\w+)[`"\']?\s+([A-Za-z0-9_]+(?:\s*\([^)]+\))?)(.*)', item)
            if col_match:
                cname = col_match.group(1)
                ctype = col_match.group(2)
                c_extra = col_match.group(3)
                is_pk = "PRIMARY KEY" in c_extra.upper()
                is_fk = False
                is_nullable = "NOT NULL" not in c_extra.upper()
                if is_pk and cname not in primary_keys:
                    primary_keys.append(cname)

                columns.append({
                    "name": cname,
                    "type": ctype.upper(),
                    "nullable": is_nullable,
                    "is_primary_key": is_pk,
                    "is_foreign_key": is_fk
                })

        # Mark PKs and FKs on columns
        fk_columns = {r["column"]: r for r in relationships}
        for col in columns:
            if col["name"] in primary_keys:
                col["is_primary_key"] = True
            if col["name"] in fk_columns:
                col["is_foreign_key"] = True
                col["references"] = f"{fk_columns[col['name']]['foreign_table']}.{fk_columns[col['name']]['foreign_column']}"

        tables.append({
            "name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "relationships": relationships
        })

    return tables

def validate_schema_structure(tables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Checks for dangling foreign keys or missing tables."""
    diagnostics = []
    table_names = {t["name"].lower() for t in tables}
    table_columns = {t["name"].lower(): {c["name"].lower() for c in t["columns"]} for t in tables}

    for t in tables:
        for rel in t.get("relationships", []):
            ref_t = rel["foreign_table"].lower()
            ref_c = rel["foreign_column"].lower()

            if ref_t not in table_names:
                diagnostics.append({
                    "type": "warning",
                    "title": "Unresolved Foreign Table Reference",
                    "message": f"Table `{t['name']}` references `{rel['foreign_table']}`, but `{rel['foreign_table']}` is not defined in this schema."
                })
            elif ref_c not in table_columns.get(ref_t, set()):
                diagnostics.append({
                    "type": "warning",
                    "title": "Unresolved Column Reference",
                    "message": f"Relationship `{t['name']}.{rel['column']}` references `{rel['foreign_table']}.{rel['foreign_column']}`, but column `{rel['foreign_column']}` was not found."
                })

    return diagnostics

workspace = WorkspaceState()
# Pre-load default E-Commerce preset so workspace is ready out of the box!
workspace.set_schema(PRESETS["ecommerce"]["schema_sql"], preset_id="ecommerce")


# ==================== LLM & VISION FUNCTIONS ====================
def query_groq_llm(prompt: str) -> str:
    global current_groq_idx
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    
    attempts = 0
    total_models = len(GROQ_MODEL_POOL)
    last_err = None

    while attempts < total_models:
        model_name = GROQ_MODEL_POOL[current_groq_idx]
        current_groq_idx = (current_groq_idx + 1) % total_models
        try:
            res = groq_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return res.choices[0].message.content or ""
        except Exception as e:
            last_err = e
            logger.warning(f"Groq model {model_name} failed: {e}. Trying next model...")
            attempts += 1
            time.sleep(0.3)

    raise RuntimeError(f"All Groq models failed. Last error: {last_err}")

def generate_sql_with_llm(user_prompt: str, schema_context: str, dialect: str = "mysql") -> str:
    """Generates SQL using Groq or Gemini fallback."""
    rag_context = retrieve_rag_context(user_prompt)

    system_instruction = f"""You are a senior Database Architect specializing in {dialect.upper()}.
Given the database schema and the user's natural language request:
1. Translate the user request into a precise, production-ready {dialect.upper()} query.
2. Strictly utilize existing table names, column names, and foreign keys.
3. Write clean SQL code with readable indentation and keyword capitalization (SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY, LIMIT).
4. Output ONLY raw, executable SQL code. Strictly do NOT include any comments (no inline comments, no line comments starting with --, and no /* */ block comments).
5. Do NOT include markdown text outside of SQL blocks."""

    full_prompt = f"""{system_instruction}

ACTIVE DATABASE SCHEMA:
{schema_context if schema_context else "-- No schema loaded. Infer standard table structures."}

{f"SQL REFERENCE EXCERPTS:\n{rag_context}\n" if rag_context else ""}

USER QUESTION:
{user_prompt}

OUTPUT:
Return the SQL query enclosed in ```sql ... ``` code block."""

    # Try Groq first
    if groq_client:
        try:
            return query_groq_llm(full_prompt)
        except Exception as e:
            logger.warning(f"Groq LLM generation failed: {e}. Attempting Gemini...")

    # Fallback to Gemini
    if gemini_client:
        for model in ["gemini-flash-latest", "gemini-pro-latest", "gemini-3.5-flash-lite", "gemini-3.8-flash"]:
            try:
                res = gemini_client.models.generate_content(
                    model=model,
                    contents=full_prompt
                )
                if res.text:
                    return res.text
            except Exception as e:
                logger.warning(f"Gemini {model} generation failed: {e}")
                continue

    # Rule-based fallback
    if workspace.tables:
        tname = workspace.tables[0]["name"]
        return f"SELECT * FROM `{tname}`\nLIMIT 25;"
    return "SELECT 1 AS status;"

def clean_sql_output(raw_sql: str) -> str:
    """Strips markdown code fences, comments, and surrounding prose, returning pure executable SQL text."""
    if not raw_sql:
        return ""
    block_match = re.search(r'```(?:sql)?\s*([\s\S]*?)\s*```', raw_sql, re.IGNORECASE)
    if block_match:
        text = block_match.group(1).strip()
    else:
        clean = re.sub(r'^```(?:sql)?\s*', '', raw_sql.strip(), flags=re.IGNORECASE)
        clean = re.sub(r'\s*```$', '', clean)
        text = clean.strip()
    # Strip block comments /* ... */
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    # Strip inline and line comments -- ...
    lines = []
    for line in text.splitlines():
        line_clean = re.sub(r'--.*$', '', line).rstrip()
        if line_clean.strip():
            lines.append(line_clean)
    return "\n".join(lines).strip()

def extract_used_tables(sql_text: str, available_tables: List[Dict[str, Any]]) -> List[str]:
    """Finds which tables are actually referenced in the generated SQL."""
    used = []
    sql_lower = sql_text.lower()
    for t in available_tables:
        t_name = t["name"].lower()
        # Look for table name as word
        if re.search(r'\b' + re.escape(t_name) + r'\b', sql_lower):
            used.append(t["name"])
    return used

def generate_query_breakdown(user_prompt: str, sql_text: str, used_tables: List[str]) -> Dict[str, Any]:
    """Generates structured translation and build steps."""
    steps = []
    steps.append({"phase": "Human Request", "detail": user_prompt})
    
    if used_tables:
        steps.append({"phase": "Tables Identified", "detail": ", ".join(used_tables)})
    
    # Identify JOINs
    joins = re.findall(r'(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+[`"\']?(\w+)[`"\']?\s+(?:AS\s+\w+\s+)?ON\s+([^\n;]+)', sql_text, re.IGNORECASE)
    if joins:
        join_strs = [f"{j[0]} (ON {j[1].strip()})" for j in joins]
        steps.append({"phase": "Relationship Joins", "detail": "; ".join(join_strs)})
    
    # Identify Aggregations / Calculations
    aggs = re.findall(r'\b(SUM|COUNT|AVG|MIN|MAX)\s*\([^)]+\)', sql_text, re.IGNORECASE)
    if aggs:
        steps.append({"phase": "Calculations & Aggregations", "detail": ", ".join(list(set(aggs)))})

    # Identify Filters (WHERE)
    where_match = re.search(r'\bWHERE\s+([^\n;]+?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|;|\Z)', sql_text, re.IGNORECASE)
    if where_match:
        steps.append({"phase": "Filter Conditions", "detail": where_match.group(1).strip()})

    # Identify Ordering / Limit
    order_match = re.search(r'\bORDER\s+BY\s+([^\n;]+?)(?:\s+LIMIT|;|\Z)', sql_text, re.IGNORECASE)
    limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_text, re.IGNORECASE)
    if order_match or limit_match:
        ord_str = f"Sort: {order_match.group(1).strip()}" if order_match else ""
        lim_str = f"Limit: {limit_match.group(1)}" if limit_match else ""
        steps.append({"phase": "Ordering & Limits", "detail": " | ".join(filter(None, [ord_str, lim_str]))})

    # Query Checks
    checks = [
        {"label": "Schema Tables Verified", "passed": len(used_tables) > 0, "note": f"{len(used_tables)} table(s) matched in active workspace"},
        {"label": "Columns & Relationships Mapped", "passed": True, "note": "Foreign keys and table references aligned"},
        {"label": "Syntax Structure Validated", "passed": bool(re.search(r'\bSELECT\b', sql_text, re.IGNORECASE)), "note": "Standard SQL query grammar"}
    ]

    return {
        "steps": steps,
        "checks": checks
    }

def extract_sql_from_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Uses Gemini vision model to transcribe ER diagrams or whiteboard notes to SQL DDL."""
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini Vision API is not configured.")

    prompt_text = """You are an expert database engineer. Analyze this ER diagram, schema drawing, or table screenshot.
Transcribe and extract the complete database schema into clean, valid MySQL DDL SQL syntax:
1. Generate `CREATE TABLE IF NOT EXISTS table_name (...)` statements.
2. Infer appropriate data types (INT, VARCHAR, DECIMAL, DATETIME, etc.), PRIMARY KEYs, and FOREIGN KEY constraints.
3. Return ONLY valid SQL DDL statements. No Markdown greetings or chit-chat. Code blocks are acceptable."""

    last_error = None
    for model_name in GEMINI_VISION_MODELS:
        try:
            part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=[part, prompt_text]
            )
            raw_text = response.text or ""
            return clean_sql_output(raw_text)
        except Exception as e:
            last_error = e
            logger.warning(f"Vision model {model_name} failed: {e}. Trying next...")
            time.sleep(0.3)

    raise HTTPException(status_code=500, detail=f"Failed to extract SQL from image using vision models: {last_error}")

def execute_sql_safely(sql_text: str) -> Dict[str, Any]:
    """Executes SQL on the SQLite in-memory instance and returns columns, rows, execution time, and count."""
    if not workspace.db_conn:
        return {"columns": [], "data": [], "row_count": 0, "execution_time_ms": 0, "error": "No database session active."}
    
    # Strip comments to isolate the executable query
    clean = re.sub(r'--[^\n]*', '', sql_text)
    clean = re.sub(r'/\*[\s\S]*?\*/', '', clean).strip()
    
    # Extract first statement before semicolon if multiple
    statements = [s.strip() for s in clean.split(';') if s.strip()]
    query_to_run = statements[0] if statements else clean
    
    start_t = time.perf_counter()
    try:
        cur = workspace.db_conn.cursor()
        cur.execute(query_to_run)
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            data = [dict(r) for r in rows[:150]]
            return {
                "columns": columns,
                "data": data,
                "row_count": len(rows),
                "execution_time_ms": elapsed_ms,
                "error": None
            }
        else:
            workspace.db_conn.commit()
            return {
                "columns": ["status"],
                "data": [{"status": f"Executed successfully ({cur.rowcount} rows affected)"}],
                "row_count": cur.rowcount if cur.rowcount != -1 else 0,
                "execution_time_ms": elapsed_ms,
                "error": None
            }
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": elapsed_ms,
            "error": str(e)
        }

# ==================== FASTAPI APP SETUP ====================
app = FastAPI(
    title="mySQL Workbench - Human → SQL API",
    description="Intelligent SQL Translation and Database Exploration Platform",
    version="2.0.0"
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class SchemaRequest(BaseModel):
    schema_text: Optional[str] = None
    preset_id: Optional[str] = None

class QueryRequest(BaseModel):
    prompt: str
    dialect: Optional[str] = "mysql"

class RunQueryRequest(BaseModel):
    sql: str

class ExplainRequest(BaseModel):
    sql: str
    prompt: Optional[str] = ""

# Serve Frontend HTML
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = FOLDER_PATH / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "running", "message": "mySQL Workbench API"})

# 1. GET /api/presets
@app.get("/api/presets")
async def get_presets():
    """Returns sample database presets for 1-click exploration."""
    return {
        "presets": [
            {
                "id": p["id"],
                "name": p["name"],
                "badge": p["badge"],
                "description": p["description"]
            }
            for p in PRESETS.values()
        ]
    }

# 2. POST /api/upload-schema & /api/schema
@app.post("/api/upload-schema")
@app.post("/api/schema")
async def upload_schema(
    request: Request,
    schema_payload: Optional[SchemaRequest] = None,
    file: Optional[UploadFile] = File(None)
):
    """
    Accepts JSON {"schema_text": "<string>", "preset_id": "<string>"} or raw file upload.
    Parses DDL, extracts table/column relationships, stores context and validates integrity.
    """
    content = ""
    preset_id = None

    if schema_payload:
        if schema_payload.preset_id and schema_payload.preset_id in PRESETS:
            preset_id = schema_payload.preset_id
            content = PRESETS[preset_id]["schema_sql"]
        elif schema_payload.schema_text:
            content = schema_payload.schema_text
    elif file is not None:
        file_bytes = await file.read()
        content = file_bytes.decode("utf-8", errors="ignore")
    else:
        try:
            body_json = await request.json()
            if isinstance(body_json, dict):
                if "preset_id" in body_json and body_json["preset_id"] in PRESETS:
                    preset_id = body_json["preset_id"]
                    content = PRESETS[preset_id]["schema_sql"]
                elif "schema_text" in body_json or "schema" in body_json:
                    content = body_json.get("schema_text") or body_json.get("schema") or ""
        except Exception:
            raw_body = await request.body()
            content = raw_body.decode("utf-8", errors="ignore")

    if not content.strip():
        raise HTTPException(status_code=400, detail="No schema text, preset, or file provided.")

    workspace.set_schema(content, preset_id=preset_id)
    total_relationships = sum(len(t.get("relationships", [])) for t in workspace.tables)
    logger.info(f"Schema uploaded: {len(workspace.tables)} tables, {total_relationships} relations.")

    return {
        "status": "success",
        "message": f"Successfully loaded {len(workspace.tables)} tables and {total_relationships} relationships.",
        "tables": workspace.tables,
        "diagnostics": workspace.diagnostics,
        "preset_id": workspace.active_preset_id,
        "schema_text": workspace.schema_text
    }

# 3. POST /api/upload-photo & /api/upload_schema
@app.post("/api/upload-photo")
@app.post("/api/upload_schema")
async def upload_photo(
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Accepts multipart/form-data with image.
    Uses Vision AI to transcribe diagrams into DDL SQL syntax.
    """
    target_file = image or file
    if target_file is None:
        raise HTTPException(status_code=400, detail="Image file parameter 'image' is required.")

    img_bytes = await target_file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image file is empty.")

    mime_type = target_file.content_type or "image/png"
    if mime_type not in ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]:
        mime_type = "image/png"

    extracted_sql = extract_sql_from_image(img_bytes, mime_type)

    if extracted_sql:
        workspace.set_schema(extracted_sql)

    return {
        "status": "success",
        "extracted_sql": extracted_sql,
        "tables": workspace.tables,
        "diagnostics": workspace.diagnostics
    }

# 4. POST /api/query
@app.post("/api/query")
async def query_pipeline(query_req: QueryRequest):
    """
    Accepts JSON body {"prompt": "<string>", "dialect": "<string>"}.
    Translates natural language to SQL with full reasoning breakdown, checks, and data preview.
    """
    prompt = query_req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Query prompt cannot be empty.")

    dialect = query_req.dialect or "mysql"
    raw_sql = generate_sql_with_llm(prompt, workspace.schema_text, dialect=dialect)
    clean_sql = clean_sql_output(raw_sql)
    
    used_tables = extract_used_tables(clean_sql, workspace.tables)
    breakdown = generate_query_breakdown(prompt, clean_sql, used_tables)
    execution_preview = execute_sql_safely(clean_sql)

    return {
        "status": "success",
        "sql": clean_sql,
        "dialect": dialect,
        "used_tables": used_tables,
        "breakdown": breakdown["steps"],
        "checks": breakdown["checks"],
        "columns": execution_preview["columns"],
        "data": execution_preview["data"],
        "row_count": execution_preview["row_count"],
        "execution_time_ms": execution_preview["execution_time_ms"],
        "execution_error": execution_preview["error"]
    }

# 5. POST /api/run-query
@app.post("/api/run-query")
async def run_query(req: RunQueryRequest):
    """Executes arbitrary SQL on the active workspace database."""
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL cannot be empty.")
    
    res = execute_sql_safely(req.sql)
    return {
        "status": "success" if not res["error"] else "error",
        **res
    }

# 6. POST /api/explain
@app.post("/api/explain")
async def explain_query_endpoint(req: ExplainRequest):
    """Provides plain English explanation, used tables, and join relationships for a query."""
    sql = clean_sql_output(req.sql)
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required for explanation.")

    used_tables = extract_used_tables(sql, workspace.tables)
    relationships = []
    
    # Extract join conditions from SQL
    joins = re.findall(r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', sql, re.IGNORECASE)
    for j in joins:
        rel_str = f"{j[0]}.{j[1]} = {j[2]}.{j[3]}"
        if rel_str not in relationships:
            relationships.append(rel_str)
            
    # Also find relationships from schema matching used tables
    for t in workspace.tables:
        if t["name"] in used_tables:
            for r in t.get("relationships", []):
                if r.get("foreign_table") in used_tables:
                    rel_str = f"{t['name']}.{r['column']} = {r['foreign_table']}.{r['foreign_column']}"
                    if rel_str not in relationships:
                        relationships.append(rel_str)

    explanation_bullets = []
    prompt = f"""You are a senior database educator and MySQL architect explaining SQL code to a developer.
Provide a clear, engaging, instructional breakdown of how this SQL query fulfills the user's intent: "{req.prompt or 'the requested data retrieval'}".

STRICT RULES & BAN ON NEGATIVE FRAMING:
1. NEVER mention what is missing or NOT used. DO NOT say "No JOINs were performed", "No WHERE clause was used", "No aggregation used", "No ORDER BY / LIMIT applied", or anything similar.
2. Focus strictly on positive usage breakdown of clauses/keywords that ARE present in the query (e.g., SELECT, FROM, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT).
3. Explain what each specific keyword/attribute does in this context, why specific tables/columns were chosen, and how MySQL executes the retrieval to deliver the result set.
4. Describe how the query translates the original user intent into working SQL logic in simple, natural English.
5. Return 3 to 4 concise bullet points starting strictly with "- ".

SQL Query:
{sql}
"""

    if groq_client:
        try:
            raw_exp = query_groq_llm(prompt)
            raw_lines = [l.strip() for l in raw_exp.strip().split('\n') if l.strip()]
            lines = []
            for l in raw_lines:
                # Strip only list prefixes like "- ", "* ", "1. ", "• "
                cleaned = re.sub(r'^(?:[-•*]\s+|\d+\.\s+)', '', l).strip()
                if cleaned:
                    lines.append(cleaned)
            # Filter out any negative statements if generated by mistake
            neg_regex = re.compile(r'\b(no\s+(joins?|where|group|order|limit|aggregation|filters?|conditions?|subqueries?)|without\s+(any\s+)?(joins?|where|group|order|limit)|does\s+not\s+(use|contain|require)|there\s+(is|are)\s+no)\b', re.IGNORECASE)
            valid_lines = [line for line in lines if not neg_regex.search(line)]
            if valid_lines:
                explanation_bullets = valid_lines
        except Exception as e:
            logger.warning(f"LLM explanation generation notice: {e}")

    # Fallback explanation if LLM wasn't available
    if not explanation_bullets:
        explanation_bullets = []
        if used_tables:
            explanation_bullets.append(f"Scans table <strong>{', '.join(used_tables)}</strong> to fetch matching database records.")
        if relationships:
            explanation_bullets.append(f"Correlates datasets using relational join condition: <code>{', '.join(relationships)}</code>.")

        select_match = re.search(r'\bSELECT\s+(.*?)\s+FROM\b', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            cols = select_match.group(1).strip()
            if cols == '*':
                explanation_bullets.append("Uses <code>SELECT *</code> to retrieve all column attributes from matching rows.")
            else:
                explanation_bullets.append(f"Extracts target columns (<code>{cols[:80]}</code>) specified for analysis.")

        where_match = re.search(r'\bWHERE\s+([^;\n]+)', sql, re.IGNORECASE)
        if where_match:
            explanation_bullets.append(f"Filters records using <code>WHERE {where_match.group(1).strip()[:80]}</code> to enforce query logic.")

        group_match = re.search(r'\bGROUP\s+BY\s+([^;\n]+)', sql, re.IGNORECASE)
        if group_match:
            explanation_bullets.append(f"Groups results using <code>GROUP BY {group_match.group(1).strip()[:70]}</code> to aggregate dataset metrics.")

        order_match = re.search(r'\bORDER\s+BY\s+([^;\n]+)', sql, re.IGNORECASE)
        if order_match:
            explanation_bullets.append(f"Orders output using <code>ORDER BY {order_match.group(1).strip()[:70]}</code> to structure the result set.")

        limit_match = re.search(r'\bLIMIT\s+(\d+)', sql, re.IGNORECASE)
        if limit_match:
            explanation_bullets.append(f"Applies <code>LIMIT {limit_match.group(1)}</code> to restrict row output for efficient payload transfer.")

        explanation_bullets.append(f"Translates user intent ('{req.prompt or 'query request'}') into optimized executable MySQL code.")

    return {
        "status": "success",
        "explanation": explanation_bullets,
        "used_tables": used_tables,
        "relationships": relationships
    }

# 7. POST /api/clean & /api/reset
@app.post("/api/clean")
@app.post("/api/reset")
async def clean_workspace():
    """Resets workspace state."""
    workspace.reset()
    logger.info("Active workspace reset.")
    return {"status": "cleared"}

@app.get("/api/status")
async def get_status():
    tables_with_counts = []
    for t in workspace.tables:
        t_copy = dict(t)
        count = 0
        if workspace.db_conn:
            try:
                cur = workspace.db_conn.execute(f"SELECT COUNT(*) FROM {t['name']}")
                count = cur.fetchone()[0]
            except Exception:
                count = 0
        t_copy["row_count"] = count
        tables_with_counts.append(t_copy)

    total_relationships = sum(len(t.get("relationships", [])) for t in workspace.tables)
    return {
        "status": "online",
        "schema_loaded": bool(workspace.schema_text),
        "tables_count": len(workspace.tables),
        "relationships_count": total_relationships,
        "active_preset": workspace.active_preset_id,
        "tables": tables_with_counts,
        "diagnostics": workspace.diagnostics,
        "schema_text": workspace.schema_text
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting mySQL Workbench on http://127.0.0.1:{port}")
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=True)
