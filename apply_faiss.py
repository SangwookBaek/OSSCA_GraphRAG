import hydra
import openai
import os
from dotenv import load_dotenv
import pandas as pd
from utils.faiss_utils import get_embedding
from openai import OpenAI
import faiss
import numpy as np


def load_faiss_index(index_path: str, dim: int) -> faiss.IndexIDMap:
    """
    Load a FAISS index if it exists, else create a new one.
    Wraps an IndexFlatL2 inside an IndexIDMap for ID-based additions.

    Args:
        index_path: Path to .index file on disk.
        dim: Dimension of embedding vectors.

    Returns:
        An IndexIDMap for adding/querying vectors with IDs.
    """
    if os.path.exists(index_path):
        print(f"Loading existing FAISS index from '{index_path}'...")
        index = faiss.read_index(index_path)
    else:
        print(f"Creating new FAISS index of dimension {dim}...")
        flat_index = faiss.IndexFlatL2(dim)
        index = faiss.IndexIDMap(flat_index)
    return index


def save_faiss_index(index: faiss.Index, index_path: str):
    """
    Write the FAISS index back to disk.
    """
    faiss.write_index(index, index_path)
    print(f"FAISS index saved to '{index_path}'.")


if __name__ == "__main__":
    load_dotenv()
    csv_file_path = "./data/ustr_chunked.csv"
    # 파일이 없을 경우에만 다운로드
    chunked_df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",")
    client = OpenAI(api_key=os.getenv("TEAM1_OPENAI_API_KEY"))
    VECTOR_DIM = 1536
    INDEX_FILE = "./faiss/idmap.index"
    BASE_INDEX_FILE = "./faiss/flatl2.index"
    index = load_faiss_index(INDEX_FILE, dim=VECTOR_DIM)
    embeddings_list = []
    ids_list = []
    for _, row in chunked_df.iterrows():
        gid = int(row["global_id"])
        text = row["chunk_text"]
        vec = get_embedding(text, client=client, model="text-embedding-3-small")
        embeddings_list.append(vec)
        ids_list.append(gid)
        print(f"Processed global_id={gid}")

    # Stack into arrays
    all_vecs = np.vstack(embeddings_list).astype("float32")  # shape (N, dim)
    all_ids = np.array(ids_list, dtype="int64")  # shape (N,)

    # Batch add to FAISS
    index.add_with_ids(all_vecs, all_ids)
    print(f"Added {len(all_ids)} vectors to index in batch.")

    # Save updated index
    save_faiss_index(index, INDEX_FILE)

    base_index = faiss.downcast_index(index.index)
    save_faiss_index(base_index, BASE_INDEX_FILE)
