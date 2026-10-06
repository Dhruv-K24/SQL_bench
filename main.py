import os
import sys
import time
from dotenv import load_dotenv
from pypdf import PdfReader
from rank_bm25 import BM25Okapi
from rapidfuzz import process, fuzz
from openai import OpenAI

load_dotenv()

FOLDER_PATH = r"C:\Users\Dhruv\Documents\Coding\Python\Cheap_llm"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY missing from .env file.")
    sys.exit(1)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

MODEL_POOL = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b"
]

current_model_idx = 0
GREEN = "\033[92m"
RESET = "\033[0m"

def get_pdf_files(folder):
    return [
        os.path.join(folder, f) 
        for f in os.listdir(folder) 
        if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith('.pdf')
    ]

def ensure_multi_pdf_extracted(pdf_paths, output_txt_path):
    if os.path.exists(output_txt_path):
        print(f"Loaded existing extracted text database: {output_txt_path}")
        return
        
    print("Extracting and merging text from all PDF books...")
    with open(output_txt_path, "w", encoding="utf-8") as out:
        for pdf_path in pdf_paths:
            book_title = os.path.basename(pdf_path)
            print(f" Processing book: {book_title}...")
            reader = PdfReader(pdf_path)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                out.write(f"\n--- BOOK: {book_title} | PAGE: {page_num} ---\n{text}")
    print(f"Extraction complete -> {output_txt_path}")

def build_local_rag_index(txt_path):
    print("Indexing all book pages locally...")
    with open(txt_path, "r", encoding="utf-8") as f:
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
            book_title = "Reference Book"
            page_num = "Unknown"
            content = chunk

        chunks.append({
            "book": book_title.strip(),
            "page": page_num.strip(),
            "text": content.strip()
        })

    corpus = [c["text"].lower().split() for c in chunks]
    bm25 = BM25Okapi(corpus)
    print(f"Successfully indexed {len(chunks)} pages across all books.")
    return chunks, bm25

def retrieve_top_chunks(query, chunks, bm25, top_k=6):
    clean_query = query.lower().strip()
    tokenized_query = clean_query.split()
    
    # 1. BM25 Search
    top_bm25_chunks = bm25.get_top_n(tokenized_query, chunks, n=top_k)
    
    # 2. Fuzzy Search
    chunk_texts = [c["text"].lower() for c in chunks]
    fuzzy_results = process.extract(clean_query, chunk_texts, scorer=fuzz.partial_ratio, limit=3)
    fuzzy_chunks = [chunks[i[2]] for i in fuzzy_results]

    combined_chunks = []
    seen_entries = set()

    for c in top_bm25_chunks + fuzzy_chunks:
        entry_id = f"{c['book']}_P{c['page']}"
        if entry_id not in seen_entries:
            seen_entries.add(entry_id)
            combined_chunks.append(c)
        if len(combined_chunks) >= top_k:
            break

    context = ""
    for idx, chunk in enumerate(combined_chunks, start=1):
        context += f"\n--- EXCERPT {idx} [{chunk['book']} - Page {chunk['page']}] ---\n{chunk['text']}\n"
    return context

def query_groq_round_robin(prompt):
    global current_model_idx
    attempts = 0
    total_models = len(MODEL_POOL)

    while attempts < total_models:
        model_name = MODEL_POOL[current_model_idx]
        current_model_idx = (current_model_idx + 1) % total_models

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return response.choices[0].message.content, model_name

        except Exception as e:
            attempts += 1
            next_model = MODEL_POOL[current_model_idx]
            print(f"{GREEN}[System] {model_name} unavailable or rate-limited. Switching to {next_model}...{RESET}")
            time.sleep(0.5)

    raise RuntimeError("All models in the pool failed.")

def main():
    print("=== Multi-Book SQL Code Generator ===")
    
    if not os.path.exists(FOLDER_PATH):
        print(f"Error: Folder path '{FOLDER_PATH}' does not exist.")
        return

    pdf_paths = get_pdf_files(FOLDER_PATH)
    if not pdf_paths:
        print(f"No PDF files found in '{FOLDER_PATH}'.")
        return

    txt_path = os.path.join(FOLDER_PATH, "extracted_book.txt")
    ensure_multi_pdf_extracted(pdf_paths, txt_path)
    chunks, bm25 = build_local_rag_index(txt_path)

    print("\n" + "=" * 60)
    print("System ONLINE! Code-only mode.")
    print("=" * 60)

    while True:
        try:
            user_query = input("\nYou: ").strip()
            if not user_query or user_query.lower() in ["exit", "quit"]:
                break

            start_time = time.time()
            relevant_context = retrieve_top_chunks(user_query, chunks, bm25, top_k=6)

            system_instruction = """You are a senior SQL database architect.

CRITICAL OUTPUT FORMAT INSTRUCTIONS:
1. Output ONLY two SQL query code blocks. 
2. Absolutely NO explanatory text, NO markdown headers, NO bullet points, NO intro/outro text, and NO prose.
3. Query 1 must be Standard ANSI SQL.
4. Query 2 must be MySQL-optimized or an alternative dialect approach.
5. Use SQL comments (-- comment) inside the code blocks if necessary.
"""

            prompt = f"""{system_instruction}

REFERENCE BOOK EXCERPTS:
{relevant_context}

USER REQUEST:
{user_query}"""

            answer, used_model = query_groq_round_robin(prompt)
            elapsed = time.time() - start_time
            
            print(f"\nAI [{used_model}] ({elapsed:.2f}s):\n{answer}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()