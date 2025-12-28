import pytest
from unittest.mock import MagicMock, patch

from services.story_generator import StoryGenerator
from models.story import Story, StoryNode
from core.models import StoryLLMResponse, StoryNodeLLM

@pytest.fixture
def mock_db_session():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    return db


@pytest.fixture
def mock_llm_response():
    """
    Creates a valid StoryLLMResponse object with a simple story tree.
    """
    root_node = StoryNodeLLM(
        content="You wake up in a forest.",
        isEnding=False,
        isWinningEnding=False,
        options=[
            {
                "text": "Go left",
                "nextNode": {
                    "content": "You find a treasure.",
                    "isEnding": True,
                    "isWinningEnding": True,
                    "options": []
                }
            }
        ]
    )

    return StoryLLMResponse(
        title="Forest Adventure",
        rootNode=root_node
    )

@patch("services.story_generator.ChatOpenAI")
def test_get_llm_with_env_vars(mock_chat_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_SERVICE_URL", "http://test-url")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    llm = StoryGenerator._get_llm()

    mock_chat_openai.assert_called_once_with(
        model="gpt-test",
        api_key="test-key",
        base_url="http://test-url"
    )
    assert llm is not None

@patch("services.story_generator.ChatOpenAI")
def test_get_llm_without_service_url(mock_chat_openai, monkeypatch):
    monkeypatch.delenv("OPENAI_SERVICE_URL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    llm = StoryGenerator._get_llm()

    mock_chat_openai.assert_called_once_with(model="gpt-test")
    assert llm is not None


@patch("services.story_generator.PydanticOutputParser")
@patch("services.story_generator.ChatOpenAI")
def test_generate_story_success(
    mock_chat_openai,
    mock_parser,
    mock_db_session,
    mock_llm_response
):
    # Mock LLM invoke
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "mocked-response"
    mock_chat_openai.return_value = mock_llm

    # Mock parser behavior
    mock_parser_instance = MagicMock()
    mock_parser_instance.parse.return_value = mock_llm_response
    mock_parser.return_value = mock_parser_instance

    story = StoryGenerator.generate_story(
        db=mock_db_session,
        session_id="session-123",
        theme="fantasy"
    )

    assert isinstance(story, Story)
    assert story.title == "Forest Adventure"

    mock_db_session.add.assert_called()
    mock_db_session.flush.assert_called()
    mock_db_session.commit.assert_called()


def test_process_story_node_root_and_child(mock_db_session):
    root_node = StoryNodeLLM(
        content="Start",
        isEnding=False,
        isWinningEnding=False,
        options=[
            {
                "text": "Continue",
                "nextNode": {
                    "content": "The End",
                    "isEnding": True,
                    "isWinningEnding": True,
                    "options": []
                }
            }
        ]
    )

    result = StoryGenerator._process_story_node(
        db=mock_db_session,
        story_id=1,
        node_data=root_node,
        is_root=True
    )

    assert result.is_root is True
    assert result.is_ending is False

    # root + child node
    assert mock_db_session.add.call_count >= 2
    assert mock_db_session.flush.call_count >= 2



def test_process_story_node_ending_node(mock_db_session):
    ending_node = StoryNodeLLM(
        content="Game Over",
        isEnding=True,
        isWinningEnding=False,
        options=[]
    )

    node = StoryGenerator._process_story_node(
        db=mock_db_session,
        story_id=1,
        node_data=ending_node,
        is_root=False
    )

    assert node.is_ending is True
    assert node.options == []
