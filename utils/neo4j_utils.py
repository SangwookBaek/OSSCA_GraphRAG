from datetime import datetime
import os
import boto3
import pandas as pd
from neo4j import GraphDatabase
import itertools
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from collections import ChainMap

def convert_date(date_str):
    # 이미 YYYY-MM-DD 형식이면 그대로 반환
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str
    
    # 아니면 "월 일, 연도" 형식으로 변환 시도
    try:
        dt = datetime.strptime(date_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # 다른 형식일 수도 있으므로 추가 처리
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return date_str  # 이미 원하는 형식이므로 그대로 반환
        except ValueError:
            # 여기서 다른 형식들도 추가 가능
            raise ValueError(f"지원하지 않는 날짜 형식입니다: {date_str}")

####################
# For prerequisite #
####################
def check_document(tx, doc_id):
    result = tx.run(
        """
        MATCH (d:Document {doc_id: $doc_id})
        RETURN COUNT(d) AS DOC_COUNT
        """,
        doc_id=doc_id,
    ).single()

    if result["DOC_COUNT"] != 1:
        raise ValueError(f"Document with doc_id: {doc_id} not exist; unexpected error")


def check_chunk(tx, chunk_number, doc_id):
    result = tx.run(
        """
        MATCH (c:Chunk {chunk_number: $chunk_number, doc_id: $doc_id})
        RETURN COUNT(c) AS CHUNK_COUNT
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
    ).single()

    if result["CHUNK_COUNT"] != 1:
        raise ValueError(
            f"Chunk with doc_id: {doc_id} / chunk_number: {chunk_number} not exist; unexpected error"
        )


# call when connect relationship between entities
# it can return error when does not in entity list, but in relationship (source or target)
def check_chunk_to_entity(tx, chunk_number, doc_id, source_entity, target_entity):
    source_result = tx.run(
        """
        MATCH (c {chunk_number: $chunk_number, doc_id: $doc_id})-[:CONTAINS_ENTITY]->(e {name: $source_entity})
        WITH COUNT(e) AS SOURCE_COUNT
        RETURN SOURCE_COUNT
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
        source_entity=source_entity,
    ).single()
    if source_result["SOURCE_COUNT"] != 1:
        raise ValueError(
            f"Relationship with doc_id: {doc_id} / chunk_number: {chunk_number} / entity: {source_entity} not exist; unexpected error"
        )

    target_result = tx.run(
        """
        MATCH (c {chunk_number: $chunk_number, doc_id: $doc_id})-[:CONTAINS_ENTITY]->(e {name: $target_entity})
        WITH COUNT(e) AS TARGET_COUNT
        RETURN TARGET_COUNT
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
        target_entity=target_entity,
    ).single()
    if target_result["TARGET_COUNT"] != 1:
        raise ValueError(
            f"Chunk with doc_id: {doc_id} / chunk_number: {chunk_number} / entity: {target_entity} not exist; unexpected error"
        )


#####################
# For postrequisite #
#####################
def check_document_node_count(session, expected_count):
    result = session.run("MATCH (n:Document) RETURN count(n) AS COUNT").single()
    count = result["COUNT"]
    if count != expected_count:
        raise ValueError(
            f"Document node count mismatch: expected {expected_count}, got {count}"
        )
    else:
        print(f"✅ Correct document node count : {count}")


def check_entity_node_count(session, doc_id, chunk_number, expected_count):
    result = session.run(
        """
        MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:Chunk {chunk_number: $chunk_number})-[:CONTAINS_ENTITY]->(e)
        RETURN count(e) AS COUNT
        """,
        doc_id=doc_id,
        chunk_number=chunk_number,
    ).single()

    count = result["COUNT"]
    if count != expected_count:
        raise ValueError(
            f"Entity node count mismatch for doc_id: {doc_id}, chunk_number: {chunk_number}. Expected {expected_count}, got {count}"
        )
    else:
        print(
            f"✅ Correct entity node count for doc_id: {doc_id}, chunk_number: {chunk_number} -> count: {count}"
        )


def check_entity_relationship_count(session, doc_id, chunk_number, expected_count):
    result = session.run(
        """
        MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:Chunk {chunk_number: $chunk_number})-[:CONTAINS_ENTITY]->()-[r:RELATED_TO]->()
        RETURN count(r) AS COUNT
        """,
        doc_id=doc_id,
        chunk_number=chunk_number,
    ).single()

    count = result["COUNT"]
    if count != expected_count:
        raise ValueError(
            f"Entity relationship count mismatch for doc_id: {doc_id}, chunk_number: {chunk_number}. Expected {expected_count}, got {count}"
        )
    else:
        print(
            f"✅ Correct entity relationship count for doc_id: {doc_id}, chunk_number: {chunk_number} -> count: {count}"
        )


# drop all nodes & relationships
def delete_all_nodes(tx):
    tx.run("MATCH (n) DETACH DELETE n")


# set constraint in document / chunk
# TODO: add constraint to entity? for unique {entity_type, entity_name} <-
def set_constraints(tx):
    tx.run(
        """
        CREATE CONSTRAINT document_doc_id_unique IF NOT EXISTS
        FOR (d:Document)
        REQUIRE d.doc_id IS UNIQUE
        """
    )
    tx.run(
        """
        CREATE CONSTRAINT chunk_unique_per_document IF NOT EXISTS
        FOR (c:Chunk)
        REQUIRE (c.doc_id, c.chunk_number) IS UNIQUE
        """
    )


def insert_document_node(tx, doc_id, date, title, content, url):
    tx.run(
        """
        MERGE (d:Document {doc_id: $doc_id})
        ON CREATE SET d.date = $date, d.title = $title, d.content = $content, d.url = $url
        """,
        doc_id=doc_id,
        date=date,
        title=title,
        content=content,
        url=url,
    )


def insert_chunk_node(tx, chunk_number, doc_id, keyword_variables):
    check_document(tx, doc_id)
    tx.run(
        """
        MERGE (c:Chunk {chunk_number: $chunk_number, doc_id: $doc_id})
        ON CREATE SET c.keyword_variables = $keyword_variables

        MERGE (d:Document {doc_id: $doc_id})
        MERGE (d)-[r:HAS_CHUNK {doc_id: $doc_id, chunk_id: $chunk_number}]->(c)
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
        keyword_variables=keyword_variables,
    )


