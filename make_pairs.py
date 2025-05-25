import csv
import ast

unique_pairs = set()

with open("./data/ustr_chunked.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        a = int(row["global_id"])
        # 문자열로 된 리스트를 실제 파이썬 리스트로 변환
        b_list = ast.literal_eval(row["inter_doc_neighbor"])  
        for b in b_list:
            if a == b:
                # 자기 자신과의 링크는 스킵
                continue
            # (min, max) 순으로 정렬된 튜플을 키로 사용하면 1-5, 5-1이 같은 쌍으로 취급됩니다.
            pair = tuple(sorted((a, b)))
            unique_pairs.add(pair)

with open("./data/ustr_chunked.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        a = int(row["global_id"])
        # 문자열로 된 리스트를 실제 파이썬 리스트로 변환
        b_list = ast.literal_eval(row["intra_doc_neighbor"])  
        for b in b_list:
            if a == b:
                # 자기 자신과의 링크는 스킵
                continue
            # (min, max) 순으로 정렬된 튜플을 키로 사용하면 1-5, 5-1이 같은 쌍으로 취급됩니다.
            pair = tuple(sorted((a, b)))
            unique_pairs.add(pair)

