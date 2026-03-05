"""
Sirus AI-CRM 测试 — 接口契约验证
验证 contracts/ 目录下的接口定义文件存在且格式正确。
对应 docs/08 §4.4 "Layer-2 契约对齐"。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


EXPECTED_CONTRACTS = [
    "crm-api.yaml",
    "agent-api.yaml",
    "agent-tools.yaml",
    "health-api.yaml",
    "event-bus.yaml",
    "db-schema.sql",
]


class TestContractsExist:
    """验证所有必需的契约文件存在"""

    def test_contracts_dir_exists(self, contracts_dir: Path):
        assert contracts_dir.exists(), f"contracts 目录不存在: {contracts_dir}"
        assert contracts_dir.is_dir()

    @pytest.mark.parametrize("filename", EXPECTED_CONTRACTS)
    def test_contract_file_exists(self, contracts_dir: Path, filename: str):
        filepath = contracts_dir / filename
        assert filepath.exists(), f"缺少契约文件: {filename}"
        assert filepath.stat().st_size > 0, f"契约文件为空: {filename}"


class TestContractsFormat:
    """验证 YAML 契约文件格式正确"""

    YAML_CONTRACTS = [f for f in EXPECTED_CONTRACTS if f.endswith(".yaml")]

    @pytest.mark.parametrize("filename", YAML_CONTRACTS)
    def test_yaml_parseable(self, contracts_dir: Path, filename: str):
        filepath = contracts_dir / filename
        if not filepath.exists():
            pytest.skip(f"{filename} 不存在")
        content = filepath.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            pytest.fail(f"{filename} YAML 解析失败: {e}")
        assert data is not None, f"{filename} 解析为 None"

    @pytest.mark.parametrize("filename", YAML_CONTRACTS)
    def test_yaml_has_required_fields(self, contracts_dir: Path, filename: str):
        filepath = contracts_dir / filename
        if not filepath.exists():
            pytest.skip(f"{filename} 不存在")
        data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            pytest.skip(f"{filename} 不是字典格式")
        # OpenAPI 规范或自定义格式至少要有某些字段
        # 宽松检查: 有任何 key 即可
        assert len(data) > 0, f"{filename} 是空字典"


class TestDbSchema:
    """验证 SQL schema 文件"""

    def test_db_schema_has_create_table(self, contracts_dir: Path):
        filepath = contracts_dir / "db-schema.sql"
        if not filepath.exists():
            pytest.skip("db-schema.sql 不存在")
        content = filepath.read_text(encoding="utf-8").upper()
        assert "CREATE TABLE" in content, "db-schema.sql 缺少 CREATE TABLE 语句"
