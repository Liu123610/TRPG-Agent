import logging
from typing import List, Optional
import pickle
from pathlib import Path
import jieba
import requests

from langchain_core.documents import Document
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# 引入 Rerank 组件
from app.config.settings import settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(settings.rag_db_dir)
if not DB_PATH.is_absolute():
    DB_PATH = BACKEND_DIR / DB_PATH
BM25_PATH = DB_PATH / "bm25_index.pkl"

logger = logging.getLogger(__name__)

class TRPGHybridRetriever:
    def __init__(self):
        # 反序列化底层文本并快速重建BM25；若索引缺失则降级到向量检索。
        self.bm25_retriever = None
        if BM25_PATH.exists():
            try:
                with open(BM25_PATH, "rb") as f:
                    bm25_chunks = pickle.load(f)

                self.bm25_retriever = BM25Retriever.from_documents(
                    bm25_chunks,
                    preprocess_func=jieba.lcut
                )
                # 将基础检索召回数量扩大
                self.bm25_retriever.k = 10
            except Exception as exc:
                logger.warning(
                    "BM25 retriever unavailable; continue without BM25. reason=%s",
                    exc,
                )
        else:
            logger.warning("BM25 index missing; continue without BM25. path=%s", BM25_PATH)

        # 尝试初始化向量检索，如果嵌入模型或接口不兼容，则自动降级到BM25-only
        self.embeddings = None
        self.vectorstore = None
        try:
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url,
                check_embedding_ctx_length=False,
            )
            self.vectorstore = Chroma(
                persist_directory=str(DB_PATH),
                embedding_function=self.embeddings,
            )
        except Exception as exc:
            logger.warning(
                "Vector retriever unavailable; fallback to BM25 only. reason=%s",
                exc,
            )

        # Rerank 统一走云端接口，团队成员只需按供应商配置环境变量。
        self.rerank_url = self._build_rerank_url(settings.rerank_base_url)
        self.rerank_api_key = settings.rerank_api_key
        self.rerank_model = settings.rerank_model

    def _build_vector_retriever(self, filter_category: Optional[str], top_k: int = 10):
        if self.vectorstore is None:
            return None

        search_kwargs = {"k": top_k}
        if filter_category:
            search_kwargs["filter"] = {"category": filter_category}
        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)

    def get_ensemble_retriever(self, filter_category: Optional[str] = None):
        bm25_retriever = self.bm25_retriever
        chroma_retriever = self._build_vector_retriever(filter_category, top_k=10)

        if bm25_retriever is not None and chroma_retriever is not None:
            base_retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, chroma_retriever],
                weights=[0.5, 0.5],
            )
        elif bm25_retriever is not None:
            base_retriever = bm25_retriever
        elif chroma_retriever is not None:
            base_retriever = chroma_retriever
        else:
            raise RuntimeError("No available retriever backend (BM25 and vector are both unavailable).")

        return base_retriever

    @staticmethod
    def _build_rerank_url(base_url: Optional[str]) -> Optional[str]:
        if not base_url:
            return None
        return f"{base_url.rstrip('/')}/rerank"

    @staticmethod
    def _apply_category_filter(results: List[Document], filter_category: Optional[str]) -> List[Document]:
        if not filter_category:
            return results
        return [doc for doc in results if doc.metadata.get("category") == filter_category]

    def search(self, query: str, filter_category: Optional[str] = None, top_k: int = 3) -> List[Document]:
        # 动态赋值期望的返回结果数
        try:
            retriever = self.get_ensemble_retriever(filter_category)
        except Exception as exc:
            logger.warning(
                "No retriever backend available at initialization stage. reason=%s",
                exc,
            )
            return []

        try:
            results = retriever.invoke(query)
        except Exception as exc:
            logger.warning(
                "Hybrid retrieval failed at query time; fallback to single backend. reason=%s",
                exc,
            )
            if self.bm25_retriever is not None:
                try:
                    self.bm25_retriever.k = top_k
                    fallback_results = self.bm25_retriever.invoke(query)
                    filtered_fallback = self._apply_category_filter(fallback_results, filter_category)
                    return filtered_fallback[:top_k]
                except Exception as bm25_exc:
                    logger.warning("BM25 fallback failed. reason=%s", bm25_exc)

            vector_fallback = self._build_vector_retriever(filter_category, top_k=top_k)
            if vector_fallback is not None:
                try:
                    fallback_results = vector_fallback.invoke(query)
                    filtered_fallback = self._apply_category_filter(fallback_results, filter_category)
                    return filtered_fallback[:top_k]
                except Exception as vector_exc:
                    logger.warning("Vector fallback failed. reason=%s", vector_exc)

            return []

        filtered_results = self._apply_category_filter(results, filter_category)
        return self._rerank(query, filtered_results, top_k)

    def _rerank(self, query: str, docs: List[Document], top_k: int) -> List[Document]:
        if not docs or not self.rerank_url or not self.rerank_api_key:
            return docs[:top_k]

        try:
            response = requests.post(
                self.rerank_url,
                headers={
                    "Authorization": f"Bearer {self.rerank_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.rerank_model,
                    "query": query,
                    "documents": [doc.page_content for doc in docs],
                    "top_n": min(top_k, len(docs)),
                    "return_documents": False,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            ranked_docs = [
                docs[item["index"]]
                for item in payload.get("results", [])
                if 0 <= item.get("index", -1) < len(docs)
            ]
            return ranked_docs[:top_k] or docs[:top_k]
        except Exception as exc:
            logger.warning("Cloud rerank unavailable; return ensemble results. reason=%s", exc)
            return docs[:top_k]

if __name__ == "__main__":
    print("Initializing retriever")
    retriever = TRPGHybridRetriever()
    print("OK, execute search: '我能攻击躲在树后的人吗'")
    results = retriever.search("我能攻击躲在树后的人吗")
    for i, doc in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(f"[{doc.metadata.get('category')} / {doc.metadata.get('sub_category')}]")
        print(doc.page_content)
