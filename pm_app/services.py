import chromadb 
from django.conf import settings

#initialize persistent ChromaDB client

client = chromadb.PersistentClient(path=settings.CHROMA_DB)

def get_or_create_collection(collection_name: str):
    """
    Get or create a collection in the ChromaDB client.
    This method is idempotent, its safe to call multiple times without creating duplicates.
    """
    collection = client.get_or_create_collection(name=collection_name)
    return collection