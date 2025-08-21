import json

def is_well_formed(json_str: str) -> bool:
    """
    Check if a string is valid JSON.
    """
    try:
        json.loads(json_str)
        return True
    except Exception:
        return False


def validate_against_schema(json_str: str, schema: dict = None) -> bool:
    """
    Validate JSON against a given schema (if provided).
    For now, just checks if it’s valid JSON.
    """
    try:
        obj = json.loads(json_str)
        # If no schema provided, just return True if JSON is valid
        if schema is None:
            return True
        # TODO: Add schema validation (using `jsonschema` library) if needed
        return True
    except Exception:
        return False
