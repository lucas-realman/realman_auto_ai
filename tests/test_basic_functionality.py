"""Basic functionality tests run by the post-receive hook.

These tests verify that the codebase is in a valid state after
each push — contract files exist, core modules can be imported,
and the project structure is sound.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestProjectStructure:
    """Verify essential project files and directories exist."""

    def test_requirements_file_exists(self):
        """requirements.txt must be present."""
        assert (PROJECT_ROOT / "requirements.txt").exists()

    def test_requirements_includes_pytest(self):
        """requirements.txt must list pytest."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "pytest" in content, "pytest not listed in requirements.txt"

    def test_scripts_directory_exists(self):
        """scripts/ directory must be present."""
        assert (PROJECT_ROOT / "scripts").is_dir()

    def test_contracts_directory_exists(self):
        """contracts/ directory must be present."""
        assert (PROJECT_ROOT / "contracts").is_dir()

    def test_tests_directory_exists(self):
        """tests/ directory must be present."""
        assert (PROJECT_ROOT / "tests").is_dir()


class TestContractsExist:
    """Verify all interface contract files are present."""

    CONTRACT_FILES = [
        "contracts/crm-api.yaml",
        "contracts/agent-api.yaml",
        "contracts/agent-tools.yaml",
        "contracts/db-schema.sql",
        "contracts/event-bus.yaml",
        "contracts/health-api.yaml",
    ]

    @pytest.mark.parametrize("contract_file", CONTRACT_FILES)
    def test_contract_file_exists(self, contract_file: str):
        """Each contract file must exist."""
        path = PROJECT_ROOT / contract_file
        assert path.exists(), f"Contract file not found: {contract_file}"

    @pytest.mark.parametrize("contract_file", CONTRACT_FILES)
    def test_contract_file_not_empty(self, contract_file: str):
        """Each contract file must have content."""
        path = PROJECT_ROOT / contract_file
        assert path.stat().st_size > 0, f"Contract file is empty: {contract_file}"


class TestCRMApiContract:
    """Verify CRM API contract completeness."""

    @pytest.fixture(autouse=True)
    def _load_contract(self):
        self.content = (PROJECT_ROOT / "contracts" / "crm-api.yaml").read_text()

    REQUIRED_ENDPOINTS = [
        "/api/v1/leads",
        "/api/v1/customers",
        "/api/v1/opportunities",
        "/api/v1/activities",
        "/api/v1/analytics/funnel",
        "/api/v1/dashboard",
    ]

    @pytest.mark.parametrize("endpoint", REQUIRED_ENDPOINTS)
    def test_endpoint_defined(self, endpoint: str):
        """Each CRM API endpoint must be defined in the contract."""
        assert endpoint in self.content, (
            f"Endpoint {endpoint} not in CRM API contract"
        )

    REQUIRED_SCHEMAS = [
        "LeadCreate",
        "LeadUpdate",
        "Lead",
        "PaginatedLeads",
        "CustomerCreate",
        "Customer",
        "OpportunityCreate",
        "Opportunity",
        "ActivityCreate",
        "Activity",
    ]

    @pytest.mark.parametrize("schema", REQUIRED_SCHEMAS)
    def test_schema_defined(self, schema: str):
        """Each schema must be defined in the contract."""
        assert schema in self.content, (
            f"Schema {schema} not in CRM API contract"
        )


class TestAgentApiContract:
    """Verify Agent API contract completeness."""

    @pytest.fixture(autouse=True)
    def _load_contract(self):
        self.content = (PROJECT_ROOT / "contracts" / "agent-api.yaml").read_text()

    def test_chat_endpoint_defined(self):
        """Agent /agent/chat endpoint must be defined."""
        assert "/agent/chat" in self.content

    def test_stream_endpoint_defined(self):
        """Agent /agent/chat/stream endpoint must be defined."""
        assert "/agent/chat/stream" in self.content

    def test_evaluate_endpoint_defined(self):
        """Agent /agent/evaluate endpoint must be defined."""
        assert "/agent/evaluate" in self.content

    def test_health_endpoint_defined(self):
        """Agent /health endpoint must be defined."""
        assert "/health" in self.content


class TestDatabaseSchema:
    """Verify database schema contract."""

    @pytest.fixture(autouse=True)
    def _load_schema(self):
        self.content = (PROJECT_ROOT / "contracts" / "db-schema.sql").read_text()

    REQUIRED_TABLES = [
        "users",
        "leads",
        "customers",
        "contacts",
        "opportunities",
        "activities",
        "audit_log",
        "agent_log",
    ]

    @pytest.mark.parametrize("table", REQUIRED_TABLES)
    def test_table_defined(self, table: str):
        """Each core table must be defined in the schema."""
        assert table in self.content, f"Table '{table}' not in db-schema.sql"

    def test_uuid_extension_enabled(self):
        """uuid-ossp extension must be enabled."""
        assert "uuid-ossp" in self.content

    def test_pgvector_extension_enabled(self):
        """pgvector extension must be enabled."""
        assert '"vector"' in self.content or "'vector'" in self.content

    def test_updated_at_trigger_defined(self):
        """update_updated_at() trigger function must be defined."""
        assert "update_updated_at" in self.content


class TestEventBusContract:
    """Verify event bus contract."""

    @pytest.fixture(autouse=True)
    def _load_contract(self):
        self.content = (PROJECT_ROOT / "contracts" / "event-bus.yaml").read_text()

    def test_stream_defined(self):
        """crm.events stream must be defined."""
        assert "crm.events" in self.content

    def test_consumer_groups_defined(self):
        """Consumer groups must be defined."""
        assert "agent_engine" in self.content
        assert "celery_workers" in self.content

    REQUIRED_EVENTS = [
        "lead.created",
        "lead.updated",
        "lead.converted",
        "customer.created",
        "opportunity.created",
        "opportunity.stage_changed",
        "opportunity.won",
        "opportunity.lost",
        "activity.created",
    ]

    @pytest.mark.parametrize("event", REQUIRED_EVENTS)
    def test_event_type_defined(self, event: str):
        """Each event type must be defined."""
        assert event in self.content, f"Event type '{event}' not defined"


class TestAgentToolsContract:
    """Verify agent tools contract."""

    @pytest.fixture(autouse=True)
    def _load_contract(self):
        self.content = (PROJECT_ROOT / "contracts" / "agent-tools.yaml").read_text()

    REQUIRED_TOOLS = [
        "create_lead",
        "query_leads",
        "update_lead",
        "convert_lead_to_customer",
        "create_customer",
        "query_customers",
        "get_customer_360",
        "create_opportunity",
        "query_opportunities",
        "update_opportunity_stage",
        "create_activity",
        "query_activities",
    ]

    @pytest.mark.parametrize("tool", REQUIRED_TOOLS)
    def test_tool_defined(self, tool: str):
        """Each tool must be defined in the contract."""
        assert tool in self.content, f"Tool '{tool}' not defined"
