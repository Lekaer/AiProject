import os
import sys

# 确保项目根目录在 sys.path 中

from AiLearning.agents.rag_agent import RAGAgent


if __name__ == '__main__':
    agent = RAGAgent()
    question = "商户的哪些模块和功能涉及数据同步"
    collection_name = "col_aaf01d1195d17942"
    result = agent.execute(question, collection_name=collection_name)
    print(result.answer)