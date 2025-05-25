import json


def to_kg_in_chunk(output, gid):
    # print(output)
    TUPLE_DELEMITER = "<|>"
    RECORD_DELEMITER = "##"
    WRAPPER = "()"
    ENTITY_PREFIX, RELATIONSHIP_PREFIX, CONTENT_KEYWORDS_PREFIX = (
        '"entity"',
        '"relationship"',
        '"content_keywords"',
    )

    kg = {
        "entities": [],
        "relationships": [],
        "content_keywords": [],
    }
    source_id = f"Source{gid+1}"
    output_list = output.strip().split(RECORD_DELEMITER)
    for tmp_output in output_list:
        tmp_list = tmp_output.strip("\n").strip(WRAPPER).split(TUPLE_DELEMITER)
        if tmp_list[0] == ENTITY_PREFIX:
            tmp = {
                "entity_name": tmp_list[1],
                "entity_type": tmp_list[2],
                "description": tmp_list[3],
                "source_id": source_id,
            }
            kg["entities"].append(tmp)
        elif tmp_list[0] == RELATIONSHIP_PREFIX:
            tmp = {
                "src_id": tmp_list[1],
                "tgt_id": tmp_list[2],
                "description": tmp_list[3],
                "keywords": tmp_list[4],
                "weight": float(tmp_list[5]),
                "source_id": source_id,
            }
            kg["relationships"].append(tmp)
        elif tmp_list[0] == CONTENT_KEYWORDS_PREFIX:
            tmp = {
                "high_level_keywords": tmp_list[-1].strip().split(","),
                "source_id": source_id,
            }
            kg["content_keywords"].append(tmp)
        else:
            continue
    return kg



def to_kg_inter_chunk(output):
    # print(output)
    TUPLE_DELEMITER = "<|>"
    RECORD_DELEMITER = "##"
    WRAPPER = "()"
    ENTITY_PREFIX, RELATIONSHIP_PREFIX, CONTENT_KEYWORDS_PREFIX = (
        '"entity"',
        '"relationship"',
        '"content_keywords"',
    )

    relationships = []
    output_list = output.strip().split(RECORD_DELEMITER)
    for tmp_output in output_list:
        tmp_list = tmp_output.strip("\n").strip(WRAPPER).split(TUPLE_DELEMITER)
        if tmp_list[0] == RELATIONSHIP_PREFIX:
            tmp = {
                "src_id": tmp_list[1],
                "tgt_id": tmp_list[2],
                "description": tmp_list[3],
                "keywords": tmp_list[4],
                "weight": float(tmp_list[5]),
            }
            relationships.append(tmp)

    return relationships




