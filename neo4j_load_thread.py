import pandas as pd
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import concurrent.futures

# === NODE CREATION ===
def create_node(tx, label, props):
    query = f"""
    MERGE (n:{label} {{id: $id}})
    SET n += $props
    """
    tx.run(query, id=props['id'], props=props)

def load_csv_as_nodes(csv_path, label):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if 'node' in df.columns:
        df.rename(columns={'node': 'id'}, inplace=True)

    with driver.session(database = base_database) as session:
        for _, row in df.iterrows():
            props = row.dropna().to_dict()
            if 'id' not in props:
                continue
            session.execute_write(create_node, label, props)

# === RELATIONSHIP CREATION ===
def create_relationship(tx, node1_id, node2_id, rel_type, props):
    query = f"""
    MATCH (a {{id: $node1_id}})
    MATCH (b {{id: $node2_id}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r += $props
    """
    tx.run(query, node1_id=node1_id, node2_id=node2_id, props=props)

def infer_relationship_type(filename):
    basename = os.path.splitext(filename)[0]
    category = basename.replace("Edges", "").strip(" ()").upper().replace(" ", "_")
    return f"CONNECTED_{category}"

def load_relationships_from_csv(csv_path, rel_type):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if 'node1' not in df.columns or 'node2' not in df.columns:
        print(f"⚠️ Skipping {csv_path}: missing 'node1' or 'node2'")
        return

    with driver.session(database = base_database) as session:
        for _, row in df.iterrows():
            props = row.dropna().to_dict()
            node1 = props.pop('node1')
            node2 = props.pop('node2')
            session.execute_write(create_relationship, node1, node2, rel_type, props)

    print(f"✅ {rel_type} relationships loaded.")

def load_all_relationships_from_directory(edge_dir):
    for fname in os.listdir(edge_dir):
        if fname.lower().endswith('.csv'):
            path = os.path.join(edge_dir, fname)
            rel_type = infer_relationship_type(fname)
            print(f"🔗 Loading {fname} as relationship type :{rel_type}")
            load_relationships_from_csv(path, rel_type)

# === TEMPORAL DATA HANDLING ===
def create_event_constrain(tx):
    tx.run("CREATE CONSTRAINT event_date_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.date IS UNIQUE;")

def create_event(tx, date):
    tx.run("MERGE (:Event {date: $date})", date=date)

def create_temporal_relationship(tx, node_id, date, value, rel_type):
    query = f"""
    MATCH (n {{id: $node_id}})
    MERGE (e:Event {{date: $date}})
    MERGE (n)-[r:{rel_type}]->(e)
    SET r.value = $value
    """
    tx.run(query, node_id=node_id, date=date, value=value)

def load_temporal_csv(file_path):
    df = pd.read_csv(file_path)
    df.columns = [c.strip() for c in df.columns]

    # ✅ Normalize date format
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')

    rel_type = os.path.splitext(os.path.basename(file_path))[0].strip().upper().replace(" ", "_")

    with driver.session(database = base_database) as session:
        for _, row in df.iterrows():
            date = row['Date']
            if pd.isnull(date):
                continue
            session.execute_write(create_event, date)
            for node_id in row.index:
                if node_id == 'Date':
                    continue
                value = row[node_id]
                if pd.notnull(value):
                    session.execute_write(
                        create_temporal_relationship,
                        node_id, date, float(value), rel_type
                    )
    print(f"📈 Loaded temporal data from {file_path} as :{rel_type} relationships")

# === MAIN ===
def supplychain_main():
    # Step 0: Ensure uniqueness constraint
    with driver.session(database = base_database) as session:
        session.execute_write(create_event_constrain)

    # Step 1: Load nodes
    nodes_dir = './data/supplychainGraph/Nodes/'
    for file in os.listdir(nodes_dir):
        if file.endswith('.csv'):
            label = os.path.splitext(file)[0].capitalize()
            path = os.path.join(nodes_dir, file)
            print(f"📄 Loading node file: {file} as label :{label}")
            load_csv_as_nodes(path, label)

    # Step 2: Load relationships
    edge_dir = './data/supplychainGraph/Edges'
    load_all_relationships_from_directory(edge_dir)

    # Step 3: Load temporal data
    temporal_dir = './data/supplychainGraph/Temporal Data/Unit/'
    for file in os.listdir(temporal_dir):
        if file.endswith('.csv'):
            path = os.path.join(temporal_dir, file)
            load_temporal_csv(path)

    driver.close()
    print("🏁 All nodes, relationships, and temporal data loaded successfully.")



