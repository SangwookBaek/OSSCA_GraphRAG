import hydra
from omegaconf import DictConfig, OmegaConf
import openai
import os
from dotenv import load_dotenv
import pandas as pd
from utils.chunking import download_csv_from_s3, get_chuncked_df

# if __name__ == "__main__":
#     load_dotenv()
#     csv_file_path = "./data/ustr_2023_press_releases.csv"
#     tailed_csv_file_path =  "./data/ustr_2023_press_releases_tailed.csv"
#     chunked_csv_file_path = "./data/ustr_chunked.csv"
#     # 파일이 없을 경우에만 다운로드
#     if not os.path.exists(csv_file_path):
#         download_csv_from_s3(csv_file_path)
#     df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",")
#     if not os.path.exists(tailed_csv_file_path):
#         df['date'] = pd.to_datetime(df['date'])
#         # 2023년 8월 31일까지의 데이터만 유지
#         filtered_df = df[df['date'] <= '2023-08-31']
#         filtered_df.to_csv(tailed_csv_file_path)
#     else : 
#         filtered_df = pd.read_csv(tailed_csv_file_path, encoding="utf-8", delimiter=",")
#     if not os.path.exists(chunked_csv_file_path):
#         chunked_df = get_chuncked_df(filtered_df)
#         chunked_df.insert(0, "global_id", range(len(chunked_df)))
#         chunked_df.to_csv(chunked_csv_file_path, index=False)


if __name__ == "__main__":
    load_dotenv()
    if not os.path.exists("./data"):
        os.mkdir("./data")
    csv_file_path = "./data/ustr_2023_press_releases.csv"
    tailed_csv_file_path =  "./data/ustr_2023_press_releases_tailed.csv"
    chunked_csv_file_path = "./data/ustr_chunked.csv"

    # 파일이 없을 경우에만 다운로드
    if not os.path.exists(csv_file_path):
        download_csv_from_s3(csv_file_path)
    df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",")
    if not os.path.exists(tailed_csv_file_path):
        df['date'] = pd.to_datetime(df['date'])
        # 2023년 8월 31일까지의 데이터만 유지
        
        filtered_df = df[df['date'] <= '2023-08-31']
        filtered_df.insert(0, "doc_id", range(len(filtered_df)))
        filtered_df.to_csv(tailed_csv_file_path, index=False)
    else : 
        filtered_df = pd.read_csv(tailed_csv_file_path, encoding="utf-8", delimiter=",",index_col=0)
    if not os.path.exists(chunked_csv_file_path):
        chunked_df = get_chuncked_df(filtered_df)
        chunked_df.insert(0, "global_id", range(len(chunked_df)))
        chunked_df.to_csv(chunked_csv_file_path, index=False)