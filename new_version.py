import os
import ast
from typing import Set, Tuple, List, Union
import pandas as pd
from neo4j import GraphDatabase
from omegaconf import DictConfig, OmegaConf
import hydra
import openai
from dotenv import load_dotenv

from utils.to_kg import to_kg_inter_chunk
from utils.neo4j_utils import insert_inter_relationship, fetch_chunk_entities


def get_unique_pairs(
    df: pd.DataFrame,
) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
    """
    DataFrame에서 inter_doc_neighbor와 intra_doc_neighbor를 읽어,
    두 종류의 (min, max) 형태로 정렬된 고유한 쌍을 반환합니다.

    Returns:
        (inter_pairs, intra_pairs)
    """
    def parse_neighbors(cell: Union[str, List[int]]) -> List[int]:
        if isinstance(cell, str):
            try:
                return ast.literal_eval(cell)
            except (ValueError, SyntaxError):
                return []
        if isinstance(cell, list):
            return cell
        return []

    inter_pairs: Set[Tuple[int, int]] = set()
    intra_pairs: Set[Tuple[int, int]] = set()

    for _, row in df.iterrows():
        a = int(row["global_id"])
        for col_name, container in (
            ("inter_doc_neighbor", inter_pairs),
            ("intra_doc_neighbor", intra_pairs),
        ):
            for b in parse_neighbors(row.get(col_name, [])):
                b = int(b)
                if a == b:
                    continue
                pair = tuple(sorted((a, b)))
                container.add(pair)

    return inter_pairs, intra_pairs

def prop_to_input(neo4j_entities):
    source = []
    for entity in neo4j_entities:
        description = entity["props"]['description']
        name = entity["props"]['name']
        entity_type = entity['labels'][0]
        tmp_line = f"(\"\"entity\"\"<|>{name}<|>{entity_type}<|>{description})##"
        source.append(tmp_line)
    return "\n".join(source)

def process_pair(
    session,
    client,
    cfg,
    df: pd.DataFrame,
    source_global: int,
    target_global: int,
) -> None:
    """
    한 쌍에 대해 엔티티를 가져와 LLM 호출, 관계를 Neo4j에 저장합니다.
    """
    src_row = df.loc[df.global_id == source_global].iloc[0]
    tgt_row = df.loc[df.global_id == target_global].iloc[0]

    s_doc, s_chunk = src_row.doc_id, src_row.chunk_id + 1
    t_doc, t_chunk = tgt_row.doc_id, tgt_row.chunk_id + 1

    # Neo4j에서 각 chunk의 엔티티 가져오기
    s_entities = session.execute_read(fetch_chunk_entities, s_chunk, s_doc)
    t_entities = session.execute_read(fetch_chunk_entities, t_chunk, t_doc)
    s_names = [e['props']['name'] for e in s_entities]
    t_names = [e['props']['name'] for e in t_entities]

    # LLM 입력 준비
    source_text = prop_to_input(s_entities)
    target_text = prop_to_input(t_entities)

    prompt_cfg = cfg.prompt_entity
    examples = "\n\n".join(prompt_cfg.examples)
    user_prompt = prompt_cfg.prompt_template.format(
        language=prompt_cfg.language,
        tuple_delimiter=prompt_cfg.tuple_delimiter,
        record_delimiter=prompt_cfg.record_delimiter,
        completion_delimiter=prompt_cfg.completion_delimiter,
        examples=examples,
        source_text=source_text,
        target_text=target_text,
    )

    resp = client.chat.completions.create(
        model=cfg.model.model_name,
        messages=[
            {"role": "system", "content": cfg.prompt_entity.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=cfg.model.temperature,
        max_tokens=cfg.model.max_tokens,
    )
    relations = to_kg_inter_chunk(resp.choices[0].message.content)
    # 관계 저장
    total = len(relations)
    for rel in relations:
        #print(rel['src_id'], rel['tgt_id'])
        if rel['src_id'] in t_names or rel['tgt_id'] in s_names:
            print(f"Skipping {rel} due to missing entities")
            total -= 1
            continue
        try:
            session.execute_write(
                insert_inter_relationship,
                s_chunk,
                s_doc,
                t_chunk,
                t_doc,
                rel['src_id'],
                rel['tgt_id'],
                rel['description'],
                rel['keywords'],
                rel['weight'],
            )
        except Exception as e:
            print(f"Failed to insert {rel}: {e}")
            total -= 1
    print(f"Chunks {s_doc}({s_chunk}) -> {t_doc}({t_chunk}): {total} relationships inserted")

@hydra.main(
    config_path="config_inter",
    config_name="base_prompt_v1.yaml",
    version_base="1.3",
)
def main(cfg: DictConfig):
    # 환경 변수, API 클라이언트, DB 드라이버 초기화
    load_dotenv()
    client = openai.OpenAI(api_key=cfg.model.api_key)
    driver = GraphDatabase.driver(
        os.environ['NEO4J_URI'],
        auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD']),
    )

    # 데이터 로드 및 유니크 페어 생성
    df = pd.read_csv("./backup/ustr_chunked.csv", encoding="utf-8")
    inter_pairs, intra_pairs = get_unique_pairs(df)

    # Neo4j 세션 열고 모든 페어 처리
    with driver.session(database=os.environ['NEO4J_DATABASE']) as session:
        for s, t in inter_pairs:
            process_pair(session, client, cfg, df, s, t)
            break
        for s, t in intra_pairs:
            process_pair(session, client, cfg, df, s, t)
            break


if __name__ == "__main__":
    main()
