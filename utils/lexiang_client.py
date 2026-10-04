"""腾讯乐享知识库 OpenAPI 客户端（AI 问答 / AI 搜索）

接口来源：<https://lexiang.tencent.com/wiki/api/>

* ``POST /cgi-bin/token``
  用 AppKey/AppSecret 换 access_token（有效期 7200s，限 20 次/10 分钟，**必须缓存**）
* ``POST /cgi-bin/v1/ai/qa``
  **基于知识库的 AI 问答**：乐享自己完成检索（含 PDF/图片解析）+ 大模型生成，
  响应里带 ``content``（答案）与 ``additional_content.reference_docs``（引用来源）。
  比 ima 的 OpenAPI 强得多 —— ima 只有知识库文件的增删查改，没有问答接口。
* ``POST /cgi-bin/v1/ai/search``
  AI 搜索，返回 rerank 后的原文片段（本模块保留给调试/扩展用）

请求头：``Authorization: Bearer <access_token>`` + ``x-staff-id``。
``x-staff-id`` 传固定值 ``system-bot`` 表示匿名调用，只能读到「公开」知识，
群机器人的场景正合适（不绑定某个具体同学的身份）。
"""

import asyncio
import json
import time

import aiohttp
import botpy

from config import (
    LEXIANG_APP_KEY,
    LEXIANG_APP_SECRET,
    LEXIANG_BASE_URL,
    LEXIANG_QA_MODE,
    LEXIANG_STAFF_ID,
    LEXIANG_TARGETS,
)

_log = botpy.logging.get_logger()

PATH_TOKEN = "cgi-bin/token"
PATH_AI_QA = "cgi-bin/v1/ai/qa"
PATH_AI_SEARCH = "cgi-bin/v1/ai/search"
PATH_KB_SPACES = "cgi-bin/v1/kb/spaces"

_DEFAULT_TIMEOUT = 60
# 乐享返回的「答不出来」提示语（内容未收录/解析中/权限受限/命中敏感词）
NO_ANSWER_HINT = "当前问题可能因内容未收录"


class LexiangError(Exception):
    """乐享接口错误（业务 code != 0 或网络异常）"""

    def __init__(self, path: str, code: int, message: str, request_id: str = None):
        self.path = path
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"[{path}] code={code} message={message}")


def unwrap_payload(path: str, status: int, payload: dict) -> dict:
    """解析乐享响应信封，返回 ``data`` 部分

    乐享的接口有**两种**返回风格，这里统一处理：

    * AI 助手类（``ai/qa``、``ai/search``）：``{"code":0,"message":"success","data":{…}}``
    * 知识库类（``kb/spaces`` …）：JSON:API 风格 ``{"data":{…},"included":[…]}}``，**没有 code 字段**

    出错时一律带非 0 的 ``code``（401 / 403 / 12 / 400…），抛 :class:`LexiangError`。
    """
    code = payload.get("code")
    if code is not None and code != 0:
        raise LexiangError(
            path,
            code if isinstance(code, int) else status,
            payload.get("message") or str(payload.get("errors") or "")[:200] or "未知错误",
            payload.get("request_id"),
        )
    if "data" in payload:
        return payload.get("data") or {}
    return payload


def parse_targets(raw: str) -> list:
    """解析 ``LEXIANG_TARGETS``：``"space:xxx,team:yyy,kb_entry:zzz"`` → targets 数组"""
    if not raw:
        return []
    targets = []
    for chunk in str(raw).replace("；", ",").replace("，", ",").split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        kind, _, ident = chunk.partition(":")
        kind = kind.strip()
        ident = ident.strip()
        if kind in ("space", "team", "team_code", "kb_entry") and ident:
            targets.append({"type": kind, "id": ident})
    return targets


