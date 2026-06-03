"""RAG 流水线端到端测试脚本。

加载 PDF 文档 → 文本切分 → 打印切分结果，验证 loader 和 splitter 是否正常工作。
直接用 `python AiLearning/rag/test.py` 运行。
"""
import AiLearning.rag.loader as loader
import AiLearning.rag.splitter as splitter
import os

# 获取项目根目录的绝对路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == '__main__':
    # 加载两篇 PDF 文档
    # docs1 = loader.load_document(os.path.join(BASE_DIR, 'AiLearning/docs/商户征信项目.pdf'))
    docs = loader.load_document(os.path.join(BASE_DIR, 'AiLearning/docs/新商户平台概念说明.pdf'))
    # docs = docs1 + docs2
    # 按 500 字符切分，重叠 50 字符
    chunks = splitter.split_documents(docs)
    print(f"原始文档数：{len(docs)}")
    print(f"切分后块数：{len(chunks)}")
    print(f"第 21 块内容：{chunks[20].page_content}")

