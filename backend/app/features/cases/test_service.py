from app.features.cases.service import CaseService
from app.features.cases.repository import CaseRepository


class FakeCaseRepository:
    def list_ops_cases(self, owner_id=None):
        return [{"owner_id": owner_id}]

    def get_case(self, case_id):
        return [
            {"SK": "META", "case_id": case_id},
            {"SK": "TL#1", "entity_type": "timeline"},
            {"SK": "ACTION#1", "entity_type": "action"},
            {"SK": "MESSAGE#1", "entity_type": "message"},
        ]


def test_case_service_builds_case_detail_from_shared_partition():
    case = CaseService(FakeCaseRepository()).case_detail("EX-1")
    assert case["case_id"] == "EX-1"
    assert len(case["timeline"]) == len(case["actions"]) == len(case["messages"]) == 1


def test_case_repository_uses_shipment_index_for_open_case_deduplication():
    class FakeTable:
        def query(self, **kwargs):
            assert kwargs["IndexName"] == "GSI3"
            assert kwargs["Limit"] == 1
            return {"Items": [{"case_id": "EX-1"}]}

        def get_item(self, **kwargs):
            assert kwargs["Key"] == {"PK": "SHIPMENT#123", "SK": "META"}
            return {"Item": {"shipment_id": "123"}}

    repository = CaseRepository(FakeTable())
    assert repository.find_open_case("123", "delay") == [{"case_id": "EX-1"}]
    assert repository.get_shipment("123") == {"shipment_id": "123"}
