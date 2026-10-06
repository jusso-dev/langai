from sqlalchemy import inspect


def serialize(obj):
    result = {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs if c.key != "token_hash"}
    if "entry_metadata" in result:
        result["metadata"] = result.pop("entry_metadata")
    return result


def entry_snapshot(obj):
    value = serialize(obj)
    value["entry_metadata"] = value.pop("metadata")
    return value
