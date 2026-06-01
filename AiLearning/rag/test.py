import AiLearning.rag.loader as loader
import AiLearning.rag.splitter as splitter
import os

# 获取当前脚本所在目录，拼接成绝对路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == '__main__':
    print(os.getcwd())
    print(os.path.join(BASE_DIR, 'AiLearning/docs/商户征信项目.pdf'))
    docs1 = loader.load_document(os.path.join(BASE_DIR, 'AiLearning/docs/商户征信项目.pdf'))
    docs2 = loader.load_document(os.path.join(BASE_DIR, 'AiLearning/docs/新商户平台概念说明.pdf'))
    docs = docs1 + docs2
    chunks = splitter.split_documents(docs)
    print(f"原始文档数：{len(docs)}")
    print(f"切分后块数：{len(chunks)}")
    print(f"第一块内容：{chunks[20].page_content}")

