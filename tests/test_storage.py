import pytest
from apps.api.storage import store


def test_integrity_and_path_traversal():
    sha = store().put("test/bytes", b"dictionary")
    assert store().get("test/bytes", sha) == b"dictionary"
    with pytest.raises(ValueError, match="integrity"):
        store().get("test/bytes", "incorrect")
    with pytest.raises(ValueError, match="Invalid object"):
        store().put("../../outside", b"bad")