if __name__ == "__main__":
    raw = """
    ("entity"<|>United States<|>Actor<|>The United States is a country that issues proclamations and regulations regarding trade and international relations, including actions under the African Growth and Opportunity Act (AGOA).)##("entity"<|>Islamic Republic of Mauritania<|>Actor<|>Mauritania is a country in sub-Saharan Africa that has been designated as a beneficiary country under the AGOA, subject to eligibility criteria set by the Trade Act.)##("entity"<|>Proclamation 9834<|>Regulation<|>Proclamation 9834 is a formal declaration issued by the President of the United States regarding trade actions under the AGOA, specifically addressing Mauritania's eligibility.)##("entity"<|>African Growth and Opportunity Act<|>Regulation<|>The AGOA is a United States trade act that enhances trade and economic relations with sub-Saharan African countries by providing them with duty-free access to the U.S. market.)##("entity"<|>Trade Act of 1974<|>Regulation<|>The Trade Act of 1974 is a U.S. law that allows the President to designate countries as beneficiaries for trade benefits based on their compliance with certain eligibility criteria.)##("entity"<|>section 506A<|>Regulation<|>Section 506A of the Trade Act outlines the criteria and processes for designating beneficiary sub-Saharan African countries under the AGOA.)##("entity"<|>section 112(c)<|>Regulation<|>Section 112(c) of the AGOA provides special rules for certain apparel articles imported from lesser developed beneficiary sub-Saharan African countries.)##("entity"<|>Africa Investment Incentive Act of 2006<|>Regulation<|>This act amended certain provisions of the AGOA, including special rules for apparel imports from lesser developed beneficiary countries.)##("entity"<|>lesser developed beneficiary sub-Saharan African countries<|>Region<|>This term refers to a classification of sub-Saharan African countries that are eligible for special trade treatment under the AGOA.)##("entity"<|>eligibility requirements<|>Policy<|>Eligibility requirements are the criteria set forth in the AGOA and the Trade Act that determine whether a country can be designated as a beneficiary.)##("entity"<|>beneficiary sub-Saharan African country<|>Policy<|>A beneficiary sub-Saharan African country is one that meets specific eligibility criteria to receive trade benefits under the AGOA.)##("relationship"<|>United States<|>Islamic Republic of Mauritania<|>The United States issued a proclamation affecting Mauritania's status as a beneficiary country under the AGOA based on its compliance with eligibility requirements.<|>trade regulation, beneficiary designation<|>8)##("relationship"<|>Proclamation 9834<|>Islamic Republic of Mauritania<|>Proclamation 9834 determined Mauritania's lack of compliance with the AGOA eligibility requirements, leading to the termination of its beneficiary status.<|>regulatory action, compliance<|>7)##("relationship"<|>Proclamation 9834<|>African Growth and Opportunity Act<|>Proclamation 9834 is issued under the authority of the AGOA, which governs the eligibility of countries for trade benefits.<|>regulatory framework, trade benefits<|>9)##("relationship"<|>Trade Act of 1974<|>African Growth and Opportunity Act<|>The Trade Act of 1974 provides the legal foundation for the AGOA, allowing the designation of beneficiary countries.<|>legal framework, trade policy<|>9)##("relationship"<|>section 506A<|>Islamic Republic of Mauritania<|>Section 506A outlines the criteria for determining Mauritania's eligibility as a beneficiary country under the AGOA.<|>eligibility criteria, regulatory compliance<|>8)##("relationship"<|>section 112(c)<|>lesser developed beneficiary sub-Saharan African countries<|>Section 112(c) provides special trade rules for apparel imports from lesser developed beneficiary sub-Saharan African countries.<|>trade rules, special treatment<|>7)##("relationship"<|>Africa Investment Incentive Act of 2006<|>African Growth and Opportunity Act<|>The Africa Investment Incentive Act of 2006 amended provisions of the AGOA, impacting trade rules for beneficiary countries.<|>legislative amendment, trade policy<|>8)##("content_keywords"<|>trade, regulation, eligibility, AGOA, Mauritania, proclamation, compliance, beneficiary<|>trade, regulation, eligibility, AGOA, Mauritania)##("content_keywords"<|>high_level_keywords<|>trade policy, international relations, compliance, legislative framework)##<|COMPLETE|>
    """
    kg = to_kg_in_chunk(raw, gid=0)
    # 1) 딕셔너리를 JSON 문자열로 변환

    # 2) 파일로 저장하기
    with open("kg.json", "w", encoding="utf-8") as file:
        json.dump(kg, file, ensure_ascii=False, indent=4)

    # print(kg["relationships"])

    # for relation in kg["relationships"]:
    #     print(relation)
    #     print("#######################")
    # kg = {"entities":[],
    #       "relationships":[]
    #       }
    # # print(raw.strip().split("##")[0].strip("()").split("<|>"))
    # tmp_list = raw.strip().split("##")[0].strip("()").split("<|>")

    # if tmp_list[0].strip('""') == 'entity':
    #     tmp = {"entity_name" : tmp_list[1],
    #            "entity_type" : tmp_list[2],
    #            "description" : tmp_list[3]

    #            }
    #     kg["entities"].append(tmp)

    # tmp_list = raw.strip().split("##")[-4].strip("()").split("<|>")
    # if tmp_list[0].strip('""') == 'relationship':
    #     tmp = {"src_id" : tmp_list[1],
    #            "tgt_id" : tmp_list[2],
    #            "description" : tmp_list[3],
    #             "keywords": tmp_list[4],
    #            "weight" : float(tmp_list[5])
    #            }
    #     kg["relationships"].append(tmp)
    # print(kg)
