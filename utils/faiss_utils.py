import numpy as np
import faiss
import os


def get_embedding(text, client, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    emb = client.embeddings.create(input=[text], model=model).data[0].embedding
    return np.array(emb, dtype=np.float32)


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


def get_doc_neighbor(df, gid):
    doc_id = df.loc[df["global_id"] == gid, "doc_id"].iloc[0]
    # Get the document ID for the given global ID
    doc_id = df.loc[df["global_id"] == gid, "doc_id"].iloc[0]

    # Get all global IDs from the same document (including the input gid)
    indoc_global_ids = df.loc[df["doc_id"] == doc_id, "global_id"]

    # Get all global IDs from different documents
    outdoc_global_ids = df.loc[df["doc_id"] != doc_id, "global_id"]
    return indoc_global_ids, outdoc_global_ids


def search_in_subset(index, query_vector,query_index, index_subset, top_k=5):
    """
    불연속적인 인덱스 집합에서 유사도 검색을 수행하는 함수

    Parameters:
    -----------
    index : faiss.Index
        이미 생성되고 벡터가 추가된 FAISS 인덱스 객체
    query_vector : numpy.ndarray
        쿼리 벡터 (shape: [1, d] 또는 [d,])
    index_subset : list or numpy.ndarray
        검색할 인덱스들의 집합 (불연속적인 인덱스도 가능)
    top_k : int
        반환할 가장 유사한 벡터의 개수

    Returns:
    --------
    tuple
        (distances, indices) - 유사도 거리와 해당 인덱스
    """
    # 선택된 인덱스 집합 생성 (IDSelectorBatch 사용)
    # 인덱스는 int64 타입이어야 함
    subset_indices = np.array(index_subset, dtype=np.int64)
    selector = faiss.IDSelectorBatch(
        len(subset_indices), faiss.swig_ptr(subset_indices)
    )

    # 검색 파라미터 설정
    params = faiss.SearchParameters()
    params.sel = selector

    # 쿼리 벡터가 2D 배열인지 확인
    if len(query_vector.shape) == 1:
        query_vector = query_vector.reshape(1, -1)

    # 검색 수행 (제한된 인덱스 집합에서만)
    k = min( top_k + 1, len(subset_indices))  # 요청한 k와 실제 서브셋 크기 중 작은 값 사용
    distances, indices = index.search(query_vector.astype("float32"), k, params=params)
    dists = distances[0]
    inds  = indices[0]
    filtered = [(d, i) for d, i in zip(dists, inds) if i != query_index]

    # 5) 앞에서 top_k개만 잘라서 리턴
    filtered = filtered[:top_k]
    if not filtered:
        return np.array([], dtype=dists.dtype), np.array([], dtype=inds.dtype)
    d_out, i_out = zip(*filtered)
    return np.array(d_out), np.array(i_out)


if __name__ == "__main__":
    import pandas as pd

    chunked_df = pd.read_csv("chunked_df.csv", encoding="utf-8", delimiter=",")
    indoc_neighbor, outdoc_neighbor = get_doc_neighbor(chunked_df, 0)
    index = faiss.read_index("./faiss/idmap.index")
    base_index = faiss.downcast_index(index.index)
    query = base_index.reconstruct(0).reshape(1, -1)
    D, I = base_index.search(query, 3)
    D, I = search_in_subset(
        base_index, query_vector=query, index_subset=indoc_neighbor, top_k=3
    )
    D, I = search_in_subset(
        base_index, query_vector=query, index_subset=outdoc_neighbor, top_k=3
    )
    print(D)
    print(I)
