import nest_asyncio

nest_asyncio.apply()

import os
import pickle
from llama_index.core import Document, PropertyGraphIndex
from llama_index.core.graph_stores import SimplePropertyGraphStore
from llama_index.core.graph_stores.types import EntityNode, Relation
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb
from dotenv import load_dotenv

load_dotenv()

import torch
from llama_index.llms.huggingface import HuggingFaceLLM

# ── LLM & Embedding ───────────────────────────────────────────────────────────
# The local model download in gemma_3.7b was incomplete/corrupted.
# Using Qwen2.5-1.5B-Instruct (an ungated, highly capable small model) so it works out of the box.
model_id = "Qwen/Qwen2.5-1.5B-Instruct"

llm = HuggingFaceLLM(
    model_name=model_id,
    tokenizer_name=model_id,
    context_window=4096,
    max_new_tokens=512,
    generate_kwargs={"temperature": 0.1, "do_sample": False},
    device_map="auto",
    model_kwargs={"torch_dtype": torch.float16}
)

embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

Settings.llm = llm
Settings.embed_model = embed_model

# ── Persistent Graph Store ────────────────────────────────────────────────────
_graph_store = SimplePropertyGraphStore()
GRAPH_STORE_PATH = "./graph_store.pkl"


def _save_graph_store():
    with open(GRAPH_STORE_PATH, "wb") as f:
        pickle.dump(_graph_store, f)


def _load_graph_store() -> SimplePropertyGraphStore:
    global _graph_store
    if os.path.exists(GRAPH_STORE_PATH):
        try:
            with open(GRAPH_STORE_PATH, "rb") as f:
                _graph_store = pickle.load(f)
        except Exception as e:
            print(f"[graph_service] Could not load graph store, starting fresh: {e}")
            _graph_store = SimplePropertyGraphStore()
    return _graph_store


def _get_vector_store() -> ChromaVectorStore:
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = chroma_client.get_or_create_collection("ocr_graph_nodes")
    return ChromaVectorStore(chroma_collection=chroma_collection)


_load_graph_store()


def _triplets_to_nodes_edges(triplets):
    nodes = []
    edges = []
    seen = set()
    for subj, rel, obj in triplets:
        subj_id = str(subj.id) if getattr(subj, 'id', None) else str(subj.label)
        obj_id = str(obj.id) if getattr(obj, 'id', None) else str(obj.label)
        subj_label = str(getattr(subj, 'name', subj.label))
        obj_label = str(getattr(obj, 'name', obj.label))
        rel_label = str(getattr(rel, 'name', rel.label))

        if subj_id not in seen:
            nodes.append({"id": subj_id, "label": subj_label})
            seen.add(subj_id)
        if obj_id not in seen:
            nodes.append({"id": obj_id, "label": obj_label})
            seen.add(obj_id)

        edges.append({
            "source": subj_id,
            "target": obj_id,
            "label": rel_label
        })
    return nodes, edges


def process_text_to_graph(text: str):
    if not text.strip():
        return {"status": "error", "message": "No text provided."}
    try:
        doc = Document(text=text)
        vector_store = _get_vector_store()
        index = PropertyGraphIndex.from_documents(
            [doc],
            vector_store=vector_store,
            property_graph_store=_graph_store,
            show_progress=True,
        )
        _save_graph_store()
        triplets = index.property_graph_store.get_triplets()
        
        # Fallback: if small local LLMs fail to output valid triplets, extract keywords
        if not triplets:
            import re
            words = list(set([w.lower() for w in re.split(r'\W+', text) if len(w) > 4]))
            doc_node = EntityNode(name="Document", label="DOCUMENT")
            nodes_to_add = [doc_node]
            rels_to_add = []
            for w in words[:30]:
                kw_node = EntityNode(name=w, label="KEYWORD")
                rel = Relation(source_id=doc_node.id, target_id=kw_node.id, label="contains")
                nodes_to_add.append(kw_node)
                rels_to_add.append(rel)
            _graph_store.upsert_nodes(nodes_to_add)
            _graph_store.upsert_relations(rels_to_add)
            _save_graph_store()
            triplets = _graph_store.get_triplets()
            
        nodes, edges = _triplets_to_nodes_edges(triplets)
        return {
            "status": "success",
            "message": "Graph extracted and stored.",
            "text": text,
            "nodes": nodes,
            "edges": edges,
        }
    except Exception as e:
        return {"status": "error", "message": f"Graph processing failed: {str(e)}"}


