import os
import asyncio
import hashlib
import json
import logging
from typing import List, Optional

try:
    from apps.api.app.core.config import settings
except ImportError:
    settings = None


try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
    logging.warning("sentence-transformers is not installed.")

class EmbeddingClient:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize the embedding client.
        
        Using a local model explicitly on the CPU to avoid CUDA dependency issues
        and keep the footprint lean for the demo.
        """
        self.model_name = model_name
        if SentenceTransformer:
            self.model = SentenceTransformer(self.model_name, device="cpu")
        else:
            self.model = None

    async def embed_texts(
        self, 
        tenant_id: str, 
        texts: List[str], 
        redis_client=None
    ) -> List[List[float]]:
        """
        Generate embeddings asynchronously with tenant-aware Redis caching.
        """
        if not texts:
            return []

        # 1. Compute cache keys
        cache_keys = []
        for text in texts:
            text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
            cache_keys.append(f"emb:{tenant_id}:{text_hash}")

        results = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []

        # 2. Try fetching from cache
        if redis_client:
            try:
                cached_values = await redis_client.mget(cache_keys)
                for idx, cached_val in enumerate(cached_values):
                    if cached_val:
                        results[idx] = json.loads(cached_val)
                    else:
                        texts_to_embed.append(texts[idx])
                        indices_to_embed.append(idx)
            except Exception as e:
                logging.warning(f"Redis cache read failed: {e}")
                texts_to_embed = texts
                indices_to_embed = list(range(len(texts)))
        else:
            texts_to_embed = texts
            indices_to_embed = list(range(len(texts)))

        # 3. Compute missing embeddings
        if texts_to_embed:
            if not self.model:
                raise RuntimeError("SentenceTransformer is not installed.")
                
            loop = asyncio.get_running_loop()
            
            # Retry logic: 3 retries, exponential backoff
            max_retries = 3
            base_delay = 1.0
            
            new_embeddings = None
            for attempt in range(max_retries):
                try:
                    api_key = settings.GROQ_API_KEY if settings and hasattr(settings, "GROQ_API_KEY") else os.getenv("GROQ_API_KEY", "")
                    
                    new_embeddings = await loop.run_in_executor(
                        None, 
                        lambda: self.model.encode(texts_to_embed, convert_to_numpy=True).tolist()
                    )
                    break  # Success, exit the retry loop
                except Exception as e:
                    logging.warning(f"Embedding generation failed (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        raise e
                    
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(base_delay * (2 ** attempt))
            
            # 4. Save missing embeddings back to cache
            if redis_client:
                try:
                    pipeline = redis_client.pipeline()
                    for idx, emb in zip(indices_to_embed, new_embeddings):
                        results[idx] = emb
                        # Cache for 24 hours (86400 seconds)
                        pipeline.setex(cache_keys[idx], 86400, json.dumps(emb))
                    await pipeline.execute()
                except Exception as e:
                    logging.warning(f"Redis cache write failed: {e}")
                    for idx, emb in zip(indices_to_embed, new_embeddings):
                        results[idx] = emb
            else:
                for idx, emb in zip(indices_to_embed, new_embeddings):
                    results[idx] = emb

        return results

    async def embed_text(self, tenant_id: str, text: str, redis_client=None) -> List[float]:
        """Generate an embedding for a single text, backed by cache."""
        result = await self.embed_texts(tenant_id, [text], redis_client)
        return result[0]

# Global instance to avoid reloading the model into memory
_client = None

def get_embedding_client() -> EmbeddingClient:
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client
