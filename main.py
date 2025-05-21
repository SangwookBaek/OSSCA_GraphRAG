import hydra
from omegaconf import DictConfig, OmegaConf
import openai
import os
from dotenv import load_dotenv
import boto3
import pandas as pd
from notion_sdk import config2notion
from utils import download_csv_from_s3, get_chuncked_df
from utils.to_kg import to_kg_in_chunk
from neo4j import GraphDatabase
from utils.neo4j_utils import (
    insert_entity_relationship,
    check_entity_node_count,
    check_entity_relationship_count,
    insert_chunk_node,
    insert_entity_node,
    delete_all_nodes,
    check_document_node_count,
    insert_document_node,
    convert_date,
)


@hydra.main(
    config_path="config",
    config_name="base_prompt_v1.yaml",
    version_base="1.3",
)
def run(cfg: DictConfig):
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    prompt_cfg = cfg_dict["prompt_entity"]
    examples = "\n\n".join(cfg_dict["prompt_entity"]["examples"])
    entity_refernce_lines = []
    entity_descriptions = prompt_cfg.get("entity_types_descriptions", {})

    for entity in prompt_cfg["entity_types"]:
        description = entity_descriptions.get(entity, "")
        entity_refernce_lines.append(f"• {entity}: {description}")
    entity_types_reference = "\n".join(entity_refernce_lines)
    client = openai.OpenAI(api_key=cfg.model.api_key)

    for i, row in df.iterrows():
        input_text = row["chunk_text"]
        doc_id = row["doc_id"]
        chunk_id = row["chunk_id"] + 1 #1부터 indexing됨 2팀 내부 구현인듯 맞춰야함
        prompt = prompt_cfg["prompt_template"].format(
            language=prompt_cfg["language"],
            tuple_delimiter=prompt_cfg["tuple_delimiter"],
            record_delimiter=prompt_cfg["record_delimiter"],
            completion_delimiter=prompt_cfg["completion_delimiter"],
            entity_types_reference=entity_types_reference,
            examples=examples,
            entity_types=", ".join(prompt_cfg["entity_types"]),
            input_text=input_text,
        )
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
        tmp_kg = to_kg_in_chunk(entity_output, i)
        entities = tmp_kg["entities"]
        relationships = tmp_kg["relationships"]
        content_keywords = tmp_kg["content_keywords"]
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        )
        with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
            session.execute_write(
                insert_chunk_node,
                chunk_id,
                doc_id,
                content_keywords[0][
                    "high_level_keywords"
                ],  # assume high_level_keywords has single record
            )
            for entity in entities:
                # TODO: Check entity_type in ENTITY_LABEL_LIST
                session.execute_write(
                    insert_entity_node,
                    chunk_id,
                    doc_id,
                    entity["entity_name"],
                    entity["entity_type"],
                    entity["description"],
                )
            for relationship in relationships:
                session.execute_write(
                    insert_entity_relationship,
                    chunk_id,
                    doc_id,
                    relationship["src_id"],
                    relationship["tgt_id"],
                    relationship["description"],
                    relationship["keywords"],
                    relationship["weight"],
                )
            check_entity_node_count(session, doc_id, chunk_id, len(entities))
            check_entity_relationship_count(
                session, doc_id, chunk_id, len(relationships)
            )
        exit()


if __name__ == "__main__":
    load_dotenv()
    full_csv_path = "./data/ustr_2023_press_releases_tailed.csv"
    df = pd.read_csv(full_csv_path, encoding="utf-8")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        session.execute_write(delete_all_nodes)
        for i, (_, row) in enumerate(df.iterrows()):
            session.execute_write(
                insert_document_node,
                i,
                convert_date(row["date"]),  # convert_date 함수로 날짜 파싱
                row["title"],
                row["content"],
                row["url"],
            )
    check_document_node_count(
        driver.session(database=os.getenv("NEO4J_DATABASE")), len(df)
    )
    driver.close()



    '''
    chunk단위를 적재 + kg 삽임
    '''
    csv_file_path = "./data/ustr_chunked.csv"
    if not os.path.exists(csv_file_path):
        print("preprocess.py를 먼저 실행시키세요")
        exit()
    df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",")
    run()



