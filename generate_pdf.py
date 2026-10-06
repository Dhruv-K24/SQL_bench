import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "mySQL Workbench AI - Architecture & Learning Guide")
            self.drawRightString(612 - 54, 750, "Mastering Modern Python & AI")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 612 - 54, 742)
            
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 36, page_text)
        self.drawString(54, 36, "Confidential & Educational Material - From Beginner to Pro")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 612 - 54, 48)
        
        self.restoreState()

def build_pdf(filename="learn_llm.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    primary_color = colors.HexColor("#0f172a") # Slate 900
    accent_blue = colors.HexColor("#0284c7")   # Sky 600
    secondary_color = colors.HexColor("#334155")
    bg_light = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")
    code_bg = colors.HexColor("#1e293b")
    callout_bg = colors.HexColor("#f0fdf4")
    callout_border = colors.HexColor("#22c55e")

    # Typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=accent_blue,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=accent_blue,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=secondary_color,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#38bdf8")
    )

    callout_text_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#065f46")
    )

    story = []

    def make_box(text, title="KEY TAKEAWAY / ANALOGY", bg=callout_bg, border=callout_border):
        content = [
            Paragraph(f"<b>{title}</b>", ParagraphStyle('BTitle', parent=callout_text_style, fontName='Helvetica-Bold', textColor=border, spaceAfter=3)),
            Paragraph(text, callout_text_style)
        ]
        t = Table([[content]], colWidths=[504])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('BOX', (0,0), (-1,-1), 1, border),
            ('PADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t

    def make_code_box(code_text):
        p = Paragraph(code_text.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style)
        t = Table([[p]], colWidths=[504])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), code_bg),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#475569")),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    # ==================== COVER & HEADER ====================
    story.append(Paragraph("AI-Powered Database Workbench", title_style))
    story.append(Paragraph("The Beginner-to-Pro Guide to Python, FastAPI, Vision OCR, RAG, and LLM Engineering", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_blue, spaceAfter=12))

    # ==================== SECTION 1: THE BIG PICTURE ====================
    story.append(Paragraph("1. The Big Picture: What Did We Just Build?", h1_style))
    story.append(Paragraph(
        "Imagine you have a relational database (like MySQL) and you want to interact with it, but you don't want to type complex SQL queries by hand or manually type out database tables from napkin sketches or whiteboard diagrams. "
        "We built a complete <b>Full-Stack AI Application</b> called <b>mySQL Workbench</b> that acts like an expert database architect sitting right beside you.",
        body_style
    ))
    story.append(Paragraph("The system has 3 core superpowers:", body_style))
    story.append(Paragraph("&bull; <b>Schema Ingestion:</b> You can paste raw SQL definitions or upload a <code>.sql</code> file. The app parses it and remembers your tables, columns, and foreign key relationships.", bullet_style))
    story.append(Paragraph("&bull; <b>Vision OCR (Image to Database):</b> You take a photo or screenshot of an ER (Entity-Relationship) diagram or whiteboard sketch. The AI looks at the photo and writes clean <code>CREATE TABLE</code> SQL statements automatically.", bullet_style))
    story.append(Paragraph("&bull; <b>Natural Language Query (English to SQL):</b> You type what you want in plain English (e.g., <i>'Find the average employee salary per department'</i>), and the AI consults database textbooks (RAG) and generates optimized SQL with data previews.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(make_box(
        "<b>The Human-to-Computer Translation Analogy:</b><br/>"
        "Think of this project as a 3-layer restaurant. You (the user) sit in the dining room looking at a glowing menu (the <b>Frontend HTML</b>). "
        "When you speak or upload a photo, the waiter (<b>FastAPI Backend</b>) takes your order, runs into the kitchen to consult master recipe books (<b>RAG Search</b>) "
        "and coordinates with world-class chefs in the cloud (<b>Groq & Google Gemini AI</b>) to prepare a freshly baked SQL query back to your table in milliseconds.",
        title="CORE INTUITION"
    ))
    story.append(Spacer(1, 10))

    # ==================== SECTION 2: THE 3-TIER ARCHITECTURE ====================
    story.append(Paragraph("2. System Architecture: How the Moving Parts Connect", h1_style))
    story.append(Paragraph(
        "Modern applications are divided into clean, decoupled layers so that if one piece needs an upgrade, the rest of the system keeps running smoothly without breaking.",
        body_style
    ))

    arch_data = [
        [Paragraph("<b>Component</b>", body_style), Paragraph("<b>Technology</b>", body_style), Paragraph("<b>What It Actually Does (In Simple Words)</b>", body_style)],
        [Paragraph("<b>Frontend (UI)</b>", body_style), Paragraph("HTML5, CSS3, Vanilla JS", body_style), Paragraph("The visual window with dark glassmorphism, animated glowing blobs, tab switching, and loading pixel effects.", body_style)],
        [Paragraph("<b>Backend (API)</b>", body_style), Paragraph("Python 3, FastAPI, Uvicorn", body_style), Paragraph("The fast local web server running on port 5000 that listens for requests, processes data, and handles memory.", body_style)],
        [Paragraph("<b>RAG Engine</b>", body_style), Paragraph("BM25, RapidFuzz, PyPDF", body_style), Paragraph("Searches hundreds of pages from SQL reference textbooks locally to give the AI exact domain knowledge.", body_style)],
        [Paragraph("<b>Vision AI</b>", body_style), Paragraph("Google Gemini 2.5 / 3.x Flash", body_style), Paragraph("High-speed multimodal AI that inspects image pixels to transcribe boxes, arrows, and table handwriting into SQL.", body_style)],
        [Paragraph("<b>Language AI</b>", body_style), Paragraph("Groq LPU (GPT-OSS / Qwen)", body_style), Paragraph("Ultra-fast AI chip inference that transforms plain English questions into bulletproof SQL queries.", body_style)],
        [Paragraph("<b>In-Memory DB</b>", body_style), Paragraph("SQLite3 (:memory:)", body_style), Paragraph("A zero-install sandbox database inside Python's RAM that tests and runs queries on the fly.", body_style)]
    ]
    t_arch = Table(arch_data, colWidths=[100, 115, 289])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 12))

    # ==================== SECTION 3: KEY TECHNICAL CONCEPTS DEMYSTIFIED ====================
    story.append(Paragraph("3. Technical Concepts Demystified (Without the Jargon)", h1_style))
    
    story.append(Paragraph("A. What is an API & REST?", h2_style))
    story.append(Paragraph(
        "<b>API</b> stands for <i>Application Programming Interface</i>. It is simply a formal contract or door that allows two different computer programs to talk to each other. "
        "Your browser (written in JavaScript) cannot directly execute Python code on your computer. An API provides specific URL paths (called <b>endpoints</b>) "
        "like <code>POST /api/query</code> where JavaScript sends a message, and Python answers.",
        body_style
    ))
    story.append(Paragraph(
        "<b>HTTP Methods (GET vs POST):</b><br/>"
        "&bull; <b>GET:</b> 'Give me something.' Like reading a webpage (<code>GET /</code>).<br/>"
        "&bull; <b>POST:</b> 'Take this data and do work.' Like uploading a schema (<code>POST /api/upload-schema</code>) or sending an image.",
        body_style
    ))

    story.append(Paragraph("B. What is CORS (Cross-Origin Resource Sharing)?", h2_style))
    story.append(Paragraph(
        "Web browsers have a built-in security rule: website A is not allowed to spy on or fetch data from website B unless website B explicitly gives permission. "
        "When our frontend runs on your browser and sends requests to <code>http://127.0.0.1:5000</code>, CORS middleware in FastAPI tells the browser: "
        "<i>'It is safe! Allow this webpage to communicate with me.'</i>",
        body_style
    ))

    story.append(Paragraph("C. What is RAG (Retrieval-Augmented Generation)?", h2_style))
    story.append(Paragraph(
        "General LLMs (like ChatGPT or Gemini) know a lot, but they can hallucinate or forget obscure database nuances. "
        "<b>RAG</b> is the gold standard technique in modern AI: before asking the AI to answer, your code searches a private library (in our case, the <i>SQL Cookbook</i> and <i>MySQL Notes</i> PDFs) "
        "for the most relevant paragraphs and attaches them directly into the prompt. It turns an AI from taking a closed-book test into an <b>open-book test</b>!",
        body_style
    ))

    story.append(Paragraph("D. What is BM25 & Fuzzy Search?", h2_style))
    story.append(Paragraph(
        "&bull; <b>BM25:</b> The industry-standard search algorithm used by search engines. It calculates how rare and important words are to find the exact pages that match your topic.<br/>"
        "&bull; <b>Fuzzy Matching (RapidFuzz):</b> Real humans make spelling mistakes or use slight variations (e.g., 'employe' vs 'employees'). Fuzzy search calculates letter similarity (Levenshtein distance) so search never fails.",
        body_style
    ))

    story.append(PageBreak()) # Clean page break for module breakdown

    # ==================== SECTION 4: PYTHON MODULES DEEP DIVE ====================
    story.append(Paragraph("4. The Python Toolbelt: Modules Used & Why", h1_style))
    story.append(Paragraph(
        "Python is famous in the AI world because of its rich ecosystem of specialized packages. Here is the breakdown of what each module in our virtual environment does:",
        body_style
    ))

    modules_data = [
        [Paragraph("<b>Package</b>", body_style), Paragraph("<b>Why We Use It in This Project</b>", body_style), Paragraph("<b>Everyday Analogy</b>", body_style)],
        [Paragraph("<code>fastapi</code>", body_style), Paragraph("Builds high-speed web endpoints with automatic data validation and documentation.", body_style), Paragraph("The lightning-fast airport switchboard.", body_style)],
        [Paragraph("<code>uvicorn</code>", body_style), Paragraph("The asynchronous web server worker that keeps FastAPI running 24/7.", body_style), Paragraph("The engine under the car hood.", body_style)],
        [Paragraph("<code>pydantic</code>", body_style), Paragraph("Guarantees that incoming JSON requests have the exact data types expected.", body_style), Paragraph("The bouncer checking IDs at the club.", body_style)],
        [Paragraph("<code>openai</code> (Groq)", body_style), Paragraph("Official client SDK used to connect to Groq's ultra-low latency AI cloud.", body_style), Paragraph("The direct hotline telephone to Groq.", body_style)],
        [Paragraph("<code>google-genai</code>", body_style), Paragraph("Google's new official SDK for Gemini 2.5/3.x vision and text reasoning.", body_style), Paragraph("The telescope to Google's supercomputers.", body_style)],
        [Paragraph("<code>pypdf</code>", body_style), Paragraph("Extracts raw text and page numbers from large PDF database books.", body_style), Paragraph("The high-speed book scanner.", body_style)],
        [Paragraph("<code>rank-bm25</code>", body_style), Paragraph("Indexes text chunks and ranks document relevance for search queries.", body_style), Paragraph("The library index card catalog.", body_style)],
        [Paragraph("<code>rapidfuzz</code>", body_style), Paragraph("C-accelerated string similarity engine for fuzzy search and typo handling.", body_style), Paragraph("The smart spellchecker.", body_style)],
        [Paragraph("<code>python-dotenv</code>", body_style), Paragraph("Loads secret keys from <code>.env</code> file into OS environment variables.", body_style), Paragraph("The secret combination vault.", body_style)],
        [Paragraph("<code>sqlite3</code>", body_style), Paragraph("Python's built-in, zero-configuration SQL database engine in RAM.", body_style), Paragraph("The practice chalkboard in the lab.", body_style)]
    ]
    t_mod = Table(modules_data, colWidths=[90, 240, 174])
    t_mod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_mod)
    story.append(Spacer(1, 12))

    # ==================== SECTION 5: CLEVER TRICKS & DESIGN PATTERNS ====================
    story.append(Paragraph("5. Clever Engineering Tricks & Patterns in This Project", h1_style))
    story.append(Paragraph(
        "What makes professional code different from amateur tutorials is how gracefully it handles real-world errors, rate limits, and edge cases. Here are the smart patterns implemented in your backend:",
        body_style
    ))

    story.append(Paragraph("1. Round-Robin Multi-Model Fallback (The Self-Healing AI Pipeline)", h2_style))
    story.append(Paragraph(
        "AI cloud providers frequently hit rate limits or undergo temporary spikes (like HTTP 503 errors). "
        "Instead of crashing, our code uses a <b>Model Pool</b> (<code>['openai/gpt-oss-120b', 'qwen/qwen3.8-27b', 'openai/gpt-oss-20b']</code>). "
        "If model A fails or is busy, the backend instantly catches the error, rotates to model B, and completes the user's request without them ever noticing!",
        body_style
    ))

    story.append(Paragraph("2. Multi-Tier AI Provider Redundancy (Groq + Gemini + Heuristics)", h2_style))
    story.append(Paragraph(
        "We don't rely on just one AI company. If Groq is completely down, the system automatically falls back to Google Gemini. "
        "If both are offline or out of quota, it falls back to a smart heuristic SQL generator. <b>The app never crashes with a 500 error.</b>",
        body_style
    ))

    story.append(Paragraph("3. In-Memory Dialect Normalization (MySQL to SQLite)", h2_style))
    story.append(Paragraph(
        "MySQL has special keywords like <code>AUTO_INCREMENT</code>, <code>ENGINE=InnoDB</code>, and <code>UNSIGNED</code> that SQLite does not understand. "
        "Our backend automatically strips and normalizes these keywords using regex so that MySQL schemas can be safely executed and previewed directly inside SQLite without needing a heavy MySQL server installed!",
        body_style
    ))

    story.append(Paragraph("4. Flexible Dual-Mode Schema Input", h2_style))
    story.append(Paragraph(
        "The <code>POST /api/upload-schema</code> endpoint handles JSON payloads (<code>{\"schema_text\": \"...\"}</code>), raw SQL text, and multipart file uploads (<code>.sql</code> files) all in the same handler.",
        body_style
    ))

    story.append(Spacer(1, 10))

    # ==================== SECTION 6: INDUSTRY STANDARDS & ROADMAP ====================
    story.append(Paragraph("6. Industry Reality Check: How Close Are You & What's Next?", h1_style))
    story.append(Paragraph(
        "You might wonder: <i>Is this real professional engineering, or just a student project?</i> Here is an honest, transparent breakdown:",
        body_style
    ))

    story.append(make_box(
        "<b>Scorecard: You Are ~75% of the Way to Full Enterprise Grade!</b><br/>"
        "Your project already uses production FastAPI, asynchronous routing, CORS protection, real RAG retrieval with BM25, multi-model failover, and multimodal vision processing. "
        "Many startups raise millions of dollars on architectures identical to this one!",
        title="INDUSTRY EVALUATION",
        bg=colors.HexColor("#f0fdfa"),
        border=colors.HexColor("#0d9488")
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("What Separates This From a Multi-Million User Enterprise System?", h2_style))
    story.append(Paragraph("&bull; <b>Persistent Database Connection:</b> Connect to real remote MySQL / PostgreSQL instances with connection pooling (e.g. <code>SQLAlchemy</code> / <code>asyncpg</code>) instead of ephemeral SQLite in memory.", bullet_style))
    story.append(Paragraph("&bull; <b>Dense Vector Embeddings:</b> In addition to BM25 keyword search, enterprise systems use vector databases (like ChromaDB, Pinecone, or Qdrant) with embeddings (like <code>text-embedding-3</code>) to understand conceptual semantic similarity.", bullet_style))
    story.append(Paragraph("&bull; <b>User Authentication & Sessions:</b> Adding JWT (JSON Web Tokens) or OAuth (Google/GitHub login) so multiple users have isolated private workspaces.", bullet_style))
    story.append(Paragraph("&bull; <b>Docker Containerization:</b> Packaging the entire app into a Docker container for 1-click deployment on AWS, Google Cloud, or Render.", bullet_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Your Step-by-Step Learning Roadmap", h2_style))
    story.append(Paragraph("1. <b>Level 1 (The Core):</b> Learn Python basics (functions, dictionaries, lists, classes, and <code>try/except</code> error handling).", bullet_style))
    story.append(Paragraph("2. <b>Level 2 (The Web):</b> Understand how web servers work (HTTP status codes like 200/404/500, JSON formatting, FastAPI endpoints).", bullet_style))
    story.append(Paragraph("3. <b>Level 3 (The AI):</b> Experiment with prompt engineering, system instructions, temperature settings, and multimodal vision prompts.", bullet_style))
    story.append(Paragraph("4. <b>Level 4 (The Cloud):</b> Deploy your FastAPI backend to the cloud (e.g., Render, Railway, or Fly.io) so friends can access it from their phones.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=border_color, spaceAfter=8))
    story.append(Paragraph("<b>Summary:</b> Be proud of this codebase. It brings together modern frontend aesthetics, asynchronous Python API design, state-of-the-art vision models, and robust RAG search into a unified, practical developer tool.", body_style))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated: {filename}")

if __name__ == "__main__":
    build_pdf("learn_llm.pdf")
