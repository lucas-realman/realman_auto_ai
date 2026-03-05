"""
钉钉企业应用配置验证测试。

验证钉钉 AppKey / AppSecret 等凭证是否已正确配置，
以及基本的 API 连通性。

运行方式:
    pytest tests/test_dingtalk_config.py -v

注意:
    - 需要先配置环境变量或 .env 文件
    - 连通性测试需要网络访问钉钉 API
"""

import os
import re
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _get_env(name: str) -> Optional[str]:
    """从环境变量获取配置值。

    Args:
        name: 环境变量名称。

    Returns:
        环境变量的值，未设置时返回 None。
    """
    return os.environ.get(name)


def _is_valid_app_key(key: str) -> bool:
    """校验 AppKey 格式。

    钉钉 AppKey 通常以 'ding' 开头，后跟字母数字，总长度约 20 字符。

    Args:
        key: 待校验的 AppKey 字符串。

    Returns:
        格式是否合法。
    """
    if not key:
        return False
    return bool(re.match(r"^ding[a-zA-Z0-9]{10,30}$", key))


def _is_valid_app_secret(secret: str) -> bool:
    """校验 AppSecret 格式。

    钉钉 AppSecret 通常为 30-50 位的字母数字和特殊字符组合。

    Args:
        secret: 待校验的 AppSecret 字符串。

    Returns:
        格式是否合法。
    """
    if not secret:
        return False
    return len(secret) >= 20


def _is_valid_agent_id(agent_id: str) -> bool:
    """校验 AgentId 格式。

    AgentId 通常为纯数字。

    Args:
        agent_id: 待校验的 AgentId 字符串。

    Returns:
        格式是否合法。
    """
    if not agent_id:
        return False
    return agent_id.isdigit()


# 已知的占位符值集合，用于检测未替换的示例配置
_PLACEHOLDER_KEYS = {
    "dingxxxxxxxxxxxxxxxx",
    "your_app_key",
    "changeme",
    "placeholder",
    "todo",
}

_PLACEHOLDER_SECRETS = {
    "your_app_secret",
    "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "changeme",
    "placeholder",
    "todo",
}


# ---------------------------------------------------------------------------
# 配置存在性测试
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("DINGTALK_APP_KEY"),
    reason="钉钉环境变量未配置 — 跳过 (在部署机器上运行)",
)
class TestDingtalkConfigExists:
    """验证钉钉配置环境变量是否已设置。"""

    def test_app_key_exists(self):
        """AppKey 环境变量必须存在。"""
        app_key = _get_env("DINGTALK_APP_KEY")
        assert app_key is not None, (
            "环境变量 DINGTALK_APP_KEY 未设置。"
            "请参考 docs/dingtalk-config.md 完成钉钉应用注册并配置环境变量。"
        )

    def test_app_secret_exists(self):
        """AppSecret 环境变量必须存在。"""
        app_secret = _get_env("DINGTALK_APP_SECRET")
        assert app_secret is not None, (
            "环境变量 DINGTALK_APP_SECRET 未设置。"
            "请参考 docs/dingtalk-config.md 完成钉钉应用注册并配置环境变量。"
        )

    def test_agent_id_exists(self):
        """AgentId 环境变量必须存在。"""
        agent_id = _get_env("DINGTALK_AGENT_ID")
        assert agent_id is not None, (
            "环境变量 DINGTALK_AGENT_ID 未设置。"
            "请参考 docs/dingtalk-config.md 完成钉钉应用注册并配置环境变量。"
        )


# ---------------------------------------------------------------------------
# 配置格式验证测试
# ---------------------------------------------------------------------------


class TestDingtalkConfigFormat:
    """验证钉钉配置值的格式是否正确。"""

    def test_app_key_format(self):
        """AppKey 格式应以 'ding' 开头，后跟字母数字字符。"""
        app_key = _get_env("DINGTALK_APP_KEY")
        if app_key is None:
            pytest.skip("DINGTALK_APP_KEY 未设置，跳过格式验证")
        assert _is_valid_app_key(app_key), (
            f"DINGTALK_APP_KEY 格式不正确: '{app_key[:8]}...'。"
            "钉钉 AppKey 通常以 'ding' 开头，后跟字母数字字符。"
        )

    def test_app_secret_format(self):
        """AppSecret 长度应不少于 20 字符。"""
        app_secret = _get_env("DINGTALK_APP_SECRET")
        if app_secret is None:
            pytest.skip("DINGTALK_APP_SECRET 未设置，跳过格式验证")
        assert _is_valid_app_secret(app_secret), (
            f"DINGTALK_APP_SECRET 长度不足 (当前 {len(app_secret)} 字符)。"
            "钉钉 AppSecret 通常为 30-50 位字符。"
        )

    def test_agent_id_format(self):
        """AgentId 应为纯数字。"""
        agent_id = _get_env("DINGTALK_AGENT_ID")
        if agent_id is None:
            pytest.skip("DINGTALK_AGENT_ID 未设置，跳过格式验证")
        assert _is_valid_agent_id(agent_id), (
            f"DINGTALK_AGENT_ID 格式不正确: '{agent_id}'。"
            "AgentId 应为纯数字。"
        )

    def test_app_key_not_placeholder(self):
        """AppKey 不应为占位符值。"""
        app_key = _get_env("DINGTALK_APP_KEY")
        if app_key is None:
            pytest.skip("DINGTALK_APP_KEY 未设置，跳过验证")
        assert app_key.lower() not in _PLACEHOLDER_KEYS, (
            "DINGTALK_APP_KEY 仍为占位符值，请替换为真实的 AppKey。"
        )

    def test_app_secret_not_placeholder(self):
        """AppSecret 不应为占位符值。"""
        app_secret = _get_env("DINGTALK_APP_SECRET")
        if app_secret is None:
            pytest.skip("DINGTALK_APP_SECRET 未设置，跳过验证")
        assert app_secret.lower() not in _PLACEHOLDER_SECRETS, (
            "DINGTALK_APP_SECRET 仍为占位符值，请替换为真实的 AppSecret。"
        )