def query_graph(query: str):
    if not query.strip():
        return {"status": "error", "message": "Empty query."}
    try:
        graph_store = _load_graph_store()
        vector_store = _get_vector_store()
        index = PropertyGraphIndex.from_existing(
            property_graph_store=graph_store,
            vector_store=vector_store,
        )
        query_engine = index.as_query_engine(include_text=True)
        response = query_engine.query(query)
        return {"status": "success", "query": query, "response": str(response)}
    except Exception as e:
        return {"status": "error", "message": f"Query failed: {str(e)}"}


def compare_text_with_graph(target_text: str):
    if not target_text.strip():
        return {"status": "error", "message": "No comparison text provided."}
    try:
        graph_store = _load_graph_store()
        vector_store = _get_vector_store()
        source_index = PropertyGraphIndex.from_existing(
            property_graph_store=graph_store,
            vector_store=vector_store,
        )
        source_triplets = source_index.property_graph_store.graph.get_triplets()
        if not source_triplets:
            return {
                "status": "error",
                "message": "No source graph found. Please upload a document first.",
            }
        source_entities = set()
        for subj, _, obj in source_triplets:
            source_entities.add(str(getattr(subj, 'name', subj.label)).lower())
            source_entities.add(str(getattr(obj, 'name', obj.label)).lower())
            
        temp_graph_store = SimplePropertyGraphStore()
        doc = Document(text=target_text)
        target_index = PropertyGraphIndex.from_documents(
            [doc],
            property_graph_store=temp_graph_store,
            show_progress=False,
        )
        target_triplets = target_index.property_graph_store.graph.get_triplets()
        
        # Fallback: if small local LLMs fail to output valid target triplets, extract keywords
        if not target_triplets:
            import re
            words = list(set([w.lower() for w in re.split(r'\W+', target_text) if len(w) > 4]))
            doc_node = EntityNode(name="TargetDocument", label="DOCUMENT")
            nodes_to_add = [doc_node]
            rels_to_add = []
            for w in words[:30]:
                kw_node = EntityNode(name=w, label="KEYWORD")
                rel = Relation(source_id=doc_node.id, target_id=kw_node.id, label="contains")
                nodes_to_add.append(kw_node)
                rels_to_add.append(rel)
            temp_graph_store.upsert_nodes(nodes_to_add)
            temp_graph_store.upsert_relations(rels_to_add)
            target_triplets = temp_graph_store.graph.get_triplets()
            
        target_entities = set()
        for subj, _, obj in target_triplets:
            target_entities.add(str(getattr(subj, 'name', subj.label)).lower())
            target_entities.add(str(getattr(obj, 'name', obj.label)).lower())
            
        if not target_entities:
            return {
                "status": "success",
                "similarity_score": 0,
                "matching_keywords": [],
                "target_entity_count": 0,
                "source_entity_count": len(source_entities),
                "message": "No entities found in target text.",
            }
        matching_keywords = list(source_entities & target_entities)
        score = round((len(matching_keywords) / len(target_entities)) * 100, 2)
        return {
            "status": "success",
            "similarity_score": score,
            "matching_keywords": matching_keywords,
            "target_entity_count": len(target_entities),
            "source_entity_count": len(source_entities),
        }
    except Exception as e:
        return {"status": "error", "message": f"Comparison failed: {str(e)}"}
