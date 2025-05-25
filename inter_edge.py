import hydra
from omegaconf import DictConfig, OmegaConf
import openai
import os
from dotenv import load_dotenv
import boto3
import tiktoken
import pandas as pd
from neo4j import GraphDatabase
from utils.notion_sdk import config2notion
from utils.to_kg import to_kg_in_chunk,to_kg_inter_chunk
from utils.neo4j_utils import insert_inter_relationship
import json 
@hydra.main(
    config_path="config_inter",
    config_name="base_prompt_v1.yaml",
    version_base="1.3",
)
def run(cfg: DictConfig):
    global_id = 0
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
    #print(" Entity Extraction Output:\n", entity_output)
    relationships = to_kg_inter_chunk(entity_output)
    total = len(relationships)

    # insert_inter_relationship(tx)


    driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        )
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        for relationship in relationships:
            try :
                session.execute_write(
                    insert_inter_relationship,
                    1,
                    0,
                    1,
                    69,
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


def output_to_only_entity(output):
    entity_list = []
    TUPLE_DELEMITER = "<|>"
    RECORD_DELEMITER = "##"
    WRAPPER = "()"
    ENTITY_PREFIX, RELATIONSHIP_PREFIX, CONTENT_KEYWORDS_PREFIX = (
        '"entity"',
        '"relationship"',
        '"content_keywords"',
    )
    for tmp_output in output.split("##"):
        tmp_list = tmp_output.strip("\n").strip(WRAPPER).split(TUPLE_DELEMITER)
        if tmp_list[0] == ENTITY_PREFIX:
            entity_list.append(tmp_output)
    return "".join(entity_list)


if __name__ == "__main__":
    load_dotenv()
    csv_file_path = "./entity_outputs/base_prompt_v1.csv"
    # 파일이 없을 경우에만 다운로드
    if not os.path.exists(csv_file_path):
        print("main.py를 먼저 실행시키세요")
        exit()
    df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",", index_col=0)
    for i,row in df.iterrows():
        inter_doc_neighbor = eval(row["inter_doc_neighbor"])
        # print(inter_doc_neighbor)
        neighbor_indices = inter_doc_neighbor[0]  # 문자열을 리스트로 변환
        # print(df.iloc[neighbor_indices])  # index로 접근
        # print(row['output'].split("(\"relationship")[0])
        #print(output_to_only_entity(row['output']))
        target = output_to_only_entity(df.iloc[neighbor_indices,-1])
        source = output_to_only_entity(row['output'])
        print(source)
        print("#"*20)
        print(target)
        print("#"*20)
        break 
    run()


