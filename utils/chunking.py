import os
import boto3
import tiktoken
import pandas as pd


def chunk_text_with_overlap(tokenizer, text, chunk_size=500, overlap=100):
    tokens = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        if end == len(tokens):  # 마지막 청크 처리
            break
        start += chunk_size - overlap
    return chunks


def download_csv_from_s3(csv_file_path):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="ap-northeast-2",
    )
    bucket_name = "ossca"
    key = "USTRGraph/ustr_2023_press_releases.csv"
    local_file_path = csv_file_path
    # S3에서 파일 다운로드
    s3.download_file(bucket_name, key, local_file_path)


def get_chuncked_df(df, chunk_size=500, chunk_overlap=100):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    chunk_size = 500
    chunk_overlap = 100
    # 전체 청크 처리 및 태깅
    chunked_data = []
    for idx, row in df.iterrows():
        chunks = chunk_text_with_overlap(
            tokenizer, row["content"], chunk_size, chunk_overlap
        )
        for i, chunk in enumerate(chunks):

            chunked_data.append(
                {
                    "doc_id": row["doc_id"],
                    "chunk_id": i,
                    "title": row["title"],
                    "date": row["date"],
                    "url": row["url"],
                    "chunk_text": chunk,
                }
            )
    chunked_df = pd.DataFrame(chunked_data)
    return chunked_df
