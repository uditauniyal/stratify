import os
import glob
import math
from typing import List, Any
from dotenv import load_dotenv

# Load env variables (API key)
load_dotenv()

from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Optional: Try importing OpenAIEmbeddings
try:
    from langchain_openai import OpenAIEmbeddings
    HAS_OPENAI_LIB = True
except ImportError:
    HAS_OPENAI_LIB = False

def get_document_type(filename: str) -> str:
    base = os.path.basename(filename).lower()
    if "instructions" in base: return "instructions"
    if "errors" in base: return "errors"
    if "typologies" in base: return "typologies"
    if "templates" in base: return "templates"
    return "general"

class SimpleEmbeddings(Embeddings):
    """
    Deterministic fallback embedding model based on character trigram hashing.
    Produces 384-dimensional vectors. Sufficient for prototyping without API keys.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dim
        text = text.lower()
        if len(text) < 3:
            return vector
            
        # Hash trigrams
        for i in range(len(text) - 2):
            trigram = text[i:i+3]
            idx = hash(trigram) % self.dim
            vector[idx] += 1.0
            
        # Normalize (L2)
        norm = math.sqrt(sum(v*v for v in vector))
        if norm > 0:
            vector = [v/norm for v in vector]
            
        return vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

def load_corpus(corpus_dir: str = "rag/corpus") -> List[Document]:
    """
    Load all .txt files from the corpus directory.
    """
    docs = []
    files = glob.glob(os.path.join(corpus_dir, "*.txt"))
    
    for f in files:
        try:
            loader = TextLoader(f, encoding="utf-8")
            loaded = loader.load()
            
            # Add custom metadata
            doc_type = get_document_type(f)
            for d in loaded:
                d.metadata["source"] = os.path.basename(f)
                d.metadata["document_type"] = doc_type
                
            docs.extend(loaded)
        except Exception as e:
            print(f"Error loading {f}: {e}")
            
    print(f"Loaded {len(files)} files from {corpus_dir}")
    return docs

def create_vectorstore(documents: List[Document], persist_directory: str = "rag/chroma_db") -> Chroma:
    """
    Chunk documents and create Chroma vectorstore.
    """
    # 1. Split
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " "]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks from {len(documents)} documents")
    
    # 2. Embeddings
    embedding_function = None
    api_key = os.environ.get("OPENAI_API_KEY")

    if HAS_OPENAI_LIB and api_key and not api_key.startswith("sk-your-key"):
        try:
            embedding_function = OpenAIEmbeddings(model="text-embedding-3-small")
            # Trigger a dummy embed to check connectivity
            embedding_function.embed_query("test")
            print("Using OpenAI Embeddings (text-embedding-3-small)")
        except Exception as e:
            embedding_function = SimpleEmbeddings()
            print(f"Failed to init OpenAI Embeddings: {e}. Falling back to SimpleEmbeddings.")
    else:
        embedding_function = SimpleEmbeddings()
        if not HAS_OPENAI_LIB:
            print("langchain_openai not found.")
        elif not api_key:
            print("No OPENAI_API_KEY found.")
        print("Using Fallback SimpleEmbeddings (Deterministic Hashing)")

    # 3. Create Vectorstore
    # Chroma handles persistence automatically if persist_directory is set
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_function,
        persist_directory=persist_directory
    )
    
    print(f"Vectorstore created at {persist_directory}")
    return vectorstore

def get_vectorstore(persist_directory: str = "rag/chroma_db", embedding_function=None) -> Chroma:
    """
    Load existing vectorstore or create new one if empty.
    """
    # Define embedding function to use for loading (must match creation)
    if embedding_function is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if HAS_OPENAI_LIB and api_key and not api_key.startswith("sk-your-key"):
            try:
                embedding_function = OpenAIEmbeddings(model="text-embedding-3-small")
                # Trigger a dummy embed to check connectivity
                embedding_function.embed_query("test")
                print("Using OpenAI Embeddings (text-embedding-3-small)")
            except Exception as e:
                embedding_function = SimpleEmbeddings()
                print(f"Failed to init OpenAI Embeddings: {e}. Falling back to SimpleEmbeddings.")
        else:
            embedding_function = SimpleEmbeddings()


    if os.path.exists(persist_directory) and os.listdir(persist_directory):
        # Load existing
        # print(f"Loading existing vectorstore from {persist_directory}")
        return Chroma(persist_directory=persist_directory, embedding_function=embedding_function)
    else:
        # Create new
        docs = load_corpus()
        return create_vectorstore(docs, persist_directory)

def query_vectorstore(vectorstore, query: str, k: int = 5) -> List[str]:
    """
    Query the vectorstore and return document contents.
    """
    results = vectorstore.similarity_search(query, k=k)
    print(f"Found {len(results)} relevant chunks for query: '{query}'")
    return [d.page_content for d in results]

if __name__ == "__main__":
    # Test Run
    print("Initializing RAG Vectorstore...")
    
    # Force rebuild for testing if main is run directly? 
    # Or just ensure it exists.
    # We'll use get_vectorstore logic but force create if we suspect it handles rebuilds.
    # Actually, let's just run logic:
    
    docs = load_corpus()
    if docs:
        vectorstore = create_vectorstore(docs)
        
        test_query = "How should I structure a SAR narrative for structuring activity?"
        print(f"\nTest Query: {test_query}")
        
        results = query_vectorstore(vectorstore, test_query, k=3)
        
        print("\nTop Results:")
        for i, res in enumerate(results):
            print(f"--- Chunk {i+1} ---")
            print(res[:200] + "...")
