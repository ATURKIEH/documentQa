import os
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_huggingface import HuggingFaceEmbeddings
from document_utils import DocumentUtils
load_dotenv()
class EmbedUtils:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        else:
            self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            self.index= self.pc.Index(os.getenv("PINECONE_INDEX_NAME"))
            self.embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
            self._initialized = True

    def store_document_chunks(self, chunks: list[str], user_id: int, document_id:int)-> None:
        for i, chunk in enumerate(chunks):
            vector = self.embeddings.embed_query(chunk)
            metadata = {
                "user_id": user_id,
                "document_id": document_id,
                "chunk_index": i,
                "text": chunk
            }
            self.index.upsert(vectors=[(f"{user_id}_{document_id}_{i}", vector, metadata)])