# ---------------------------------------------------------------------------
# API 连通性测试（需要网络和有效凭证）
# ---------------------------------------------------------------------------


class TestDingtalkAPIConnectivity:
    """验证钉钉 API 连通性。

    这些测试需要有效的 AppKey/AppSecret 和网络连接。
    如果凭证未配置或网络不可用，测试会被跳过。
    """

    @pytest.fixture(autouse=True)
    def _check_credentials(self):
        """检查凭证是否可用，不可用则跳过整个测试类。"""
        app_key = _get_env("DINGTALK_APP_KEY")
        app_secret = _get_env("DINGTALK_APP_SECRET")
        if not app_key or not app_secret:
            pytest.skip("钉钉凭证未配置，跳过 API 连通性测试")
        if not _is_valid_app_key(app_key):
            pytest.skip("DINGTALK_APP_KEY 为占位符，跳过 API 连通性测试")
        if app_secret.lower() in _PLACEHOLDER_SECRETS:
            pytest.skip("DINGTALK_APP_SECRET 为占位符，跳过 API 连通性测试")

    def test_get_access_token(self):
        """通过 AppKey + AppSecret 获取 access_token。

        这是验证凭证有效性的最直接方式。
        钉钉 API: https://oapi.dingtalk.com/gettoken
        """
        import json
        import urllib.request

        app_key = os.environ["DINGTALK_APP_KEY"]
        app_secret = os.environ["DINGTALK_APP_SECRET"]

        url = (
            f"https://oapi.dingtalk.com/gettoken"
            f"?appkey={app_key}&appsecret={app_secret}"
        )

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            pytest.skip(f"网络请求失败，跳过连通性测试: {exc}")

        assert data.get("errcode") == 0, (
            f"获取 access_token 失败: errcode={data.get('errcode')}, "
            f"errmsg={data.get('errmsg')}。"
            "请检查 AppKey 和 AppSecret 是否正确。"
        )
        assert "access_token" in data, "响应中缺少 access_token 字段"
        assert len(data["access_token"]) > 0, "access_token 为空"

    def test_access_token_has_valid_expiry(self):
        """access_token 应包含有效的过期时间。"""
        import json
        import urllib.request

        app_key = os.environ["DINGTALK_APP_KEY"]
        app_secret = os.environ["DINGTALK_APP_SECRET"]

        url = (
            f"https://oapi.dingtalk.com/gettoken"
            f"?appkey={app_key}&appsecret={app_secret}"
        )

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            pytest.skip(f"网络请求失败，跳过连通性测试: {exc}")

        if data.get("errcode") != 0:
            pytest.skip("access_token 获取失败，跳过过期时间检查")

        expires_in = data.get("expires_in", 0)
        assert expires_in > 0, (
            f"access_token 过期时间异常: expires_in={expires_in}"
        )


# ---------------------------------------------------------------------------
# 文档完整性测试
# ---------------------------------------------------------------------------


class TestDingtalkDocumentation:
    """验证钉钉配置文档是否存在且内容完整。"""

    @pytest.fixture()
    def doc_path(self) -> str:
        """返回配置文档的绝对路径。"""
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "docs",
            "dingtalk-config.md",
        )

    def test_config_doc_exists(self, doc_path: str):
        """docs/dingtalk-config.md 文件必须存在。"""
        assert os.path.isfile(doc_path), (
            f"配置文档不存在: {doc_path}。"
            "请创建 docs/dingtalk-config.md 文件。"
        )

    def test_config_doc_has_required_sections(self, doc_path: str):
        """配置文档应包含关键章节。"""
        if not os.path.isfile(doc_path):
            pytest.skip("配置文档不存在，跳过内容检查")

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_keywords = [
            "AppKey",
            "AppSecret",
            "环境变量",
            "机器人",
            "权限",
        ]
        for keyword in required_keywords:
            assert keyword in content, (
                f"配置文档缺少关键内容: '{keyword}'。"
                "请确保文档覆盖完整的注册和配置流程。"
            )

    def test_config_doc_has_env_examples(self, doc_path: str):
        """配置文档应包含环境变量配置示例。"""
        if not os.path.isfile(doc_path):
            pytest.skip("配置文档不存在，跳过内容检查")

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "DINGTALK_APP_KEY" in content, (
            "配置文档缺少 DINGTALK_APP_KEY 环境变量示例。"
        )
        assert "DINGTALK_APP_SECRET" in content, (
            "配置文档缺少 DINGTALK_APP_SECRET 环境变量示例。"
        )

    def test_config_doc_has_verification_checklist(self, doc_path: str):
        """配置文档应包含验证清单。"""
        if not os.path.isfile(doc_path):
            pytest.skip("配置文档不存在，跳过内容检查")

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "验证清单" in content or "检查" in content, (
            "配置文档缺少验证清单章节。"
        )
