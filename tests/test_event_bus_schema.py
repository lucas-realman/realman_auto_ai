"""
事件总线契约验证测试

验证 Redis Stream 事件格式是否符合 contracts/event-bus.yaml 定义。
覆盖: lead.created / lead.updated / lead.converted / lead.assigned /
       customer.created / customer.updated / customer.level_changed /
       opportunity.created / opportunity.stage_changed / opportunity.won /
       opportunity.lost / activity.created
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
import yaml

# ──────── 契约文件路径 ────────
EVENT_BUS_YAML = Path(__file__).resolve().parent.parent / "contracts" / "event-bus.yaml"


# ──────── 辅助: 加载契约 ────────
def _load_schema() -> dict:
    """加载并返回 event-bus.yaml 内容。"""
    with open(EVENT_BUS_YAML, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ──────── 事件验证器 ────────
class EventValidator:
    """
    根据 event-bus.yaml 定义验证事件消息格式。

    用法::

        ok, err = EventValidator.validate(event_dict)
    """

    REQUIRED_COMMON_FIELDS = {
        "event_id",
        "event_type",
        "timestamp",
        "user_id",
        "entity_type",
        "entity_id",
    }

    VALID_EVENT_TYPES = {
        "lead.created",
        "lead.updated",
        "lead.converted",
        "lead.assigned",
        "customer.created",
        "customer.updated",
        "customer.level_changed",
        "opportunity.created",
        "opportunity.stage_changed",
        "opportunity.won",
        "opportunity.lost",
        "activity.created",
    }

    VALID_ENTITY_TYPES = {"lead", "customer", "opportunity", "activity", "contact"}

    # 每种事件类型所需的额外字段
    EXTRA_FIELDS_MAP: Dict[str, set] = {
        "lead.created": {"company_name", "source"},
        "lead.updated": {"changed_fields"},
        "lead.converted": {"customer_id"},
        "lead.assigned": {"owner_id"},
        "customer.created": {"company_name"},
        "customer.updated": {"changed_fields"},
        "customer.level_changed": {"old_level", "new_level"},
        "opportunity.created": {"customer_id", "amount"},
        "opportunity.stage_changed": {"old_stage", "new_stage", "amount"},
        "opportunity.won": {"amount"},
        "opportunity.lost": {"lost_reason"},
        "activity.created": {"type"},
    }

    @classmethod
    def validate(cls, event: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证事件是否符合契约。

        Args:
            event: 事件字典。

        Returns:
            (通过, 错误信息)  —— 通过时错误信息为空字符串。
        """
        # 1. 必需公共字段
        missing = cls.REQUIRED_COMMON_FIELDS - set(event.keys())
        if missing:
            return False, f"缺少必需字段: {sorted(missing)}"

        # 2. event_type 枚举
        if event["event_type"] not in cls.VALID_EVENT_TYPES:
            return False, f"无效的 event_type: {event['event_type']}"

        # 3. entity_type 枚举
        if event["entity_type"] not in cls.VALID_ENTITY_TYPES:
            return False, f"无效的 entity_type: {event['entity_type']}"

        # 4. UUID 格式
        for field in ("event_id", "entity_id"):
            try:
                uuid.UUID(event[field])
            except (ValueError, AttributeError) as exc:
                return False, f"{field} UUID 格式错误: {exc}"

        # 5. 时间戳 ISO-8601
        try:
            ts = event["timestamp"]
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            return False, f"时间戳格式错误: {exc}"

        return True, ""

    @classmethod
    def validate_with_extras(cls, event: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证公共字段 + 该事件类型要求的额外字段。

        Args:
            event: 事件字典。

        Returns:
            (通过, 错误信息)
        """
        ok, msg = cls.validate(event)
        if not ok:
            return False, msg

        event_type = event["event_type"]
        required_extra = cls.EXTRA_FIELDS_MAP.get(event_type, set())
        missing_extra = required_extra - set(event.keys())
        if missing_extra:
            return False, f"{event_type} 缺少额外字段: {sorted(missing_extra)}"

        return True, ""


# ──────── 工厂: 构造测试事件 ────────
def _base_event(**overrides: Any) -> Dict[str, Any]:
    """生成包含所有公共字段的基础事件。"""
    base = {
        "event_id": str(uuid.uuid4()),
        "event_type": "lead.created",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": str(uuid.uuid4()),
        "entity_type": "lead",
        "entity_id": str(uuid.uuid4()),
    }
    base.update(overrides)
    return base


# ================================================================
# 测试: YAML 结构完整性
# ================================================================
class TestEventBusYamlStructure:
    """验证 event-bus.yaml 文件本身的结构完整性。"""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.schema = _load_schema()

    def test_yaml_file_exists(self) -> None:
        """contracts/event-bus.yaml 文件必须存在。"""
        assert EVENT_BUS_YAML.exists(), f"{EVENT_BUS_YAML} 不存在"

    def test_top_level_keys(self) -> None:
        """顶层必须包含 redis / streams / event_schema。"""
        for key in ("redis", "streams", "event_schema"):
            assert key in self.schema, f"缺少顶层 key: {key}"

    # ── Redis 配置 ──
    def test_redis_config(self) -> None:
        """Redis 连接信息完整。"""
        rc = self.schema["redis"]
        assert rc["host"] == "172.16.12.50"
        assert rc["port"] == 6379
        assert rc["db"] == 0

    # ── Stream 定义 ──
    def test_stream_crm_events_exists(self) -> None:
        """crm.events stream 存在。"""
        assert "crm.events" in self.schema["streams"]

    def test_stream_max_length(self) -> None:
        """crm.events 配置了 max_length。"""
        assert self.schema["streams"]["crm.events"]["max_length"] == 100000

    def test_consumer_groups(self) -> None:
        """消费者组包含 agent_engine 和 celery_workers。"""
        groups = self.schema["streams"]["crm.events"]["consumer_groups"]
        names = {g["name"] for g in groups}
        assert "agent_engine" in names
        assert "celery_workers" in names

    # ── 公共字段 ──
    def test_common_fields_complete(self) -> None:
        """公共字段覆盖 6 个必需字段。"""
        common = self.schema["event_schema"]["common_fields"]
        expected = {"event_id", "event_type", "timestamp", "user_id", "entity_type", "entity_id"}
        assert set(common.keys()) == expected

    def test_entity_type_enum(self) -> None:
        """entity_type 枚举包含 5 种实体。"""
        enums = self.schema["event_schema"]["common_fields"]["entity_type"]["enum"]
        assert set(enums) == {"lead", "customer", "opportunity", "activity", "contact"}


# ================================================================
# 测试: 事件类型定义
# ================================================================
class TestEventTypeDefinitions:
    """验证每种事件类型在 YAML 中的定义完整性。"""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.event_types = _load_schema()["event_schema"]["event_types"]

    # ── 覆盖率 ──
    def test_all_required_event_types_present(self) -> None:
        """所有契约要求的事件类型都已定义。"""
        required = {
            "lead.created",
            "lead.updated",
            "lead.converted",
            "lead.assigned",
            "customer.created",
            "customer.updated",
            "customer.level_changed",
            "opportunity.created",
            "opportunity.stage_changed",
            "opportunity.won",
            "opportunity.lost",
            "activity.created",
        }
        assert required.issubset(set(self.event_types.keys()))

    # ── 每种事件都有 description ──
    @pytest.mark.parametrize("event_type", [
        "lead.created", "lead.updated", "lead.converted", "lead.assigned",
        "customer.created", "customer.updated", "customer.level_changed",
        "opportunity.created", "opportunity.stage_changed",
        "opportunity.won", "opportunity.lost",
        "activity.created",
    ])
    def test_event_has_description(self, event_type: str) -> None:
        """每种事件类型必须有 description。"""
        assert "description" in self.event_types[event_type]

    # ── lead 事件 ──
    def test_lead_created_extra_fields(self) -> None:
        """lead.created 包含 company_name 和 source 额外字段。"""
        extra = self.event_types["lead.created"]["extra_fields"]
        assert "company_name" in extra
        assert "source" in extra

    def test_lead_created_triggers(self) -> None:
        """lead.created 触发 lead_scoring agent。"""
        triggers = self.event_types["lead.created"]["triggers"]
        agent_triggers = [t for t in triggers if "agent" in t]
        assert any(t["agent"] == "lead_scoring" for t in agent_triggers)

    def test_lead_updated_extra_fields(self) -> None:
        """lead.updated 包含 changed_fields。"""
        extra = self.event_types["lead.updated"]["extra_fields"]
        assert "changed_fields" in extra

    def test_lead_converted_extra_fields(self) -> None:
        """lead.converted 包含 customer_id。"""
        extra = self.event_types["lead.converted"]["extra_fields"]
        assert "customer_id" in extra

    def test_lead_assigned_extra_fields(self) -> None:
        """lead.assigned 包含 owner_id。"""
        extra = self.event_types["lead.assigned"]["extra_fields"]
        assert "owner_id" in extra

    # ── customer 事件 ──
    def test_customer_created_extra_fields(self) -> None:
        """customer.created 包含 company_name。"""
        extra = self.event_types["customer.created"]["extra_fields"]
        assert "company_name" in extra

    def test_customer_level_changed_triggers(self) -> None:
        """customer.level_changed 触发 customer_insight agent。"""
        triggers = self.event_types["customer.level_changed"]["triggers"]
        assert any(t.get("agent") == "customer_insight" for t in triggers)

    # ── opportunity 事件 ──
    def test_opportunity_created_triggers(self) -> None:
        """opportunity.created 触发 opportunity_predictor agent。"""
        triggers = self.event_types["opportunity.created"]["triggers"]
        assert any(t.get("agent") == "opportunity_predictor" for t in triggers)

    def test_opportunity_stage_changed_extra_fields(self) -> None:
        """opportunity.stage_changed 包含 old_stage / new_stage / amount。"""
        extra = self.event_types["opportunity.stage_changed"]["extra_fields"]
        for field in ("old_stage", "new_stage", "amount"):
            assert field in extra, f"缺少 {field}"

    def test_opportunity_stage_changed_triggers(self) -> None:
        """opportunity.stage_changed 触发预测 + 钉钉卡片 + 漏斗缓存。"""
        triggers = self.event_types["opportunity.stage_changed"]["triggers"]
        trigger_values: List[str] = []
        for t in triggers:
            trigger_values.extend(t.values())
        assert "opportunity_predictor" in trigger_values
        assert "push_dingtalk_card" in trigger_values
        assert "update_funnel_cache" in trigger_values

    def test_opportunity_won_extra_fields(self) -> None:
        """opportunity.won 包含 amount。"""
        extra = self.event_types["opportunity.won"]["extra_fields"]
        assert "amount" in extra

    def test_opportunity_lost_extra_fields(self) -> None:
        """opportunity.lost 包含 lost_reason。"""
        extra = self.event_types["opportunity.lost"]["extra_fields"]
        assert "lost_reason" in extra

    # ── activity 事件 ──
    def test_activity_created_extra_fields(self) -> None:
        """activity.created 包含 type。"""
        extra = self.event_types["activity.created"]["extra_fields"]
        assert "type" in extra


# ================================================================
# 测试: EventValidator 公共字段验证
# ================================================================
class TestEventValidatorCommon:
    """测试 EventValidator.validate() 对公共字段的校验。"""

    def test_valid_minimal_event(self) -> None:
        """包含全部公共字段的最小事件通过校验。"""
        event = _base_event()
        ok, msg = EventValidator.validate(event)
        assert ok, msg

    def test_missing_event_id(self) -> None:
        """缺少 event_id 报错。"""
        event = _base_event()
        del event["event_id"]
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "缺少必需字段" in msg

    def test_missing_timestamp(self) -> None:
        """缺少 timestamp 报错。"""
        event = _base_event()
        del event["timestamp"]
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "缺少必需字段" in msg

    def test_invalid_event_type(self) -> None:
        """非法 event_type 报错。"""
        event = _base_event(event_type="unknown.event")
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "无效的 event_type" in msg

    def test_invalid_entity_type(self) -> None:
        """非法 entity_type 报错。"""
        event = _base_event(entity_type="invalid")
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "无效的 entity_type" in msg

    def test_invalid_event_id_uuid(self) -> None:
        """event_id 非 UUID 格式报错。"""
        event = _base_event(event_id="not-a-uuid")
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "UUID 格式错误" in msg

    def test_invalid_entity_id_uuid(self) -> None:
        """entity_id 非 UUID 格式报错。"""
        event = _base_event(entity_id="bad-uuid")
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "UUID 格式错误" in msg

    def test_invalid_timestamp_format(self) -> None:
        """非 ISO-8601 时间戳报错。"""
        event = _base_event(timestamp="not-a-date")
        ok, msg = EventValidator.validate(event)
        assert not ok
        assert "时间戳格式错误" in msg

    def test_timestamp_with_z_suffix(self) -> None:
        """带 Z 后缀的时间戳合法。"""
        event = _base_event(timestamp="2026-03-05T10:00:00Z")
        ok, msg = EventValidator.validate(event)
        assert ok, msg


# ================================================================
# 测试: EventValidator 额外字段验证
# ================================================================
class TestEventValidatorExtras:
    """测试 EventValidator.validate_with_extras() 对各事件类型的校验。"""

    def test_lead_created_valid(self) -> None:
        """合法的 lead.created 事件通过。"""
        event = _base_event(
            event_type="lead.created",
            entity_type="lead",
            company_name="睿尔曼智能",
            source="dingtalk",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_lead_created_missing_source(self) -> None:
        """lead.created 缺少 source 报错。"""
        event = _base_event(
            event_type="lead.created",
            entity_type="lead",
            company_name="睿尔曼智能",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert not ok
        assert "source" in msg

    def test_lead_updated_valid(self) -> None:
        """合法的 lead.updated 事件通过。"""
        event = _base_event(
            event_type="lead.updated",
            entity_type="lead",
            changed_fields=["status", "notes"],
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_lead_converted_valid(self) -> None:
        """合法的 lead.converted 事件通过。"""
        event = _base_event(
            event_type="lead.converted",
            entity_type="lead",
            customer_id=str(uuid.uuid4()),
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_lead_assigned_valid(self) -> None:
        """合法的 lead.assigned 事件通过。"""
        event = _base_event(
            event_type="lead.assigned",
            entity_type="lead",
            owner_id=str(uuid.uuid4()),
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_customer_created_valid(self) -> None:
        """合法的 customer.created 事件通过。"""
        event = _base_event(
            event_type="customer.created",
            entity_type="customer",
            company_name="测试公司",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_customer_level_changed_valid(self) -> None:
        """合法的 customer.level_changed 事件通过。"""
        event = _base_event(
            event_type="customer.level_changed",
            entity_type="customer",
            old_level="C",
            new_level="A",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_opportunity_created_valid(self) -> None:
        """合法的 opportunity.created 事件通过。"""
        event = _base_event(
            event_type="opportunity.created",
            entity_type="opportunity",
            customer_id=str(uuid.uuid4()),
            amount=100000.0,
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_opportunity_stage_changed_valid(self) -> None:
        """合法的 opportunity.stage_changed 事件通过。"""
        event = _base_event(
            event_type="opportunity.stage_changed",
            entity_type="opportunity",
            old_stage="initial_contact",
            new_stage="needs_confirmed",
            amount=50000.0,
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_opportunity_stage_changed_missing_amount(self) -> None:
        """opportunity.stage_changed 缺少 amount 报错。"""
        event = _base_event(
            event_type="opportunity.stage_changed",
            entity_type="opportunity",
            old_stage="initial_contact",
            new_stage="needs_confirmed",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert not ok
        assert "amount" in msg

    def test_opportunity_won_valid(self) -> None:
        """合法的 opportunity.won 事件通过。"""
        event = _base_event(
            event_type="opportunity.won",
            entity_type="opportunity",
            amount=200000.0,
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_opportunity_lost_valid(self) -> None:
        """合法的 opportunity.lost 事件通过。"""
        event = _base_event(
            event_type="opportunity.lost",
            entity_type="opportunity",
            lost_reason="预算不足",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_activity_created_valid(self) -> None:
        """合法的 activity.created 事件通过。"""
        event = _base_event(
            event_type="activity.created",
            entity_type="activity",
            type="visit",
            customer_id=str(uuid.uuid4()),
            opportunity_id=str(uuid.uuid4()),
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert ok, msg

    def test_activity_created_missing_type(self) -> None:
        """activity.created 缺少 type 报错。"""
        event = _base_event(
            event_type="activity.created",
            entity_type="activity",
        )
        ok, msg = EventValidator.validate_with_extras(event)
        assert not ok
        assert "type" in msg


# ================================================================
# 测试: YAML 与 Validator 一致性
# ================================================================
class TestSchemaValidatorConsistency:
    """确保 YAML 定义的事件类型与 EventValidator 常量同步。"""

    def test_event_types_in_sync(self) -> None:
        """YAML event_types 与 Validator VALID_EVENT_TYPES 一致。"""
        schema = _load_schema()
        yaml_types = set(schema["event_schema"]["event_types"].keys())
        assert yaml_types == EventValidator.VALID_EVENT_TYPES

    def test_entity_types_in_sync(self) -> None:
        """YAML entity_type enum 与 Validator VALID_ENTITY_TYPES 一致。"""
        schema = _load_schema()
        yaml_entities = set(schema["event_schema"]["common_fields"]["entity_type"]["enum"])
        assert yaml_entities == EventValidator.VALID_ENTITY_TYPES

    def test_extra_fields_map_covers_all_types(self) -> None:
        """EventValidator.EXTRA_FIELDS_MAP 覆盖所有事件类型。"""
        assert set(EventValidator.EXTRA_FIELDS_MAP.keys()) == EventValidator.VALID_EVENT_TYPES
