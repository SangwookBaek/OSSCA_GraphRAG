import hydra
from omegaconf import DictConfig, OmegaConf
import openai
import os
from dotenv import load_dotenv
import boto3
import tiktoken
import pandas as pd
from utils.notion_sdk import config2notion
from utils.to_kg import to_kg_in_chunk
import json 
@hydra.main(
    config_path="config",
    config_name="base_prompt_v1.yaml",
    version_base="1.3",
)
def run(cfg: DictConfig):
    global_id = 0
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    prompt_cfg = cfg_dict["prompt_entity"]
    input_text = df["chunk_text"][global_id]

    entity_refernce_lines = []
    entity_descriptions = prompt_cfg.get("entity_types_descriptions", {})
    examples = "\n\n".join(cfg_dict["prompt_entity"]["examples"])
    for entity in prompt_cfg["entity_types"]:
        description = entity_descriptions.get(entity, "")
        entity_refernce_lines.append(f"• {entity}: {description}")
    entity_types_reference = "\n".join(entity_refernce_lines)

    prompt = prompt_cfg["prompt_template"].format(
        language=prompt_cfg["language"],
        tuple_delimiter=prompt_cfg["tuple_delimiter"],
        record_delimiter=prompt_cfg["record_delimiter"],
        completion_delimiter=prompt_cfg["completion_delimiter"],
        entity_types_reference=entity_types_reference,
        examples = examples,
        entity_types=", ".join(prompt_cfg["entity_types"]),
        input_text=input_text,
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
    print(" Entity Extraction Output:\n", entity_output)
    #print(entity_output)
    kg = to_kg_in_chunk(entity_output,global_id)
    with open("kg.json", "w", encoding="utf-8") as file:
        json.dump(kg, file, ensure_ascii=False, indent=4)
    config2notion(prompt_cfg)


if __name__ == "__main__":
    load_dotenv()
    csv_file_path = "./data/ustr_chunked.csv"
    # 파일이 없을 경우에만 다운로드
    if not os.path.exists(csv_file_path):
        print("preprocess.py를 먼저 실행시키세요")
        exit()
    df = pd.read_csv(csv_file_path, encoding="utf-8", delimiter=",")
    run()
