import os
import re
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb
from dotenv import load_dotenv

load_dotenv()

import torch
from llama_index.llms.huggingface import HuggingFaceLLM

# ── LLM & Embedding ───────────────────────────────────────────────────────────
model_id = "Qwen/Qwen2.5-1.5B-Instruct"

llm = HuggingFaceLLM(
    model_name=model_id,
    tokenizer_name=model_id,
    context_window=4096,
    max_new_tokens=512,
    generate_kwargs={"temperature": 0.01, "do_sample": False},
    device_map="auto",
    model_kwargs={"torch_dtype": torch.float16}
)

embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

Settings.llm = llm
Settings.embed_model = embed_model

# ── Persistent Document Store ──────────────────────────────────────────────────
_global_extracted_text = ""
_global_index = None

def process_text(text: str):
    global _global_extracted_text, _global_index
    if not text.strip():
        return {"status": "error", "message": "No text provided."}
    
    try:
        _global_extracted_text = text
        doc = Document(text=text)
        
        # Build in-memory index for fast Q&A
        _global_index = VectorStoreIndex.from_documents(
            [doc],
            show_progress=False,
        )
        
        return {
            "status": "success",
            "message": "Document processed and indexed.",
            "text": text,
        }
    except Exception as e:
        return {"status": "error", "message": f"Processing failed: {str(e)}"}

def chat_with_document(query: str):
    global _global_index
    if not query.strip():
        return {"status": "error", "message": "Empty query."}
    if not _global_index:
        return {"status": "error", "message": "No document loaded. Please upload a document first!"}
    
    try:
        # For small local LLMs, a simple prompt wrapper helps
        from llama_index.core import PromptTemplate
        qa_prompt_tmpl = PromptTemplate(
            "Context information is below.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Given the context information and not prior knowledge, "
            "answer the query.\n"
            "Query: {query_str}\n"
            "Answer: "
        )
        query_engine = _global_index.as_query_engine(text_qa_template=qa_prompt_tmpl)
        response = query_engine.query(query)
        res_str = str(response).strip()
        if not res_str or res_str.lower() == "empty response":
            res_str = "I couldn't find an answer to that in the document."
        return {"status": "success", "query": query, "response": res_str}
    except Exception as e:
        return {"status": "error", "message": f"Chat failed: {str(e)}"}

def compare_document(target_text: str, strategy: str):
    global _global_extracted_text
    if not _global_extracted_text:
        return {"status": "error", "message": "No source document found. Please upload a document first."}
    if not target_text.strip():
        return {"status": "error", "message": "No comparison text provided."}

    try:
        score = 0
        matching_keywords = []
        missing_keywords = []

        if strategy == "word":
            source_words = set(w.lower() for w in re.split(r'\W+', _global_extracted_text) if len(w) > 4)
            target_words = set(w.lower() for w in re.split(r'\W+', target_text) if len(w) > 4)
            
            if not target_words:
                return {"status": "success", "similarity_score": 0, "matching_keywords": [], "missing_keywords": [], "message": "No valid words to compare."}
                
            matching_keywords = list(source_words & target_words)
            missing_keywords = list(target_words - source_words)
            score = round((len(matching_keywords) / len(target_words)) * 100, 2)

        elif strategy == "paragraph":
            target_paras = [p.strip() for p in target_text.split('\n\n') if p.strip()]
            source_words = set(w.lower() for w in re.split(r'\W+', _global_extracted_text) if len(w) > 3)
            
            matched_paras = 0
            for p in target_paras:
                p_words = set(w.lower() for w in re.split(r'\W+', p) if len(w) > 3)
                overlap = p_words & source_words
                if len(overlap) / max(1, len(p_words)) > 0.4:
                    matched_paras += 1
                    matching_keywords.extend(list(overlap))
                else:
                    missing_keywords.extend(list(p_words - source_words))
                    
            if not target_paras:
                return {"status": "success", "similarity_score": 0, "matching_keywords": [], "missing_keywords": []}
                
            matching_keywords = list(set(matching_keywords))
            missing_keywords = list(set(missing_keywords))
            score = round((matched_paras / len(target_paras)) * 100, 2)

        elif strategy == "context":
            source_embedding = embed_model.get_text_embedding(_global_extracted_text[:4000])
            target_embedding = embed_model.get_text_embedding(target_text[:4000])
            
            import numpy as np
            v1 = np.array(source_embedding)
            v2 = np.array(target_embedding)
            cosine_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            
            score = round(float(cosine_sim) * 100, 2)
            source_words = set(w.lower() for w in re.split(r'\W+', _global_extracted_text) if len(w) > 4)
            target_words = set(w.lower() for w in re.split(r'\W+', target_text) if len(w) > 4)
            matching_keywords = list(source_words & target_words)[:20]
            missing_keywords = list(target_words - source_words)[:20]

        return {
            "status": "success",
            "similarity_score": score,
            "matching_keywords": matching_keywords[:30],
            "missing_keywords": missing_keywords[:30],
            "strategy": strategy
        }
    except Exception as e:
        return {"status": "error", "message": f"Comparison failed: {str(e)}"}
