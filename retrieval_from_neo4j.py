import pandas as pd
from typing import Set, Tuple, List, Union
import ast
import os 
from neo4j import GraphDatabase
import hydra
from omegaconf import DictConfig, OmegaConf
import openai
import os
from dotenv import load_dotenv
from utils.to_kg import to_kg_inter_chunk
from utils.neo4j_utils import insert_inter_relationship, fetch_chunk_entities



def get_unique_pairs(
    df: pd.DataFrame,
) -> Tuple[Set[Tuple[int,int]], Set[Tuple[int,int]]]:
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
        elif isinstance(cell, list):
            return cell
        else:
            return []
    
    inter_pairs: Set[Tuple[int,int]] = set()
    intra_pairs: Set[Tuple[int,int]] = set()

    for idx, row in df.iterrows():
        a = int(row["global_id"])
        for col, container in (("inter_doc_neighbor", inter_pairs), ("intra_doc_neighbor", intra_pairs)):
            nbrs = parse_neighbors(row.get(col, []))
            for b in nbrs:
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




@hydra.main(
    config_path="config_inter",
    config_name="base_prompt_v1.yaml",
    version_base="1.3",
)
def run(cfg: DictConfig):
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    prompt_cfg = cfg_dict["prompt_entity"]


    examples = "\n\n".join(cfg_dict["prompt_entity"]["examples"])

    prompt = prompt_cfg["prompt_template"].format(
        language=prompt_cfg["language"],
        tuple_delimiter=prompt_cfg["tuple_delimiter"],
        record_delimiter=prompt_cfg["record_delimiter"],
        completion_delimiter=prompt_cfg["completion_delimiter"],
        examples = examples,
        source_text = source,
        target_text = target,
    )
    # -----------------------
    # STEP 1: Entity Extraction
    # -----------------------

    client = openai.OpenAI(api_key=cfg.model.api_key)
    entity_response = client.chat.completions.create(
        model=cfg.model.model_name,
        messages=[
            {"role": "system", "content": cfg.prompt_entity.system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=cfg.model.temperature,
        max_tokens=cfg.model.max_tokens,
    )
    entity_output = entity_response.choices[0].message.content
    relationships = to_kg_inter_chunk(entity_output)
    total = len(relationships)


    driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        )
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        for relationship in relationships:
            try :
                session.execute_write(
                    insert_inter_relationship,
                    s_chunk_id,
                    s_doc_id,
                    t_chunk_id,
                    t_doc_id,
                    relationship["src_id"],
                    relationship["tgt_id"],
                    relationship["description"],
                    relationship["keywords"],
                    relationship["weight"],
                )
            except Exception as e:
                print("Error inserting relationship:", e)
                print("Relationship data:", relationship)
                total = total - 1
                continue
    print("Total relationships inserted:", total)




# 사용 예시
if __name__ == "__main__":
    load_dotenv()
    df = pd.read_csv("./data/ustr_chunked.csv", encoding="utf-8",delimiter=",")
    inter_pairs, intra_pairs = get_unique_pairs(df)

    driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        for source, target in inter_pairs:
            source_row = df.loc[df['global_id'] == source].iloc[0]
            target_row = df.loc[df['global_id'] == target].iloc[0]
            s_doc_id = source_row['doc_id']
            s_chunk_id = source_row['chunk_id'] + 1
            t_doc_id = target_row['doc_id']
            t_chunk_id = target_row['chunk_id'] + 1
            s_entities = session.execute_read(fetch_chunk_entities, s_chunk_id, s_doc_id)
            t_entities = session.execute_read(fetch_chunk_entities, t_chunk_id, t_doc_id)

            source = prop_to_input(s_entities)
            target = prop_to_input(t_entities)
            print(s_doc_id, s_chunk_id, t_doc_id, t_chunk_id)
            run()

            break 