# SQLAlchemy 在小奕项目中的作用

## 1. SQLAlchemy 是什么

SQLAlchemy 是 Python 访问关系型数据库的工具。它可以提供：

1. ORM：把数据库表映射成 Python 类。
2. SQL 表达式：用 Python 对象拼接查询。
3. Engine：管理数据库连接。
4. Session：管理一次数据库操作过程和事务。
5. 异步数据库访问：通过 AsyncSession 配合 asyncpg。

它不是 PostgreSQL 本身，而是 Python 程序和 PostgreSQL 之间的数据库访问层。

## 2. 你的项目确实用了 SQLAlchemy

数据库配置在 app/db/database.py：

1. create_async_engine 创建异步数据库引擎。
2. async_sessionmaker 创建异步 Session 工厂。
3. AsyncSession 表示一次异步数据库会话。
4. DeclarativeBase 是所有 ORM 模型的基类。
5. get_db 为请求提供 Session，并在请求结束后关闭。

模型文件包括：

1. app/model/user.py
2. app/model/document.py
3. app/model/chat_history.py

这些模型使用 mapped_column、ForeignKey、relationship、Index 等 SQLAlchemy 功能描述数据库表、字段、外键和索引。

## 3. 它帮你省了什么

### 3.1 不用手动把表映射成对象

不用 ORM 时，查询结果通常是元组或字典，需要自己把每一列转换成对象。

使用 SQLAlchemy 后，User、Document、DocumentChunk、ChatHistory 等表有对应的 Python 模型，可以通过对象属性访问字段。

例如可以使用 user.id、document.user_id、chunk.content 这样的形式。

### 3.2 不用到处手写字符串 SQL

项目中常见写法是 select、where、update 等 SQLAlchemy 表达式。

例如根据用户和状态查询文档时，可以用 Document.user_id、Document.status 构造条件。

SQLAlchemy 会把这些表达式编译成数据库能执行的 SQL。

### 3.3 统一管理连接

create_async_engine 负责数据库连接池。

连接池的作用是复用数据库连接，避免每个请求都重新建立和销毁连接。

### 3.4 统一管理事务

通过 AsyncSession 执行查询、增加、修改和 commit。

项目中可以看到：

1. db.add(...)
2. await db.execute(...)
3. await db.commit()
4. await db.refresh(...)

这些操作由 Session 组织起来。

### 3.5 支持异步数据库访问

项目的路由和服务函数是 async def，数据库会话使用 AsyncSession，底层连接地址使用 postgresql+asyncpg。

因此数据库等待时可以把事件循环控制权交还给其他请求。

## 4. 项目中的典型调用链

以文档接口为例：

1. FastAPI 通过 Depends(get_db) 获取 AsyncSession。
2. 路由把 db 传给 service。
3. service 通过 select 或 update 构造数据库操作。
4. await db.execute 执行操作。
5. result.scalars().all() 或 scalar_one_or_none() 读取 ORM 对象。
6. 修改数据后 await db.commit() 提交事务。

## 5. 代码中的几个概念

### Base

app/db/database.py 中的 Base 是 ORM 模型基类。

User、Document、DocumentChunk、ChatHistory 继承它后，SQLAlchemy 才能识别这些类对应的表结构。

### mapped_column

mapped_column 描述数据库字段的类型、是否为空、是否主键、是否唯一等约束。

### ForeignKey

ForeignKey 表示外键关系，例如 DocumentChunk.document_id 指向 Document.id。

### relationship

relationship 表示 Python 对象之间的关联，例如一个 Document 有多个 DocumentChunk。

### AsyncSession

AsyncSession 是异步数据库会话。它不是数据库本身，而是当前业务操作和事务的管理对象。

### commit

commit 提交当前事务。提交成功后，修改才会持久化到 PostgreSQL。

## 6. 项目也可以执行原生 SQL

app/eval/clear_history.py 使用了：

from sqlalchemy import text

然后通过 text 构造原生 SQL，使用 db.execute 执行。

所以 SQLAlchemy 不等于“永远不能写 SQL”。它既能使用 ORM，也能在需要时执行原生 SQL。

## 7. 不用 SQLAlchemy，自己写 SQL 行不行

可以。

可以直接使用 asyncpg、psycopg 或其他 PostgreSQL 驱动：

1. 自己建立连接。
2. 自己写 SQL。
3. 自己绑定参数。
4. 自己把查询结果转换成 Python 对象。
5. 自己管理事务、连接池和异常处理。

但这样会失去或减少 SQLAlchemy 提供的便利：

1. 表和 Python 类的统一映射。
2. 统一的 Session 和事务管理。
3. 连接池封装。
4. relationship 关联。
5. 更少的重复转换代码。
6. 更容易复用的查询表达式。

实际项目也可以混用：常规 CRUD 使用 ORM，复杂查询或批量操作使用原生 SQL。

## 8. 面试时必须说清的边界

1. SQLAlchemy 不是数据库，它是 Python 数据库访问工具。
2. PostgreSQL 负责真正存储和执行数据库操作。
3. ORM 是 SQLAlchemy 的一种使用方式，不是 SQLAlchemy 的全部。
4. 不用 SQLAlchemy 也能写项目，但要自己承担 SQL、映射、连接池和事务管理。
5. 小奕使用的是 SQLAlchemy 的异步 ORM 和 AsyncSession。
6. clear_history.py 还展示了 SQLAlchemy 执行原生 SQL 的用法。
