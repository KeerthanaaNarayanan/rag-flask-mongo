import pytest

from swagger_server.services import embedder


class FakeVectors:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


@pytest.fixture(autouse=True)
def reset_embedder_state():
    embedder._model = None
    embedder._model_name = None
    yield
    embedder._model = None
    embedder._model_name = None


def test_load_initializes_model_once(mocker):
    model_ctor = mocker.patch("swagger_server.services.embedder.SentenceTransformer")
    model_ctor.return_value = mocker.Mock()

    embedder.load("test-model")
    embedder.load("test-model")

    model_ctor.assert_called_once_with("test-model")


def test_embed_empty_input_returns_empty_list(mocker):
    load_spy = mocker.patch("swagger_server.services.embedder.load")

    result = embedder.embed([])

    assert result == []
    load_spy.assert_not_called()


def test_embed_lazy_loads_and_returns_list_of_float_vectors(mocker):
    fake_model = mocker.Mock()
    fake_model.encode.return_value = FakeVectors([[0.1, 0.2], [0.3, 0.4]])

    def fake_load(_model_name=None):
        embedder._model = fake_model
        embedder._model_name = "mock-model"

    load_spy = mocker.patch("swagger_server.services.embedder.load", side_effect=fake_load)

    vectors = embedder.embed(["hello", "world"])

    load_spy.assert_called_once()
    fake_model.encode.assert_called_once_with(["hello", "world"], normalize_embeddings=True)
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_validates_input_type():
    with pytest.raises(TypeError):
        embedder.embed("not-a-list")

    with pytest.raises(TypeError):
        embedder.embed(["ok", 1])