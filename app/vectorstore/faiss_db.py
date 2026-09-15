import faiss #核心向量索引库
import numpy as np #高效数组操作，FASSI数据通常以NumPy数组形式传入
import pickle #序列化元数据列表
from pathlib import Path #面向对象的路径操作
from typing import Dict, List, Optional#类型注解，Dict表示字典，List表示列表，Optional表示可选类型
class FAISSVectorStore:
    def __init__(
        self,
        dimension: int = 384,
        use_cosine: bool = True
    ):#向量维度初始化与embedding一致
        self.dimension = dimension
        self.use_cosine = use_cosine#默认使用余弦相似度进行向量检索：use_cosine=True
        self.index = self._create_index()
        # 与 FAISS index 中的向量一一对应
        self.metadata: List[Dict] = []#空列表，用来存放每个向量对应的元数据，与向量在索引中内部得id严格对应

# """
#   Index
#    ↓
#    一种向量索引结构

#   Flat
#    ↓
#    Flat（暴力 / 精确搜索）

#   IP
#    ↓
#    Inner
#    Product（内积）  ps:因为我的项目比较小，涉及的内部数据库比较小，所以采用·flat（暴力搜索）更加精确
#   FAISS内部index用来存向量及其索引结构 FAISS的核心功能就是向量相似度搜索，所以一些例如用户相关数据就不适合全塞进faiss

    def _create_index(self):
        if self.use_cosine:
            base_index=faiss.IndexFlatIP(self.dimension)
        else:
            base_index=faiss.IndexFlatL2(self.dimension)
        #用IndexIDMap把base_index包起来
        #这样FAISS就支持自定义ID了
        index=faiss.IndexIDMap(base_index)
        return index

    #向量预准备，前面有下划线说明是内部方法不对外访问
    def _prepare_vectors(
            self,
            vectors,
    ) -> np.ndarray:

        vectors = np.asarray(
            vectors,
            dtype="float32"
        )
        #np.asarray() 将输入转换为 NumPy 数组，dtype="float32" 指定数据类型为 32 位浮点数，这是 FAISS 所要求的格式。例如会将[384]的向量转为[1, 384]的二维数组
        # 单个向量：
        #
        # [384]
        #
        # 转成：
        #
        # [1, 384]

        if vectors.ndim == 1:
            #如果输入向量是一维数组（即单个向量），则将其重塑为二维数组，形状为 (1, dimension)，以便与 FAISS 索引兼容。例如[384] -> [[384]]
            vectors = vectors.reshape(1, -1)
            #1的意思是给他变成一行，-1的意思是列数你自己算
        if vectors.shape[1] != self.dimension:
            #一维数组（只有一根棍子）：np.array([1, 2, 3]) 的 .shape 是 (3,)。
            #二维数组（表格/矩阵）：np.array([[1,2,3],[4,5,6]]) 的 .shape 是 (2, 3)。意思是：有 2 行，每行有 3 列。
            raise ValueError(
                f"向量维度错误："
                f"期望 {self.dimension}，"
                f"实际 {vectors.shape[1]}"
            )

        if self.use_cosine:
            faiss.normalize_L2(vectors)

        return vectors


    #内部归一化方法，原地归一，不占内存
    def _normalize(self, arr):
        #arr 是一个二维 NumPy 数组，形状为 (n, dimension)，即每行是一个向量。
        """对二维数组（行向量）进行 L2 归一化（原地修改），即把每个向量长度变成1"""
        faiss.normalize_L2(arr)

    #添加向量add方法
    #embeddings：列表的列表，列表的每个内部元素都是一个向量
    #metadata，与embeddings长度相同的列表，每个元素是与对应向量关联的元数据（字典）
    # {"text": "向量加法的定义...", "page": 8, "source": "高等数学.pdf"}，这就是元数据。
    def add(
            self,
            embeddings,
            metadata: List[Dict]
    ):
        """
               添加多个向量。

               embeddings:
                   [
                       vector1,
                       vector2,
                       ...
                   ]

               metadata:
                   [
                       {
                           "text": "...",
                           "page": 1
                       },
                       ...
                   ]
               """
        if not embeddings:
            return

        if len(embeddings) != len(metadata):
            raise ValueError(
                "embeddings 和 metadata 数量不一致"
            )

        vectors = self._prepare_vectors(
            embeddings
        )
        #提取chunk_id 作为FAISS向量的id
        for m in metadata:
            if "chunk_id" not in m:
                raise ValueError(
                    "metadata 中缺少 chunk_id"
                    "无法使用IndexIDMap"
                )
        #使用数据库chunk id 作为FAISS ID
        ids=np.array(
            [m["chunk_id"] for m in metadata],
            dtype=np.int64
        )#array将metadata中每个字典的chunk_id提取出来，组成一个numpy数组，作为FAISS索引的id
        #ids此时装的是所有chunk_id组成的数组
        #使用add_with_ids方法将向量和对应的id一起添加到FAISS索引中
        #add_with_ids方法是FAISS提供的一个函数，用于将向量和对应的ID一起添加到索引中。这样可以确保每个向量在索引中都有一个唯一的标识符，便于后续的检索和管理。

        self.index.add_with_ids(vectors, ids)

        #index是容纳向量的，metadata是存放对应元数据的
        self.metadata.extend(metadata)

        print(
            f"FAISS 新增 {len(embeddings)} 个向量，"
            f"当前总数：{self.index.ntotal}"#ntotal 表示在这个FASSI索引中当前存了多少向量
        )

    #检索search方法
    #query_vector:查询单个向量，长度dimesion
    #top_k:返回最相似的结果个数
    def search(
            self,
            query_vector,
            top_k=3,
            user_id: Optional[int] = None,
            document_ids:Optional[List[str]]=None,
            threshold: Optional[float] = None
    ) -> List[Dict]:
        """
                相似度搜索。

                user_id 不传：
                    搜索全部知识库

                user_id 传入：
                    只返回该用户自己的知识库
                """
        if self.index.ntotal == 0:
            return []
        query = self._prepare_vectors(
            query_vector
        )

        # 如果需要 user_id 过滤，
        # 多搜索一些结果，避免过滤后数量不足。
        search_k = top_k

        if user_id is not None or document_ids is not None:
            search_k = min(
                max(top_k * 5, 20),#取top_k*5和20的最大值
                self.index.ntotal#取index内部向量总数
                #取两者最小，多搜索一些结果
            )

        scores, ids = self.index.search(
            query,
            search_k
        )
    #scores（1，search_k）一个二维数组，里面装着 search_k 个浮点数。代表查询向量和找到的那些向量之间的“距离”或“内积”。
    #例子：scores[0] 可能是 [0.85, 0.72, 0.55, ...]，表示最像的得分 0.85，第二像 0.72...
    #ids（向量在 FAISS 里的位置编号 / 序号）内容：一个二维数组，里面装着 search_k 个整数（比如 [2, 5, 0, ...]）。
    #ids[0]装的是vector_id
        # ==================================
        # 建立：
        #
        # chunk_id -> metadata
        #
        # 的映射
        # ==================================
        metadata_map={}

        for m in self.metadata:
            chunk_id=m.get("chunk_id")
            if chunk_id is not None:
                metadata_map[chunk_id]=m
    #metadata_map装的是由metadata元数据组成的字典，chunk_id作为每个元素的索引
        results=[]
        # scores[0]
        # 和 ids[0]
        # 一一对应
        #ids[0] = [16, 15, 17]
        for score, vector_id in zip(
                scores[0],
                ids[0]
        ):
