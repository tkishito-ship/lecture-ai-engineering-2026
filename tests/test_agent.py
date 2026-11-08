"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app.agent import agent

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（requires_approval=True）は、実行されずに承認待ちになるので戻り値が無い
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


def test_learning_log_waits_for_approval_and_saves_after_approval(tmp_path, monkeypatch):
    """承認待ちでは保存せず、承認結果を渡して再開した後にだけ保存する。"""
    from app import tools

    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    with agent.override(model=TestModel(call_tools=["save_learning_log"])):
        waiting = agent.run_sync("学習記録を保存して")

    assert isinstance(waiting.output, DeferredToolRequests)
    assert len(waiting.output.approvals) == 1
    assert not tools.LOG_DIR.exists()

    approval = waiting.output.approvals[0]
    with agent.override(model=TestModel(call_tools=[])):
        completed = agent.run_sync(
            message_history=waiting.all_messages(),
            deferred_tool_results=DeferredToolResults(
                approvals={approval.tool_call_id: True}
            ),
        )

    assert isinstance(completed.output, str)
    assert list(tools.LOG_DIR.glob("*.json"))


def test_learning_log_is_not_saved_when_approval_is_denied(tmp_path, monkeypatch):
    """拒否を渡して再開した場合、保存ファイルが作られないことを確認する。"""
    from app import tools

    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    with agent.override(model=TestModel(call_tools=["save_learning_log"])):
        waiting = agent.run_sync("学習記録を保存して")

    assert isinstance(waiting.output, DeferredToolRequests)
    approval = waiting.output.approvals[0]
    with agent.override(model=TestModel(call_tools=[])):
        completed = agent.run_sync(
            message_history=waiting.all_messages(),
            deferred_tool_results=DeferredToolResults(
                approvals={approval.tool_call_id: False}
            ),
        )

    assert isinstance(completed.output, str)
    assert not tools.LOG_DIR.exists()