def supplychain_main_parallel():
    # 0. Constraint
    with driver.session(database=base_database) as session:
        session.execute_write(create_event_constrain)

    # 1. Nodes
    nodes_dir = './data/supplychainGraph/Nodes/'
    node_files = [f for f in os.listdir(nodes_dir) if f.endswith('.csv')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        for fname in node_files:
            
            path = os.path.join(nodes_dir, fname)
            label = os.path.splitext(fname)[0].capitalize()
            print(f"📄 Loading node file: {fname} as label :{label}")
            executor.submit(load_csv_as_nodes, path, label)

    # 2. Relationships
    edges_dir = './data/supplychainGraph/Edges'
    edge_files = [f for f in os.listdir(edges_dir) if f.endswith('.csv')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        for fname in edge_files:
            path = os.path.join(edges_dir, fname)
            rel_type = infer_relationship_type(fname)
            print(f"🔗 Loading {fname} as relationship type :{rel_type}")
            executor.submit(load_relationships_from_csv, path, rel_type)

    # 3. Temporal
    temp_dir = './data/supplychainGraph/Temporal Data/Unit/'
    temp_files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        for fname in temp_files:
            path = os.path.join(temp_dir, fname)
            print(f"📈 Loading temporal data from {fname}")
            executor.submit(load_temporal_csv, path)

    print("🏁 All supplychain data loaded in parallel.")




'''
여기서부터는 USTR Press Release 관련된 부분
'''




def create_document_and_link_event(tx,doc):
    tx.run("""
        MERGE (e:Event {date: $date})
        MERGE (d:Document {doc_id: $doc_id})
        SET d += {
            url: $url,
            content: $content,
            title : $title,
            date: $date
        }
        MERGE (d)-[:OCCURRED_ON]->(e)
    """,doc_id = doc["doc_id"], title=doc["title"], date=doc["date"], url=doc["url"], content=doc["content"])

# === Load and Normalize CSV ===
def load_documents_with_event_links(doc_csv_path):
    df = pd.read_csv(doc_csv_path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Rename and normalize
    required = {'title', 'date', 'url', 'content'}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing required columns: {required - set(df.columns)}")

    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')

    with driver.session(database = base_database) as session:
        for idx, row in df.iterrows():
            if pd.isnull(row['date']):
                print(f"⚠️ Skipping due to invalid date: {row.to_dict()}")
                continue
            doc = row.dropna().to_dict()
            session.execute_write(create_document_and_link_event, doc)

    print(f"📘 Loaded documents and linked them to :Event nodes.")


# === DOCUMENT LOADER (PARALLEL) ===
def _insert_document(doc):
    print(f"📄 Inserting document: {doc['title']}")
    with driver.session(database=base_database) as session:
        session.execute_write(create_document_and_link_event, doc)


def load_documents_with_event_links_parallel(path):
    df = pd.read_csv(path,encoding='utf-8', delimiter=",")
    df.columns = [c.strip().lower() for c in df.columns]
    required = {'doc_id','title', 'date', 'url', 'content'}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing required columns: {required - set(df.columns)}")

    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
    docs = []
    for _, row in df.iterrows():
        if pd.isnull(row['date']):
            print(f"⚠️ Skipping due to invalid date: {row.to_dict()}")
            continue
        docs.append(row.dropna().to_dict())

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(_insert_document, doc) for doc in docs]
        for fut in concurrent.futures.as_completed(futures):
            fut.result()

    print(f"📘 Documents loaded and linked in parallel from {os.path.basename(path)}.")



def clear_database(tx):
    # Remove all nodes and relationships
    tx.run("MATCH (n) DETACH DELETE n")


# Main Entry Point

if __name__ == "__main__":
    load_dotenv()
    # === Neo4j Config ===
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    base_database = os.getenv('NEO4J_BASE_DATABASE')
    num_workers = int(os.getenv('NUM_WORKERS', 12))  # Default to 4 if not set

    driver = GraphDatabase.driver(uri, auth=(user, password))


    # with driver.session(database=base_database) as session:
    #     session.execute_write(clear_database)
    # print("🗑️ Cleared all existing nodes and relationships from database.")

    #supplychain_main_parallel()
    load_documents_with_event_links_parallel('./data/ustr_2023_press_releases_tailed.csv')

    driver.close()