class LexiangClient:
    """乐享 OpenAPI 异步客户端（access_token 进程内共享缓存）"""

    # 类级缓存：多实例共享同一个 token，避免触发 20 次/10 分钟的限流
    _token = None
    _token_expire_at = 0.0
    _token_lock = asyncio.Lock()

    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        base_url: str = None,
        staff_id: str = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        self.app_key = app_key or LEXIANG_APP_KEY
        self.app_secret = app_secret or LEXIANG_APP_SECRET
        self.base_url = (base_url or LEXIANG_BASE_URL).rstrip("/")
        self.staff_id = staff_id or LEXIANG_STAFF_ID or "system-bot"
        self.timeout = timeout
        self._session = None

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.app_secret)

    # ------------------------------------------------------------------ 基础设施
    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc_info):
        await self.close()
        return False

    def _headers(self, token: str = None) -> dict:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["x-staff-id"] = self.staff_id
        return headers

    async def _request(self, path: str, method: str = "POST", *, json_body=None, token=None, params=None) -> dict:
        if not self.configured:
            raise LexiangError(path, -100, "未配置 LEXIANG_APP_KEY / LEXIANG_APP_SECRET")

        session = await self._ensure_session()
        url = f"{self.base_url}/{path}"
        try:
            async with session.request(
                method, url, headers=self._headers(token), json=json_body, params=params
            ) as resp:
                status = resp.status
                raw = await resp.text()
        except asyncio.TimeoutError as e:
            raise LexiangError(path, -100, f"请求超时: {e}") from e
        except aiohttp.ClientError as e:
            raise LexiangError(path, -100, f"网络错误: {e}") from e

        try:
            payload = json.loads(raw or "{}")
        except ValueError as e:
            raise LexiangError(path, status, f"响应不是合法 JSON: {raw[:200]}") from e

        # token 接口直接返回 access_token，没有 code 字段
        if path == PATH_TOKEN:
            if payload.get("access_token"):
                return payload
            raise LexiangError(path, status, str(payload.get("errors") or payload)[:200])

        # 业务接口分两种风格：AI 助手类带 code 信封，知识库类是 JSON:API 风格
        return unwrap_payload(path, status, payload)

    # ------------------------------------------------------------------ token
    async def get_token(self, force: bool = False) -> str:
        """获取（并缓存）access_token"""
        cls = type(self)
        now = time.time()
        if not force and cls._token and now < cls._token_expire_at:
            return cls._token

        async with cls._token_lock:
            # 双检：并发时只有一个协程真正去取
            if not force and cls._token and time.time() < cls._token_expire_at:
                return cls._token
            data = await self._request(
                PATH_TOKEN,
                json_body={
                    "grant_type": "client_credentials",
                    "app_key": self.app_key,
                    "app_secret": self.app_secret,
                },
            )
            token = data.get("access_token")
            expires_in = int(data.get("expires_in") or 7200)
            cls._token = token
            # 提前 5 分钟过期，避免边界情况
            cls._token_expire_at = time.time() + max(60, expires_in - 300)
            _log.debug(f"[乐享] access_token 已刷新，{expires_in}s 后过期")
            return token

    @classmethod
    def clear_token_cache(cls):
        cls._token = None
        cls._token_expire_at = 0.0

    # ------------------------------------------------------------------ AI 问答
    async def ai_qa(
        self,
        query: str,
        *,
        qa_mode: str = None,
        max_chars: int = None,
        targets: list = None,
        skip_faq: bool = False,
        language: str = "zh-CN",
        session_id: str = None,
        staff_id: str = None,
    ) -> dict:
        """调用乐享 AI 问答，返回 ``data``（含 content / reference_docs）

        :param max_chars: 不传就不限制回答字数（乐享侧默认）
        :param targets: 不传则用 ``LEXIANG_TARGETS``（默认锁定「苏群新生指南」知识库）
        :param session_id: 传 None 表示每次都是新会话（单次问答场景）
        """
        body = {
            "query": query,
            "stream": False,
            "skip_faq": skip_faq,
            "language": language,
            "qa_mode": qa_mode or LEXIANG_QA_MODE,
        }
        if max_chars and max_chars > 0:
            body["max_chars"] = int(max_chars)
        if targets is None:
            targets = parse_targets(LEXIANG_TARGETS)
        if targets:
            body["targets"] = targets
        if session_id:
            body["session_id"] = session_id
        else:
            body["new_session"] = True

        original_staff = self.staff_id
        if staff_id:
            self.staff_id = staff_id
        try:
            token = await self.get_token()
            return await self._request(PATH_AI_QA, json_body=body, token=token)
        finally:
            self.staff_id = original_staff

    async def ai_search(self, query: str, top_n: int = 5, targets: list = None) -> list:
        """AI 搜索：返回 rerank 后的知识片段列表"""
        body = {"query": query, "top_n": top_n, "with_score": True}
        if targets is None:
            targets = parse_targets(LEXIANG_TARGETS)
        if targets:
            body["targets"] = targets
        token = await self.get_token()
        data = await self._request(PATH_AI_SEARCH, json_body=body, token=token)
        return data.get("list") or []

    async def list_spaces(self, team_id: str, limit: int = 50) -> list:
        """获取团队下的知识库列表"""
        token = await self.get_token()
        data = await self._request(
            PATH_KB_SPACES, method="GET", token=token,
            params={"team_id": team_id, "limit": limit},
        )
        return data if isinstance(data, list) else (data.get("data") or [])

    async def get_space(self, space_id: str) -> dict:
        """获取知识库详情（``GET /cgi-bin/v1/kb/spaces/<id>``）

        用于核实 ``LEXIANG_TARGETS`` 配的 space id 到底是哪个知识库：
        返回 ``{"id":…, "name":…, "team_id":…, "root_entry_id":…}``
        """
        token = await self.get_token()
        data = await self._request(f"{PATH_KB_SPACES}/{space_id}", method="GET", token=token)
        attributes = (data or {}).get("attributes") or {}
        relationships = (data or {}).get("relationships") or {}
        team = ((relationships.get("team") or {}).get("data") or {}).get("id") or ""
        root_entry = ((relationships.get("root_entry") or {}).get("data") or {}).get("id") or ""
        return {
            "id": (data or {}).get("id") or space_id,
            "name": attributes.get("name") or "",
            "description": attributes.get("description") or "",
            "team_id": team,
            "root_entry_id": root_entry,
        }

    async def verify_targets(self, targets: list = None) -> dict:
        """核实配置的 targets 是否有效（space 类型会顺带查出知识库名字）"""
        targets = targets if targets is not None else parse_targets(LEXIANG_TARGETS)
        result = {"targets": targets, "ok": True, "spaces": [], "error": None}
        try:
            for target in targets:
                if target["type"] == "space":
                    space = await self.get_space(target["id"])
                    result["spaces"].append(space)
        except LexiangError as e:
            result["ok"] = False
            result["error"] = str(e)
        return result

    # ------------------------------------------------------------------ 便捷封装
    def extract_answer(self, data: dict) -> dict:
        """把 ``ai_qa`` 的原始 data 整理成 ``{content, sources, answer_source, no_answer}``"""
        content = (data or {}).get("content") or ""
        additional = (data or {}).get("additional_content") or {}
        sources = []
        for doc in additional.get("reference_docs") or []:
            title = (doc or {}).get("title") or ""
            if title and title not in sources:
                sources.append(title)
        if not sources:
            for chunk in additional.get("reference_chunks") or []:
                title = (chunk or {}).get("title") or ""
                if title and title not in sources:
                    sources.append(title)
        return {
            "content": content,
            "sources": sources,
            "answer_source": (data or {}).get("answer_source") or "",
            "session_id": (data or {}).get("session_id") or "",
            "no_answer": (not content.strip()) or (NO_ANSWER_HINT in content),
        }


async def probe_credentials(app_key: str = None, app_secret: str = None) -> dict:
    """自检用：验证凭证与 AI 问答是否可用"""
    client = LexiangClient(app_key=app_key, app_secret=app_secret)
    try:
        await client.get_token()
        return {"ok": True, "msg": "凭证可用"}
    except LexiangError as e:
        return {"ok": False, "msg": str(e)}
    finally:
        await client.close()