def insert_entity_node(tx, chunk_number, doc_id, entity_name, entity_type, description):
    check_chunk(tx, chunk_number, doc_id)
    # overwrite
    # tx.run(
    #    f"""
    #    MATCH (c:Chunk {{chunk_number: $chunk_number, doc_id: $doc_id}})
    #    MERGE (e:{entity_type} {{name: $entity_name}})
    #    ON CREATE SET e.description = $description
    #    MERGE (c)-[:CONTAINS_ENTITY]->(e)
    #    """, chunk_number=chunk_number, doc_id=doc_id, entity_name=entity_name, description=description
    # )

    # create
    tx.run(
        f"""
        MATCH (c:Chunk {{chunk_number: $chunk_number, doc_id: $doc_id}})
        CREATE (e:{entity_type} {{name: $entity_name, description: $description}})
        CREATE (c)-[:CONTAINS_ENTITY]->(e)
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
        entity_name=entity_name,
        description=description,
    )


def insert_entity_relationship(
    tx,
    chunk_number,
    doc_id,
    source_entity,
    target_entity,
    description,
    keywords,
    strength,
):
    check_chunk_to_entity(tx, chunk_number, doc_id, source_entity, target_entity)
    tx.run(
        """
        MATCH (c:Chunk {chunk_number: $chunk_number, doc_id: $doc_id})
        MATCH (c)-[:CONTAINS_ENTITY]->(e1 {name: $source_entity})
        MATCH (c)-[:CONTAINS_ENTITY]->(e2 {name: $target_entity})
        MERGE (e1)-[:RELATED_TO {
            source_entity: $source_entity,
            target_entity: $target_entity,
            description: $description,
            keywords: $keywords,
            strength: $strength
        }]->(e2)
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
        source_entity=source_entity,
        target_entity=target_entity,
        description=description,
        keywords=keywords,
        strength=strength,
    )


def insert_ustr_document(doc_id, row):
    session.execute_write(
        insert_document_node,
        doc_id,
        convert_date(row["date"]),
        row["title"],
        row["content"],
        row["url"],
    )




if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    
    # 4. Drop all data in database
    load_dotenv()

    """
    Document Data Insertion
    """
    full_csv_path = "./ustr_2023_press_releases.csv"
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





def check_chunk_to_entity_single(tx, chunk_number, doc_id, entity):
    source_result = tx.run(
        """
        MATCH (c {chunk_number: $chunk_number, doc_id: $doc_id})-[:CONTAINS_ENTITY]->(e {name: $source_entity})
        WITH COUNT(e) AS SOURCE_COUNT
        RETURN SOURCE_COUNT
        """,
        chunk_number=chunk_number,
        doc_id=doc_id,
        source_entity=entity,
    ).single()
    if source_result["SOURCE_COUNT"] != 1:
        raise ValueError(
            f"Relationship with doc_id: {doc_id} / chunk_number: {chunk_number} / entity: {entity} not exist; unexpected error"
        )


def insert_inter_relationship(
    tx,
    s_chunk_number,
    s_doc_id,
    t_chunk_number,
    t_doc_id,
    source_entity,
    target_entity,
    description,
    keywords,
    strength,
):
    #일단 나눠서 체크
    check_chunk_to_entity_single(tx, s_chunk_number, s_doc_id, source_entity) #souce
    check_chunk_to_entity_single(tx, t_chunk_number, t_doc_id, source_entity) #target 
    tx.run(
        """
        MATCH (s_c:Chunk {chunk_number: $s_chunk_number, doc_id: $s_doc_id})
        MATCH (s_c)-[:CONTAINS_ENTITY]->(e1 {name: $source_entity})

        MATCH (t_c:Chunk {chunk_number: $t_chunk_number, doc_id: $t_doc_id})
        MATCH (t_c)-[:CONTAINS_ENTITY]->(e2 {name: $target_entity})
        MERGE (e1)-[:RELATED_TO {
            source_entity: $source_entity,
            target_entity: $target_entity,
            description: $description,
            keywords: $keywords,
            strength: $strength
        }]->(e2)
        """,
        s_chunk_number=s_chunk_number,
        s_doc_id=s_doc_id,
        t_chunk_number=t_chunk_number,
        t_doc_id=t_doc_id,
        source_entity=source_entity,
        target_entity=target_entity,
        description=description,
        keywords=keywords,
        strength=strength,
    )





def fetch_chunk_entities(tx, chunk_number, doc_id):
    query = """
    MATCH (c:Chunk {chunk_number: $chunk_number, doc_id: $doc_id})
          -[:CONTAINS_ENTITY]->(e)
    RETURN 
        properties(e) AS props,
        labels(e)   AS labels   // c 노드에 달린 라벨들의 리스트
    """
    result = tx.run(query, chunk_number=chunk_number, doc_id=doc_id)
    # list(result) 을 찍어보면 몇 개 레코드가 돌아오는지 알 수 있습니다.
    return [record.data() for record in result]
    