#zip() 是 Python 内置的“拉链函数”。它会把两个列表按位置配对，生成一个新的“配对器”。一对一对取
            #vector_id无效结果
            if vector_id<0:
                continue
            #根据FAISS ID 找metadata
            item=metadata_map.get(
                int(vector_id)
            )#这里就是item=metadata_map[vector_id]

            if not item:
                continue

            # 用户隔离
            if user_id is not None:

                if item.get("user_id") != user_id:
                    continue#get用法：有就取没有也不报错
            #文档范围过滤
            if document_ids is not None:
                if item.get("document_id") not in document_ids:
                    continue


            # 👇 新增：如果设置了阈值，过滤低分结果
            if threshold is not None and score < threshold:
                continue#如果score低于阈值，则直接continue跳过该score，不收录进答案

            result = {
                **item,#将item内部所有键值对都展开，这里 ** 就是把字典拆成“键=值”的形式传给函数。
                "score": float(score)
            }

            results.append(result)

            if len(results) >= top_k:
                break

        return results

    #保存save方法：将当前 FAISS 索引和元数据持久化到磁盘，以便下次启动时不用重新构建向量库。
    #path - 保存文件的基础路径（不加扩展名）。例如 "./data/vectors/faiss_index"。


# 把内存里的数字和文字，原封不动地搬到硬盘上，防止关机丢失。
    def save(
            self,
            path:str
    ):
        """
                持久化 FAISS。

                path:
                    data/vectors/faiss_index
                """
        path = Path(path)#Path() 是 Python 专门处理文件路径的“高级导航仪”。它把普通字符串变成一个有智能方法的对象。

        #path.parent：找路径的“爸爸”（上一级目录）。比如 data/vectors/faiss_index 的爸爸是 data/vectors。
        #.mkdir()：就是 “Make Directory”（创建目录）
        path.parent.mkdir(
            parents=True,#parents=True：意思是“如果爸爸目录不存在，连爷爷、太爷爷目录一起全建了”。比如 data 不存在，它会先建 data，再建 data/vectors。
            exist_ok=True#exist_ok=True：意思是“如果这个文件夹已经存在了，别报错，继续往下走”。
        )

        faiss_path = Path(
            str(path) + ".faiss"#faiss_path：在原来的路径名字后面加上 .faiss 尾巴。比如 data/vectors/faiss_index.faiss。
        )

        metadata_path = Path(
            str(path) + ".pkl"#同理
        )

        #faiss.write_index()：这是 FAISS 官方提供的“烧录”函数。它把内存里密密麻麻的浮点数（比如 0.12, -0.34...）转换成 FAISS 特有的二进制格式，写入硬盘上的 .faiss 文件中。
        faiss.write_index(
            self.index,
            str(faiss_path)
        )

        # 保存 metadata
        with open(
                metadata_path,
                "wb"#注意不是写字（文本），而是写“字节流”，因为数据含有中文和各种特殊符号，用二进制保存最安全、最快。
        ) as f:
            pickle.dump(
                self.metadata,
                f
            )

        print(
            f"FAISS 已保存：{faiss_path}"
        )

        print(
            f"Metadata 已保存：{metadata_path}"
        )

    #从之前保存的文件里面加载索引和元数据，恢复self.index 和 self.metadata。即读档
    def load(
        self,
        path: str
    ):
        """
        从磁盘加载 FAISS。
        """

        path = Path(path)

        faiss_path = Path(
            str(path) + ".faiss"
        )

        metadata_path = Path(
            str(path) + ".pkl"
        )

        if not faiss_path.exists():

            print(
                "FAISS 文件不存在，"
                "创建新的向量库"
            )

            return

        if not metadata_path.exists():

            print(
                "Metadata 文件不存在，"
                "无法恢复向量库"
            )

            return

        # 加载 FAISS
        #它打开硬盘上的 .faiss 文件，把里面那一大串 0.12, -0.34... 的二进制数据，重新解压成 C++ 内存对象，赋值给 self.index。1
        self.index = faiss.read_index(
            str(faiss_path)
        )

        # 加载 metadata
        with open(
            metadata_path,
            "rb"
        ) as f:
    #open(..., "rb")：以二进制读模式打开 .pkl 文件。
            self.metadata = pickle.load(f)#pickle.load(f)：pickle 的“拆包”函数。它把之前打包压缩塞进硬盘的 Python 列表，原封不动地还原成内存里的 Python 对象（列表里装着字典），赋值给 self.metadata。

        print(
            f"FAISS 加载成功："
            f"{self.index.ntotal} 个向量"
        )

        print(
            f"Metadata 加载成功："
            f"{len(self.metadata)} 条"
        )

    def delete_by_vector_ids(self,vector_ids:List[int]):
        """
        根据 FAISS 自定义 ID 删除向量和对应 metadata
        """
        if not vector_ids:
            return 0

        #转成int64，FAISS要求ID类型匹配
        ids=np.array(vector_ids,dtype=np.int64)

        #1.从FAISS索引中删除
        remove_count=self.index.remove_ids(ids)

        #2.删除metadata中对应的数据
        ids_to_delete=set(int(vector_id) for vector_id in vector_ids)

        old_count=len(self.metadata)

        self.metadata=[
            item
            for item in self.metadata
            if item.get("chunk_id") not in ids_to_delete
        ]

        metadata_remove_count=old_count-len(self.metadata)

        print(
            f"FAISS删除完成:"
            f"向量{remove_count}个"
            f"metadata{metadata_remove_count}个"
        )

        return remove_count



vector_store = FAISSVectorStore(
    dimension=384,
    use_cosine=True
)