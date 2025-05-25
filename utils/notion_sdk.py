import os
import yaml
from notion_client import Client
from dotenv import load_dotenv
import datetime
import yaml
import yaml
import ast
import re
from zoneinfo import ZoneInfo


# PyYAML에서 리터럴 스타일 문자열을 위한 클래스 정의
class LiteralString(str):
    pass


# 리터럴 스타일 문자열 표현 방식 등록
def represent_literal_str(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(LiteralString, represent_literal_str)


def parse_string_to_python_object(text):
    """
    문자열을 분석하여 리스트 또는 딕셔너리 형태로 변환합니다.
    내부 콘텐츠는 문자열 그대로 유지합니다.
    """
    # 공백 제거
    # text = text.strip()

    # 문자열이 리스트 형태인지 확인
    if (text.startswith("[") and text.endswith("]")) or (
        text.startswith("['") and text.endswith("']")
    ):
        try:
            # 직접 리스트로 변환 시도
            result = ast.literal_eval(text)

            return result
        except (SyntaxError, ValueError) as e:
            # 추가 처리: 문자열을 수정하여 다시 시도
            try:
                # 작은따옴표와 큰따옴표 문제 처리
                modified_text = re.sub(r"'(\w+)':", r'"\1":', text)
                result = ast.literal_eval(modified_text)
                return result
            except (SyntaxError, ValueError):
                pass

    # 문자열이 딕셔너리 형태인지 확인
    if (text.startswith("{") and text.endswith("}")) or (
        text.startswith("{'") and text.endswith("'}")
    ):
        try:
            # 직접 딕셔너리로 변환 시도
            result = ast.literal_eval(text)
            return result
        except (SyntaxError, ValueError) as e:
            print(f"딕셔너리 변환 중 오류 발생: {e}")

            # 추가 처리: 작은따옴표를 큰따옴표로 변환하여 JSON으로 파싱 시도
            try:
                import json

                # 작은따옴표를 큰따옴표로 대체하여 유효한 JSON 형식으로 만들기
                json_text = text.replace("'", '"')
                result = json.loads(json_text)
                return result
            except json.JSONDecodeError:
                pass

    # 특수한 형식의 리스트인 경우 (예: ['문자열1', '문자열2', ...])
    list_pattern = r"\['([^']*)'(?:,\s*'([^']*)')*\]"
    if re.match(list_pattern, text):
        try:
            # 정규식으로 직접 파싱
            items = re.findall(r"'([^']*)'", text)
            return items
        except Exception:
            pass

    # 특수한 형식의 딕셔너리인 경우 (예: {'키1': '값1', '키2': '값2', ...})
    dict_pattern = (
        r"\{(?:'([^']*)':\s*'?([^'{}]*)'?(?:,\s*'([^']*)':\s*'?([^'{}]*)'?)*)}"
    )
    if re.match(dict_pattern, text):
        try:
            # 정규식으로 직접 파싱
            pairs = re.findall(r"'([^']*)':\s*'?([^',{}]*)'?", text)
            return {k: v.strip("'") for k, v in pairs}
        except Exception:
            pass
    # 해당없으면 원본 반환
    return text  # 원본 문자열 반환


def to_rich_text(val):
    MAX_RICH_TEXT_LEN = 2000
    """문자열을 Notion rich_text 포맷으로, 2000자씩 분할하여 리스트로 반환"""
    if not val:
        return []
    text_str = str(val)
    # text_str = str(val).encode('utf-8').decode('unicode_escape')
    # 2000자씩 청크 분할
    chunks = [
        text_str[i : i + MAX_RICH_TEXT_LEN]
        for i in range(0, len(text_str), MAX_RICH_TEXT_LEN)
    ]
    # 각 청크를 rich_text 객체로 매핑
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


def to_date(val):
    """
    val: datetime.datetime 또는 None
    반환: Notion API용 {"start": ISO_문자열+09:00} 또는 None
    """
    if not val:
        return None

    # 1) tz 정보가 없으면 UTC라고 간주
    if val.tzinfo is None:
        val = val.replace(tzinfo=ZoneInfo("UTC"))

    # 2) Asia/Seoul 로 변환
    seoul_dt = val.astimezone(ZoneInfo("Asia/Seoul"))

    # 3) Notion이 요구하는 포맷으로
    return {"start": seoul_dt.isoformat()}


def dict_to_props(row_dict, notion_schema):
    props = {}
    # title 필드 자동 매핑
    title_col = next(
        (k for k, v in notion_schema.items() if v["type"] == "title"), None
    )

    for key, val in row_dict.items():
        if key not in notion_schema:
            continue

        prop_type = notion_schema[key]["type"]

        if key == "id" and title_col:
            props[title_col] = {"title": to_rich_text(val)}
        elif prop_type == "rich_text":
            props[key] = {"rich_text": to_rich_text(val)}
        elif prop_type == "number":
            props[key] = {"number": val}
        elif prop_type == "date":
            props[key] = {"date": to_date(val)}
        elif prop_type == "checkbox":
            props[key] = {"checkbox": bool(val)}
        elif prop_type == "url":
            props[key] = {"url": str(val) if val else None}
        else:
            print(f"⚠️ '{key}' → 타입 '{prop_type}'은 아직 미지원 → 무시")
        now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
        # to_date 함수가 datetime 객체를 처리하도록 가정
        props["last_updated"] = {"date": to_date(now)}
    return props


def config2notion(cfg):
    load_dotenv()
    # ─── 1) 설정 ───
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")  # Integration 토큰
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")  # 대상 데이터베이스 ID
    for key in cfg:
        if isinstance(cfg[key], list):
            for idx in range(len(cfg[key])):
                cfg[key][idx] = str(cfg[key][idx])

    # ─── 2) Notion 클라이언트 초기화 ───
    notion = Client(auth=NOTION_TOKEN)
    db_info = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)

    notion_schema = db_info["properties"]
    props = dict_to_props(cfg, notion_schema)
    notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)


