import hydra
from omegaconf import DictConfig, OmegaConf
from hydra.core.hydra_config import HydraConfig
import openai
import os
from dotenv import load_dotenv
import pandas as pd
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

from concurrent.futures import ThreadPoolExecutor, as_completed


# --- Worker function for threading ---
def process_row(i, row, cfg, prompt_cfg, entity_types_reference, examples,neo4j = False):
    client = openai.OpenAI(api_key=cfg.model.api_key)
    input_text = row["chunk_text"]
    doc_id = row["doc_id"]
    chunk_id = row["chunk_id"] + 1


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
    response = client.chat.completions.create(
        model=cfg.model.model_name,
        messages=[
            {"role": "system", "content": prompt_cfg["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        temperature=cfg.model.temperature,
        max_tokens=cfg.model.max_tokens,
    )
    entity_output = response.choices[0].message.content
    tmp_kg = to_kg_in_chunk(entity_output, i)
    if neo4j:
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        )
        with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
            session.execute_write(
                insert_chunk_node,
                chunk_id,
                doc_id,
                tmp_kg["content_keywords"][0]["high_level_keywords"],
            )
            for ent in tmp_kg["entities"]:
                session.execute_write(
                    insert_entity_node,
                    chunk_id,
                    doc_id,
                    ent["entity_name"],
                    ent["entity_type"],
                    ent["description"],
                )
            for rel in tmp_kg["relationships"]:
                session.execute_write(
                    insert_entity_relationship,
                    chunk_id,
                    doc_id,
                    rel["src_id"],
                    rel["tgt_id"],
                    rel["description"],
                    rel["keywords"],
                    rel["weight"],
                )
            check_entity_node_count(session, doc_id, chunk_id, len(tmp_kg["entities"]))
            check_entity_relationship_count(
                session, doc_id, chunk_id, len(tmp_kg["relationships"]),
            )
        driver.close()
    return entity_output

# --- ThreadPoolExecutor runner ---
def run_with_threads(df, cfg, prompt_cfg, entity_types_reference, examples):
    max_workers = cfg.thread_workers if hasattr(cfg, 'thread_workers') else 16
    df["output"] = None
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(
            process_row, i, row, cfg, prompt_cfg, entity_types_reference, examples): i
            for i, row in df.iterrows()
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                #future.result()
                result_text = future.result()
                df.at[idx, "output"] = result_text
                print(f"Processed chunk {idx}")
            except Exception as exc:
                print(f"Error processing chunk {idx}: {exc}")
    
@hydra.main(
    config_path="config",
    config_name="base_prompt_v1.yaml",
    version_base="1.3",
)
def run(cfg: DictConfig):
    hydra_cfg = HydraConfig.get()
    config_name = hydra_cfg.job.config_name
    base = os.path.splitext(os.path.basename(config_name))[0]
    out_fname = f"./entity_outputs/{base}.csv"

    # Prepare prompt config
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    prompt_cfg = cfg_dict["prompt_entity"]
    examples = "\n\n".join(prompt_cfg["examples"])
    entity_descriptions = prompt_cfg.get("entity_types_descriptions", {})
    entity_reference_lines = [
        f"• {etype}: {entity_descriptions.get(etype, '')}"
        for etype in prompt_cfg["entity_types"]
    ]
    entity_types_reference = "\n".join(entity_reference_lines)
    # Run threaded processing
    run_with_threads(df, cfg, prompt_cfg, entity_types_reference, examples)

    df.to_csv(out_fname, index=False)
    print(f"→ saved results to {out_fname}")

    
if __name__ == "__main__":
    load_dotenv()
    
    '''
    press 전체를 neo4j에 적재
    '''
    full_csv_path = "./data/ustr_2023_press_releases_tailed.csv"
    df = pd.read_csv(full_csv_path, encoding="utf-8")
    # driver = GraphDatabase.driver(
    #     os.getenv("NEO4J_URI"),
    #     auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    # )
    # with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
    #     session.execute_write(delete_all_nodes)
    #     for i, (_, row) in enumerate(df.iterrows()):
    #         session.execute_write(
    #             insert_document_node,
    #             i,
    #             convert_date(row["date"]),  # convert_date 함수로 날짜 파싱
    #             row["title"],
    #             row["content"],
    #             row["url"],
    #         )
    # check_document_node_count(
    #     driver.session(database=os.getenv("NEO4J_DATABASE")), len(df)
    # )
    # driver.close()

    '''
    chunk단위를 적재 + kg 삽임
    '''
    csv_file_path = "./data/ustr_chunked.csv"
    if not os.path.exists(csv_file_path):
        print("preprocess.py를 먼저 실행시키세요")
        exit()
    df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",")
    run()
