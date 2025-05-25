import pandas as pd
from utils.faiss_utils import get_doc_neighbor,search_in_subset
import faiss


if __name__ == "__main__":
    df = pd.read_csv("./data/ustr_chunked.csv", encoding="utf-8", delimiter=",")
    df['intra_doc_neighbor'] = None
    df['inter_doc_neighbor'] = None

    index = faiss.read_index("./faiss/idmap.index")
    base_index = faiss.downcast_index(index.index)
    for id in df["global_id"]:
        indoc_neighbor, outdoc_neighbor = get_doc_neighbor(df, id)
        query = base_index.reconstruct(id).reshape(1, -1)
        D, I = search_in_subset(
            base_index, query_vector=query,query_index=id, index_subset=indoc_neighbor, top_k=3
        )
        #print(D,I)
        df.at[id, 'intra_doc_neighbor'] = I.tolist()
        D, I = search_in_subset(
            base_index, query_vector=query,query_index=id, index_subset=outdoc_neighbor, top_k=3
        )
        #print(D,I)p
        df.at[id, 'inter_doc_neighbor'] = I.tolist()
        print(f"{id}처리")
    df.to_csv("./data/ustr_chunked.csv", index=False)