def props_to_dict(properties, notion_schema):
    """
    Notion 프로퍼티를 딕셔너리로 변환

    Args:
        properties: Notion API에서 반환된 페이지의 properties 객체
        notion_schema: Notion 데이터베이스의 스키마 정보

    Returns:
        dict: 간단한 키-값 형태의 딕셔너리
    """
    result = {}

    # 스키마에 기반한 역변환
    for key, schema_info in notion_schema.items():
        prop_type = schema_info["type"]

        # 해당 프로퍼티가 페이지에 없으면 스킵
        if key not in properties:
            continue

        prop = properties[key]

        if prop_type == "title":
            title_array = prop["title"]
            result[key] = title_array[0]["plain_text"] if title_array else ""

        elif prop_type == "rich_text":
            # 모든 rich_text 요소를 연결하여 전체 텍스트 추출
            rich_text_array = prop["rich_text"]
            if rich_text_array:
                full_text = "".join([text["plain_text"] for text in rich_text_array])
                result[key] = full_text
            else:
                result[key] = ""

        elif prop_type == "number":
            result[key] = prop["number"]

        elif prop_type == "date":
            continue  # 날짜는 받아오지마 다시 작성할때 에러 생김
            date_obj = prop["date"]
            result[key] = date_obj["start"] if date_obj else None

        elif prop_type == "checkbox":
            result[key] = prop["checkbox"]

        elif prop_type == "url":
            result[key] = prop["url"]

        elif prop_type == "select":
            select_obj = prop["select"]
            result[key] = select_obj["name"] if select_obj else None

        elif prop_type == "multi_select":
            multi_select = prop["multi_select"]
            result[key] = (
                [item["name"] for item in multi_select] if multi_select else []
            )

    # id 필드 특별 처리 (title 필드로 매핑된 경우)
    title_col = next(
        (k for k, v in notion_schema.items() if v["type"] == "title"), None
    )
    if title_col and title_col in properties:
        title_array = properties[title_col]["title"]
        result["id"] = title_array[0]["plain_text"] if title_array else ""

    return result


def save_to_yaml_file(
    prompt_config_dict, model_config_dict, file_path, root_key="prompt_entity"
):
    """
    딕셔너리를 원하는 형식의 YAML 파일로 저장

    Args:
        config_dict: 저장할 딕셔너리
        file_path: 저장할 파일 경로
        root_key: YAML 파일의 루트 키
    """
    # 루트 키를 가진 딕셔너리 생성
    yaml_dict = {root_key: prompt_config_dict}
    yaml_dict.update(model_config_dict)

    # YAML 설정
    class IndentDumper(yaml.Dumper):
        """들여쓰기 설정을 위한 커스텀 Dumper"""

        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    # # 특별 처리가 필요한 필드
    for key in ["description", "prompt_template", "system_prompt"]:
        if (
            key in prompt_config_dict
            and isinstance(prompt_config_dict[key], str)
            and "\n" in prompt_config_dict[key]
        ):
            prompt_config_dict[key] = LiteralString(prompt_config_dict[key])

    # YAML 파일로 저장
    # print(yaml_dict)
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(
            yaml_dict,
            f,
            Dumper=IndentDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=4,
        )

    print(f"YAML 파일이 '{file_path}'에 성공적으로 저장되었습니다.")
    return yaml_dict


def notion2config(target_id, cfg_path, model_cfg_path="./config/base.yaml"):
    load_dotenv()
    # ─── 1) 설정 ───
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")  # Integration 토큰
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")  # 대상 데이터베이스 ID

    # ─── 2) Notion 클라이언트 초기화 ───
    notion = Client(auth=NOTION_TOKEN)
    db_info = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    notion_schema = db_info["properties"]
    response = notion.databases.query(
        **{
            "database_id": NOTION_DATABASE_ID,
            "filter": {"property": "id", "title": {"equals": target_id}},
            "sorts": [{"property": "last_updated", "direction": "descending"}],
            "page_size": 1,  # 가장 최신 한 건만
        }
    )

    # 3) 결과 확인
    results = response.get("results", [])
    if not results:
        print("해당 id의 페이지가 없습니다.")
        return None
    else:
        page = results[0]
        cfg = props_to_dict(page["properties"], notion_schema)
        prompt_cfg = {}
        for key in cfg:
            tmp = cfg[key]
            tmp_object = parse_string_to_python_object(tmp)

            prompt_cfg[key] = tmp_object  # 새로 저장

        with open(model_cfg_path, "r", encoding="utf-8") as f:
            model_cfg = yaml.safe_load(f)
        save_to_yaml_file(prompt_cfg, model_cfg, cfg_path)


if __name__ == "__main__":
    # notion2config(target_id="entity_extraction_prompt_v1",cfg_path="./config/test.yaml")
    notion2config(target_id="simple", cfg_path="./config/simple_test.yaml")
    # config2notion()
