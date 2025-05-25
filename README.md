
## Directory 구조
``` 

.
├── apply_faiss.py
├── config #prompt 저장
│   ├── base_prompt_v1.yaml
│   ├── base_test.yaml
│   └── base.yaml
├── data #csv데이터 저장 
│   ├── ustr_2023_press_releases_tailed.csv #8월까지만의 press
│   ├── ustr_2023_press_releases.csv
│   └── ustr_chunked.csv #8월까지만의 press를 chunking
├── faiss #faiss인덱스 파일
│   ├── flatl2.index
│   └── idmap.index
├── from_notion.py #notion에서 config가져와서 실행하는 파일
├── main.py #prompt를 돌리고 Neo4j에 적재하는 코드 -> new
├── main_thread.py #main의  thread버전 -> new
├── preprocess.py #데이터 전처리 코드 
├── prompt.py #prompt테스트용 코드
├── README.md
└── utils
    ├── chunking.py #chunking 코드
    ├── faiss_utils.py #faiss 관련 코드
    ├── neo4j_utils.py #Neo4j 적재 관련 코드 -> new
    ├── notion_sdk.py
    └── to_kg.py #prompt결과를 lighrag의 kg형태로 가공 -> new

``` 

# What's New

## 수정사항
디렉토리 구조가 복잡해서 좀 수정했습니다.  
데이터를 8월까지만의 데이터로 청킹을 다시 했습니다.
돌아가는 코드는 모두 8월까지의 데이터입니다.


## config/prompt
prompt에 ```updated_by``` 항목이 추가되었습니다.  
수정하셨다면 이 부분에 본인의 이름이나 id를 기입해주시면 됩니다.

## to_kg.py
to_kg라는 유틸이 추가되었습니다.  
이건 prompt의 결과로 나온 데이터를 lighrag의 kg형태로 변환하는 코드입니다.

## neo4j_utils.py
neo4j python api를 이용해서 팀2분들이 작성해주신 적재 코드를 살짝 수정했습니다.


## main & main_thread
main은 neo4j에 팀2분들이 준비하신 것에 맞춰서 문서와 prompt 결과를 적재합니다.  
main_thread는 이걸 스레딩버전으로 수정하여서 더 빠르게 처리할 수 있도록 한 것입니다.




## notion sdk
notino_sdk 파일은 notion2config, config2notion 2개가 핵심입니다.  
``` config2notion```   
prompt_entity cfg를 입력으로 주면 해당 내용을 notion에 업데이트함

``` notion2config```  
id를 입력으로 주면 해당 id를 가진 row를 notion database에서 꺼내옴  
이때 중복 id가 있으면 최신 날짜에서 꺼내옴

###  유의사항
notion api와 연동하면 notion table에 정의해놓은 이름에 맞도록 key를 잡아줘야합니다.  
만약 다른 key를 추가하고싶다면 알려주시면 이를 반영할 예정입니다.

---

## simple.py & baseline.py
``` simple.py```  
simple은 entity description, example 2개 field가 없이 작동하는 코드입니다.  


``` baseline.py```  
baseline은  이와 달리 entity description, example 2개가 field에 있을때 작동하는 코드입니다. 



## requirements
- pandas==2.1.4
- hydra
- openai
- numpy
- notion-client
- python-dotenv
- boto3
- tiktoken
- faiss (optional, conda로 설치해야해서 안쓰실 분들은 설치 안하셔도 됩니다)
- neo4j #new